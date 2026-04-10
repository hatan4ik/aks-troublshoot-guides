# Module 4: Scheduling, Storage, And Stateful Workloads

## Purpose

Teach students to debug workloads that never schedule, volumes that never bind, and stateful apps that depend on storage and stable service identity.

## Required Reading

- [Pod Startup Issues](../docs/engineers/pod-startup-issues.md)
- [Stateful Workloads](../docs/engineers/stateful-workloads.md)
- [Storage Architecture](../docs/architects/storage-architecture.md)
- [Node Pools](../docs/architects/node-pools.md)

## Learning Objectives

- Diagnose `Pending` due to resources, taints, or selectors
- Diagnose PVC and StorageClass failures
- Understand why StatefulSets need headless services
- Explain the AKS implications of zones, Azure Disk, and Azure Files

## Core Commands

```bash
kubectl describe pod <pod> -n <ns>
kubectl get nodes --show-labels
kubectl describe node <node>
kubectl get pvc -n <ns>
kubectl describe pvc <pvc> -n <ns>
kubectl get storageclass
```

## Hands-On Labs

Required:

- `practice/06-pending-resources.yaml`
- `practice/08-taint-no-toleration.yaml`
- `practice/09-node-selector-no-match.yaml`
- `practice/13-pvc-wrong-storageclass.yaml`
- `practice/18-statefulset-missing-headless-svc.yaml`

## AKS Overlay

Focus discussion on:

- Azure Disk is zone-sensitive and `ReadWriteOnce`
- Azure Files is the common RWX path
- Node pools are a scheduling boundary, not just a scaling construct
- Subnet IP pressure can look like a scheduling problem when it is actually a platform problem

## Assessment Prompt

Give students one `Pending` pod and ask them to prove whether the blocker is:

- capacity
- tainting
- selector mismatch
- storage
