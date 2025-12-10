# Rollback Procedures

## Overview
Safe rollback patterns for Deployments/StatefulSets/Helm/GitOps.

## Deployment Rollback
```bash
kubectl rollout undo deployment/<name> -n <ns> --to-revision=<rev>
kubectl rollout status deployment/<name> -n <ns>
```
- Confirm PDBs allow rollback; watch events for scheduling issues.

## Helm Rollback
```bash
helm history <release> -n <ns>
helm rollback <release> <rev> -n <ns>
```
- Re-run `./scripts/diagnostics/deployment-diagnostics.sh` after rollback.

## GitOps Rollback
- Revert Git commit; ensure controller syncs cleanly.
- Use `./scripts/diagnostics/gitops-diagnostics.sh` to verify sync/drift.

## Data Safety
- For stateful apps, snapshot volumes before rollback.
- Validate schema compatibility.

## Prevention
- Progressive delivery (canary/blue-green) to reduce rollback frequency.
- Automated preflight checks in CI/CD; store manifests per release.
