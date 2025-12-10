# Networking Setup

## Overview
Stand up network primitives (CNI, ingress, DNS, egress) for AKS/EKS clusters.

## Steps
1. Choose CNI (Azure CNI overlay/Kubenet or AWS VPC CNI/Cilium/Calico).
2. Configure subnetting/IP plans; allocate for pods/services/LB.
3. Deploy ingress controller with TLS and WAF integration.
4. Set NetworkPolicies default-deny and allow lists.
5. Configure egress control (NAT Gateway/Firewall, VPC NAT, SGs).

## Diagnostics
```bash
./scripts/diagnostics/network-diagnostics.sh
kubectl get pods -n kube-system | grep -E "cni|coredns"
kubectl get svc -A --field-selector spec.type=LoadBalancer
```
- Validate DNS and service endpoints; check LB pending states.

## AKS Notes
- Azure CNI overlay for IP scale; UDR/Firewall for egress; AGIC for ingress.
- Private clusters + Private DNS when needed.

## EKS Notes
- Prefix delegation for IP scale; Security Groups for Pods; ALB ingress; VPC endpoints for registries.

## Prevention
- Keep standardized ingress annotations and TLS policies.
- Monitor CNI/ingress pods via `health-dashboard.sh`.
