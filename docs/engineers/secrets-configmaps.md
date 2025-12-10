# Secrets and ConfigMaps

## Overview
Manage application configuration securely and predictably.

## Diagnostics
```bash
kubectl get secret,configmap -n <ns>
kubectl describe pod <pod> -n <ns> | grep -i "Secrets" -A3
kubectl get events -n <ns> --sort-by=.lastTimestamp | tail
```
- Validate mounts/envFrom keys; check for `permission denied` or missing keys.

## Fixes
- Recreate secrets with correct data; ensure base64 encoding where needed.
- Mount with least privilege; avoid large configmaps in env vars.
- Use CSI Secrets Store for external vaults.

## Prevention
- Rotate secrets; audit exposure; enable encryption at rest.
- Disallow plaintext secrets in Git; use sealed-secrets or external stores.
