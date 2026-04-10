# AKS Course Track

This folder turns the repository into a teachable AKS course without changing the underlying reference layout.

Use it in one of two ways:

- Instructor-led bootcamp: follow the module order, run the labs in `practice/`, and use the instructor guide for pacing.
- Self-paced track: work module-by-module, complete the labs, then attempt the capstone without looking at `practice/SOLUTIONS.md`.

## Audience

- Platform engineers
- SREs
- DevOps engineers
- Software engineers who operate workloads on AKS

## What Students Should Leave With

- A repeatable debugging workflow for AKS and Kubernetes
- Confidence reading events, pod state, services, ingress, DNS, and node health
- Clear separation between Kubernetes failures and Azure infrastructure failures
- Practical experience fixing broken manifests and validating recovery

## Course Sequence

1. [00-syllabus.md](./00-syllabus.md)
2. [01-foundations.md](./01-foundations.md)
3. [02-pod-lifecycle.md](./02-pod-lifecycle.md)
4. [03-service-networking.md](./03-service-networking.md)
5. [04-scheduling-storage.md](./04-scheduling-storage.md)
6. [05-aks-platform.md](./05-aks-platform.md)
7. [06-capstone.md](./06-capstone.md)
8. [INSTRUCTOR-GUIDE.md](./INSTRUCTOR-GUIDE.md)

## Core Repo References

- [AKS Debugging Framework](../docs/AKS-DEBUGGING-FRAMEWORK.md)
- [Live Debug Runbook](../DEBUG-RUNBOOK.md)
- [Live Debugging Workflow](../docs/LIVE-DEBUG-WORKFLOW.md)
- [Engineering Depth](../docs/ENGINEERING-DEPTH.md)
- [Hands-On Practice](../practice/README.md)
- [Common Issues Playbook](../playbooks/common-issues.md)

## Lab Backbone

The course relies on `practice/` as the main lab system:

- Pod lifecycle and config: `01`, `05`, `07`, `14`, `15`, `16`, `17`, `19`
- Service, probes, ingress, and policy: `02`, `03`, `04`, `10`, `11`
- Scheduling and storage: `06`, `08`, `09`, `13`, `18`

## Recommended Delivery Modes

### 5-Day Bootcamp

- Day 1: debugging framework and investigation flow
- Day 2: pod lifecycle and runtime failures
- Day 3: networking, DNS, ingress, and traffic flow
- Day 4: scheduling, storage, and stateful systems
- Day 5: AKS overlays, observability, and capstone

### 2-Day Intensive

- Day 1: foundations, pod lifecycle, and networking
- Day 2: AKS platform overlays and capstone

## Rule For Students

Do not start with `practice/SOLUTIONS.md`. Diagnose first, then fix, then verify.
