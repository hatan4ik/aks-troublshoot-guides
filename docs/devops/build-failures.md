# Build Failures

## Overview
CI/CD builds failing for containers/Helm/manifests. Aim to shorten MTTR with standard checks.

## Symptoms
- Image build errors, dependency resolution failures
- Lint/test failures, image push denied
- Slow or flaky builds

## Diagnostics
```bash
./scripts/diagnostics/pipeline-debug.sh  # when available
docker build .                           # reproduce locally
kubectl auth can-i create pods           # verify permissions for build jobs
```
- Check registry auth: `./scripts/diagnostics/registry-issues.sh` (future)
- Review recent pipeline changes/runner images.

## Quick Fixes
- Clear/refresh registry credentials; rotate tokens.
- Pin base images; ensure proxies/certs configured.
- Retry with cache disabled for suspected corruption.

## Prevention
- Pre-commit lint/tests; immutable base image versions.
- Cache strategy per runner; SBoM + vulnerability scans gate.
- Use remote build (ACR Tasks/CodeBuild) for heavy builds.
