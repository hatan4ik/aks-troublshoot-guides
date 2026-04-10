# Interview Practice: Broken Kubernetes Manifests

Apply each scenario to a local cluster (`kind` or `minikube`), diagnose the failure using only `kubectl`, and fix it. Each manifest has exactly one bug.

## Setup

```bash
kubectl create namespace practice
```

Apply a scenario:

```bash
kubectl apply -f practice/01-image-pull-backoff.yaml
```

Clean up after each scenario:

```bash
kubectl delete -f practice/01-image-pull-backoff.yaml
```

---

## Scenarios

### Pod Lifecycle

| # | File | Symptom | Skill tested |
| --- | --- | --- | --- |
| 1 | [01-image-pull-backoff.yaml](./01-image-pull-backoff.yaml) | `ImagePullBackOff` | Bad image tag |
| 7 | [07-crashloop-bad-command.yaml](./07-crashloop-bad-command.yaml) | `CrashLoopBackOff`, exit 127 | Bad entrypoint |
| 14 | [14-oomkilled.yaml](./14-oomkilled.yaml) | `OOMKilled`, exit 137 | Memory limit |
| 15 | [15-liveness-kills-healthy-app.yaml](./15-liveness-kills-healthy-app.yaml) | Healthy app restarts every ~30s | Liveness probe timing |
| 16 | [16-init-container-fails.yaml](./16-init-container-fails.yaml) | `Init:CrashLoopBackOff` | Init container |

### Scheduling

| # | File | Symptom | Skill tested |
| --- | --- | --- | --- |
| 6 | [06-pending-resources.yaml](./06-pending-resources.yaml) | `Pending` — Insufficient cpu | Resource requests |
| 8 | [08-taint-no-toleration.yaml](./08-taint-no-toleration.yaml) | `Pending` — node tainted | Taint/Toleration |
| 9 | [09-node-selector-no-match.yaml](./09-node-selector-no-match.yaml) | `Pending` — no matching node | nodeSelector |

### Configuration

| # | File | Symptom | Skill tested |
| --- | --- | --- | --- |
| 5 | [05-missing-configmap-key.yaml](./05-missing-configmap-key.yaml) | `CreateContainerConfigError` | ConfigMap key name |
| 17 | [17-wrong-secret-name.yaml](./17-wrong-secret-name.yaml) | `CreateContainerError` | Secret object missing |
| 12 | [12-missing-image-pull-secret.yaml](./12-missing-image-pull-secret.yaml) | `ImagePullBackOff` (auth error) | imagePullSecret |

### Networking & Traffic

| # | File | Symptom | Skill tested |
| --- | --- | --- | --- |
| 2 | [02-port-mismatch.yaml](./02-port-mismatch.yaml) | Pod Running, curl fails | targetPort |
| 3 | [03-selector-mismatch.yaml](./03-selector-mismatch.yaml) | Endpoints empty | Service selector |
| 4 | [04-bad-probe.yaml](./04-bad-probe.yaml) | Pod never Ready (0/1) | Readiness probe path |
| 10 | [10-networkpolicy-blocks-ingress.yaml](./10-networkpolicy-blocks-ingress.yaml) | Pod Running, traffic times out | NetworkPolicy |
| 11 | [11-ingress-wrong-service.yaml](./11-ingress-wrong-service.yaml) | Ingress returns 503 | Ingress backend |

### Storage

| # | File | Symptom | Skill tested |
| --- | --- | --- | --- |
| 13 | [13-pvc-wrong-storageclass.yaml](./13-pvc-wrong-storageclass.yaml) | Pod Pending, PVC Pending | StorageClass |

### Stateful Workloads & Jobs

| # | File | Symptom | Skill tested |
| --- | --- | --- | --- |
| 18 | [18-statefulset-missing-headless-svc.yaml](./18-statefulset-missing-headless-svc.yaml) | StatefulSet pods can't use stable DNS | Headless Service |
| 19 | [19-job-backoff-exceeded.yaml](./19-job-backoff-exceeded.yaml) | Job fails, `BackoffLimitExceeded` | Job debugging |

---

## Investigation Pattern (use every time)

```bash
# Step 1 — big picture
kubectl get pods -n practice
kubectl get events -n practice --sort-by=.metadata.creationTimestamp | tail -20

# Step 2 — zoom in
kubectl describe pod <pod> -n practice
kubectl logs <pod> -n practice --previous

# Step 3 — service wiring (for networking bugs)
kubectl get endpoints -n practice
kubectl describe svc <svc> -n practice

# Step 4 — storage (for PVC bugs)
kubectl get pvc -n practice
kubectl describe pvc <pvc> -n practice
kubectl get storageclass

# Step 5 — scheduling (for Pending bugs)
kubectl describe pod <pod> -n practice   # Events section: reason for not scheduling
kubectl get nodes --show-labels
kubectl describe node <node>
```

### Exit Code Quick Reference

| Code | Meaning |
| --- | --- |
| 0 | Clean exit (check: should this be a Job?) |
| 1 | App error (bad config, unhandled exception) |
| 127 | Command not found — bad entrypoint |
| 137 | SIGKILL — usually OOMKilled |
| 139 | Segmentation fault |
| 143 | SIGTERM — graceful shutdown |

---

## Check your answers

See [SOLUTIONS.md](./SOLUTIONS.md) — diagnose first.
