# Kubernetes/AKS/EKS Troubleshooting Guide  
Zero-to-hero with automation for architects, engineers, DevOps, SREs, and technical writers.

## How to Use This Guide
- **In an incident**: Run the Emergency Checklist below, then dive into the playbook for your symptom.
- **For prevention**: Follow the role guides and automation sections to bake guardrails into CI/CD and operations.
- **For growth**: Walk the docs in order—start with Quick Start, then team guides, then automation.

## Quick Start (Do This First)
- Install and configure `kubectl`; add Azure CLI (AKS) or AWS CLI (EKS) as needed.
- Validate connectivity: `kubectl cluster-info`
- Run the Emergency Checklist:
  1) Cluster health: `./scripts/diagnostics/cluster-health-check.sh`  
  2) Pod issues: `./scripts/diagnostics/pod-diagnostics.sh`  
  3) Network/DNS: `./scripts/diagnostics/network-diagnostics.sh`  
  4) Resources: `./scripts/diagnostics/resource-analysis.sh`  
  5) Storage: `./scripts/diagnostics/storage-analysis.sh`  
  6) Stuck rollout: `./scripts/diagnostics/deployment-diagnostics.sh <deploy> <ns>`  
  7) DNS repair: `./scripts/fixes/fix-dns-issues.sh`

## Repository Map
```
├── docs/
│   ├── architects/      # Cluster design, security, DR, sizing, mesh
│   ├── engineers/       # App debugging, perf, config, images
│   ├── devops/          # CI/CD, GitOps, rollout strategies, infra
│   ├── sre/             # Observability, incident response, SLOs
│   └── copywriters/     # Style, templates, documentation QA
├── scripts/
│   ├── diagnostics/     # Health, network, storage, rollout, GitOps
│   ├── fixes/           # Pods/DNS cleanup, scaling, cert refresh
│   └── monitoring/      # Prometheus/Grafana/alerts/logs bootstrap
├── playbooks/           # Severity-focused runbooks (P0/P1)
├── templates/           # Troubleshooting, runbook, post-mortem, API
└── k8s/                 # Deployment manifests for the diagnostics API
```

## Role Cheat Sheet
- **Architects**: Start at `docs/architects/` for tenancy, network, security, DR, sizing, and mesh patterns.
- **Engineers**: See `docs/engineers/` for pod startup, images, config/secrets, debugging, testing, performance.
- **DevOps**: Use `docs/devops/` for CI/CD failures, registry issues, GitOps, rollout patterns, infra setup.
- **SREs**: Check `docs/sre/` for monitoring, alerting, incident process, capacity/perf.
- **Technical Writers**: Follow `docs/copywriters/` with templates in `templates/`.

## Automation Highlights
- Diagnostics: pods, network/DNS, resources, storage, deployments, Helm, GitOps, pipelines.
- Remediation: restart failed pods, cleanup evicted, fix DNS, scale workloads, cert refresh.
- Observability: quick-start Prometheus/Grafana, baseline alerts, starter health dashboard, log aggregation.
- Programmatic: REST API and CLI for detect/fix flows (see `PROGRAMMATIC-GUIDE.md`).

## Supported Platforms
- AKS, EKS, self-managed Kubernetes, and GKE (patterns and scripts are cloud-aware where needed).

## Incident Escalation
Use the [Emergency Response Guide](docs/emergency-response.md). It defines roles, cadence, and cloud-provider escalation paths.

---
Version: 1.0.0  
Maintainers: FAAN Board (Architects, Engineers, DevOps, SREs, Technical Writers)  
Last Updated: $(date)
