# AKS Course Syllabus

## Course Goal

Teach engineers to debug AKS clusters systematically, fix common production failures safely, and know when the problem is no longer inside Kubernetes and has moved into Azure infrastructure.

## Learning Outcomes

By the end of the course, students should be able to:

- Use a top-down debugging model instead of random command execution
- Diagnose pod lifecycle, probe, image pull, service, ingress, DNS, storage, and scheduling failures
- Separate Layer 1-4 Kubernetes failures from Layer 5 Azure failures
- Use `kubectl`, events, logs, endpoints, and node state as primary evidence
- Use AKS-specific signals such as Azure CNI, ACR reachability, Azure LB behavior, and Azure Monitor data

## Prerequisites

- Basic Linux shell usage
- Basic Docker and container concepts
- Basic Kubernetes objects: Pod, Deployment, Service, Ingress, ConfigMap, Secret, PVC
- Azure fundamentals helpful but not required

## Required Tooling

- `kubectl`
- `helm`
- `python3`
- `kind` or `minikube` for local labs
- `az` CLI for AKS-specific modules

## Module Map

1. Foundations and debugging framework
2. Pod lifecycle, probes, config, and runtime failures
3. Services, ingress, DNS, and network policy
4. Scheduling, storage, and stateful workloads
5. AKS-specific networking, observability, and infrastructure boundaries
6. Capstone

## Primary Reading Order

1. [AKS Debugging Framework](../docs/AKS-DEBUGGING-FRAMEWORK.md)
2. [Live Debug Runbook](../DEBUG-RUNBOOK.md)
3. [Live Debugging Workflow](../docs/LIVE-DEBUG-WORKFLOW.md)
4. [Hands-On Practice](../practice/README.md)
5. [Engineering Depth](../docs/ENGINEERING-DEPTH.md)

## Assessments

- Short module checks: students explain symptom, root cause, and smallest safe fix
- Hands-on labs: students diagnose and patch broken resources
- Capstone: one multi-layer AKS debugging exercise with verification and explanation

## Completion Standard

A student passes the course if they can:

- Identify the failure layer correctly
- Use evidence from `kubectl describe`, events, logs, and endpoints
- Apply a minimal fix
- Prove recovery with rollout, readiness, and service validation

## Recommended Delivery Format

### Lecture

- 20-40 minutes per module
- Emphasize investigation order and failure boundaries

### Labs

- 30-60 minutes per module
- Students work from symptoms, not from bug descriptions

### Review

- 10-15 minutes per module
- Students explain what signal proved the root cause
