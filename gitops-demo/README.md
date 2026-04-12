# GitOps Demo — Argo CD & Flux CD

This directory is a self-contained GitOps demo that uses **this repository** as the Git source.
Both tools watch the same GitHub repo and reconcile independently into their own namespaces.

If you fork this repo, replace the hard-coded `repoURL` / `url` values in `gitops-demo/argocd/application.yaml` and `gitops-demo/flux/gitrepository.yaml` with your fork URL before applying the GitOps CRs.

```
gitops-demo/
├── apps/
│   ├── argocd-app/          # Manifests managed by Argo CD  → argocd-demo namespace
│   │   ├── namespace.yaml
│   │   ├── configmap.yaml
│   │   ├── deployment.yaml
│   │   ├── service.yaml
│   │   ├── ingress.yaml
│   │   └── kustomization.yaml
│   └── flux-app/            # Manifests managed by Flux CD  → flux-demo namespace
│       ├── namespace.yaml
│       ├── configmap.yaml
│       ├── deployment.yaml
│       ├── service.yaml
│       ├── ingress.yaml
│       └── kustomization.yaml
├── argocd/
│   └── application.yaml     # Argo CD Application CR  (apply once)
└── flux/
    ├── gitrepository.yaml   # Flux GitRepository source (apply once)
    └── kustomization.yaml   # Flux Kustomization CR    (apply once)
```

---

## Prerequisites

| Tool | Check |
|------|-------|
| minikube running | `minikube status` |
| kubectl context set | `kubectl config current-context` → `minikube` |
| Argo CD installed | `kubectl get pods -n argocd` — all Running |
| Flux CD installed | `kubectl get pods -n flux-system` — all Running |

---

## Part 1 — Argo CD

### How Argo CD works

```
Git repo (source of truth)
        │  push commit
        ▼
   Argo CD polls / receives webhook
        │  detects diff
        ▼
   kubectl apply (server-side)
        │
        ▼
   Kubernetes cluster (desired state)
```

Argo CD compares the **live cluster state** against the **desired state in Git**.
Any drift (manual `kubectl edit`, accidental delete, etc.) triggers an automatic revert when `selfHeal: true`.

### Concepts

| Term | Meaning |
|------|---------|
| **Application** | The core CR — points a Git path at a cluster namespace |
| **Project** | Logical grouping of Applications with RBAC boundaries (`default` = unrestricted) |
| **Sync** | Bringing the cluster in line with Git |
| **Prune** | Delete cluster resources that were removed from Git |
| **Self-heal** | Revert manual cluster changes back to what Git says |
| **Health** | Argo CD's own assessment of whether resources are healthy (Deployment ready, pods running, etc.) |

### Step 1 — Register your app

Every app is declared as an `Application` CR in the `argocd` namespace.
The one in this demo ([argocd/application.yaml](argocd/application.yaml)):

```yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: argocd-demo-app
  namespace: argocd                              # always argocd namespace
  finalizers:
    - resources-finalizer.argocd.argoproj.io    # cascade-delete managed resources on app delete
spec:
  project: default

  source:
    repoURL: https://github.com/hatan4ik/aks-troublshoot-guides
    targetRevision: main                         # branch / tag / commit SHA
    path: gitops-demo/apps/argocd-app           # subdirectory within the repo

  destination:
    server: https://kubernetes.default.svc      # in-cluster
    namespace: argocd-demo                      # target namespace

  syncPolicy:
    automated:
      prune: true       # delete resources removed from Git
      selfHeal: true    # revert manual cluster changes
    syncOptions:
      - CreateNamespace=true    # create argocd-demo if it doesn't exist
      - ServerSideApply=true    # use SSA instead of client-side apply
```

Apply it once — Argo CD takes over from there:

```sh
kubectl apply -f gitops-demo/argocd/application.yaml
```

### Step 2 — Watch it sync

```sh
# Real-time status
kubectl get application argocd-demo-app -n argocd -w

# Detailed view — conditions, sync result, events
kubectl describe application argocd-demo-app -n argocd

# Pods in the managed namespace
kubectl get pods -n argocd-demo
```

