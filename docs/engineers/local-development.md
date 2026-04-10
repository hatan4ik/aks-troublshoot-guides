# Local Development Setup

## Overview
Run and debug Kubernetes apps locally with parity to clusters.

When the local cluster platform itself is broken, use [LOCAL-CLUSTER-DEBUGGING.md](../LOCAL-CLUSTER-DEBUGGING.md) before debugging application manifests.

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
- Run `./scripts/local/minikube-doctor.sh` when Docker, Minikube, or kubeconfig health is unclear.
- Run `./scripts/local/restart-minikube.sh` for in-place Minikube recovery.

## Prevention
- Pre-commit hooks; container health checks; resource requests set locally.
- Keep sample `.env` with non-secret defaults.
- Prefer in-place `minikube start` recovery before deleting a local cluster.
