# GitOps Workflows

## Overview
Declarative delivery via controllers (Argo CD/Flux) syncing from Git to clusters.

## Best Practices
- One source of truth; separate env folders/branches.
- Use Kustomize/Helm overlays; sign commits and container images.
- Enforce PR checks (policy, lint, `kubectl diff`).

## Diagnostics
```bash
./scripts/diagnostics/gitops-diagnostics.sh
kubectl get applications -A   # Argo CD
kubectl get kustomizations -A # Flux
```
- Check sync status, health, and drift.
- Inspect controller logs for auth/rate limits.

## Recovery
- Pause sync for investigations; manual sync with health checks.
- Roll back by reverting Git commit; confirm controller applies cleanly.

## Prevention
- Admission policy to block out-of-band changes.
- Alert on OutOfSync or degraded apps; integrate with `health-dashboard.sh`.
