# Deployment Failures

## Overview
Deployment/Helm releases fail or stall during rollout.

## Symptoms
- `kubectl rollout status` hangs or fails
- Pods stuck Pending/CrashLoop/ImagePull
- Readiness probes failing after update

## Diagnostics
```bash
./scripts/diagnostics/deployment-diagnostics.sh
kubectl rollout status deploy/<name> -n <ns>
kubectl describe rs -n <ns>
```
- Check events for failed scheduling or image pulls.
- Inspect Helm history: `helm history <release> -n <ns>`

## Quick Fixes
- Roll back: `kubectl rollout undo deploy/<name> -n <ns>` or `helm rollback`.
- Fix probes/resources/secrets and redeploy.
- Validate image tag exists and registry reachable.

## Prevention
- Use canary/blue-green for risk reduction.
- Pre-deploy validation (policy checks, `kubectl diff`, `helm lint`).
- Health checks in pipelines using Programmatic CLI (`python k8s-diagnostics-cli.py diagnose <ns> <pod>`).
