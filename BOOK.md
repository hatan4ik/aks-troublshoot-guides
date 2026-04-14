# Kubernetes Troubleshooting Field Guide

This is the book spine for the repository. Use it when reading the material end to end, teaching it as a course, or preparing it for publication.

The repo still works as a reference library. This file defines the narrative order so the material reads like a book instead of a pile of independent runbooks.

## Reading Locally

For clickable local navigation, use a Markdown preview:

- VS Code or Cursor: open `BOOK.md`, then open Markdown Preview. In the raw editor, use Command-click on links.
- JetBrains IDEs: use the Markdown preview pane.
- Browser opened directly on a raw `.md` file: not recommended, because it is not a full documentation renderer.

The links are intentionally relative so they work on GitHub, in forks, and on other machines. Do not replace them with absolute `file://` links.

## Audience

- Platform engineers who operate Kubernetes across AKS, EKS, GKE, and bare metal.
- SREs who need a repeatable production incident workflow.
- DevOps engineers who own CI/CD, GitOps, cluster bootstrap, and release safety.
- Software engineers who need to debug their own workloads inside Kubernetes.
- Interview candidates preparing for practical Kubernetes troubleshooting exercises.

## Reader Promise

By the end, readers should be able to:

- Diagnose a failing workload without jumping randomly between layers.
- Separate application failures from Kubernetes control-plane, networking, storage, and cloud-provider failures.
- Explain failures using events, pod state, service endpoints, node conditions, and provider signals.
- Apply safe remediations with clear verification steps.
- Operate GitOps, ingress, storage, multi-tenant, and advanced workload patterns with production discipline.

## Part I: The Debugging Mindset

### Chapter 1: How Kubernetes Fails

Core reading:

- [Live Debugging Workflow](./docs/LIVE-DEBUG-WORKFLOW.md)
- [Live Debug Runbook](./DEBUG-RUNBOOK.md)
- [Common Kubernetes Issues](./playbooks/common-issues.md)

Editorial goal:

Teach the layered model first: pod lifecycle, runtime, service routing, cluster networking, storage, node health, then provider infrastructure.

### Chapter 2: Hands-On Failure Lab

Core reading:

- [Practice Labs](./practice/README.md)
- [Practice Lab Solutions](./practice/SOLUTIONS.md)
- [Course Foundations](./course/01-foundations.md)

Editorial goal:

Make readers diagnose before reading the answer. Each lab should include symptom, investigation path, fix, and verification.

## Part II: Core Kubernetes Failure Domains

### Chapter 3: Pod Lifecycle and Runtime Failures

Core reading:

- [Pod Startup Issues](./docs/engineers/pod-startup-issues.md)
- [Advanced Debugging Techniques](./docs/engineers/debugging-techniques.md)
- [Container Images](./docs/engineers/container-images.md)

Editorial goal:

Make `kubectl describe pod`, events, exit codes, logs, probes, and resource limits feel like one coherent workflow.

### Chapter 4: Service, Ingress, DNS, and CNI

Core reading:

- [Network Controller Troubleshooting](./docs/network-controllers-troubleshooting.md)
- [Service Networking Course Module](./course/03-service-networking.md)
- [DNS Failures Playbook](./playbooks/p1-dns-failures.md)
- [Cloud FQDN Service Access](./docs/cloud-fqdn-service-access.md)

Editorial goal:

Teach the traffic chain: client, DNS, load balancer or gateway, ingress, service selector, endpoints, pod readiness, and application port.

### Chapter 5: Scheduling, Node Health, and Resource Pressure

Core reading:

- [Scheduling and Storage Course Module](./course/04-scheduling-storage.md)
- [Node Pools](./docs/architects/node-pools.md)
- [Node Management](./docs/devops/node-management.md)
- [FinOps and Resource Optimization](./docs/finops-resource-optimization.md)

Editorial goal:

