# Module 1: Foundations And Debugging Framework

## Purpose

Give students the operating model they will use for the entire course: investigate top-down, use evidence, and do not jump to Azure before eliminating Kubernetes layers first.

## Required Reading

- [AKS Debugging Framework](../docs/AKS-DEBUGGING-FRAMEWORK.md)
- [Live Debug Runbook](../DEBUG-RUNBOOK.md)
- [Live Debugging Workflow](../docs/LIVE-DEBUG-WORKFLOW.md)

## Learning Objectives

- Understand the 5-layer AKS debugging model
- Read events before making changes
- Distinguish scheduling failures from runtime failures
- Distinguish connection refused from timeout
- Explain why readiness and liveness are different

## Class Flow

### 1. Mental Model

Teach the five layers:

1. Pod lifecycle
2. Container runtime
3. Service networking
4. Cluster infrastructure
5. Azure infrastructure

### 2. Default Investigation Sequence

```bash
kubectl config current-context
kubectl get ns
kubectl get pods -A
kubectl get events -A --sort-by=.metadata.creationTimestamp | tail -30
```

### 3. Evidence Standards

Require students to state:

- Symptom
- Root cause hypothesis
- Exact field or object they plan to change

## Recommended Live Demo

- Show one broken workload
- Read events first
- Classify it as scheduling or runtime
- Fix it with the smallest possible patch
- Verify recovery

## Lab

Start with one simple scenario from [practice/README.md](../practice/README.md):

- `01-image-pull-backoff.yaml`
- `04-bad-probe.yaml`

## Exit Criteria

Students can answer:

- What layer is this failure in?
- What signal proved that?
- What command should come next?
