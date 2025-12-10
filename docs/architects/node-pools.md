# Node Pool Strategies

## Overview
Segment workloads by characteristics and isolation needs. Optimize cost/perf while keeping SLOs.

## Patterns
- **System Pool**: Control plane add-ons, ingress, observability.
- **General Pool**: Default workloads.
- **Performance Pool**: CPU/IO intensive (use faster disks/instance families).
- **GPU/Accelerator Pool**: ML/AI tasks with taints/tolerations.
- **Compliance Pool**: Hardened OS, restricted egress.

## Best Practices
- Taint system and special pools; use tolerations explicitly.
- Separate spot/preemptible pools for cost; enforce PDBs to handle eviction.
- Align topology spread constraints to AZs.

## AKS Notes
- Use node pool labels/taints for Windows/Linux split; enable surge upgrades.
- Spot node pools with eviction toleration and fallback.

## EKS Notes
- Managed Node Groups or Karpenter for dynamic provisioning.
- Security Groups per pool for isolation; Bottlerocket for immutable OS.

## Diagnostics
```bash
kubectl get nodes -L agentpool,node.kubernetes.io/instance-type,topology.kubernetes.io/zone
kubectl get pod -A -o wide | grep -v Running
./scripts/diagnostics/resource-analysis.sh
```

## Prevention
- Admission policies enforcing pool placement for critical workloads.
- Autoscaler profiles per pool; surge upgrades with maxUnavailable tuned.
