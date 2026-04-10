# GKE Debugging Framework

The structured mental model for diagnosing failures in a Google Kubernetes Engine cluster. Use this before opening a runbook. It tells you which layer to investigate and in what order.

---

## The 5-Layer Model

Every GKE failure lives in one of these layers. Diagnose top-down. Most failures are still in layers 1-3.

```text
Layer 1 │ Pod Lifecycle      │ Scheduling, image pull, startup, probes, config
Layer 2 │ Container Runtime  │ OOM, cgroups, exit codes, containerd
Layer 3 │ Service Networking │ Selector, endpoints, ports, DNS, Ingress
Layer 4 │ Cluster Infra      │ Nodes, Dataplane V2/CNI, CoreDNS, kube-proxy, NetworkPolicy
Layer 5 │ Google Infra       │ Firewall Rules, Cloud Load Balancing, Cloud NAT, Artifact Registry, Persistent Disk, Cloud DNS
```

**The key discipline:** prove the Kubernetes objects are correct before blaming firewall rules, Cloud NAT, or the external load balancer.

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
  - taints / node selector -> Layer 1
  - PVC / PD provisioning -> Layer 5 if storage topology is the blocker
- `ImagePullBackOff`
  - bad tag -> Layer 1
  - auth issue -> Layer 1 or Artifact Registry IAM
  - timeout -> Layer 5, often Cloud NAT, Private Google Access, or egress control
- `CrashLoopBackOff`
  - exit `127` -> bad command
  - exit `137` -> OOM
  - exit `1` -> app/config
- pod Running, traffic fails
  - endpoints empty -> Layer 3 selector or readiness
  - endpoints populated, refusal -> Layer 3 port mismatch
  - endpoints populated, timeout -> Layer 4 or 5, often NetworkPolicy, firewall, NEG, or load balancer wiring

---

## Layer 4 — Cluster Infrastructure

**Scope:** GKE-managed cluster networking and node services.

### Node and kube-system checks

```bash
kubectl get nodes
kubectl describe node <node>
kubectl get pods -n kube-system
```

### Dataplane and DNS checks

```bash
kubectl get pods -n kube-system
kubectl get networkpolicy -A
kubectl get pods -n kube-system -l k8s-app=kube-dns
kubectl logs -n kube-system -l k8s-app=kube-dns --tail=30
```

Look for:

- Dataplane V2 or CNI issues
- CoreDNS problems
- cluster-local traffic blocked by policy

---

## Layer 5 — Google Infrastructure

**Scope:** Google Cloud services around the cluster.

### Common GKE-specific failure patterns

- `ImagePullBackOff` with timeout -> Cloud NAT, Private Google Access, or Artifact Registry reachability
- External service or ingress is provisioned but traffic fails -> backend service, NEG, or firewall rule issue
- PVC provisioning or attach failure -> Persistent Disk CSI, zone mismatch, or quota
- Private cluster access broken -> master authorized networks, private control plane, or DNS

### GCP checks

```bash
gcloud container clusters describe <cluster> --region <region>

# Firewall and routes
gcloud compute firewall-rules list
gcloud compute routes list

# Load balancer and backend health
gcloud compute backend-services list
gcloud compute backend-services get-health <backend-service> --global
```

**When to escalate to Google Cloud investigation:**

- Kubernetes service path is correct but traffic still times out externally
- Artifact Registry access times out from private nodes
- Persistent Disk or load balancer provisioning is blocked
- Private control plane access or DNS is failing outside the cluster

---

## Key References

- [GKE Networking Deep Dive](./gcp/gke-networking.md)
- [GCP Observability For GKE](./gcp/gcp-observability.md)
- [Live Debug Runbook](../DEBUG-RUNBOOK.md)
- [Live Debugging Workflow](./LIVE-DEBUG-WORKFLOW.md)

