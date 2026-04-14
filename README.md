# Kubernetes Troubleshooting Field Guide

Hands-on Kubernetes debugging guides, incident runbooks, provider overlays, labs, and automation for platform engineers, SREs, DevOps engineers, and application engineers.

This repository can be used in three ways:

- As a live incident reference for diagnosing broken workloads.
- As a structured course with labs and provider overlays.
- As a book-style manuscript through [BOOK.md](./BOOK.md).

## Start Here

| Situation | Start with |
|---|---|
| You are in a live incident | [DEBUG-RUNBOOK.md](./DEBUG-RUNBOOK.md) |
| You need a safe investigation workflow | [Live Debugging Workflow](./docs/LIVE-DEBUG-WORKFLOW.md) |
| Minikube or Docker is broken | [Local Cluster Debugging](./docs/LOCAL-CLUSTER-DEBUGGING.md) |
| You want a course path | [Course Track](./course/README.md) |
| You want the book order | [BOOK.md](./BOOK.md) |
| You want hands-on failures | [Practice Labs](./practice/README.md) |
| You want automation | [Programmatic Guide](./PROGRAMMATIC-GUIDE.md) |
| You need term definitions | [Glossary](./docs/GLOSSARY.md) |
| You need command safety rules | [Command Conventions](./docs/COMMAND-CONVENTIONS.md) |

## Reading Locally

For clickable local navigation, open this repo in a Markdown-aware viewer:

- In VS Code or Cursor, open `README.md` or `BOOK.md`, then use Markdown Preview. In the raw editor, use Command-click on links.
- In JetBrains IDEs, use the Markdown preview pane.
- Do not open the raw `.md` file directly in Chrome or Safari and expect Markdown links to behave like rendered documentation.

The repo validation checks local Markdown file links and anchors:

```bash
python3 scripts/validate-links.py
make validate
```

## Quick Incident Workflow

Run the least invasive checks first:

```bash
kubectl config current-context
kubectl cluster-info
kubectl get ns
kubectl get pods -A
kubectl get events -A --sort-by=.metadata.creationTimestamp | tail -50
```

Then use the repo diagnostics:

```bash
./scripts/diagnostics/cluster-health-check.sh
./scripts/diagnostics/pod-diagnostics.sh
./scripts/diagnostics/network-diagnostics.sh
./scripts/diagnostics/storage-analysis.sh
./scripts/diagnostics/gitops-diagnostics.sh
```

Preview remediations before mutating cluster state:

```bash
python3 ./k8s-diagnostics-cli.py suggest
python3 ./k8s-diagnostics-cli.py fix --dry-run
```

## Book Spine

Use [BOOK.md](./BOOK.md) when reading the repo like a book. It organizes the material into:

- Part I: The debugging mindset.
- Part II: Core Kubernetes failure domains.
- Part III: AKS, EKS, GKE, and bare-metal provider overlays.
- Part IV: Advanced operations such as GitOps, multi-application isolation, AI/GPU workloads, and observability.
- Part V: Automation toolkit and test strategy.

## Core Failure Domains

| Domain | Guide |
|---|---|
| Pod lifecycle and startup failures | [Pod Startup Issues](./docs/engineers/pod-startup-issues.md) |
| Runtime debugging and profiling | [Advanced Debugging Techniques](./docs/engineers/debugging-techniques.md) |
| Services, DNS, ingress, and CNI | [Network Controller Troubleshooting](./docs/network-controllers-troubleshooting.md) |
| Production URLs and DNS | [Cloud FQDN Service Access](./docs/cloud-fqdn-service-access.md) |
| Storage and stateful systems | [Storage and Stateful Workload Incident Playbook](./docs/storage-stateful-incident-playbook.md) |
| Security, identity, and policy | [Security Control Framework](./docs/security-control-framework.md) |
| Multi-application isolation | [Multi-Application Isolation Blueprint](./docs/multi-application-isolation-blueprint.md) |
| AI and GPU workloads | [AI/GPU Workload Troubleshooting](./docs/ai-gpu-workload-troubleshooting.md) |
| FinOps and resource optimization | [FinOps and Resource Optimization](./docs/finops-resource-optimization.md) |
| CI/CD, GitOps, Helm, and CRDs | [SDLC Pipeline Troubleshooting](./docs/devops/sdlc-pipeline-troubleshooting.md) |

