# Local Cluster Debugging

Use this guide when the lab environment itself is broken: Docker Desktop is unhealthy, the Minikube profile will not start, `kubectl` points at a dead local API server, or the local control plane is only partially up.

This guide is for local environments such as:
- Docker Desktop + Minikube
- `kubectl` against a local Minikube profile
- local rehearsal clusters used before AKS, EKS, GKE, or bare-metal work

Do not use this as the primary workflow for production or shared clusters. For application failures inside a healthy cluster, start with [DEBUG-RUNBOOK.md](../DEBUG-RUNBOOK.md) and [LIVE-DEBUG-WORKFLOW.md](./LIVE-DEBUG-WORKFLOW.md).

## When To Use This Guide

Common symptoms:
- `minikube start` hangs or exits before the API server is ready
- `minikube status` shows `Host: Running` but `Kubelet` or `APIServer` is stopped
- `kubectl` points to `127.0.0.1:<port>` and cannot connect
- Docker Desktop has no working socket, wrong context, or a dead daemon
- the `minikube` container exists, but the control plane inside it is down

## Recovery Order

Keep the order strict. Do not delete the cluster first.

1. Confirm Docker health.
2. Confirm Minikube profile health.
3. Confirm kubeconfig and current context.
4. Inspect the control plane inside the Minikube node.
5. Try an in-place `minikube start`.
6. Recreate the profile only if recovery-in-place fails or the profile is clearly stale/corrupt.

## Read-Only Triage

Use the repo's local doctor script first:

```bash
./scripts/local/minikube-doctor.sh
```

Manual checks:

```bash
docker context ls
docker version
docker ps -a --filter name='^minikube$'

minikube version
minikube profile list
minikube status

kubectl config current-context
kubectl config view --minify
kubectl get nodes --request-timeout=5s
```

Interpretation:
- If Docker is down, Minikube cannot recover.
- If Docker is healthy and the `minikube` container exists, prefer recovery in place.
- If kubeconfig points to a dead `127.0.0.1:<port>`, the profile may be half-started or the context may be stale.

## Docker Checks

On Docker Desktop, the usual failure boundary is the Docker socket, not Kubernetes.

Check:

```bash
docker context show
docker info
docker ps -a
```

Typical failure patterns:
- `permission denied while trying to connect to the docker API`
- `no such file or directory` for `~/.docker/run/docker.sock`
- Docker UI is open but `docker info` still fails

Repair:
- Start Docker Desktop and wait for the daemon to answer `docker info`
- Recheck the active Docker context
- Do not touch Minikube until Docker is healthy

## Minikube Checks

Once Docker is healthy:

```bash
minikube status --output=json
minikube logs --problems --profile=minikube
```

High-value states:
- `Host: Stopped`: the profile is down; start it
- `Host: Running`, `Kubelet: Stopped`, `APIServer: Stopped`: the Minikube container is alive but the control plane is broken
- `Kubeconfig: Configured` with an unreachable API server: the local context exists, but the cluster is not healthy yet

## Inspect The Node

If the Minikube container is reachable, inspect inside it before deleting anything:

```bash
minikube ssh -- 'sudo systemctl is-active kubelet'
minikube ssh -- 'sudo crictl ps -a | egrep "kube-apiserver|etcd|kube-controller|kube-scheduler"'
minikube ssh -- 'sudo journalctl -u kubelet -n 100 --no-pager'
```

What this tells you:
- whether `kubelet` is actually running
- whether static control-plane containers are restarting or exited
- whether the manifests still exist under `/etc/kubernetes/manifests`

## Safe Recovery Ladder

### 1. In-place Start

This is the first mutating step:

```bash
minikube start --driver=docker
```

Use the repo helper if you want a repeatable wrapper:

```bash
./scripts/local/restart-minikube.sh
```

This is the preferred path when:
- Docker is healthy
- the `minikube` container already exists
- the profile mostly worked before
- cluster state matters and you want to preserve it

### 2. Stop And Start

Use this only if the profile is wedged but still identifiable:

```bash
minikube stop
minikube start --driver=docker
```

### 3. Recreate The Profile

This is destructive. Use it only when:
- profile image and Minikube binary versions have drifted badly
- kubeconfig repair and in-place start both fail
- control-plane services remain dead after restart attempts
- you do not need to preserve the current local cluster state

```bash
./scripts/local/restart-minikube.sh --recreate
```

Equivalent manual path:

```bash
minikube delete
minikube start --driver=docker
```

## Kubeconfig Drift

If the cluster is healthy but `kubectl` still points at the wrong endpoint:

```bash
kubectl config current-context
minikube update-context
kubectl config view --minify
```

Confirm that:
- current context is `minikube`
- the cluster endpoint matches the latest Minikube API port
- the client cert paths still point into `~/.minikube`

## Verification

Do not stop at "start completed". Verify the cluster is usable:

```bash
minikube status --output=json
kubectl get nodes -o wide
kubectl get pods -A
```

Healthy outcome:
- `Host`, `Kubelet`, and `APIServer` are all `Running`
- the `minikube` node is `Ready`
- `kube-system` control-plane pods are `Running`

## Repo Tools

Use these repo tools for local platform work:
- [scripts/local/minikube-doctor.sh](../scripts/local/minikube-doctor.sh): read-only checks for Docker, Minikube, kubeconfig, and cluster reachability
- [scripts/local/restart-minikube.sh](../scripts/local/restart-minikube.sh): safe recovery wrapper with an explicit `--recreate` path

Use these repo tools for application-level debugging after the local platform is healthy:
- [DEBUG-RUNBOOK.md](../DEBUG-RUNBOOK.md)
- [LIVE-DEBUG-WORKFLOW.md](./LIVE-DEBUG-WORKFLOW.md)
- [playbooks/common-issues.md](../playbooks/common-issues.md)
