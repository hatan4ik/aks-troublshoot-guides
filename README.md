# Kubernetes/AKS/EKS Troubleshooting Guide

**Hands-on debugging guides, incident playbooks, engineering reference, and provider overlays for Kubernetes operators and engineers.**

This repository is a practical toolkit for Kubernetes operations, debugging, and architecture. It is designed for real incident response, production troubleshooting, structured investigation in live clusters, and provider-specific overlays for AKS, EKS, GKE, and bare metal.

---

## 📖 Table of Contents
- [Prerequisites & Setup](#-prerequisites--setup)
- [How to Use This Guide](#how-to-use-this-guide)
- [🏫 Course Track](#-course-track)
- [☁️ Provider Overlays](#-provider-overlays)
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
*   `docker` and `minikube` (for local lab clusters)

---

## How to Use This Guide

- **For a course or workshop**: Start with [course/README.md](./course/README.md) for the syllabus, module order, and instructor notes.
- **For live cluster debugging**: Open [DEBUG-RUNBOOK.md](./DEBUG-RUNBOOK.md) — symptom ToC and fix commands in one file.
- **For broken local labs**: Use [docs/LOCAL-CLUSTER-DEBUGGING.md](./docs/LOCAL-CLUSTER-DEBUGGING.md) before treating a Minikube or Docker failure like an application issue.
- **In an incident**: Run the [Emergency Checklist](#-quick-start-emergency-response) below, then dive into the `playbooks/` folder.
- **For prevention**: Follow the [Operating Models](#-role-based-operating-models) and automation sections to bake guardrails into CI/CD.
- **For growth**: Walk the docs in order—start with Quick Start, then team guides, then automation.

---

## 🏫 Course Track

Use this path when the repo is being taught as a structured Kubernetes course with provider-specific overlays rather than used as a reference library:

1. 👉 **[Kubernetes Provider Course Track](./course/README.md)**  
   *Audience, course sequence, delivery options, and lab backbone.*
2. **[Course Syllabus](./course/00-syllabus.md)**  
   *Learning outcomes, prerequisites, module map, and assessments.*
3. **[Hands-On Practice](./practice/README.md)**  
   *Broken-manifest labs used throughout the course.*
4. **[Instructor Guide](./course/INSTRUCTOR-GUIDE.md)**  
   *Pacing, lab mapping, and facilitation notes.*

---

## ☁️ Provider Overlays

Use the shared Kubernetes debugging core first, then branch into the provider overlay that matches the environment:

- **AKS**
  [AKS Debugging Framework](./docs/AKS-DEBUGGING-FRAMEWORK.md),
  [AKS Networking](./docs/azure/aks-networking.md),
  [Azure Observability](./docs/azure/azure-observability.md)
- **EKS**
  [EKS Debugging Framework](./docs/EKS-DEBUGGING-FRAMEWORK.md),
  [EKS Networking](./docs/aws/eks-networking.md),
  [AWS Observability](./docs/aws/aws-observability.md)
- **GKE**
  [GKE Debugging Framework](./docs/GKE-DEBUGGING-FRAMEWORK.md),
  [GKE Networking](./docs/gcp/gke-networking.md),
  [GCP Observability](./docs/gcp/gcp-observability.md)
- **Bare Metal / On-Prem**
  [Bare Metal Debugging Framework](./docs/BAREMETAL-DEBUGGING-FRAMEWORK.md),
  [Bare Metal Networking](./docs/baremetal/baremetal-networking.md),
  [Bare Metal Observability](./docs/baremetal/baremetal-observability.md),
  [On-Prem Kubernetes](./docs/on-prem-kubernetes.md)

---

## 🧪 Live Cluster Debugging (Start Here)

Given a running cluster with a failing application, use this repo in this order:

1. 👉 **[Live Debug Runbook](./DEBUG-RUNBOOK.md)** — symptom ToC, copy-paste commands, single file
2. **[Live Debugging Workflow](./docs/LIVE-DEBUG-WORKFLOW.md)** — investigation strategy and safe change process
3. **[Common Kubernetes Issues Playbook](./playbooks/common-issues.md)** — symptom-to-cause reference
4. **[Pod Startup Issues](./docs/engineers/pod-startup-issues.md)** — scheduling, init containers, misconfigurations
5. **[Advanced Debugging Techniques](./docs/engineers/debugging-techniques.md)** — exit codes, probes, runtime troubleshooting

If the environment itself is broken before workloads can even run, switch to [Local Cluster Debugging](./docs/LOCAL-CLUSTER-DEBUGGING.md).

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
3.  **Preview Fixes Before Mutating:**
    *   `python3 ./k8s-diagnostics-cli.py suggest`
    *   `python3 ./k8s-diagnostics-cli.py fix --dry-run`
    *   Use scripts in `scripts/fixes/` only after the root cause and blast radius are clear.

---

## 🗺️ Repository Map
The repository is organized by function and role:

```text
.
├── DEBUG-RUNBOOK.md                 # <--- ACTIVE DEBUGGING: Symptom ToC + fix commands
├── course/                          # Course track: shared core + provider overlays
├── docs/
│   ├── AKS-DEBUGGING-FRAMEWORK.md   # AKS provider overlay
│   ├── EKS-DEBUGGING-FRAMEWORK.md   # EKS provider overlay
│   ├── GKE-DEBUGGING-FRAMEWORK.md   # GKE provider overlay
│   ├── BAREMETAL-DEBUGGING-FRAMEWORK.md # Bare metal provider overlay
│   ├── LIVE-DEBUG-WORKFLOW.md       # Investigation workflow + safe change strategy
│   ├── LOCAL-CLUSTER-DEBUGGING.md   # Docker Desktop + Minikube recovery workflow
│   ├── ENGINEERING-DEPTH.md         # Staff-level systems thinking + production scenarios
│   ├── aws/
│   │   ├── eks-networking.md        # VPC CNI, NLB/ALB, SGs, NACLs, NAT, ECR
│   │   └── aws-observability.md     # CloudWatch, target health, VPC Flow Logs, CloudTrail
│   ├── gcp/
│   │   ├── gke-networking.md        # VPC-native, firewall, NEG, Cloud NAT, Artifact Registry
│   │   └── gcp-observability.md     # Cloud Logging, Monitoring, Flow Logs, Audit Logs
│   ├── baremetal/
│   │   ├── baremetal-networking.md  # MetalLB, VIPs, BGP, MTU, routing
│   │   └── baremetal-observability.md # Prometheus, Loki, journald, switch and host signals
│   ├── azure/
│   │   ├── aks-networking.md        # NSG, Azure CNI, Load Balancer, UDR, Private clusters
│   │   └── azure-observability.md   # Container Insights, Log Analytics KQL, Azure Monitor
│   ├── on-prem-kubernetes.md        # Bare Metal / DIY K8s Guide
│   ├── network-controllers-...md    # CNI (Calico/Cilium) & Ingress Debugging
│   ├── security-control-...md       # SCF, OPA/Kyverno & Runtime Security
│   ├── architects/                  # Architecture & Design Patterns
│   ├── engineers/                   # Development & Debugging
│   ├── devops/                      # CI/CD & Infrastructure Automation
│   └── sre/                         # Site Reliability Engineering (Observability)
├── practice/                        # 19 broken manifests for hands-on debugging
├── scripts/
│   ├── diagnostics/                 # Read-only health checks (Safe to run)
│   ├── fixes/                       # Auto-remediation tools (Changes state)
│   ├── local/                       # Local Docker Desktop + Minikube checks and recovery
│   └── monitoring/                  # Prometheus/Grafana bootstrap
├── playbooks/                       # P0/P1 Incident Runbooks
└── k8s/                             # Manifests & Example Apps
```

---

## 🛠️ Deep Dive Guides

### 0. Provider-Specific Layers

Use the shared Kubernetes debugging core first, then branch into the provider overlay that matches the environment.

- [**AKS**](./docs/AKS-DEBUGGING-FRAMEWORK.md) — Azure CNI, NSG, Azure Load Balancer, ACR, Azure Monitor.
- [**EKS**](./docs/EKS-DEBUGGING-FRAMEWORK.md) — VPC CNI, security groups, NLB/ALB, ECR, CloudWatch.
- [**GKE**](./docs/GKE-DEBUGGING-FRAMEWORK.md) — VPC-native networking, firewall rules, backend services, Artifact Registry, Cloud Monitoring.
- [**Bare Metal**](./docs/BAREMETAL-DEBUGGING-FRAMEWORK.md) — MetalLB, BGP, VIPs, MTU, storage backends, physical infrastructure.

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
*   **Local Lab Recovery:** `minikube-doctor`, `restart-minikube`.
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
*Last Updated: April 2026*
