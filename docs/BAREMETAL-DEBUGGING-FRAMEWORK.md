# Bare Metal Debugging Framework

The structured mental model for diagnosing failures in a bare-metal or on-prem Kubernetes cluster. Use this before opening a runbook. It tells you which layer to investigate and in what order.

---

## The 5-Layer Model

Bare-metal clusters still benefit from the same layered model. The difference is that there is no cloud provider to absorb the outer infrastructure layer for you.

```text
Layer 1 │ Pod Lifecycle      │ Scheduling, image pull, startup, probes, config
Layer 2 │ Container Runtime  │ OOM, cgroups, exit codes, containerd
Layer 3 │ Service Networking │ Selector, endpoints, ports, DNS, Ingress
Layer 4 │ Cluster Infra      │ Nodes, CNI, CoreDNS, kube-proxy, NetworkPolicy, etcd
Layer 5 │ Physical Infra     │ Switches, Routers, BGP, MetalLB/Kube-VIP, Storage arrays, DNS, Hypervisor
```

**The key discipline:** do not jump to switch ACLs or BGP until the pod, service, endpoints, and kube-system path are proven.

---

## Decision Tree

Start here every time:

```bash
kubectl get pods -A
kubectl get events -A --sort-by=.metadata.creationTimestamp | tail -30
```

Use these branches:

- `Pending`
  - resource pressure -> Layer 1
  - taint / selector -> Layer 1
  - PVC / storage unavailable -> Layer 4 or 5 depending on the provisioner
- `ImagePullBackOff`
  - bad tag / auth -> Layer 1
  - timeout to registry -> Layer 5, often proxy, firewall, or routing
- pod Running, traffic fails
  - endpoints empty -> Layer 3
  - endpoints populated, refusal -> Layer 3
  - endpoints populated, timeout -> Layer 4 or 5, often NetworkPolicy, MTU, ARP, BGP, or firewall
- Service `LoadBalancer` pending forever
  - usually Layer 5, no cloud controller or broken MetalLB / Kube-VIP path

---

## Layer 4 — Cluster Infrastructure

**Scope:** node services and cluster-managed networking.

### Node and kube-system checks

```bash
kubectl get nodes
kubectl describe node <node>
kubectl get pods -n kube-system
```

### CNI and DNS checks

```bash
kubectl get pods -n kube-system
kubectl logs -n kube-system -l k8s-app=kube-dns --tail=30
kubectl get networkpolicy -A
```

Look for:

- CNI daemonset failures
- CoreDNS issues
- kube-proxy or iptables mismatches
- etcd degradation or quorum loss

---

## Layer 5 — Physical And Data Center Infrastructure

**Scope:** the network, storage, and control-plane plumbing you own directly.

### Common bare-metal failure patterns

- `LoadBalancer` services stay pending -> no CCM, MetalLB not configured, or BGP/L2 announcements broken
- pod-to-pod traffic drops across nodes -> MTU mismatch, switch ACL, or routing issue
- control-plane VIP flaps -> Keepalived or Kube-VIP split brain
- PVC stuck -> storage provisioner, NFS/Ceph/backend array issue

### Infrastructure checks

```bash
# ARP / L2
tcpdump -i <iface> arp

# Routing / BGP
ip route
birdc show protocols

# Node and host networking
ip addr show
ethtool -i <iface>
dmesg | tail -50
```

**When to escalate to physical-infra investigation:**

- Service path is correct but no traffic reaches nodes
- MetalLB or VIP advertisement is missing
- storage backend is unhealthy outside Kubernetes
- NIC, switch, router, or hypervisor behavior is causing cluster instability

---

## Key References

- [On-Prem Kubernetes Guide](./on-prem-kubernetes.md)
- [Bare Metal Networking](./baremetal/baremetal-networking.md)
- [Bare Metal Observability](./baremetal/baremetal-observability.md)
- [Live Debug Runbook](../DEBUG-RUNBOOK.md)

