# Local Development Setup

## Overview
Run and debug Kubernetes apps locally with parity to clusters.

## Workflow
- Use kind/minikube for local clusters; sync manifests/Helm charts.
- Tilt/Skaffold for live reloads.
- Connect to remote services via `kubectl port-forward`.

## Commands
```bash
kind create cluster --name dev
kubectl config use-context kind-dev
python k8s-diagnostics-cli.py health
```
- Run pod diagnostics for local pods before pushing changes.

## Prevention
- Pre-commit hooks; container health checks; resource requests set locally.
- Keep sample `.env` with non-secret defaults.
