# Pod Startup Issues

## Overview
Pods stuck Pending/Init/CrashLoop due to resources, scheduling, or config.

## Symptoms
- Pending with unschedulable events
- CrashLoopBackOff / Error state
- Init containers failing

## Diagnostics
```bash
../../scripts/diagnostics/pod-diagnostics.sh <pod> <ns>
kubectl describe pod <pod> -n <ns>
kubectl get events -n <ns> --sort-by=.lastTimestamp | tail
```
- Check resource requests vs node capacity; node selectors/taints.
- Verify images pull successfully and secrets mount.

## Fixes
- Adjust requests/limits or add node capacity.
- Fix nodeSelector/affinity to match labels; add tolerations.
- Correct image tag/registry auth; fix init container commands.

## Prevention
- Default LimitRange; imagePullSecrets bound to service accounts.
- Preflight tests in CI using `python k8s-diagnostics-cli.py diagnose <ns> <pod>`.
