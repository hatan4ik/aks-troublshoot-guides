# P0 - Cluster Outage / API Unreachable

## Symptoms
- `kubectl`/API server unreachable or frequent 5xx
- Majority workloads impacted across namespaces

## Immediate Actions (0-5 mins)
1. Declare P0, page on-call, start war room.
2. Capture basic signals (no changes yet):
```bash
kubectl cluster-info                     # may fail
./scripts/diagnostics/cluster-health-check.sh
```
3. If control plane down in managed service, open cloud ticket (AKS/EKS) with timestamps/regions.

## Stabilization (5-15 mins)
- Check node health and etcd/critical system pods (if accessible): `kubectl get nodes,pods -A`.
- For partial outages, cordon unhealthy nodes: `kubectl cordon <node>`.
- Restart stuck critical add-ons (DNS, CNI) only if safe: `python k8s-diagnostics-cli.py fix`.

## Recovery
- If managed outage, shift traffic to standby/DR cluster; update DNS/ingress.
- Re-run health: `./scripts/diagnostics/network-diagnostics.sh` and `cluster-health-check.sh`.

## Verification
- SLIs (availability, latency) within SLO; alerts cleared.
- Workloads reachable via smoke tests.

## Communication
- Update stakeholders every 15 minutes until resolved, then hourly until stable.

## Post-Incident
- File post-mortem with `templates/post-mortem-template.md`.
- Add action items: failover readiness, alerting gaps, capacity fixes.
