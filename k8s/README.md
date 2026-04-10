# k8s Deployment Guide

## Overview
Manifests and RBAC for running the Diagnostics API in-cluster.

## Files
- `deployment.yaml` – Deployment, Service, ServiceAccount, RBAC.

## Usage
```bash
kubectl apply -f k8s/deployment.yaml
kubectl -n kube-system get pods -l app=k8s-diagnostics-api
kubectl -n kube-system port-forward svc/k8s-diagnostics-api 8000:8000
curl http://localhost:8000/livez
curl http://localhost:8000/readyz
curl http://localhost:8000/health
```

## Notes
- The base manifest exposes the API only as an internal `ClusterIP` service. Use [networking.yaml](./networking.yaml) if you need ingress-based access.
- Runs in `kube-system` with read/list/watch/delete on selected resources; extend RBAC only when new endpoints require it.
- Image `k8s-diagnostics:latest` should be built and pushed to your registry; update `deployment.yaml` accordingly.
- Set resource requests/limits appropriately for your cluster size.
