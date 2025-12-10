# Kubernetes/AKS/EKS Troubleshooting Guide
## From Zero to Hero with Automation

A comprehensive troubleshooting guide for Kubernetes, Azure Kubernetes Service (AKS), and Amazon Elastic Kubernetes Service (EKS) designed for architects, engineers, DevOps, SREs, and technical writers.

## 📋 Table of Contents

- [Quick Start](#quick-start)
- [Architecture Overview](#architecture-overview)
- [Common Issues & Solutions](#common-issues--solutions)
- [Automation Scripts](#automation-scripts)
- [Team-Specific Guides](#team-specific-guides)
- [Monitoring & Observability](#monitoring--observability)
- [Best Practices](#best-practices)

## 🚀 Quick Start

### Prerequisites
- kubectl installed and configured
- Azure CLI (for AKS) or AWS CLI (for EKS)
- Basic understanding of Kubernetes concepts

### Emergency Troubleshooting Checklist
1. **Cluster Health**: `./scripts/diagnostics/cluster-health-check.sh`
2. **Pod Issues**: `./scripts/diagnostics/pod-diagnostics.sh`
3. **Network Problems**: `./scripts/diagnostics/network-diagnostics.sh`
4. **Resource Constraints**: `./scripts/diagnostics/resource-analysis.sh`
5. **Storage Issues**: `./scripts/diagnostics/storage-analysis.sh`
6. **Deployments Stuck**: `./scripts/diagnostics/deployment-diagnostics.sh <deploy> <ns>`
7. **DNS Issues**: `./scripts/fixes/fix-dns-issues.sh`

## 📁 Guide Structure

```
├── docs/
│   ├── architects/          # High-level design and architecture guides
│   ├── engineers/           # Development and implementation guides
│   ├── devops/             # CI/CD and deployment guides
│   ├── sre/                # Site reliability and operations guides
│   └── copywriters/        # Documentation templates and standards
├── scripts/
│   ├── diagnostics/        # Automated diagnostic scripts
│   ├── fixes/              # Automated fix scripts
│   └── monitoring/         # Monitoring setup scripts
├── playbooks/              # Step-by-step troubleshooting playbooks
├── templates/              # YAML templates and configurations
└── examples/               # Real-world examples and case studies
```

## 🎯 Team-Specific Quick Access

- **[Architects](docs/architects/)** - Design patterns, scalability, security architecture
- **[Engineers](docs/engineers/)** - Application deployment, debugging, development workflows
- **[DevOps](docs/devops/)** - CI/CD pipelines, infrastructure automation, deployment strategies
- **[SREs](docs/sre/)** - Monitoring, alerting, incident response, capacity planning
- **[Technical Writers](docs/copywriters/)** - Documentation standards, templates, style guides

## 🔧 Automation Features

- **One-click diagnostics** for common issues (pods, network, deployments, storage, GitOps, Helm)
- **Automated remediation** scripts for pods, DNS, evicted cleanup, scaling, and cert refresh
- **Health monitoring** dashboards and alerts (Prometheus/Grafana/alerts)
- **Performance optimization** recommendations and resource profiling
- **Security scanning** and compliance checks via `security-audit.sh`
- **Programmatic API/CLI** for detect/fix workflows

## 📊 Supported Platforms

- ✅ Azure Kubernetes Service (AKS)
- ✅ Amazon Elastic Kubernetes Service (EKS)
- ✅ Self-managed Kubernetes
- ✅ Google Kubernetes Engine (GKE)

## 🆘 Emergency Contacts & Escalation

See [Emergency Response Guide](docs/emergency-response.md) for critical issue escalation procedures.

---

**Last Updated**: $(date)
**Version**: 1.0.0
**Maintainers**: FAAN Board (Architects, Engineers, DevOps, SREs, Technical Writers)
