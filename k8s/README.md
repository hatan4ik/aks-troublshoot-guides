# k8s Deployment Guide

## Overview
Manifests and RBAC for running the Diagnostics API in-cluster.

## Files
- `deployment.yaml` - Deployment, Service, ServiceAccount, read-only RBAC.
- `remediation-rbac.yaml` - Optional write RBAC for guarded remediation endpoints.

## Usage
```bash
# Local Minikube: build the image into the local Docker daemon and load it.
make build
minikube image load k8s-diagnostics:latest

kubectl apply -f k8s/deployment.yaml
kubectl -n kube-system get pods -l app=k8s-diagnostics-api
kubectl -n kube-system port-forward svc/k8s-diagnostics-api 8000:8000
curl http://localhost:8000/livez
curl http://localhost:8000/readyz
curl http://localhost:8000/health
```

For AKS/EKS/GKE, push the image to a reachable registry and update `image:` in `deployment.yaml` or through Kustomize before applying.

## Mutating Endpoints

Read-only API endpoints work with the base manifest. Mutating endpoints are disabled by default:

```yaml
AUTO_FIX_ENABLED: "false"
K8S_DIAGNOSTICS_ALLOWED_NAMESPACES: "practice"
```

To enable API-based remediation in a lab namespace, create an API key secret and explicitly enable fixes:

```bash
kubectl -n kube-system create secret generic k8s-diagnostics-api-auth \
  --from-literal=api-key="$(openssl rand -hex 24)"
kubectl apply -f k8s/remediation-rbac.yaml
kubectl -n kube-system set env deployment/k8s-diagnostics-api AUTO_FIX_ENABLED=true
kubectl -n kube-system set env deployment/k8s-diagnostics-api K8S_DIAGNOSTICS_ALLOWED_NAMESPACES=practice
```

Then send mutating requests with `X-API-Key`. Do not set the allowlist to `*` outside disposable lab clusters.

## Notes
- The base manifest exposes the API only as an internal `ClusterIP` service. Use [networking.yaml](./networking.yaml) if you need ingress-based access.
- Runs in `kube-system` with cluster-wide read permissions by default. Write permissions live in `remediation-rbac.yaml` and should only be applied for controlled labs or tightly governed operations.
- Image `k8s-diagnostics:latest` uses `IfNotPresent` for Minikube. Managed clusters should use a registry-qualified immutable tag or digest.
- Set resource requests/limits appropriately for your cluster size.
