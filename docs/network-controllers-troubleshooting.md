# Network Controllers & CNI Troubleshooting Guide

## Overview
This guide focuses on the **Control Plane** of networking: the agents and controllers that program the dataplane (iptables, eBPF, IPVS). When the network breaks, it's often because the *controller* failed to program the routes or rules.

---

## 1. CNI Architecture: The "Hidden" Components

Most CNIs have two parts:
1.  **The Plugin (Binary):** Called by `kubelet` when a pod starts/stops. Responsible for IPAM (IP Address Management) and interface setup.
2.  **The Daemon (Agent):** Runs on every node (`calico-node`, `cilium-agent`, `aws-node`). Watches K8s API and programs the kernel.

---

## 2. Troubleshooting AWS VPC CNI (`aws-node`)

**Architecture:** Pods get real VPC IPs (ENIs).
**Common Failure:** "Failed to CreatePodSandbox", "Timeout", "IP exhaustion".

### Scenario: IPAM Exhaustion
**Symptom:** Pods stay `Pending`. Events show "Failed to assign IP".
**Debug:**
1.  **Check L-IPAM (Local IPAM):**
    *   The `aws-node` daemon maintains a "warm pool" of IPs on the node.
    *   Check logs: `kubectl logs -n kube-system -l k8s-app=aws-node`
    *   Grep for `No available IP addresses`.
2.  **Check Subnet:**
    *   Is the AWS Subnet full? (AWS Console -> VPC).
3.  **Check Limits:**
    *   EC2 instances have a max ENI/IP limit. A `t3.medium` can only hold so many IPs.
    *   **Fix:** Enable **Prefix Delegation** (assign /28 prefixes instead of single IPs) to increase density.

### Scenario: ENI Cleanups
**Symptom:** Leaked ENIs in AWS console.
**Debug:**
1.  If the node is terminated ungracefully, ENIs might linger.
2.  Use the `aws-cni-support.sh` script (provided by AWS) inside the `aws-node` container to dump the IP state.

---

## 3. Troubleshooting Calico (Overlay & Policy)

**Architecture:** Uses BGP (Bird) to sync routes and Felix to program iptables/IPSets.

### Scenario: "BGP Peering Down" (Route Propagation Fail)
**Symptom:** Pods on Node A cannot reach Pods on Node B.
**Debug:**
1.  **Check BGP Status:**
    *   `kubectl exec -n calico-system <calico-node-pod> -- calicoctl node status`
    *   Look for `State: Up`. If `Start` or `Connect`, BGP is broken.
2.  **Firewall/Security Groups:**
    *   Calico BGP uses TCP 179. Is it allowed between nodes?
    *   Calico VxLAN uses UDP 4789.
    *   Calico IPIP uses Protocol 4 (not a port, an IP Protocol!). AWS Security Groups often block "All Traffic" but need specific Protocol permission if not using "All".

### Scenario: "Felix is Churning" (High CPU)
**Symptom:** `calico-node` uses 100% CPU. API Server is hammered.
**Debug:**
1.  **Metric Explosion:**
    *   Check if you have thousands of rapidly changing endpoints (churn).
    *   Felix has to recalculate iptables for *every* change.
2.  **Typha:**
    *   For clusters > 50 nodes, you MUST use `calico-typha`.
    *   Typha caches API server state and fans it out to nodes. Without it, every node hits the API server directly.

---

## 4. Troubleshooting Cilium (eBPF)

**Architecture:** Replaces kube-proxy. Uses eBPF maps for routing, load balancing, and policy.

### Scenario: "Identity Mismatch" (Policy Drop)
**Symptom:** Traffic dropped, but NetworkPolicy looks correct.
**Debug:**
1.  **Cilium Identity:**
    *   Cilium assigns a numeric Identity to every set of labels.
    *   `kubectl exec -n kube-system <cilium-pod> -- cilium endpoint list`
    *   Check if the pod has the correct Identity ID.
