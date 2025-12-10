# Storage Configuration

## Overview
Configure storage classes, PVCs, and CSI drivers for AKS/EKS.

## Steps
1. Install CSI drivers (Azure Disk/File; EBS/EFS/FSx).
2. Define storage classes with parameters (type/performance, encryption).
3. Bind PVCs with correct access modes (RWO/RWX) and topology.
4. Enable snapshots/backups.

## Diagnostics
```bash
./scripts/diagnostics/storage-analysis.sh
kubectl get pv,pvc
kubectl describe pvc <name>
```
- Look for `Pending` PVCs, attach errors, or throttling.

## AKS Notes
- Use managed identities for CSI; ZRS for durability; match zone to node pools.
- Azure Files for RWX; tune mount options for perf.

## EKS Notes
- gp3 for general use; io2 for perf; EFS for RWX; ensure IAM roles for CSI.
- FSx for Lustre/ONTAP for high-perf shared workloads.

## Prevention
- Default storage class per workload type; enforce via admission policy.
- Monitor IOPS/throughput; alert on attach/bind failures via `storage-analysis.sh`.
