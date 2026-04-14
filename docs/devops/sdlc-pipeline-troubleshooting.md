# SDLC Pipeline Troubleshooting for Kubernetes

## Scope

Use this guide when a change passes source control but fails somewhere between CI, image build, manifest render, GitOps sync, admission control, or runtime rollout.

Debug the pipeline as layers. Do not start by rerunning the whole pipeline:

```text
source -> build -> image registry -> render -> validate -> policy -> GitOps sync -> rollout
```

## Layer 1: Source and Build

Check that the expected commit, branch, and image tag are being built.

```bash
git status --short
git rev-parse --short HEAD
git branch --show-current
```

For container build failures, preserve the failing build log and verify:

- Base image exists and is reachable.
- Dependency lock files are committed.
- Multi-stage build copies the expected artifacts.
- Image tag is immutable or traceable to a commit SHA.
- Security scanning is blocking for a real reason, not stale metadata.

## Layer 2: Registry and Image Pull

The image can build successfully and still fail in Kubernetes.

```bash
kubectl describe pod <pod> -n <namespace>
kubectl get events -n <namespace> --sort-by=.metadata.creationTimestamp | tail -60
kubectl get secret -n <namespace>
kubectl get serviceaccount <serviceaccount> -n <namespace> -o yaml
```

Common causes:

- Wrong image tag or digest.
- Private registry auth missing in the workload namespace.
- Cloud identity cannot pull from ACR, ECR, Artifact Registry, or private registry.
- Image architecture does not match the node architecture.

## Layer 3: Manifest Render

Validate generated Kubernetes YAML before blaming the cluster.

Helm:

```bash
helm lint <chart>
helm template <release> <chart> --namespace <namespace> --values <values-file>
```

Kustomize:

```bash
kubectl kustomize <path>
kubectl apply --dry-run=client -k <path>
```

Generic manifests:

```bash
kubectl apply --dry-run=client -f <path>
kubectl apply --dry-run=server -f <path>
```

Use server dry-run when possible because it catches API server schema, admission, and version behavior that client dry-run cannot.

## Layer 4: CRDs and API Versions

CRD failures are common in GitOps and operator-heavy environments.

```bash
kubectl get crd | grep -Ei "<kind>|argoproj|fluxcd|helm|cert-manager|external-secrets"
kubectl api-resources | grep -Ei "<kind>|<group>"
kubectl explain <kind> --api-version=<group>/<version>
```

Common symptoms:

- `no matches for kind`: CRD missing or installed after the custom resource.
- `unknown field`: CRD version mismatch or chart values for a newer operator.
- Conversion webhook failure: webhook service unavailable or TLS broken.
- Immutable field failure: a field requires replacement instead of patching.

Safe actions:

- Install or upgrade CRDs before applying custom resources.
- Pin chart and CRD versions together.
- Avoid automatic CRD upgrades in the same step as a large application rollout unless tested.

## Layer 5: Policy and Admission

Admission failures should be treated as real deployment failures, not bypassed.

```bash
kubectl get validatingwebhookconfiguration
kubectl get mutatingwebhookconfiguration
kubectl get events -A --sort-by=.metadata.creationTimestamp | tail -100
kubectl auth can-i create pods -n <namespace>
kubectl auth can-i patch deployments -n <namespace>
```

Common causes:

- OPA/Gatekeeper or Kyverno denies missing labels, unsafe security context, hostPath, privileged mode, or untrusted registry.
- Admission webhook timeout blocks all creates in a namespace.
- CI service account has read access but not patch/create access.
- Namespace quota or LimitRange rejects the workload.

## Layer 6: GitOps Sync

Use the repo GitOps diagnostics first:

```bash
./scripts/diagnostics/gitops-diagnostics.sh
./scripts/diagnostics/helm-diagnostics.sh
./scripts/diagnostics/pipeline-debug.sh
```

Argo CD:

```bash
kubectl get applications -A
kubectl describe application <app> -n argocd
kubectl get pods -n argocd
kubectl logs -n argocd deployment/argocd-application-controller --tail=200
```

Flux CD:

```bash
kubectl get gitrepositories,kustomizations,helmreleases -A
kubectl describe gitrepository <name> -n flux-system
kubectl describe kustomization <name> -n flux-system
kubectl describe helmrelease <name> -n flux-system
kubectl get pods -n flux-system
```

Common GitOps failures:

| Symptom | Likely cause | First check |
|---|---|---|
| Argo CD `OutOfSync` | Live drift or generated manifest differs | Application diff and rendered YAML |
| Argo CD `Degraded` | Workload applied but not healthy | Deployment/Pod events |
| Flux `GitRepository` not ready | Repo URL, auth, branch, network | `describe gitrepository` |
| Flux `Kustomization` not ready | Render/apply failure | `describe kustomization` |
| Flux `HelmRelease` not ready | Chart fetch, values, hook timeout | `describe helmrelease` |
| Repeated sync loop | Controller fighting manual changes or another controller | Managed fields, Git history, app ownership |

## Layer 7: Runtime Rollout

If the manifests applied successfully, move to workload health:

```bash
kubectl rollout status deployment/<deployment> -n <namespace>
kubectl describe deployment <deployment> -n <namespace>
kubectl get rs,pods -n <namespace> -o wide
kubectl describe pod <pod> -n <namespace>
kubectl logs <pod> -n <namespace> --all-containers --tail=200
```

Common runtime blockers:

- Bad probes.
- Missing Secret or ConfigMap.
- ImagePullBackOff.
- CrashLoopBackOff.
- PVC Pending.
- Insufficient CPU, memory, GPU, or IP capacity.
- Service selector does not match pod labels.

## Remediation Guardrails

- Prefer fixing the earliest failing layer. Do not patch live manifests if GitOps will revert them.
- Keep CRD upgrades and application upgrades separate unless the release process explicitly supports them.
- For Helm hooks, inspect the hook pod logs before increasing timeouts.
- If admission rejects the change, fix the manifest unless the policy is demonstrably wrong.
- Use roll-forward as the default. Rollback only when the previous version is known compatible with current data and CRDs.

## Interview Signals

A strong answer should explain:

- Why rendered manifests are the debugging boundary between CI and Kubernetes.
- Why Argo CD or Flux may be healthy while the application is degraded.
- Why CRD version skew causes failures even when YAML syntax is valid.
- Why manual hotfixes must be reconciled back into Git in GitOps-managed clusters.