2.  **Monitor Drops:**
    *   `kubectl exec -n kube-system <cilium-pod> -- cilium monitor --type drop`
    *   This is the "tcpdump" of eBPF. It will tell you *exactly* why a packet was dropped (Policy denied, Invalid Conntrack, etc.).

### Scenario: "eBPF Map Full"
**Symptom:** Cannot start new pods or add services. Agents crash.
**Debug:**
1.  **Check Map Pressure:**
    *   `cilium status --verbose`
    *   Look at `BPF Maps` usage. If `Connection Tracking` or `Endpoints` is near limit, you need to increase map sizes in ConfigMap.

---

## 5. Troubleshooting Ingress Controllers (Nginx)

**Architecture:** A Deployment watching Ingress resources and generating `nginx.conf`.

### Scenario: "The Config Reloader Loop"
**Symptom:** Nginx controller restarts constantly.
**Debug:**
1.  **Bad Config:**
    *   A user submitted an Ingress with a bad annotation snippet (Lua injection or syntax error).
    *   The controller tries to generate `nginx.conf`, `nginx -t` fails, the pod panics or errors out.
2.  **The Fix:**
    *   Check logs: `kubectl logs -n ingress-nginx ...`
    *   Look for the specific Ingress causing the parse error. Delete/Fix it.

### Scenario: "Backend Protocol Mismatch"
**Symptom:** 502 Bad Gateway.
**Debug:**
1.  **HTTPS vs HTTP:**
    *   Does the *Target Pod* expect HTTPS?
    *   By default, Nginx sends HTTP.
    *   **Fix:** Add annotation `nginx.ingress.kubernetes.io/backend-protocol: "HTTPS"`.

---

## 6. Advanced Interview Questions (FAANG Level)

**Q1: Explain the difference between `kube-proxy` ipvs mode and `iptables` mode.**
*   **A:** `iptables` is O(N) rule traversal (slow with 10k services). Updates require reloading large chunks of rules. `ipvs` uses hash tables O(1) (fast) and supports better load balancing algorithms (Least Conn).

**Q2: Why would you choose Cilium over Calico?**
*   **A:** Performance (eBPF bypasses iptables/conntrack for some paths), Observability (Hubble flows provide L7 visibility), and advanced L7 Policy features without a sidecar. It also replaces kube-proxy fully.

**Q3: How does the Cloud Controller Manager (CCM) interact with Ingress?**
*   **A:** It doesn't directly. CCM manages `Services` of type `LoadBalancer` (creating the cloud LB). Ingress Controllers (like ALB Controller) talk directly to Cloud APIs to create L7 LBs.

**Q4: A CNI upgrade failed and left the cluster in a broken state. New pods stick in `ContainerCreating`. How do you recover?**
*   **A:**
    1.  **Check CNI Config:** Kubelet reads `/etc/cni/net.d/`. Did the upgrade leave a malformed config or multiple configs? Kubelet uses the first one alphabetically.
    2.  **Rollback:** Revert the DaemonSet manifest.
    3.  **Restart Kubelet:** Sometimes Kubelet caches the CNI client state. `systemctl restart kubelet`.
    4.  **Manually Clean:** If `ip link` shows zombie interfaces, you might need to manually delete them (carefully!).

**Q5: We are seeing intermittent connection resets (RST) between pods. How do you verify if it's a `conntrack` issue?**
*   **A:**
    1.  Check `conntrack -S` (stats) on the node. Look for `insert_failed` counter incrementing.
    2.  Check `dmesg` for `nf_conntrack: table full`.
    3.  **Fix:** Increase `net.netfilter.nf_conntrack_max` sysctl or switch to stateless LB (DSR) if possible (Cilium/Kube-router).

**Q6: How does "External Traffic Policy: Local" work?**
*   **A:** It preserves the client Source IP.
    *   *Default (Cluster):* LB -> Node A -> Node B (Pod). Source IP is SNAT'd to Node A's IP.
    *   *Local:* LB -> Node A. If Pod is there, traffic flows (IP preserved). If not, traffic is DROPPED (Health check must fail for nodes without pods).