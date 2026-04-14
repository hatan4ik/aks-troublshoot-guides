# FinOps and Resource Optimization

## Scope

Use this guide to find Kubernetes cost leaks without weakening reliability. The goal is not to make the cluster smaller at all costs. The goal is to identify waste, prove the blast radius, and then make reversible changes with SLO context.

Start with the biggest cost drivers:

```text
nodes -> load balancers -> persistent disks -> over-requested pods -> logging/metrics volume
```

## Fast Inventory

```bash
kubectl top nodes
kubectl top pods -A
kubectl get hpa -A
kubectl get vpa -A
kubectl get pdb -A
kubectl get resourcequota -A
kubectl get limitrange -A
kubectl get pvc,pv -A
kubectl get svc -A --field-selector spec.type=LoadBalancer
kubectl get pods -A -o custom-columns=NS:.metadata.namespace,NAME:.metadata.name,CPU_REQ:.spec.containers[*].resources.requests.cpu,CPU_LIM:.spec.containers[*].resources.limits.cpu,MEM_REQ:.spec.containers[*].resources.requests.memory,MEM_LIM:.spec.containers[*].resources.limits.memory
```

Repo diagnostics that are useful during cost review:

```bash
./scripts/diagnostics/resource-analysis.sh
./scripts/diagnostics/hpa-check.sh
./scripts/diagnostics/storage-analysis.sh
./scripts/diagnostics/monitoring-audit.sh
```

## Cost Leak Matrix

| Cost signal | What it usually means | What to check | Safer remediation |
|---|---|---|---|
| Many idle nodes | Requests too high, autoscaler blocked, node pool too fragmented | `kubectl top nodes`, pending pods, PDBs, taints | Right-size requests, fix PDBs, consolidate node pools |
| Low CPU usage but high requested CPU | Over-requested workloads | Pod requests vs utilization | Lower requests gradually using historical metrics |
| Memory usage close to request but far below limit | Request may be accurate, limit may be too high | OOM history, p95/p99 memory | Avoid lowering memory without workload owner review |
| Many `LoadBalancer` services | Per-service cloud LB cost | Service list and owners | Consolidate behind Ingress/Gateway where appropriate |
| Bound PVCs with no active pods | Orphaned disks or stale environments | PVC/PV owner refs, namespace lifecycle | Snapshot or backup before deleting |
| HPA flaps up/down | Bad metric, too-sensitive target, CPU throttling | HPA events, metric server, request sizing | Tune requests, stabilization windows, and metric target |
| High log/metrics cost | Cardinality explosion, noisy debug logs, excessive retention | Top log streams, metric labels | Reduce cardinality and retention, sample debug logs |
| GPU node underutilization | Expensive accelerator capacity idle | GPU pod placement, queue depth | Batch jobs, separate GPU pools, scale to zero if safe |

## HPA and VPA Review

HPA depends on resource requests. A missing or unrealistic CPU request can make autoscaling misleading.

```bash
kubectl describe hpa <name> -n <namespace>
kubectl top pod -n <namespace>
kubectl get events -n <namespace> --sort-by=.metadata.creationTimestamp | tail -40
```

Use VPA recommendations as input, not automatic truth:

```bash
kubectl get vpa -A
kubectl describe vpa <name> -n <namespace>
```

For production workloads, prefer VPA in recommendation mode unless the team has explicitly accepted eviction behavior.

## Storage Cost Review

PVCs can outlive the workload that created them. Always confirm data ownership before cleanup:

```bash
kubectl get pvc -A
kubectl get pv
kubectl describe pv <pv-name>
kubectl get pods -A -o jsonpath='{range .items[*]}{.metadata.namespace}{" "}{.metadata.name}{" "}{.spec.volumes[*].persistentVolumeClaim.claimName}{"\n"}{end}'
```

Look for:

- PVCs in deleted or inactive namespaces.
- Retained PVs with no claim.
- Premium disk classes used by non-critical workloads.
- StatefulSet volumes from old revisions or decommissioned environments.

## Load Balancer and Ingress Review

In production, many applications should share a controlled north-south entry layer:

```bash
kubectl get svc -A --field-selector spec.type=LoadBalancer
kubectl get ingress -A
kubectl get gateway -A
```

Do not collapse all traffic into one Ingress only for cost. Keep isolation where security, ownership, blast radius, or compliance requires it.

## Provider Notes

### AKS

- Watch Azure Load Balancer, public IP, managed disk, Log Analytics ingestion, and GPU VM costs.
- Azure CNI can turn IP waste into scale limits. Review subnet sizing and node pool fragmentation together.
- For ACR-heavy workloads, image pull storms can add latency and indirect scaling cost.

### EKS

- Watch NLB/ALB count, NAT Gateway data processing, EBS volumes/snapshots, CloudWatch logs, and GPU instances.
- AWS VPC CNI IP exhaustion often appears as scheduling or pod sandbox failure, which can cause over-scaling.
- IRSA failures can trigger retries and noisy logs; fix identity rather than scaling the workload.

### GKE

- Watch forwarding rules, persistent disks, Cloud Logging/Monitoring ingestion, and regional cluster/node pool cost.
- VPC-native IP allocation issues can cause unschedulable pods even when node CPU/memory appears available.
- Autopilot changes the optimization model. Focus more on requests and workload shape.

## Remediation Guardrails

- Use 7 to 30 days of utilization for production right-sizing decisions.
- Do not lower requests for latency-sensitive services from a single quiet hour of data.
- Do not delete PVCs, PVs, or snapshots without service owner approval.
- Treat PDBs and cluster autoscaler blockers as reliability issues before treating them as cost issues.
- Prefer a measurable target: cost per namespace, cost per request, cost per job, or cost per customer.

## Interview Signals

A strong answer should explain:

- Why CPU requests drive bin-packing and HPA math.
- Why memory right-sizing is riskier than CPU right-sizing.
- Why orphaned PVCs and cloud disks are common Kubernetes cost leaks.
- Why FinOps decisions need ownership labels, SLOs, and rollback plans.
