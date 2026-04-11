# GitOps Install On Minikube

Use this guide to install Argo CD and Flux CD into a local Minikube cluster for labs, demos, and GitOps troubleshooting practice.

This is a local lab setup. It is useful for learning and testing, but do not point both Argo CD and Flux at the same application manifests unless you intentionally want to test GitOps controller conflicts.

## What Gets Installed

- Argo CD in namespace `argocd`
- Flux CD in namespace `flux-system`
- Argo CD from the official stable manifest
- Flux CD from the official latest install manifest

## Prerequisites

Minikube must already be running and `kubectl` must point at it:

```bash
kubectl config current-context
kubectl get nodes -o wide
```

Expected context:

```text
minikube
```

Optional: check whether local CLIs are already installed. These are not required for the controller install commands below.

```bash
command -v argocd || true
command -v flux || true
```

## Install Flux CD

Install Flux controllers from the official release manifest:

```bash
kubectl apply -f https://github.com/fluxcd/flux2/releases/latest/download/install.yaml
```

This creates the `flux-system` namespace, Flux CRDs, RBAC, NetworkPolicies, and controller deployments.

Verify Flux:

```bash
kubectl wait --for=condition=available deployment --all -n flux-system --timeout=180s
kubectl get pods -n flux-system
```

Expected controllers:

```text
helm-controller
image-automation-controller
image-reflector-controller
kustomize-controller
notification-controller
source-controller
```

Flux does not install a UI by default. It is mostly CLI and controller driven.

## Optional: Install Flux UI With Weave GitOps

Flux CD does not ship a built-in dashboard like Argo CD. For a local GUI, install Weave GitOps on top of Flux.

Generate a local admin password and bcrypt hash:

```bash
export WEAVE_GITOPS_PASSWORD="$(openssl rand -base64 18)"
export WEAVE_GITOPS_PASSWORD_HASH="$(
  htpasswd -nbBC 10 "" "${WEAVE_GITOPS_PASSWORD}" | tr -d ':\n' | sed 's/$2y/$2a/'
)"

echo "Weave GitOps username: admin"
echo "Weave GitOps password: ${WEAVE_GITOPS_PASSWORD}"
```

Install the Weave GitOps dashboard through Flux:

```bash
cat <<YAML | kubectl apply -f -
apiVersion: source.toolkit.fluxcd.io/v1
kind: HelmRepository
metadata:
  annotations:
    metadata.weave.works/description: This is the Weave GitOps Dashboard for Flux.
  labels:
    app.kubernetes.io/component: ui
    app.kubernetes.io/name: weave-gitops-dashboard
    app.kubernetes.io/part-of: weave-gitops
  name: ww-gitops
  namespace: flux-system
spec:
  interval: 1h
  type: oci
  url: oci://ghcr.io/weaveworks/charts
---
apiVersion: helm.toolkit.fluxcd.io/v2
kind: HelmRelease
metadata:
  name: ww-gitops
  namespace: flux-system
spec:
  interval: 1h
  chart:
    spec:
      chart: weave-gitops
      interval: 1h
      sourceRef:
        kind: HelmRepository
        name: ww-gitops
  values:
    adminUser:
      create: true
      username: admin
      passwordHash: "${WEAVE_GITOPS_PASSWORD_HASH}"
YAML
```

Wait for the dashboard:

```bash
kubectl wait --for=condition=Ready helmrelease/ww-gitops -n flux-system --timeout=300s
kubectl get pods,svc -n flux-system -l app.kubernetes.io/name=weave-gitops
```

Access the UI:

```bash
kubectl port-forward svc/ww-gitops-weave-gitops -n flux-system 9001:9001
```

Open:

```text
http://localhost:9001
```

Login:

```text
username: admin
password: value printed by WEAVE_GITOPS_PASSWORD when you installed it
```

If local port `9001` is busy, use a different local port:

```bash
kubectl port-forward svc/ww-gitops-weave-gitops -n flux-system 9101:9001
```

Then open `http://localhost:9101`.

## Install Argo CD

Create the namespace:

```bash
kubectl create namespace argocd
```

If the namespace already exists, use this idempotent alternative:

```bash
kubectl create namespace argocd --dry-run=client -o yaml | kubectl apply -f -
```

Apply the official stable Argo CD manifest:

```bash
kubectl apply -n argocd -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml
```

If you see this CRD error:

```text
The CustomResourceDefinition "applicationsets.argoproj.io" is invalid: metadata.annotations: Too long: may not be more than 262144 bytes
```

Reapply with server-side apply:

```bash
kubectl apply --server-side --force-conflicts -n argocd -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml
```

Why this works: server-side apply avoids storing the huge client-side `last-applied-configuration` annotation on large CRDs.

## Verify Argo CD

Wait for Argo CD deployments:

```bash
kubectl wait --for=condition=available deployment --all -n argocd --timeout=180s
```

Wait for the application controller StatefulSet:

```bash
kubectl rollout status statefulset/argocd-application-controller -n argocd --timeout=180s
```

Check pods:

```bash
kubectl get pods -n argocd
```

Expected pods:

```text
argocd-application-controller-0
argocd-applicationset-controller
argocd-dex-server
argocd-notifications-controller
argocd-redis
argocd-repo-server
argocd-server
```

List Argo CD services:

```bash
kubectl get svc -n argocd
```

## Access Argo CD UI

Port-forward the Argo CD server service:

```bash
kubectl port-forward svc/argocd-server -n argocd 8080:443
```

Open:

```text
https://localhost:8080
```

Username:

```text
admin
```

Get the initial admin password:

