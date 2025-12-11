# Site Reliability Engineering (SRE) Guide
Operate for uptime and fast recovery. This is a concise, action-first reference.

## Your Lens
- Build observability (metrics/logs/traces) and actionable alerts.
- Run incidents with discipline; capture learnings via post-mortems.
- Plan capacity and performance with headroom.

## Chapters
- Observability: metrics, logging, tracing, alerting.
- Incidents: classification, escalation, post-mortem, communication.
- Performance/Capacity: resource planning, tuning, autoscaling, cost.

## Run These First
```bash
./scripts/diagnostics/cluster-health-check.sh
./scripts/diagnostics/network-diagnostics.sh
./scripts/diagnostics/resource-analysis.sh
./scripts/diagnostics/performance-analysis.sh
./scripts/monitoring/setup-prometheus.sh
./scripts/monitoring/configure-alerts.sh
./scripts/monitoring/health-dashboard.sh
```

## SLI/SLO Starters
- Availability SLO: 99.9%
- Latency SLI: P95 < 200ms
- Error Rate SLI: < 0.1%
- Throughput: peak load + 20% buffer

## Troubleshooting Focus
- Service degradation: latency/error spikes, availability drops.
- Resource exhaustion: CPU/memory/storage/network pressure.
- Scaling: HPA/VPA/cluster-autoscaler behavior.
- Infra failures: node/CNI/DNS/ingress/load balancer issues.
