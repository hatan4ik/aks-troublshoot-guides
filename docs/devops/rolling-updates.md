# Rolling Updates

## Overview
Incrementally replace pods to avoid downtime.

## Best Practices
- Set `maxUnavailable`/`maxSurge` per risk tolerance.
- Ensure readiness/liveness/startup probes are correct.
- Use PDBs to keep capacity during rollouts.

## Diagnostics
```bash
kubectl rollout status deploy/<name> -n <ns>
./scripts/diagnostics/deployment-diagnostics.sh
kubectl get events -n <ns> --sort-by=.lastTimestamp | tail
```
- Watch for Pending/CrashLoop/ImagePull issues.

## Prevention
- `kubectl diff`/`helm diff` in CI; validate configs and secrets.
- Autoscaler headroom for surge.
- Use canary/blue-green for higher risk changes.
