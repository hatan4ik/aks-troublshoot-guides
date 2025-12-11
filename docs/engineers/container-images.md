# Container Image Issues

## Overview
Build, size, security, and pull problems for application images.

## Diagnostics
```bash
docker build .
kubectl describe pod <pod> -n <ns> | grep -i image
../../scripts/diagnostics/pod-diagnostics.sh <pod> <ns>
```
- Check image size and layers; scan for CVEs; validate entrypoint.

## Fixes
- Pin base images; slim layers; multi-stage builds.
- Add healthcheck scripts; ensure non-root user.
- Refresh registry creds; retry pulls; reduce rate-limit impact with mirrors.

## Prevention
- CI gates: lint, tests, SBoM, vulnerability scan, cosign signing.
- Use digests in manifests; cache bust intentionally with version bumps.
