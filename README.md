# Kubernetes/AKS/EKS Troubleshooting Guide  
**Zero-to-Hero with Automation for Architects, Engineers, DevOps, SREs, and Technical Writers.**

This repository is a comprehensive toolkit and study guide for mastering Kubernetes operations, debugging, and architecture. It is designed to help you pass **FAANG/MANGA** interviews and survive P0 incidents in production.

---

## 📖 Table of Contents
- [Prerequisites & Setup](#-prerequisites--setup)
- [How to Use This Guide](#how-to-use-this-guide)
- [🎓 **FAANG Interview Prep (Start Here)**](#-faang-interview-prep-start-here)
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

### 1. Install the Gemini CLI
This project leverages the Gemini CLI for AI-assisted debugging and analysis.
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
- **In an incident**: Run the [Emergency Checklist](#-quick-start-emergency-response) below, then dive into the `playbooks/` folder.
- **For prevention**: Follow the [Operating Models](#-role-based-operating-models) and automation sections to bake guardrails into CI/CD.
- **For growth**: Walk the docs in order—start with Quick Start, then team guides, then automation.

---

## 🎓 FAANG Interview Prep (Start Here)
**Targeting a Senior SRE/Platform role?**
This repository is your study guide for "System Design" and "Deep Troubleshooting" rounds.

1.  👉 **[The Master Interview Guide](./docs/INTERVIEW-PREP.md)**  
    *Covers: Deep Debugging (OOM, CrashLoop), Scaling to 5k nodes, Packet Walks, and Internals.*
2.  **[On-Prem / Bare Metal Questions](./docs/on-prem-kubernetes.md)**  
    *Covers: Etcd management, BGP LoadBalancing, Storage without Cloud.*
3.  **[Network Controller Deep Dive](./docs/network-controllers-troubleshooting.md)**  
    *Covers: CNI wars (Cilium vs Calico), IPAM exhaustion, Ingress internals.*
4.  **[Security Framework Scenarios](./docs/security-control-framework.md)**  
    *Covers: OPA/Kyverno debugging, Identity (IRSA/OIDC), Runtime Security (Falco).*

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
│   ├── INTERVIEW-PREP.md            # <--- START HERE
│   ├── on-prem-kubernetes.md        # Bare Metal / DIY K8s
│   ├── network-controllers-...md    # CNI & Ingress Troubleshooting
│   ├── security-control-...md       # Policy & Identity Debugging
│   ├── architects/                  # Design patterns (DR, Multi-tenancy)
│   ├── engineers/                   # App debugging & performance
│   ├── devops/                      # CI/CD & GitOps
│   └── sre/                         # Observability & Incident Response
├── scripts/
│   ├── diagnostics/                 # Read-only health checks
│   ├── fixes/                       # Auto-remediation tools
│   └── monitoring/                  # Prometheus/Grafana setup
├── playbooks/                       # P0/P1 Incident Runbooks
└── k8s/                             # Manifests & Example Apps
```

---

## 🛠️ Deep Dive Guides

### On-Prem / Bare Metal
Running K8s without AWS/Azure?
*   [**Read the Guide**](./docs/on-prem-kubernetes.md)
*   **Key Topics:** MetalLB (BGP vs L2), Rook/Ceph Storage, Etcd Defrag/Backup, VIP Management.

### Network Controllers (CNI)
When `Ping` fails, check the Controller.
*   [**Read the Guide**](./docs/network-controllers-troubleshooting.md)
*   **Key Topics:** AWS VPC CNI (IPAM), Calico (BGP), Cilium (eBPF), Nginx Ingress loops.

### Security Control Framework (SCF)
Compliance meets Engineering.
*   [**Read the Guide**](./docs/security-control-framework.md)
*   **Key Topics:** Debugging "Deny All" Policies, OPA Gatekeeper Break-Glass, Node Security.

---

## 🤖 Automation & Scripts
Stop manual debugging. Use the CLI tools in `scripts/`:
*   **Diagnostics:** pods, network/DNS, resources, storage, deployments, Helm, GitOps.
*   **Remediation:** restart failed pods, cleanup evicted, fix DNS, scale workloads.
*   **Observability:** bootstrap Prometheus/Grafana, alerts, log aggregation.

For programmatic access, see the **[Programmatic Guide](./PROGRAMMATIC-GUIDE.md)**.

---

## 👥 Role-Based Operating Models
We provide specific "Models" for each role in your organization to ensure comprehensive coverage:

*   **[Architects Model](./docs/architects/README.md)**: Focus on Tenancy, Network Topology, Security Architecture, and DR.
*   **[Engineers Model](./docs/engineers/README.md)**: Focus on Pod Startup, Container Images, Config/Secrets, and Local Dev.
*   **[DevOps Model](./docs/devops/README.md)**: Focus on CI/CD Failures, GitOps Workflows, and Rolling Updates.
*   **[SRE Model](./docs/sre/README.md)**: Focus on Observability, SLIs/SLOs, Alerting, and Incident Response.

---

*Version: 1.1.0*  
*Maintainers: FAANG Board*  
*Last Updated: December 2025*
