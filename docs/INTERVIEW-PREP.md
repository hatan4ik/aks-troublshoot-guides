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

## 🌐 Section 4: Deep Networking (The "Plumbing")

### Scenario 7: CNI Selection Wars
**Question:** "We are building a high-frequency trading platform on EKS. Which CNI do you choose and why?"

**The Expert Path:**
1.  **The Default:** AWS VPC CNI.
    *   *Pros:* Pods get real VPC IPs (fastest performance, no overlay overhead).
    *   *Cons:* IP exhaustion (running out of IPs in the subnet).
2.  **The Challenger:** Cilium (eBPF).
    *   *Why?* You need observability (Hubble) to debug microsecond latency, which iptables cannot provide. You also need strict Network Policies which AWS VPC CNI handles differently.
3.  **The Verdict:** Use **AWS VPC CNI in "Prefix Delegation" mode** (to solve IP exhaustion) + **Cilium** in "Chaining Mode" (for Network Policies & Observability).

### Scenario 8: DNS Latency Spikes
**Question:** "Our app has random 5-second latency spikes when connecting to the database. How do you debug this?"

**The Expert Path:**
1.  **The Symptom:** 5 seconds is the default DNS timeout in Linux (`glibc`). This screams "DNS Packet Drop".
2.  **The Cause:** `conntrack` races.
    *   When a pod makes a DNS request, it hits the Node's conntrack table to DNAT to the CoreDNS pod.
    *   In high-traffic clusters, UDP packets (DNS) often get dropped due to race conditions in the kernel's conntrack code.
3.  **The Fix:**
    *   **NodeLocal DNSCache:** Run a DNS cache daemonset on every node. Pods talk to the local agent (TCP/UDP) bypassing the conntrack mess for the initial hop.
    *   *Force TCP:* Configure `resolv.conf` to use `use-vc` (force TCP) to avoid UDP drops (but adds overhead).

### Scenario 9: Ingress vs. Gateway API
**Question:** "Why should we migrate from Ingress Nginx to the Gateway API?"

**The Expert Path:**
1.  **Role Separation:** Ingress is a single resource that mixes concerns (TLS, Routing, Middleware). Gateway API splits this:
    *   `GatewayClass` (Infra Provider)
    *   `Gateway` (Platform Engineer - defines ports/listeners)
    *   `HTTPRoute` (Developer - defines paths/headers).
2.  **Portability:** Ingress relies heavily on vendor-specific annotations (`nginx.ingress.kubernetes.io/...`). Gateway API standardizes these features (Header matching, Weight-based splitting for canary).

---

## 🔒 Section 5: Deep Security (The "Shield")

### Scenario 10: The "Impossible" Permission Denied
**Question:** "A developer's pod is failing to read a Secret. You checked RBAC (`kubectl auth can-i`), and the ServiceAccount has `get/list` on Secrets. What is missing?"

**The Expert Path:**
1.  **The Decoy:** It's rarely just RBAC.
2.  **The Hidden Layers:**
    *   **Filesystem Permissions:** Does the container user (UID 1000) have read access to the mount path?
    *   **SELinux/AppArmor:** Is a host profile blocking the read? (Check `dmesg` or audit logs on the node).
    *   **KMS Decryption:** If using Envelope Encryption (KMS), does the *Node's* IAM role have permission to `Decrypt` the key in AWS KMS / Azure Key Vault? If not, the Kubelet cannot mount the secret.

### Scenario 11: Container Breakout (Privileged vs. Capabilities)
**Question:** "A pentester claims they escaped a container. The pod was NOT 'privileged', but they still got root on the host. How?"

**The Expert Path:**
1.  **Capabilities:** `privileged: true` gives *all* capabilities. But specific capabilities like `CAP_SYS_ADMIN` or `CAP_DAC_READ_SEARCH` are essentially root.
2.  **Host Mounts:** Did the pod mount `/var/run/docker.sock` or `/`?
    *   *Attack:* Mount host filesystem -> `chroot /host` -> You own the node.
3.  **Kernel Vulnerabilities:** Dirty Pipe / Dirty COW. If the kernel is old, isolation doesn't matter.

### Scenario 12: Supply Chain Poisoning
**Question:** "How do we prevent a compromised developer laptop from pushing a malicious image that creates a back door?"

**The Expert Path:**
1.  **Admission Controllers:** Use Kyverno or OPA Gatekeeper.
2.  **The Policy:** "Deny any image that is not signed by our CI/CD key."
    *   *Tooling:* Sigstore (Cosign).
3.  **The Flow:**
    *   Developer commits code -> CI builds image -> CI signs image with private key -> CI pushes to Registry.
    *   K8s Admission Controller checks signature against public key -> Allows/Denies pod.

---

