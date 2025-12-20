# On-Premises Kubernetes & Bare Metal Troubleshooting

## Overview
Running Kubernetes on bare metal or on-prem VMs (VMware/KVM) is a different beast than EKS/AKS. You don't have an infinite "Cloud Controller Manager" to hand you LoadBalancers and Storage. You *are* the Cloud Provider.

This guide covers the specific challenges of the "Do It Yourself" (DIY) approach, often tested in FAANG interviews for Infrastructure roles.

---

## 1. Networking: The Hardest Part (BGP & Load Balancers)

### The Problem: "Pending" LoadBalancers
In AWS, a Service of `type: LoadBalancer` spins up an ELB. On-prem, it sits in `Pending` forever because no controller exists to fulfill it.

### Solution 1: MetalLB (Layer 2 Mode)
*   **How it works:** One node claims the Service IP and uses ARP (gratuitous ARP) to tell the switch "I have this IP".
*   **Limitation:** All traffic goes to one node (bottleneck). Failover takes seconds (ARP cache timeout).
*   **Troubleshooting:**
    *   `tcpdump -i eth0 arp` -> Do you see the ARP announcements?
    *   Switch Security: Does the physical switch block "MAC moves" or gratuitous ARP?

### Solution 2: MetalLB (BGP Mode) / Kube-VIP
*   **How it works:** All nodes speak BGP to the Top-of-Rack (ToR) switch. They advertise the Service IP via ECMP (Equal-Cost Multi-Path).
*   **Advantage:** True load balancing across all nodes. Millisecond failover.
*   **Troubleshooting:**
    *   **BGP Session Down:** Check ASN numbers, passwords, and peering IP connectivity.
    *   **Route Flapping:** If a node is "unstable", it might withdraw/advertise routes rapidly, causing the router to damp the route.

### Scenario: The "Split Brain" Network
**Symptom:** Some pods can reach the internet, others can't.
**Debug:**
1.  **MTU Mismatch:** Jumbo frames (9000) on switch, standard (1500) on OS?
2.  **Hairpinning:** Can a pod access a Service IP that resolves to *itself*? (Requires specific iptables/CNI config).

---

## 2. Storage: No EBS, No Problem?

### The Solutions
1.  **Local Path Provisioner:** Uses a folder on the node's disk (`/opt/local-path-provisioner`).
    *   *Risk:* If node dies, data is GONE (or at least inaccessible until node revives).
    *   *Use:* Caches, ephemeral databases.
2.  **Rook / Ceph:** Hyper-converged storage. Uses spare disks on nodes to create a distributed replicated filesystem.
    *   *Complexity:* High. Ceph is its own beast.

### Scenario: "Rook Ceph Health Warning"
**Symptom:** PVCs hang in `Pending`. Ceph status is `HEALTH_WARN`.
**Debug:**
1.  **Clock Skew:** Ceph relies heavily on time. If nodes drift >0.05s, monitors lose quorum.
    *   *Check:* `chronyc tracking` on all nodes.
2.  **OsdDown:** Did a disk fill up? Ceph stops writing at 95% full (backfillfull_ratio).

---

## 3. Etcd Management (You Own the Brain)

In EKS/AKS, you never see Etcd. On-prem, you manage the backups, defragmentation, and encryption.

### Scenario: "Etcd Database Space Exceeded"
**Symptom:** Cluster becomes read-only. `etcdserver: mvcc: database space exceeded`.
**Cause:** Etcd has a 2GB (default) or 8GB limit. It doesn't clear old key versions automatically if compaction fails.
**Fix:**
1.  **Get Revision:** `etcdctl endpoint status -w table`
2.  **Compact:** `etcdctl compact <revision>`
3.  **Defrag:** `etcdctl defrag` (This actually releases the file space).
4.  **Disarm Alarm:** `etcdctl alarm disarm`

---

## 4. High Availability (HA) Control Plane

### The Virtual IP (VIP)
You need a stable IP for the API Server (`https://<vip>:6443`) that floats between Control Plane nodes.
*   **Tools:** Keepalived (VRRP) or Kube-VIP.
*   **Failure Mode:** Split-brain. Two nodes think they own the VIP.
*   **Check:** `ip addr show` on all masters. If multiple have the VIP, your VRRP multicast packets are being blocked by the switch.

---

## 5. Interview Questions (On-Prem Focus)

**Q: "We have a 3-node Control Plane. One node's hardware fails permanently. How do you restore the cluster health?"**
*   **A:**
    1.  Etcd has lost quorum (need 2/3). It's still running, but if another fails, it's over.
    2.  **Remove the member:** `etcdctl member remove <id>`.
    3.  **Add replacement:** Provision new node, `etcdctl member add ...`.
    4.  **Join:** Run `kubeadm join --control-plane ...`.

**Q: "Why is 'HostPort' considered bad practice, and what is the on-prem alternative?"**
*   **A:** `HostPort` binds a pod to a specific port on the node's IP. Only one instance can run per node.
*   **Alternative:** Use `NodePort` (random high port) or `LoadBalancer` (MetalLB) to decouple the service from the physical node.

**Q: "How do you handle OS patching on bare metal nodes without downtime?"**
*   **A:**
    1.  `kubectl drain <node> --ignore-daemonsets --delete-emptydir-data`.
    2.  Wait for pod eviction.
    3.  Patch & Reboot.
    4.  `kubectl uncordon <node>`.