### Step 3 — Access the Argo CD UI

```sh
kubectl port-forward svc/argocd-server -n argocd 8080:443

# Get the initial admin password
kubectl -n argocd get secret argocd-initial-admin-secret \
  -o jsonpath="{.data.password}" | base64 -d && echo
```

Open **https://localhost:8080** → login as `admin` with the password above.

### Step 4 — Trigger a sync by pushing to Git

```sh
# Edit the deployment replica count
sed -i '' 's/replicas: 2/replicas: 3/' gitops-demo/apps/argocd-app/deployment.yaml
git add gitops-demo/apps/argocd-app/deployment.yaml
git commit -m "scale argocd-demo to 3 replicas"
git push

# Watch Argo CD reconcile (usually within 30s)
kubectl get pods -n argocd-demo -w
```

### Step 5 — Force an immediate sync (without waiting for poll)

```sh
# Requires argocd CLI — install: brew install argocd
argocd app sync argocd-demo-app --server localhost:8080 --insecure
```

### Registering a new Argo CD application (template)

Copy the pattern for any new app:

```yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: my-new-app           # unique name
  namespace: argocd
  finalizers:
    - resources-finalizer.argocd.argoproj.io
spec:
  project: default
  source:
    repoURL: https://github.com/<org>/<repo>
    targetRevision: main
    path: path/to/manifests   # directory with your YAML files
  destination:
    server: https://kubernetes.default.svc
    namespace: my-new-app-ns
  syncPolicy:
    automated:
      prune: true
      selfHeal: true
    syncOptions:
      - CreateNamespace=true
      - ServerSideApply=true
```

```sh
kubectl apply -f my-new-app.yaml
```

### Deleting an Argo CD application

```sh
# This also deletes all managed resources (because of the finalizer)
kubectl delete application argocd-demo-app -n argocd

# To delete just the Application CR without touching cluster resources, remove the finalizer first:
kubectl patch application argocd-demo-app -n argocd \
  -p '{"metadata":{"finalizers":[]}}' --type=merge
kubectl delete application argocd-demo-app -n argocd
```

---

## Part 2 — Flux CD

### How Flux CD works

```
Git repo (source of truth)
        │
        ▼
  GitRepository CR        ← defines WHERE to pull from (URL, branch, interval)
        │  fetches & stores artifact
        ▼
  Kustomization CR        ← defines WHAT to deploy (path, namespace, prune)
        │  applies manifests
        ▼
  Kubernetes cluster
```

Flux is **pull-based and controller-driven** — each CR is a separate controller loop.
There is no central "sync" button; each Kustomization reconciles on its own interval.

### Concepts

| Term | Meaning |
|------|---------|
| **GitRepository** | Source CR — tells Flux where the Git repo is and how often to fetch it |
| **Kustomization** | Deployment CR — tells Flux which path to apply and to which namespace |
| **HelmRelease** | Like Kustomization but for Helm charts |
| **Prune** | Delete cluster resources removed from Git (same as ArgoCD) |
| **Interval** | How often the controller re-reconciles, even with no Git changes |
| **Artifact** | Flux's internal compressed snapshot of the fetched repo contents |

### Step 1 — Declare a GitRepository source

The source ([flux/gitrepository.yaml](flux/gitrepository.yaml)) tells Flux where the repo lives:

```yaml
apiVersion: source.toolkit.fluxcd.io/v1
kind: GitRepository
metadata:
  name: aks-troublshoot-guides
  namespace: flux-system          # Flux controllers live here
spec:
  interval: 1m                    # fetch repo every minute
  url: https://github.com/hatan4ik/aks-troublshoot-guides
  ref:
    branch: main
```

Apply it:

```sh
kubectl apply -f gitops-demo/flux/gitrepository.yaml

# Verify Flux can reach the repo
kubectl get gitrepository aks-troublshoot-guides -n flux-system
# READY column must be True
```

### Step 2 — Declare a Kustomization

The Kustomization ([flux/kustomization.yaml](flux/kustomization.yaml)) points to a path in the fetched repo:

