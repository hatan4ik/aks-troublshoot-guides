# FAANG/MANGA Kubernetes Interview Preparation Guide

This guide is designed to transform you from a Kubernetes *user* to a Kubernetes *expert*. Top-tier tech companies (Google, Meta, Amazon, Netflix, Apple) don't just ask "how to deploy an app"; they ask "how it works," "how it breaks," and "how to fix it at scale."

---

## 🧠 The Mindset Shift
| Junior/Mid-Level | Staff/Principal (FAANG) |
| :--- | :--- |
| "I restart the pod to fix it." | "I analyze the exit code and `dmesg` to see if it was the OOMKiller or a segfault." |
| "I use a LoadBalancer." | "I use Ingress for cost efficiency, but LoadBalancer for TCP traffic, and here is how `kube-proxy` handles the iptables rules." |
| "It works on my machine." | "I need to ensure `conntrack` tables on the node don't overflow with 10k connections." |

---

## 🛠 Section 1: Deep Troubleshooting (The "Broken System")

### Scenario 1: The "Silent" Crash
**Question:** "A critical payment pod is in `CrashLoopBackOff`. You check logs, but they are empty. What is your step-by-step debugging process?"

**The Expert Path:**
1.  **Isolate the Exit Code:**
    *   `kubectl describe pod <pod>` -> Look for `LastState.Terminated.ExitCode`.
    *   **0**: Application exited normally (maybe meant to be a Job?).
    *   **1**: Application error (check app config).
    *   **137**: `SIGKILL` (Usually OOMKilled).
    *   **143**: `SIGTERM` (Graceful termination).
    *   **128+**: Signal = 128 + n (e.g., 139 = Segmentation Fault).
2.  **Debug the Container Start:**
    *   If logs are empty, the app likely failed *before* stdout was hooked up or the entrypoint is bad.
    *   **Action:** `kubectl debug -it <pod> --target=<container_name> --image=busybox -- sh`
    *   **Check:** Does the binary exist? Are shared libraries missing (`ldd /path/to/binary`)?
3.  **Check the Node:**
    *   Maybe the *Node* is out of PIDs or Disk.
    *   **Action:** Check node events: `kubectl get events --field-selector involvedObject.kind=Node`.

### Scenario 2: The "Ghost" OOM
**Question:** "A pod was OOMKilled, but your monitoring (Prometheus) shows it was only using 60% of its memory limit. How is this possible?"

**The Expert Path:**
1.  **Sampling Rate:** Prometheus scrapes every 15s-60s. A "micro-burst" of memory usage (e.g., parsing a 1GB XML file) can spike and crash the app between scrapes.
2.  **Cgroup v1 vs v2:** Understanding how the kernel tracks memory pages (RSS vs Cache).
3.  **The "Node" OOM:** The *Node itself* might have run out of memory, triggering the kernel's OOM Killer to sacrifice your pod to save the kubelet/OS, even if the pod was within its own limits.
    *   **Evidence:** `dmesg | grep -i "killed process"` on the node.

---

## 🏗 Section 2: Architecture & Design at Scale

### Scenario 3: The Multi-Tenant Platform
**Question:** "Design a Kubernetes platform for 500 development teams. How do you handle security, isolation, and upgrades?"

**The Expert Path:**
1.  **Isolation Strategy:**
    *   **Hard Multi-tenancy:** Separate clusters for sensitive/production workloads.
    *   **Soft Multi-tenancy:** Namespaces for Dev/Staging. Use **vCluster** (virtual clusters) if teams need Custom Resource Definitions (CRDs) or specific K8s versions.
2.  **Network Policies (The "Zero Trust" Model):**
    *   *Default:* Deny All.
    *   *Allow:* Explicit DNS and Egress.
    *   *Tooling:* Cilium (eBPF) for performance and L7 filtering.
3.  **The "Noisy Neighbor" Problem:**
    *   Mandatory `ResourceQuotas` and `LimitRanges` per namespace.
    *   *Advanced:* PriorityClasses to ensure critical system pods (CoreDNS, CNI) never get evicted for user workloads.

### Scenario 4: The 5,000 Node Cluster
**Question:** "What breaks when you scale a cluster from 50 nodes to 5,000 nodes?"

**The Expert Path:**
1.  **Control Plane Latency:** `etcd` becomes the bottleneck. List operations (like `kubectl get pods --all-namespaces`) can timeout.
2.  **Networking (IPTables vs IPVS):** `kube-proxy` using iptables becomes slow O(N) with thousands of services.
    *   **Fix:** Switch to IPVS or eBPF (Cilium) for O(1) lookups.
3.  **Prometheus Cardinality:** High churn of pods = explosion in metric series. Monitoring will crash.

---

## 🔬 Section 3: Internals (The "Under the Hood")

### Scenario 5: The Packet Walk
**Question:** "Explain exactly what happens when you run `kubectl exec -it my-pod -- /bin/bash`."

**The Expert Path:**
1.  **Client:** `kubectl` validates config (~/.kube/config), negotiates TLS, sends HTTP `POST` to API Server requesting an "Upgrade" (SPDY/Websocket).
2.  **API Server:** Authenticates (Who are you?), Authorizes (Can you `exec`?), finds the **Node** hosting the pod.
3.  **The Proxy:** API Server proxies the connection to the **Kubelet** on that specific node (port 10250).
4.  **Kubelet:** Acts as a server. Validates request. Calls the **CRI** (Container Runtime Interface - e.g., containerd).
5.  **Runtime:** Invokes `runc` to create a new process inside the existing namespaces (PID, Network, IPC) of the target container.
6.  **Stream:** STDIN/STDOUT are streamed: `User` <-> `API Server` <-> `Kubelet` <-> `Container`.
    *   *Key Insight:* This traffic flows *through* the Control Plane. Heavy `exec` usage can destabilize the API server!

### Scenario 6: Pod Deletion Lifecycle
**Question:** "I deleted a pod. Why is it still receiving traffic?"

**The Expert Path:**
1.  **Simultaneous Events:** When you delete a pod, two things happen *in parallel*:
    *   a) Kubelet sends `SIGTERM` to the container.
    *   b) Endpoints Controller removes the IP from the `Service` (and thus `kube-proxy` updates iptables).
2.  **The Race Condition:** If (a) happens before (b), the app shuts down while iptables still routes traffic to it => 502 Errors.
3.  **The Fix:** Use a `preStop` hook (e.g., `sleep 10`) to keep the app alive long enough for the Endpoints propagation to finish.

---

## 💻 Section 4: Coding (Platform Engineering)

**Question:** "Write a Python script using the Kubernetes library to delete all deployments in 'dev-' namespaces that haven't been updated in 30 days."

**Key Concepts to Demonstrate:**
*   Loading config (`config.load_kube_config()` vs `config.load_incluster_config()`).
*   Pagination (`list_deployment_for_all_namespaces` can return huge lists).
*   Parsing timestamps (ISO 8601 parsing).
*   Dry-run mode (Safety first!).

*(See `src/k8s_diagnostics/automation/` for implementation patterns)*
