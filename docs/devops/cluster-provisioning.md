# Cluster Provisioning

## Overview
Provision AKS/EKS clusters via IaC with repeatable patterns and day-0 validation.

## Workflow
1. Define IaC (Terraform/Bicep/CloudFormation).
2. Apply baseline add-ons (CNI, CSI, autoscaler, metrics, ingress).
3. Run post-provision validation: `./scripts/diagnostics/cluster-health-check.sh`.

## AKS Notes
- Use managed identities; enable Azure CNI overlay or Kubenet per need.
- System/user node pools separated; set network policies (Calico/Azure).
- Enable OMS/Container Insights and Defender if required.

## EKS Notes
- Enable Control Plane logging; set IRSA; install EBS/EFS CSI drivers.
- Use Managed Node Groups or Karpenter; configure cluster autoscaler IRSA.

## Validation
```bash
kubectl get nodes
kubectl get pods -A
./scripts/diagnostics/network-diagnostics.sh
```
- Confirm metrics-server, CNI, CSI pods healthy.

## Prevention
- Guardrails via policy (Azure Policy, AWS Config) and GitOps bootstrap.
- Version pinning for cluster/Kubernetes and add-ons.