```yaml
apiVersion: kustomize.toolkit.fluxcd.io/v1
kind: Kustomization
metadata:
  name: flux-demo-app
  namespace: flux-system
spec:
  interval: 1m
  sourceRef:
    kind: GitRepository
    name: aks-troublshoot-guides   # must match the GitRepository name above
  path: ./gitops-demo/apps/flux-app
  prune: true                      # delete resources removed from Git
  wait: true                       # block until all resources are Ready
  timeout: 2m
  targetNamespace: flux-demo       # override namespace for all resources
```

Apply it:

```sh
kubectl apply -f gitops-demo/flux/kustomization.yaml

# Verify reconciliation
kubectl get kustomization flux-demo-app -n flux-system
# READY=True, STATUS shows "Applied revision: main@sha1:..."
```

### Step 3 — Watch Flux reconcile

```sh
# All Flux objects at a glance
kubectl get gitrepositories,kustomizations -n flux-system

# Detailed status with conditions
kubectl describe kustomization flux-demo-app -n flux-system

# Pods in the managed namespace
kubectl get pods -n flux-demo
```

### Step 4 — Trigger reconciliation immediately (without waiting for interval)

```sh
# Requires flux CLI — install: brew install fluxcd/tap/flux
flux reconcile source git aks-troublshoot-guides
flux reconcile kustomization flux-demo-app

# Or force via annotation (no CLI needed)
kubectl annotate gitrepository aks-troublshoot-guides -n flux-system \
  reconcile.fluxcd.io/requestedAt="$(date -u +%Y-%m-%dT%H:%M:%SZ)" --overwrite
```

### Registering a new Flux application (template)

**1. Create a GitRepository** (skip if the repo is already registered):

```yaml
apiVersion: source.toolkit.fluxcd.io/v1
kind: GitRepository
metadata:
  name: my-repo
  namespace: flux-system
spec:
  interval: 5m
  url: https://github.com/<org>/<repo>
  ref:
    branch: main
```

**2. Create a Kustomization** pointing at your manifests path:

```yaml
apiVersion: kustomize.toolkit.fluxcd.io/v1
kind: Kustomization
metadata:
  name: my-app
  namespace: flux-system
spec:
  interval: 5m
  sourceRef:
    kind: GitRepository
    name: my-repo
  path: ./path/to/manifests
  prune: true
  targetNamespace: my-app-ns
  syncOptions:
    - CreateNamespace=true
```

> **Note:** The path must contain either plain YAML files or a `kustomization.yaml`.
> The flux-app in this demo uses a `kustomization.yaml` to list its resources explicitly.

### Deleting a Flux application

```sh
# Delete the Kustomization — Flux will prune all managed resources
kubectl delete kustomization flux-demo-app -n flux-system

# Then optionally remove the source
kubectl delete gitrepository aks-troublshoot-guides -n flux-system
```

---

## Part 3 — GitOps loop in practice

## Friendly local URLs with Ingress

The demo apps include Ingress resources for browser-friendly local names:

| App | URL | Service |
|-----|-----|---------|
| Argo CD demo app | `http://argocd-demo.localhost` | `nginx-argocd.argocd-demo.svc.cluster.local` |
| Flux demo app | `http://flux-demo.localhost` | `nginx-flux.flux-demo.svc.cluster.local` |

Enable the Minikube ingress controller:

```sh
minikube addons enable ingress
kubectl wait --namespace ingress-nginx \
  --for=condition=ready pod \
  --selector=app.kubernetes.io/component=controller \
  --timeout=180s
```

Verify the Ingress objects:

```sh
kubectl get ingress -n argocd-demo
kubectl get ingress -n flux-demo
```

For macOS with the Docker Minikube driver, keep a single ingress port-forward running:

```sh
sudo kubectl port-forward -n ingress-nginx svc/ingress-nginx-controller 80:80
```

To make that forward persistent with macOS `launchd`, stop any manual port-forward first, then install the local daemon:

```sh
sudo ./scripts/local/install-minikube-ingress-forward-launchd.sh install
sudo ./scripts/local/install-minikube-ingress-forward-launchd.sh status
```

