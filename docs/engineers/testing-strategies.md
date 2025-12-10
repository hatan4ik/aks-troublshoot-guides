# Testing Strategies

## Overview
Ensure Kubernetes apps are correct before deployment.

## Layers
- **Unit**: Fast logic tests.
- **Integration**: Services with dependencies (DB/cache) via docker-compose/kind.
- **E2E**: Deploy to ephemeral namespace/cluster; run smoke.
- **Performance**: Load tests with autoscaling validation.

## Commands
```bash
# Ephemeral namespace for tests
NS=test-$(date +%s); kubectl create ns $NS
helm upgrade --install app charts/app -n $NS --wait
python k8s-diagnostics-cli.py diagnose $NS <pod>
kubectl delete ns $NS
```

## Prevention
- Gate merges with e2e smoke on PRs.
- Validate manifests (`kubectl/kubeconform/kubeval`), policies (OPA/Kyverno), and security scans.
