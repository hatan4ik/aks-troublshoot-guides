# Disaster Recovery (AKS/EKS/Kubernetes)

## Overview
Recover control plane and workloads after regional or cluster-level failure. Define RPO/RTO targets and test regularly.

## Strategy
- **Backups**: etcd/cluster-state via Velero; application data via CSI snapshots/DB backups.
- **Footprint**: Multi-AZ as default; DR region with IaC + GitOps for fast recreate.
- **Traffic**: Global DNS (Traffic Manager/Route53) with health checks and failover.
- **Secrets**: Externalized (Key Vault/Secrets Manager) replicated to DR region.

## DR Runbook (Condensed)
1. Validate outage scope with `./scripts/diagnostics/cluster-health-check.sh`.
2. Restore control plane objects from backups (Velero) into standby cluster.
3. Restore persistent volumes via CSI snapshots or storage-level restores.
4. Flip traffic via DNS/ingress updates.
5. Verify app health and data integrity.

## Diagnostics
```bash
./scripts/diagnostics/cluster-health-check.sh
./scripts/diagnostics/storage-analysis.sh
kubectl get volumesnapshots -A
```

## AKS Nuances
- Use Availability Zones; back up to GRS storage; Azure Policy for backup enforcement.
- AGIC/App Gateway failover through Traffic Manager; Key Vault with geo-redundancy.

## EKS Nuances
- Multi-AZ node groups; EBS snapshots for stateful sets; Route53 failover routing; IRSA credentials replicated.

## Testing & Prevention
- Quarterly DR game days with timed RTO/RPO.
- Automate restores via `gitops-diagnostics.sh` to ensure manifests are replayable.
- Keep storage class parameters consistent across regions.
