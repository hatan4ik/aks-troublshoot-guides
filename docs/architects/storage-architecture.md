# Storage Architecture

## Overview
Choose storage classes, performance tiers, and data protection patterns per workload.

## Decisions
- **Workload type**: StatefulSets vs stateless; latency vs throughput.
- **Backing store**: Managed disks, file shares, object storage; database-as-a-service where possible.
- **Durability**: Zonal vs regional; replication and snapshots.

## AKS Notes
- Managed Disks (Premium/Ultra) via CSI; Azure Files for shared RWX; enable snapshots for backups.
- Use ZRS for regional durability; align storage class to zone topology.

## EKS Notes
- EBS CSI driver (gp3/io2) for block; EFS for RWX; FSx for performance workloads.
- Snapshots for backup; multi-AZ via EFS or RDS/Aurora where possible.

## Diagnostics
```bash
./scripts/diagnostics/storage-analysis.sh
kubectl get pv,pvc
kubectl describe pvc <name>
```
- Check attach/bind errors in events and `storage-analysis.sh`.

## Patterns
- Prefer managed DB services over in-cluster databases for critical data.
- Use topology-aware storage classes to avoid cross-zone latency.
- Quotas per namespace for PVC usage; prune orphaned PVCs/PVs.

## Prevention
- Backups via Velero + CSI snapshots; test restores quarterly.
- Enforce storage class selection via admission controls.
- Monitor IOPS/throughput vs limits using `performance-analysis.sh`.