```bash
kubectl -n argocd get secret argocd-initial-admin-secret -o jsonpath='{.data.password}' | base64 -d && echo
```

If you only want the raw base64 value:

```bash
kubectl get secret argocd-initial-admin-secret -n argocd -o jsonpath={.data.password}
```

## Verify Both Controllers

Run:

```bash
kubectl get pods -n argocd
kubectl get pods -n flux-system
kubectl get helmrepository,helmrelease -n flux-system
kubectl get crd | grep -E 'argoproj.io|fluxcd.io|toolkit.fluxcd.io'
```

Healthy outcome:

- all Argo CD pods are `Running`
- all Flux pods are `Running`
- Argo CD CRDs exist for `applications.argoproj.io`, `applicationsets.argoproj.io`, and `appprojects.argoproj.io`
- Flux CRDs exist for `gitrepositories`, `kustomizations`, `helmreleases`, and related toolkit resources
- optional Weave GitOps resources show `HelmRelease/ww-gitops` as `Ready=True`

## Deploy The Demo Applications

After Argo CD and Flux CD are installed, use the demo manifests in `gitops-demo/`.

For the full walkthrough, see:

```text
gitops-demo/README.md
```

Register the Argo CD demo app:

```bash
kubectl apply -f gitops-demo/argocd/application.yaml
kubectl get application argocd-demo-app -n argocd
kubectl get pods -n argocd-demo
```

Register the Flux demo app:

```bash
kubectl apply -f gitops-demo/flux/gitrepository.yaml -f gitops-demo/flux/kustomization.yaml
kubectl get gitrepository aks-troublshoot-guides -n flux-system
kubectl get kustomization flux-demo-app -n flux-system
kubectl get pods -n flux-demo
```

Access the demo Services from Minikube:

```bash
minikube service nginx-argocd -n argocd-demo --url
minikube service nginx-flux -n flux-demo --url
```

Use friendly local URLs with Ingress:

```bash
minikube addons enable ingress
kubectl wait --namespace ingress-nginx \
  --for=condition=ready pod \
  --selector=app.kubernetes.io/component=controller \
  --timeout=180s
kubectl get ingress -n argocd-demo
kubectl get ingress -n flux-demo
```

On macOS with the Docker Minikube driver, use a stable local ingress forward:

```bash
sudo kubectl port-forward -n ingress-nginx svc/ingress-nginx-controller 80:80
```

Open the demos:

```text
http://argocd-demo.localhost
http://flux-demo.localhost
```

If you prefer not to bind local port `80`, forward `8088:80` and open `http://argocd-demo.localhost:8088` and `http://flux-demo.localhost:8088`.

Optional: the Ingress resources also include `.test` aliases. Configure wildcard DNS once with `dnsmasq` if you want those names:

```bash
brew install dnsmasq
BREW_PREFIX="$(brew --prefix)"
mkdir -p "$BREW_PREFIX/etc/dnsmasq.d"
printf 'address=/test/127.0.0.1\n' > "$BREW_PREFIX/etc/dnsmasq.d/minikube-test.conf"
echo 'conf-dir='"$BREW_PREFIX"'/etc/dnsmasq.d,*.conf' >> "$BREW_PREFIX/etc/dnsmasq.conf"
sudo mkdir -p /etc/resolver
printf 'nameserver 127.0.0.1\n' | sudo tee /etc/resolver/test
sudo brew services start dnsmasq
```

Then the `.test` aliases also work:

```text
http://argocd-demo.test
http://flux-demo.test
```

## Troubleshoot After Install

Run the repo GitOps diagnostic script:

```bash
./scripts/diagnostics/gitops-diagnostics.sh
```

Run the Python detector and remediation preview:

```bash
python3 ./k8s-diagnostics-cli.py detect
python3 ./k8s-diagnostics-cli.py suggest
python3 ./k8s-diagnostics-cli.py heal --dry-run
```

What the remediation tool can safely fix:

- unhealthy controller-owned Argo CD pods in `argocd`
- unhealthy controller-owned Flux pods in `flux-system`

What stays manual by design:

- Argo CD Application `OutOfSync` or `Degraded`
- Flux `GitRepository`, `Kustomization`, or `HelmRelease` with `Ready=False`
- repository auth, wrong Git path, bad Helm values, missing CRDs, and admission/RBAC failures

Reason: Argo CD and Flux are GitOps controllers. The durable fix should normally be made in Git or controller configuration, not by patching live resources that reconciliation will overwrite.

For the full runbook, see:

```text
docs/devops/gitops.md
```

## Notes For Labs

- Keep Argo CD and Flux in separate namespaces.
- Do not configure both controllers to reconcile the same Kubernetes objects unless the lab is specifically about controller conflict.
- Prefer one GitOps controller per app path.
- For local demos, use port-forwarding rather than changing the Argo CD service to `LoadBalancer`.

## Cleanup

Remove Argo CD:

```bash
kubectl delete namespace argocd
```

Remove Flux:

```bash
kubectl delete namespace flux-system
```

If you only want to remove the optional Weave GitOps UI but keep Flux:

```bash
kubectl delete helmrelease ww-gitops -n flux-system
kubectl delete helmrepository ww-gitops -n flux-system
```

If you want to remove all Flux CRDs too, delete the install manifest resources:

```bash
kubectl delete -f https://github.com/fluxcd/flux2/releases/latest/download/install.yaml
```

If you want to remove all Argo CD CRDs too, delete the install manifest resources:

```bash
kubectl delete -n argocd -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml
```

If the namespace was already deleted first, some namespaced resources may already be gone; CRDs and cluster-scoped RBAC may still need manifest deletion.
