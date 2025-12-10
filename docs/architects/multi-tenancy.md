# Multi-Tenancy Strategies (AKS/EKS/Kubernetes)

## Overview
Design isolation across teams/products while sharing clusters. Balance blast-radius control, cost, and operability.

## Patterns
- **Namespace + Quota + NetworkPolicy**: Fastest, good for most teams.
- **Node Pool per Tenant**: Stronger isolation, aligns with taints/tolerations.
- **Cluster per Tenant**: Highest isolation, costlier; use for strict compliance/regulatory needs.

## Symptoms of Bad Design
- Cross-tenant traffic leakage
- One team exhausting cluster resources
- Frequent RBAC/permission escalations

## Diagnostics
```bash
kubectl get ns --show-labels
kubectl describe resourcequota -A
kubectl get networkpolicies -A
```
- Validate taints/tolerations per node pool: `kubectl get nodes -L tenant`
- Check noisy-neighbor: `./scripts/diagnostics/resource-analysis.sh`

## Recommendations
1. **Tenant boundary**: Namespace per tenant with required labels (`tenant=<name>`, `env=<env>`).
2. **Network isolation**: Default-deny NetworkPolicy, allow only required ingress/egress.
3. **Resource isolation**: ResourceQuota + LimitRange per namespace; separate node pools for latency or compliance workloads.
4. **Access control**: RBAC per tenant group; avoid cluster-admin bindings.
5. **Platform services**: Shared ingress/logging/metrics with per-tenant index/route.

## AKS/EKS Nuances
- **AKS**: Use Azure CNI powered node pools for IP isolation; AAD for RBAC; consider UDR for tenant egress.
- **EKS**: AWS VPC CNI prefix delegation for IP scale; IRSA for per-tenant IAM; Security Groups for Pods for regulated tenants.

## Automation Hooks
- Policy conformance: `./scripts/diagnostics/security-audit.sh`
- Resource pressure: `./scripts/diagnostics/resource-analysis.sh`
- Drift detection (labels/quotas/policies): `./scripts/diagnostics/gitops-diagnostics.sh`

## Prevention
- Golden namespace blueprint (quota, limits, policies)
- Admission controls (OPA/Gatekeeper/Kyverno) enforcing labels, quotas, and deny-privileged
- Periodic audits via `security-audit.sh` and `resource-analysis.sh`
