# Registry Issues

## Overview
Image pulls/pushes fail because of auth, network, or rate limits.

## Symptoms
- `ImagePullBackOff`, `ErrImagePull`
- Push denied/unauthorized; 429 rate limits
- Slow pulls causing timeouts

## Diagnostics
```bash
./scripts/diagnostics/pod-diagnostics.sh <pod> <ns>
kubectl describe pod <pod> -n <ns> | grep -i image
docker login <registry>
```
- Validate pull secret: `kubectl get secret -n <ns> | grep dockercfg`
- Test pull from node: `kubectl debug node/<node> --image=busybox -- chroot /host crictl pull <img>`

## Quick Fixes
- Refresh credentials; attach imagePullSecret to service accounts.
- Use regional mirrors/ACR geo-replication/ECR pull through cache.
- Backoff policy for CI pushes to avoid rate limits.

## Prevention
- Pin image digests; enable signing (cosign).
- Configure registry firewall/VNet endpoints (AKS) or VPC endpoints (EKS).
- Periodic token rotation and alerting on pull errors via `network-diagnostics.sh`.
