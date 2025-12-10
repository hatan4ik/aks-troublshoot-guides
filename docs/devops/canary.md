# Canary Deployments

## Overview
Gradually shift traffic to a new version to limit blast radius.

## Steps
1. Deploy new version as canary pods with small replica count.
2. Use weighted routing (ingress, service mesh, ALB/AGIC) to send small traffic %.
3. Monitor SLIs and errors; increase weight incrementally.
4. Promote to 100% or rollback quickly.

## Diagnostics
```bash
./scripts/diagnostics/deployment-diagnostics.sh
kubectl get ingress -A
kubectl get svc -A -l track=canary
```
- Track metrics/logs by version labels.

## Prevention
- Automated rollback triggers on SLO breach.
- Align HPA with canary pods; avoid starving baseline.