The daemon keeps `127.0.0.1:80 -> ingress-nginx-controller:80` running and restarts it if it exits. Remove it with:

```sh
sudo ./scripts/local/install-minikube-ingress-forward-launchd.sh uninstall
```

Then open:

```text
http://argocd-demo.localhost
http://flux-demo.localhost
```

If you do not want to bind local port `80`, use a non-privileged forward instead:

```sh
kubectl port-forward -n ingress-nginx svc/ingress-nginx-controller 8088:80
```

Then open:

```text
http://argocd-demo.localhost:8088
http://flux-demo.localhost:8088
```

Optional: the Ingress resources also include `.test` aliases. Configure local wildcard DNS once so every `*.test` hostname resolves to localhost:

```sh
brew install dnsmasq
BREW_PREFIX="$(brew --prefix)"
mkdir -p "$BREW_PREFIX/etc/dnsmasq.d"
printf 'address=/test/127.0.0.1\n' > "$BREW_PREFIX/etc/dnsmasq.d/minikube-test.conf"
echo 'conf-dir='"$BREW_PREFIX"'/etc/dnsmasq.d,*.conf' >> "$BREW_PREFIX/etc/dnsmasq.conf"
sudo mkdir -p /etc/resolver
printf 'nameserver 127.0.0.1\n' | sudo tee /etc/resolver/test
sudo brew services start dnsmasq
```

Then `.test` aliases also work:

```text
http://argocd-demo.test
http://flux-demo.test
```

### The core rule

> **Git is the only source of truth. Never `kubectl apply` app manifests directly.**

| Action | Do this instead |
|--------|----------------|
| Deploy a new version | Update the image tag in Git, push |
| Scale up | Change `replicas` in Git, push |
| Roll back | `git revert` the commit, push |
| Delete a resource | Remove the file from Git, push |

### Repo layout best practices

```
repo/
├── apps/
│   ├── base/           # shared base manifests (DRY)
│   └── overlays/
│       ├── dev/        # kustomize overlay for dev
│       └── prod/       # kustomize overlay for prod
├── clusters/
│   └── minikube/       # cluster-specific Flux/ArgoCD CRs
└── infrastructure/     # shared infra (cert-manager, ingress, etc.)
```

### Verifying the GitOps loop

```sh
# 1. Make a change to a manifest
echo "  replicas: 3" >> gitops-demo/apps/argocd-app/deployment.yaml  # bad example; edit properly
vim gitops-demo/apps/argocd-app/deployment.yaml

# 2. Push
git add . && git commit -m "test: scale to 3" && git push

# 3. Watch both tools react
kubectl get pods -n argocd-demo -w &   # ArgoCD — reacts in ~30s
kubectl get pods -n flux-demo -w &     # Flux — reacts within 1 min (its poll interval)

# 4. Prove self-heal: manually delete a pod — it should come back from Git-driven state
kubectl delete pod -n argocd-demo -l app=nginx-argocd
kubectl get pods -n argocd-demo -w    # ArgoCD re-creates it instantly
```

---

## Quick reference

```sh
# --- Argo CD ---
kubectl get applications -n argocd                                      # list all apps
kubectl get application argocd-demo-app -n argocd                       # status
kubectl describe application argocd-demo-app -n argocd                  # full detail
argocd app sync argocd-demo-app --server localhost:8080 --insecure      # force sync (CLI)
kubectl port-forward svc/argocd-server -n argocd 8080:443               # open UI

# --- Flux CD ---
kubectl get gitrepositories,kustomizations -n flux-system               # list all sources+apps
kubectl describe kustomization flux-demo-app -n flux-system             # full detail
flux reconcile source git aks-troublshoot-guides                        # force source refresh (CLI)
flux reconcile kustomization flux-demo-app                              # force reconcile (CLI)
flux logs --follow                                                      # stream controller logs

# --- Both ---
kubectl get pods -n argocd-demo                                         # ArgoCD-managed pods
kubectl get pods -n flux-demo                                           # Flux-managed pods
bash scripts/diagnostics/gitops-diagnostics.sh                          # full health check
```