## Provider Overlays

Use the shared debugging workflow first, then branch into the provider-specific layer:

| Platform | Framework | Networking | Observability |
|---|---|---|---|
| AKS | [AKS Debugging Framework](./docs/AKS-DEBUGGING-FRAMEWORK.md) | [AKS Networking](./docs/azure/aks-networking.md) | [Azure Observability](./docs/azure/azure-observability.md) |
| EKS | [EKS Debugging Framework](./docs/EKS-DEBUGGING-FRAMEWORK.md) | [EKS Networking](./docs/aws/eks-networking.md) | [AWS Observability](./docs/aws/aws-observability.md) |
| GKE | [GKE Debugging Framework](./docs/GKE-DEBUGGING-FRAMEWORK.md) | [GKE Networking](./docs/gcp/gke-networking.md) | [GCP Observability](./docs/gcp/gcp-observability.md) |
| Bare metal | [Bare Metal Debugging Framework](./docs/BAREMETAL-DEBUGGING-FRAMEWORK.md) | [Bare Metal Networking](./docs/baremetal/baremetal-networking.md) | [Bare Metal Observability](./docs/baremetal/baremetal-observability.md) |

## Role-Based Paths

| Role | Start here |
|---|---|
| Architect | [Architects Model](./docs/architects/README.md) |
| Software engineer | [Engineers Model](./docs/engineers/README.md) |
| DevOps engineer | [DevOps Model](./docs/devops/README.md) |
| SRE | [SRE Model](./docs/sre/README.md) |
| Technical writer or editor | [Technical Writing Guide](./docs/copywriters/README.md) |

## Course and Labs

Use the course path when teaching or self-studying:

- [Course Track](./course/README.md)
- [Syllabus](./course/00-syllabus.md)
- [Instructor Guide](./course/INSTRUCTOR-GUIDE.md)
- [Practice Labs](./practice/README.md)
- [Practice Solutions](./practice/SOLUTIONS.md)

The practice labs cover image pull failures, selector mismatches, bad probes, missing ConfigMaps and Secrets, scheduling failures, NetworkPolicy issues, ingress mistakes, PVC errors, OOMKilled pods, init container failures, StatefulSet headless service issues, and Job backoff failures.

## GitOps and Local Demo

For Argo CD and Flux CD labs:

- [GitOps Minikube Install](./docs/GITOPS-MINIKUBE-INSTALL.md)
- [GitOps Demo](./gitops-demo/README.md)
- [GitOps Workflows](./docs/devops/gitops.md)
- [SDLC Pipeline Troubleshooting](./docs/devops/sdlc-pipeline-troubleshooting.md)

Use one GitOps controller per application path unless you are intentionally testing controller conflict.

## Repository Map

```text
.
├── BOOK.md                         # Book-style table of contents and editorial spine
├── DEBUG-RUNBOOK.md                # Live incident runbook
├── course/                         # Structured teaching path
├── docs/                           # Deep dives, provider overlays, role-based guides
├── gitops-demo/                    # Argo CD and Flux CD demo apps and CRs
├── k8s/                            # Example manifests and isolation blueprints
├── playbooks/                      # P0/P1 incident playbooks and common issues
├── practice/                       # Broken manifests and solutions
├── scripts/diagnostics/            # Read-only diagnostics
├── scripts/fixes/                  # State-changing remediation helpers
├── src/k8s_diagnostics/            # Python diagnostics package
├── templates/                      # Runbook and documentation templates
└── tests/                          # Offline tests for diagnostics and remediation logic
```

## Documentation Standard

New chapters should follow the editorial pattern in [BOOK.md](./BOOK.md):

```markdown
# Chapter Title
## When to Use This
## Mental Model
## Fast Triage
## Failure Matrix
## Fix Safely
## Verify
## Provider Notes
## Interview Signals
## Related Reading
```

Style guidance lives in [docs/copywriters/README.md](./docs/copywriters/README.md).
Command safety rules live in [docs/COMMAND-CONVENTIONS.md](./docs/COMMAND-CONVENTIONS.md), and shared terminology lives in [docs/GLOSSARY.md](./docs/GLOSSARY.md).

## Version

- Version: 1.1.0
- Maintainers: Platform Engineering
- Last updated: April 2026
