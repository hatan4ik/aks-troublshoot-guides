# Site Reliability Engineering (SRE) Guide

## Overview
Operational excellence, monitoring, alerting, incident response, and capacity planning for Kubernetes environments.

## Key Responsibilities
- System reliability and availability
- Monitoring and observability setup
- Incident response and post-mortems
- Capacity planning and performance optimization

## Quick Reference

### Monitoring & Observability
- [Metrics Collection](metrics-collection.md)
- [Logging Strategy](logging-strategy.md)
- [Distributed Tracing](distributed-tracing.md)
- [Alerting Rules](alerting-rules.md)

### Incident Response
- [Incident Classification](incident-classification.md)
- [Escalation Procedures](escalation-procedures.md)
- [Post-Mortem Process](post-mortem.md)
- [Communication Templates](communication-templates.md)

### Performance & Capacity
- [Resource Planning](resource-planning.md)
- [Performance Tuning](performance-tuning.md)
- [Autoscaling Configuration](autoscaling.md)
- [Cost Optimization](cost-optimization.md)

### SRE Automation Tools
```bash
# System health dashboard (Grafana)
./scripts/monitoring/health-dashboard.sh

# Resource/capacity analysis
./scripts/diagnostics/resource-analysis.sh
./scripts/diagnostics/performance-analysis.sh

# Monitoring/alerts
./scripts/monitoring/setup-prometheus.sh
./scripts/monitoring/configure-alerts.sh
```

### SLI/SLO Management
- **Availability SLO**: 99.9% uptime
- **Latency SLI**: P95 < 200ms
- **Error Rate SLI**: < 0.1% error rate
- **Throughput SLI**: Handle peak load + 20%

### Troubleshooting Focus Areas
1. **Service degradation** - Latency spikes, error rates, availability
2. **Resource exhaustion** - CPU, memory, storage, network
3. **Scaling issues** - HPA, VPA, cluster autoscaler
4. **Infrastructure failures** - Node failures, network partitions

## Emergency Escalation
For production incidents:
1. **P0/P1**: Immediate escalation to on-call engineer
2. **P2**: Run incident toolkit: `./scripts/diagnostics/incident-toolkit.sh`
3. **P3/P4**: Standard troubleshooting procedures
