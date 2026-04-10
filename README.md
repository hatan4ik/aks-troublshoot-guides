# Kubernetes/AKS/EKS Troubleshooting Guide

**Hands-on debugging guides, incident playbooks, and engineering reference for Kubernetes operators and engineers.**

This repository is a practical toolkit for Kubernetes operations, debugging, and architecture. It is designed for real incident response, production troubleshooting, and structured investigation in live clusters.

---

## 📖 Table of Contents
- [Prerequisites & Setup](#-prerequisites--setup)
- [How to Use This Guide](#how-to-use-this-guide)
- [🧪 Live Cluster Debugging (Start Here)](#-live-cluster-debugging-start-here)
- [🎓 Engineering Depth](#-engineering-depth)
- [🚀 Quick Start (Emergency Response)](#-quick-start-emergency-response)
- [🗺️ Repository Map](#-repository-map)
- [🛠️ Deep Dive Guides](#-deep-dive-guides)
    - [On-Prem / Bare Metal](#on-prem--bare-metal)
    - [Network Controllers (CNI)](#network-controllers-cni)
    - [Security Control Framework (SCF)](#security-control-framework-scf)
- [🤖 Automation & Scripts](#-automation--scripts)
- [👥 Role-Based Operating Models](#-role-based-operating-models)

---

## 📦 Prerequisites & Setup
Before using the advanced features of this guide, ensure you have the necessary tooling installed.

### 1. Optional AI Tooling
AI-assisted tooling is optional. Nothing in this repository requires it for normal use or live cluster debugging.

```bash
npm install -g @google/gemini-cli
```

### 2. Install Kubernetes Tools
Ensure you have the standard K8s toolchain:
*   `kubectl`
*   `helm`
*   `python3` (for the diagnostics CLI)

---

## How to Use This Guide

- **For live cluster debugging**: Open [DEBUG-RUNBOOK.md](./DEBUG-RUNBOOK.md) — symptom ToC and fix commands in one file.
- **In an incident**: Run the [Emergency Checklist](#-quick-start-emergency-response) below, then dive into the `playbooks/` folder.
- **For prevention**: Follow the [Operating Models](#-role-based-operating-models) and automation sections to bake guardrails into CI/CD.
- **For growth**: Walk the docs in order—start with Quick Start, then team guides, then automation.

---

## 🧪 Live Cluster Debugging (Start Here)

Given a running cluster with a failing application, use this repo in this order:

1. 👉 **[Live Debug Runbook](./DEBUG-RUNBOOK.md)** — symptom ToC, copy-paste commands, single file
2. **[Live Debugging Workflow](./docs/LIVE-DEBUG-WORKFLOW.md)** — investigation strategy and safe change process
3. **[Common Kubernetes Issues Playbook](./playbooks/common-issues.md)** — symptom-to-cause reference
4. **[Pod Startup Issues](./docs/engineers/pod-startup-issues.md)** — scheduling, init containers, misconfigurations
5. **[Advanced Debugging Techniques](./docs/engineers/debugging-techniques.md)** — exit codes, probes, runtime troubleshooting

---

## 🎓 Engineering Depth

For staff-level systems thinking, architectural trade-offs, and production-scale scenarios:

1.  👉 **[Kubernetes Engineering Depth Reference](./docs/ENGINEERING-DEPTH.md)**
    *OOM analysis, 5k-node scaling, packet walks, internals, CNI selection, stateful systems.*
2.  **[On-Prem / Bare Metal](./docs/on-prem-kubernetes.md)**
    *Etcd management, BGP load balancing, storage without cloud.*
3.  **[Network Controller Deep Dive](./docs/network-controllers-troubleshooting.md)**
    *CNI comparison (Cilium vs Calico), IPAM exhaustion, Ingress internals.*
4.  **[Security Control Framework](./docs/security-control-framework.md)**
    *OPA/Kyverno debugging, identity (IRSA/OIDC), runtime security (Falco).*

---

## 🚀 Quick Start (Emergency Response)
**Cluster on fire? Run these checks immediately.**

1.  **Validate Connectivity:**
    ```bash
    kubectl cluster-info
    ```
2.  **Run Diagnostics Scripts:**
    *   🚑 **Cluster Health:** `./scripts/diagnostics/cluster-health-check.sh`
    *   📦 **Pod Issues:** `./scripts/diagnostics/pod-diagnostics.sh`
    *   🌐 **Network/DNS:** `./scripts/diagnostics/network-diagnostics.sh`
    *   💾 **Storage:** `./scripts/diagnostics/storage-analysis.sh`
    *   📉 **Resources:** `./scripts/diagnostics/resource-analysis.sh`
3.  **Apply Fixes (Use Caution):**
    *   `./scripts/fixes/fix-dns-issues.sh`
    *   `./scripts/fixes/auto-restart-failed-pods.sh`

---

## 🗺️ Repository Map
The repository is organized by function and role:

```text
.
├── docs/                            # Documentation Hub
│   ├── ENGINEERING-DEPTH.md         # <--- START HERE: Engineering Depth Reference
│   ├── on-prem-kubernetes.md        # Bare Metal / DIY K8s Guide
│   ├── network-controllers-...md    # CNI (Calico/Cilium) & Ingress Debugging
│   ├── security-control-...md       # SCF, OPA/Kyverno & Runtime Security
│   ├── architects/                  # Architecture & Design Patterns
│   ├── engineers/                   # Development & Debugging
│   ├── devops/                      # CI/CD & Infrastructure Automation
│   └── sre/                         # Site Reliability Engineering (Observability)
├── scripts/
│   ├── diagnostics/                 # Read-only health checks (Safe to run)
│   ├── fixes/                       # Auto-remediation tools (Changes state)
│   └── monitoring/                  # Prometheus/Grafana bootstrap
├── playbooks/                       # P0/P1 Incident Runbooks
└── k8s/                             # Manifests & Example Apps
```

---

## 🛠️ Deep Dive Guides

### 1. On-Prem / Bare Metal
Running K8s without AWS/Azure? "You are the Cloud Provider."
*   [**Read the On-Prem Guide**](./docs/on-prem-kubernetes.md)
*   **Key Topics:** MetalLB (BGP vs L2), Rook/Ceph Storage, Etcd Defrag/Backup, VIP Management.
*   **Engineering Focus:** "How do you restore a failed etcd member?"

### 2. Network Controllers (CNI) & Ingress
When `Ping` fails, check the Controller.
*   [**Read the Networking Guide**](./docs/network-controllers-troubleshooting.md)
*   **Key Topics:** AWS VPC CNI (IPAM), Calico (BGP), Cilium (eBPF), Nginx Ingress loops, Service Mesh.
*   **Engineering Focus:** "Debug a 504 Gateway Timeout vs a 502 Bad Gateway."

### 3. Security Control Framework (SCF)
Compliance meets Engineering (NIST/CIS).
*   [**Read the Security Guide**](./docs/security-control-framework.md)
*   **Key Topics:** Debugging "Deny All" Policies, OPA Gatekeeper Break-Glass, Node Security, Supply Chain.
*   **Engineering Focus:** "How do you debug a 'Permission Denied' even when RBAC is correct?"

---

## 🤖 Automation & Scripts
Stop manual debugging. Use the CLI tools in `scripts/`:
*   **Diagnostics:** `cluster-health`, `pod-diagnostics`, `network-diagnostics`.
*   **Remediation:** `auto-restart-failed-pods`, `fix-dns-issues`.
*   **Observability:** `setup-prometheus`, `configure-alerts`.

For programmatic access and library usage, see the **[Programmatic Guide](./PROGRAMMATIC-GUIDE.md)**.

---

## 👥 Role-Based Operating Models
We provide specific "Models" for each role in your organization to ensure comprehensive coverage:

*   **[Architects Model](./docs/architects/README.md)**: Focus on Tenancy, Network Topology, Security Architecture, and DR.
*   **[Engineers Model](./docs/engineers/README.md)**: Focus on Pod Startup, Container Images, Config/Secrets, and Local Dev.
*   **[DevOps Model](./docs/devops/README.md)**: Focus on CI/CD Failures, GitOps Workflows, and Rolling Updates.
*   **[SRE Model](./docs/sre/README.md)**: Focus on Observability, SLIs/SLOs, Alerting, and Incident Response.
*   **[Technical Writers Model](./docs/copywriters/README.md)**: Focus on Documentation Standards, Templates, and Clarity.

---

*Version: 1.1.0*
*Maintainers: Platform Engineering*
*Last Updated: December 2025*