Connect scheduler events to real causes: requests, taints, affinity, quota, pod disruption budgets, IP exhaustion, and autoscaler limits.

### Chapter 6: Storage and Stateful Systems

Core reading:

- [Storage and Stateful Workload Incident Playbook](./docs/storage-stateful-incident-playbook.md)
- [Storage Architecture](./docs/architects/storage-architecture.md)
- [Stateful Workloads](./docs/engineers/stateful-workloads.md)
- [Storage Configuration](./docs/devops/storage-configuration.md)

Editorial goal:

Make storage chapters conservative and safety-first. Readers should understand PVC binding, VolumeAttachment, reclaim policy, disk topology, and quorum before changing state.

### Chapter 7: Security, Identity, and Policy

Core reading:

- [Security Control Framework](./docs/security-control-framework.md)
- [Security Architecture](./docs/architects/security-architecture.md)
- [Secrets and ConfigMaps](./docs/engineers/secrets-configmaps.md)

Editorial goal:

Show why access failures are often layered: RBAC, admission policy, cloud identity, filesystem permissions, image policy, and runtime controls.

## Part III: Provider Overlays

### Chapter 8: AKS

Core reading:

- [AKS Debugging Framework](./docs/AKS-DEBUGGING-FRAMEWORK.md)
- [AKS Networking](./docs/azure/aks-networking.md)
- [Azure Observability](./docs/azure/azure-observability.md)
- [AKS Course Module](./course/05-aks-platform.md)

Editorial goal:

Cover Azure CNI, Azure Load Balancer, NSGs, UDRs, ACR, Azure Disk, Azure Monitor, private DNS, and managed identity.

### Chapter 9: EKS

Core reading:

- [EKS Debugging Framework](./docs/EKS-DEBUGGING-FRAMEWORK.md)
- [EKS Networking](./docs/aws/eks-networking.md)
- [AWS Observability](./docs/aws/aws-observability.md)
- [EKS Course Module](./course/05-eks-platform.md)

Editorial goal:

Cover AWS VPC CNI, prefix delegation, security groups, NLB/ALB, ECR, CloudWatch, IRSA, EBS, and NAT Gateway dependencies.

### Chapter 10: GKE

Core reading:

- [GKE Debugging Framework](./docs/GKE-DEBUGGING-FRAMEWORK.md)
- [GKE Networking](./docs/gcp/gke-networking.md)
- [GCP Observability](./docs/gcp/gcp-observability.md)
- [GKE Course Module](./course/05-gke-platform.md)

Editorial goal:

Cover VPC-native clusters, Cloud Load Balancing, firewall rules, NEGs, Artifact Registry, Cloud NAT, Cloud Monitoring, and Workload Identity.

### Chapter 11: Bare Metal and On-Prem

Core reading:

- [Bare Metal Debugging Framework](./docs/BAREMETAL-DEBUGGING-FRAMEWORK.md)
- [On-Prem Kubernetes](./docs/on-prem-kubernetes.md)
- [Bare Metal Networking](./docs/baremetal/baremetal-networking.md)
- [Bare Metal Observability](./docs/baremetal/baremetal-observability.md)
- [Bare Metal Course Module](./course/05-baremetal-platform.md)

Editorial goal:

Make the reader own the missing cloud-provider layer: VIPs, MetalLB, BGP, storage backends, physical networking, time sync, and control-plane endpoints.

## Part IV: Advanced Operations

### Chapter 12: GitOps and SDLC Pipelines

Core reading:

- [GitOps Workflows](./docs/devops/gitops.md)
- [SDLC Pipeline Troubleshooting](./docs/devops/sdlc-pipeline-troubleshooting.md)
- [GitOps Minikube Install](./docs/GITOPS-MINIKUBE-INSTALL.md)
- [GitOps Demo](./gitops-demo/README.md)

Editorial goal:

Teach source, build, registry, render, validation, policy, GitOps sync, and rollout as separate debugging layers.

