# Network Architecture (AKS/EKS/Kubernetes)

## Overview
Design cluster networking for reliability, IP scale, and security. Cover CNI choice, ingress, east-west policy, and egress control.

## Key Decisions
- **CNI**: Azure CNI vs Kubenet (AKS); AWS VPC CNI vs Cilium/Calico (EKS); choose for IP scale and policy needs.
- **Ingress**: L7 ingress controller (Nginx, AGIC, ALB) with TLS termination and WAF upstream.
- **Network Policies**: Default-deny + allow lists; isolate system namespaces.
- **Egress**: NAT Gateway/User Defined Routes (AKS) or NAT Gateway/egress-only (EKS); restrict via policies.

## Diagnostics
```bash
./scripts/diagnostics/network-diagnostics.sh
kubectl get nodes -o wide
kubectl get pods -A -o wide
kubectl get networkpolicies -A
```
- IP exhaustion: `kubectl get pods -A -o wide | awk '{print $6}' | sort | uniq | wc -l`
- LB health: `kubectl get svc -A --field-selector spec.type=LoadBalancer`

## AKS Nuances
- Azure CNI needs sufficient subnet IPs; use CNI overlay for scale.
- AGIC for App Gateway integration; UDR for custom egress; Azure Firewall for north-south.

## EKS Nuances
- AWS VPC CNI ENI/IP limits; enable prefix delegation for density.
- ALB Ingress Controller for dynamic ingress; Security Groups for Pods for granular isolation.

## Prevention & Patterns
- Reserve IP budgets per node pool; enforce NetworkPolicy defaults.
- Standardize ingress annotations (timeouts, TLS, WAF).
- Use liveness/readiness timeouts aligned to upstream LB health checks.

## Automation Hooks
- `network-diagnostics.sh` for DNS/policy/ingress checks
- `gitops-diagnostics.sh` for drift between desired and actual manifests
- `helm-diagnostics.sh` for ingress/annotation validation
