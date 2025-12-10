# Security Architecture (AKS/EKS/Kubernetes)

## Overview
Defend clusters with layered controls: identity, policy, supply chain, runtime, and encryption.

## Pillars
- **Identity & Access**: AAD/AWS IAM + RBAC least privilege; no cluster-admin outside break-glass.
- **Network**: Default-deny NetworkPolicy; restrict egress; mTLS with mesh where needed.
- **Supply Chain**: Signed images (cosign), private registries, vulnerability scanning.
- **Runtime**: Drop capabilities, read-only FS, seccomp, AppArmor/SELinux, PSP replacements (PSA/Gatekeeper/Kyverno).
- **Data**: Encrypt secrets at rest; use CSI Secrets Store (Key Vault/Secrets Manager).

## Diagnostics
```bash
./scripts/diagnostics/security-audit.sh
kubectl auth can-i --list
kubectl get pods -A -o jsonpath='{..securityContext}'
```
- Check privileged/hostPath usage: `security-audit.sh`
- Check exposed dashboards/services: `kubectl get svc -A --field-selector spec.type=LoadBalancer`

## AKS Nuances
- AAD RBAC + Azure RBAC for kube; Defender for Cloud alerts; Key Vault CSI driver; Azure Policy for Kubernetes.

## EKS Nuances
- IRSA for service accounts; Control Plane Logging; GuardDuty EKS Protection; Security Groups for Pods; Secrets Manager/Parameter Store CSI.

## Prevention
- Admission policy bundles (Kyverno/Gatekeeper) for privileged/hostPath/RunAsNonRoot/resource defaults.
- Mandatory image signing and scanning gates in CI/CD.
- Regular audits via `security-audit.sh` + `performance-analysis.sh` to catch throttling on system components.

## Automation Hooks
- `security-audit.sh` for RBAC/pod security
- `image-security-scan.sh` (planned) placeholder: integrate with registry scanner
- `network-security-scan.sh` (planned) placeholder: extend from `network-diagnostics.sh`
