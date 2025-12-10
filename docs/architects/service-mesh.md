# Service Mesh Integration

## Overview
Decide when and how to adopt a mesh (Istio/Linkerd/Consul/ASM/APP Mesh) for mTLS, traffic policy, and observability.

## When to Use
- Require zero-trust/mTLS between services
- Need fine-grained traffic shifting (canary, A/B)
- Desire uniform telemetry (traces/metrics) without code changes

## Concerns
- Control plane overhead and upgrades
- Sidecar resource cost and IP consumption
- Operational maturity and multi-cluster support

## AKS Notes
- Azure Service Mesh (ASM) or Istio; integrate with AAD for ingress; watch node pool IP capacity with sidecars.

## EKS Notes
- AWS App Mesh or Istio/Linkerd; integrate with ACM for certs; ensure ENI/IP limits account for sidecars.

## Diagnostics
```bash
kubectl get pods -A -l istio.io/rev
kubectl get envoyfilters -A
./scripts/diagnostics/performance-analysis.sh   # watch sidecar cost
```
- Validate mTLS status via mesh dashboards or `istioctl authn tls-check`.

## Adoption Steps
1. Enable mesh on a canary namespace; enforce PeerAuthentication/AuthorizationPolicy (or equivalent).
2. Test ingress/egress behavior and fail-open/fail-close choices.
3. Standardize traffic policy (timeouts/retries/circuit-breakers).
4. Add SLOs and alerts for mesh control plane health.

## Automation Hooks
- `deployment-diagnostics.sh` for rollout/health when adding sidecars
- `performance-analysis.sh` to watch resource overhead
- GitOps checks via `gitops-diagnostics.sh` for mesh CRD drift