### Chapter 13: Multi-Application Isolation

Core reading:

- [Multi-Application Isolation Blueprint](./docs/multi-application-isolation-blueprint.md)
- [Multi-Tenancy](./docs/architects/multi-tenancy.md)
- [Isolation Manifests](./k8s/multi-app-isolation/README.md)

Editorial goal:

Explain how many applications share a cluster safely: namespace boundaries, NetworkPolicy, RBAC, quotas, ingress routing, DNS, and GitOps ownership.

### Chapter 14: AI/GPU Workloads

Core reading:

- [AI/GPU Workload Troubleshooting](./docs/ai-gpu-workload-troubleshooting.md)
- [Node Pools](./docs/architects/node-pools.md)
- [Performance Profiling](./docs/engineers/performance-profiling.md)

Editorial goal:

Separate Kubernetes memory OOM from GPU VRAM OOM, and show where device plugin, driver, CUDA, node pool, model artifact, and quota failures appear.

### Chapter 15: Observability and Reliability

Core reading:

- [Observability at Scale](./docs/sre/observability-at-scale.md)
- [Emergency Response](./docs/emergency-response.md)
- [Cluster Outage Playbook](./playbooks/p0-cluster-outage.md)
- [Post-Mortem Template](./templates/post-mortem-template.md)

Editorial goal:

Make observability practical: what signal answers which question, what to collect during incidents, and how to convert findings into durable guardrails.

## Part V: Automation Toolkit

### Chapter 16: Diagnostics CLI and Scripts

Core reading:

- [Programmatic Guide](./PROGRAMMATIC-GUIDE.md)
- [Issue Index](./ISSUE-INDEX.md)
- [Tests README](./tests/README.md)

Primary tools:

- `python3 ./k8s-diagnostics-cli.py detect`
- `python3 ./k8s-diagnostics-cli.py suggest`
- `python3 ./k8s-diagnostics-cli.py fix --dry-run`
- `./scripts/diagnostics/cluster-health-check.sh`
- `./scripts/diagnostics/pod-diagnostics.sh`
- `./scripts/diagnostics/network-diagnostics.sh`
- `./scripts/diagnostics/storage-analysis.sh`
- `./scripts/diagnostics/gitops-diagnostics.sh`

Editorial goal:

Show how automation supports investigation. It should not hide the commands or make unsafe cluster changes without dry-run, scope, and verification.

## Appendices

- [Architects Model](./docs/architects/README.md)
- [Engineers Model](./docs/engineers/README.md)
- [DevOps Model](./docs/devops/README.md)
- [SRE Model](./docs/sre/README.md)
- [Technical Writing Guide](./docs/copywriters/README.md)
- [Command Conventions](./docs/COMMAND-CONVENTIONS.md)
- [Glossary](./docs/GLOSSARY.md)
- [Troubleshooting Template](./templates/troubleshooting-template.md)
- [Runbook Template](./templates/runbook-template.md)

## Chapter Pattern

Every chapter should converge toward this shape:

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

The exact headings can vary, but the reader should always know:

- What symptom this chapter solves.
- Which layer is being tested.
- Which commands are safe to run.
- Which remediation changes state.
- How to verify the fix.
- When to escalate to a provider, platform, or application owner.

## Editorial Backlog

Highest-value future edits:

- Split [DEBUG-RUNBOOK.md](./DEBUG-RUNBOOK.md) into a short incident card plus deeper failure-domain chapters.
- Split [GitOps Demo](./gitops-demo/README.md) into install, Argo CD app, Flux CD app, friendly URLs, and cleanup chapters.
- Balance provider depth so AKS, EKS, and GKE chapters follow the same table of contents.
- Apply the chapter pattern consistently to older role-based guides.
- Add lightweight diagrams where a traffic path, controller loop, or storage attachment path is hard to follow from text alone.
