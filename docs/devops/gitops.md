# GitOps Workflows

## Overview
Declarative delivery via controllers (Argo CD/Flux) syncing from Git to clusters.

## Best Practices
- One source of truth; separate env folders/branches.
- Use Kustomize/Helm overlays; sign commits and container images.
- Enforce PR checks (policy, lint, `kubectl diff`).

## Diagnostics
```bash
../../scripts/diagnostics/gitops-diagnostics.sh
kubectl get applications -A   # Argo CD
kubectl get kustomizations -A # Flux
python3 ../../k8s-diagnostics-cli.py detect
python3 ../../k8s-diagnostics-cli.py suggest
```
- Check sync status, health, and drift.
- Inspect controller logs for auth/rate limits.
- The CLI detects unhealthy Argo CD/Flux controllers, unhealthy Argo CD Applications, Flux resources with `Ready=False`, and missing GitOps CRDs.
- The CLI only auto-restarts unhealthy controller-owned pods. Application sync, drift, source, Helm, and auth errors must be fixed in Git or controller configuration.

## Demo Applications
The repo includes a self-contained Argo CD and Flux demo in `gitops-demo/`.

```bash
kubectl apply -f ../../gitops-demo/argocd/application.yaml
kubectl apply -f ../../gitops-demo/flux/gitrepository.yaml -f ../../gitops-demo/flux/kustomization.yaml
```

See `../../gitops-demo/README.md` for the full walkthrough, including how to trigger GitOps reconciliation and access the demo apps with NodePort Services or friendly local Ingress hostnames.

For friendly local URLs, enable the Minikube ingress addon and use the demo Ingress hostnames:

```bash
minikube addons enable ingress
kubectl get ingress -n argocd-demo
kubectl get ingress -n flux-demo
```

```text
http://argocd-demo.localhost
http://flux-demo.localhost
```

On macOS with the Docker Minikube driver, use a local ingress port-forward. The demo also includes optional `.test` host aliases for teams that prefer wildcard DNS through `dnsmasq`; the full command sequence is in `../../gitops-demo/README.md`.

## Argo CD Troubleshooting

### CRD Annotation Too Large During Install
**Symptom**:
```text
The CustomResourceDefinition "applicationsets.argoproj.io" is invalid: metadata.annotations: Too long
```

**Cause**: client-side apply tries to store the large CRD manifest in the `kubectl.kubernetes.io/last-applied-configuration` annotation.

**Resolution**:
```bash
kubectl apply --server-side --force-conflicts -n argocd -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml
```

### Application OutOfSync Or Degraded
**Diagnosis**:
```bash
kubectl get applications -A
kubectl describe application <application-name> -n <namespace>
kubectl logs -n argocd deploy/argocd-application-controller
kubectl logs -n argocd deploy/argocd-repo-server
```

**Common causes**:
- Git path, branch, revision, or Helm/Kustomize values are wrong.
- Repository credentials are missing or expired.
- A live cluster object was changed out-of-band and now differs from Git.
- Argo CD cannot apply a manifest because of RBAC, missing CRD, or admission policy.

**Resolution**:
- Fix the manifest, path, credentials, or policy in Git/controller config.
- If this is an intended rollback, revert the Git commit instead of patching live resources.
- Use Argo sync only after the desired state is correct.

### Argo CD Controller Pods Not Ready
**Diagnosis**:
```bash
kubectl get pods -n argocd
kubectl describe pod <pod-name> -n argocd
kubectl logs <pod-name> -n argocd --all-containers
```

**Safe remediation**:
```bash
python3 ../../k8s-diagnostics-cli.py heal --dry-run
python3 ../../k8s-diagnostics-cli.py heal
```

The tool deletes only unhealthy controller-owned Argo CD pods so their Deployment or StatefulSet can recreate them.

## Flux Troubleshooting

### Flux UI Access
Flux CD does not include a native GUI. In local labs, use Weave GitOps as an optional Flux dashboard.

If Weave GitOps is installed:

```bash
kubectl get helmrelease ww-gitops -n flux-system
kubectl get svc ww-gitops-weave-gitops -n flux-system
kubectl port-forward svc/ww-gitops-weave-gitops -n flux-system 9001:9001
```

Open:

```text
http://localhost:9001
```

Login with the admin password generated during the Weave GitOps install. If the password is lost, generate a new bcrypt hash and update `spec.values.adminUser.passwordHash` on `HelmRelease/ww-gitops`.

### GitRepository Not Ready
**Diagnosis**:
```bash
kubectl get gitrepositories -A
kubectl describe gitrepository <name> -n <namespace>
kubectl logs -n flux-system deploy/source-controller
```

**Common causes**:
- Git URL, branch, tag, or commit revision does not exist.
- SSH key, known_hosts, token, or secret reference is wrong.
- Network policy or proxy blocks the source controller.

**Resolution**: fix the source definition or secret in Git/controller config, then let Flux reconcile.

### Kustomization Not Ready
**Diagnosis**:
```bash
kubectl get kustomizations -A
kubectl describe kustomization <name> -n <namespace>
kubectl logs -n flux-system deploy/kustomize-controller
```

**Common causes**:
- `path` points to the wrong folder.
- `dependsOn` dependency is not ready.
- Manifest validation fails because a CRD is missing.
- An admission policy rejects the generated manifests.

**Resolution**: fix the Kustomization or manifests in Git. Do not patch generated live resources unless you intentionally want drift for an emergency.

### HelmRelease Not Ready
**Diagnosis**:
```bash
kubectl get helmreleases -A
kubectl describe helmrelease <name> -n <namespace>
kubectl logs -n flux-system deploy/helm-controller
```

**Common causes**:
- Chart repository is unreachable.
- Chart version does not exist.
- Values are invalid.
- Helm install/upgrade is blocked by immutable fields or admission policy.

**Resolution**: fix chart source, version, or values in Git. For immutable-field failures, delete/recreate the object only after confirming that Git will recreate the intended resource.

### Flux Controller Pods Not Ready
**Diagnosis**:
```bash
kubectl get pods -n flux-system
kubectl describe pod <pod-name> -n flux-system
kubectl logs <pod-name> -n flux-system --all-containers
```

**Safe remediation**:
```bash
python3 ../../k8s-diagnostics-cli.py heal --dry-run
python3 ../../k8s-diagnostics-cli.py heal
```

The tool deletes only unhealthy controller-owned Flux pods so their Deployment can recreate them.

## Controller Conflict
Do not point Argo CD and Flux at the same application path unless the lab is specifically testing conflict. Symptoms include repeated drift, alternating controller events, and resources changing back after a manual or controller-initiated patch.

## Recovery
- Pause sync for investigations; manual sync with health checks.
- Roll back by reverting Git commit; confirm controller applies cleanly.

## Prevention
- Admission policy to block out-of-band changes.
- Alert on OutOfSync or degraded apps; integrate with `../../scripts/monitoring/health-dashboard.sh`.
