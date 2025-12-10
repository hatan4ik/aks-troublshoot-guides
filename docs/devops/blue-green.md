# Blue-Green Deployments

## Overview
Run two production environments (blue/green) and switch traffic when green is verified.

## Steps
1. Deploy green version alongside blue with distinct services or routes.
2. Run smoke/perf checks on green.
3. Switch traffic (ingress/LB/feature flag) to green.
4. Monitor; keep blue for rollback window, then retire.

## Diagnostics
```bash
./scripts/diagnostics/deployment-diagnostics.sh
kubectl get svc -A | grep blue
kubectl get svc -A | grep green
```
- Validate endpoints and readiness before switch.

## AKS/EKS Notes
- Ingress rule/AGIC/ALB weight shift; DNS weight updates via Traffic Manager/Route53.

## Prevention
- Automated health gates; record Helm history; keep rollback plan.
