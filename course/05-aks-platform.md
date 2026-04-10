# Module 5: AKS Platform Layers, Observability, And Azure Boundaries

## Purpose

Teach students when to leave pure Kubernetes debugging and move into AKS and Azure diagnostics.

## Required Reading

- [AKS Debugging Framework](../docs/AKS-DEBUGGING-FRAMEWORK.md)
- [AKS Networking Deep Dive](../docs/azure/aks-networking.md)
- [Azure Observability For AKS](../docs/azure/azure-observability.md)
- [P0 Cluster Outage](../playbooks/p0-cluster-outage.md)
- [P1 DNS Failures](../playbooks/p1-dns-failures.md)

## Learning Objectives

- Recognize Layer 5 failures without blaming Azure too early
- Understand Azure CNI, NSG, route, LB, and ACR failure patterns
- Use Azure-native observability when `kubectl` is no longer enough
- Know what evidence to collect before opening a cloud-provider escalation

## Topics

### 1. AKS Networking

- Azure CNI vs Kubenet
- NSG drops
- Load Balancer pending and health probe behavior
- ACR timeout vs unauthorized

### 2. AKS Storage

- Azure Disk attach semantics
- Azure Files for RWX
- Zone and node-pool interactions

### 3. Observability

- Container Insights
- Log Analytics queries
- Azure Monitor metrics
- Activity Log for destructive changes

### 4. Incident Boundaries

When to escalate:

- API server unavailable across the cluster
- Azure LB not provisioning
- Azure CNI failures across nodes
- control plane upgrade or node pool upgrade stuck

## Suggested Demo

- Show one Kubernetes-looking symptom
- Prove the Kubernetes layer is healthy
- Shift to Azure evidence
- Identify the Azure component responsible

## Suggested Assessment

Students receive a case such as:

- `ImagePullBackOff` with timeout to ACR
- service `LoadBalancer` stuck pending
- cross-node traffic timing out with healthy pods

They must state:

1. Why this is no longer just a Kubernetes issue
2. Which Azure component to inspect first
3. Which Azure command or portal view they would use
