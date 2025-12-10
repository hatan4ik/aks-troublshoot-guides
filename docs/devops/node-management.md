# Node Management

## Overview
Maintain node health, upgrades, and scaling.

## Diagnostics
```bash
./scripts/diagnostics/cluster-health-check.sh
kubectl get nodes -o wide
kubectl describe node <name>
```
- Check pressure conditions; cordon/drain status.

## Operations
- **Cordon/Drain**: `kubectl cordon <node>; kubectl drain <node> --ignore-daemonsets --delete-emptydir-data`
- **Upgrades**: Surge upgrades on AKS; rolling node group updates on EKS/managed node groups.
- **Scaling**: Cluster autoscaler/HPA tuned with min/max; watch PDBs.

## AKS Notes
- Use node image upgrade; ephemeral OS disks for speed; monitor health extension.

## EKS Notes
- Use Managed Node Group version upgrades; Bottlerocket for immutability; respect max unavailable.

## Prevention
- Enforce PDBs; taints/tolerations for system vs user workloads.
- Alerts on NotReady nodes and disk/memory pressure via `health-dashboard.sh`.
