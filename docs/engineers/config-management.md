# Configuration Management

## Overview
Keep app configs safe, repeatable, and environment-specific.

## Practices
- Separate config from code; use ConfigMaps/Secrets/parameters.
- Use Kustomize/Helm for env overlays; avoid manual patching.
- Validate configs before deploy (`kubectl diff`, `helm lint`).

## Diagnostics
```bash
kubectl get configmap,secret -n <ns>
kubectl describe deploy/<name> -n <ns>
kubectl get events -n <ns> --sort-by=.lastTimestamp | tail
```
- Check env vars/volume mounts; verify keys exist.

## Fixes
- Correct missing keys; update mounts; restart rollout.
- Use feature flags for risky changes.

## Prevention
- Schema validation (cue/jsonschema) in CI.
- Keep secrets in external store (Key Vault/Secrets Manager) via CSI.
