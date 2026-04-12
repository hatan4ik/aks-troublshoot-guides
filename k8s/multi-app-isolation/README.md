# Multi-Application Isolation Example

This directory contains an applyable two-application example for sharing one Kubernetes cluster safely.

It demonstrates:

- one namespace per app
- namespace labels for ownership and environment
- `ResourceQuota` and `LimitRange`
- namespace-scoped read-only RBAC binding
- one runtime `ServiceAccount` per app
- default-deny `NetworkPolicy`
- explicit ingress-controller and DNS allows
- host-based Ingress on normal HTTP port `80`
- app Services that stay internal as `ClusterIP`

Apply in a local or disposable lab cluster:

```bash
kubectl apply -k k8s/multi-app-isolation
kubectl get ns app-a app-b --show-labels
kubectl get pods,svc,ingress,networkpolicy -n app-a
kubectl get pods,svc,ingress,networkpolicy -n app-b
```

Deploy with Argo CD:

```bash
kubectl apply -f gitops-demo/argocd/multi-app-isolation-application.yaml
kubectl get application multi-app-isolation -n argocd
```

Deploy with Flux CD:

```bash
kubectl apply -f gitops-demo/flux/gitrepository.yaml
kubectl apply -f gitops-demo/flux/multi-app-isolation-kustomization.yaml
kubectl get kustomization multi-app-isolation -n flux-system
```

Use only one GitOps controller for this path at a time. Argo CD and Flux can both manage applications in the same cluster, but they should not manage the same Kubernetes objects unless you are intentionally testing drift and controller conflict.

For Minikube with `ingress-nginx`, use the local ingress setup from `gitops-demo/README.md` and map these hosts to the ingress controller path:

```text
app-a.localhost
app-b.localhost
```

For AKS/EKS/GKE, replace `ingressClassName`, hostnames, DNS automation annotations, and TLS settings with the provider pattern from `docs/cloud-fqdn-service-access.md`.

Do not apply this unchanged in production. Treat it as a starting blueprint and replace:

- namespace names and labels
- team RBAC group names
- quota and limit values
- ingress class
- hostnames
- TLS configuration
- approved egress dependencies