## 🎛 Section 6: Deep Controller Dive (Ingress vs. CNI)

### Scenario 13: Ingress Controller Chaos
**Question:** "What is the difference between Nginx Ingress, AWS ALB Controller, and Azure AGIC? How do you debug a 504 Gateway Timeout?"

**The Expert Path:**
1.  **The Architecture:**
    *   **Nginx:** Runs *inside* the cluster (Data plane is pods). Fast, cheap, flexible (Lua), but you manage the scaling.
    *   **ALB/AGIC:** Runs *outside* the cluster (Control plane only). Configures cloud LBs (AWS ALB / Azure AppGW). Slower updates, but fully managed and integrates with WAF.
2.  **Debug 504 (Timeout):**
    *   **Upstream:** Is the pod too slow? (Check app logs).
    *   **Keep-Alive:** Does the Ingress keep-alive timeout match the App's keep-alive? (If Ingress drops connection while App is thinking -> 502/504).
    *   **The Check:** `kubectl logs -n ingress-nginx -l app=ingress-nginx` vs `kubectl logs <pod>`. Did the request reach the pod?

### Scenario 14: CNI Troubleshooting (Overlay vs. Underlay)
**Question:** "Pods on Node A cannot talk to Pods on Node B. The nodes are healthy. What is wrong with the CNI?"

**The Expert Path:**
1.  **Overlay (VxLAN/Geneve - e.g., Flannel, Calico VxLAN):** Encapsulates packets.
    *   **Check:** Is UDP port 4789 (VxLAN) blocked between nodes? (Firewall/Security Group).
    *   **Check:** MTU. Inner packet + Header > Host MTU? Packet drops!
2.  **Underlay (Direct Routing - e.g., AWS VPC CNI, Azure CNI):** No encapsulation.
    *   **Check:** Routing Table. Does Node A know the route to Node B's Pod CIDR?
    *   **Check:** IP Exhaustion. Did the node run out of ENIs or IPs? (`kubectl describe node`).

---

## 📊 Section 7: Deep Observability (Beyond Logs)

### Scenario 15: The Prometheus Meltdown
**Question:** "Our Prometheus server keeps OOMing. We allocated 64GB RAM, and it still crashes. What is happening?"

**The Expert Path:**
1.  **Cardinality Explosion:** Someone added a high-cardinality label (e.g., `user_id` or `request_id`) to a metric.
    *   *Math:* 1 metric * 1M users = 1M new time series. Prometheus dies.
2.  **The Fix:**
    *   **Identify:** Query `topk(10, count by (__name__)({__name__=~".+"}))` to find the offender.
    *   **Drop:** Update `metric_relabel_configs` to drop the label or the metric.
    *   **Recording Rules:** Pre-aggregate data and drop raw series.

### Scenario 16: The "It's Slow" Mystery
**Question:** "Users complain the checkout page is slow. CPU is low. Logs show 200 OK. How do you find the bottleneck?"

**The Expert Path:**
1.  **Distributed Tracing (OpenTelemetry):** You need a trace context (TraceID) propagated across microservices.
2.  **Span Analysis:** Look for the "Long Span".
    *   Is it the DB query?
    *   Is it a lock contention?
    *   Is it an external API call?
3.  **Tail Sampling:** If you sample 1% of traces, you might miss the error. Use *Tail Sampling* (keep trace IF latency > 2s).

---

## 💾 Section 8: Stateful Systems (The "Hard" Stuff)

### Scenario 17: The Stuck Volume
**Question:** "A node failed. The StatefulSet pod moved to a new node but is stuck in `ContainerCreating` with a 'Volume Attached to different node' error."

**The Expert Path:**
1.  **The Mechanism:** Cloud Block Storage (EBS/Azure Disk) is RWO (ReadWriteOnce). It can only attach to one node.
2.  **The Failure:** The Control Plane (AttachDetachController) thinks the volume is still attached to the dead node. It waits 6 minutes for a graceful detach.
3.  **The Fix:**
    *   *Safe:* Wait.
    *   *Emergency:* `kubectl delete pod <pod> --grace-period=0 --force`. This tells K8s "I certify the old node is dead, steal the volume." (Risk of data corruption if old node comes back!).

---

## 💻 Section 9: Coding (Platform Engineering)

**Question:** "Write a Python script using the Kubernetes library to delete all deployments in 'dev-' namespaces that haven't been updated in 30 days."

**Key Concepts to Demonstrate:**
*   Loading config (`config.load_kube_config()` vs `config.load_incluster_config()`).
*   Pagination (`list_deployment_for_all_namespaces` can return huge lists).
*   Parsing timestamps (ISO 8601 parsing).
*   Dry-run mode (Safety first!).

*(See `src/k8s_diagnostics/automation/` for implementation patterns)*
