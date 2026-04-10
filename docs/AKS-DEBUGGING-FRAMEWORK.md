# AKS Debugging Framework

The structured mental model for diagnosing failures in an AKS cluster. Use this before opening any runbook. It tells you which layer to investigate and in what order.

---

## The 5-Layer Model

Every AKS failure lives in exactly one of these layers. Diagnose top-down — do not jump to layer 5 when the problem is in layer 1.

```
Layer 1 │ Pod Lifecycle      │ Scheduling, image pull, startup, probes, config
Layer 2 │ Container Runtime  │ OOM, cgroups, exit codes, containerd
Layer 3 │ Service Networking │ Selector, endpoints, ports, DNS, Ingress
Layer 4 │ Cluster Infra      │ Nodes, CNI, CoreDNS, NetworkPolicy, etcd
Layer 5 │ Azure Infra        │ NSG, Load Balancer, VNet, UDR, Storage, DNS
```

**The key discipline:** do not escalate to a deeper layer until you have eliminated the one above it. 90% of failures are in layers 1–3 and are fixable with `kubectl` alone.

---

## Decision Tree

Start here every time. Follow the branch that matches what you observe.

```
kubectl get pods -A
        │
        ├── Pending ──────────────────────────────────────────────────┐
        │   kubectl describe pod → Events                             │
        │   ├── "Insufficient cpu/memory"  → Layer 1: lower requests  │
        │   ├── "Untolerated taint"        → Layer 1: add toleration  │
        │   ├── "node affinity/selector"   → Layer 1: fix nodeSelector│
        │   └── "Unbound PVC"             → Layer 5: storage          │
        │                                                              │
        ├── ImagePullBackOff / ErrImagePull ───────────────────────── │
        │   kubectl describe pod → Events                             │
        │   ├── "manifest unknown" / "tag" → Layer 1: fix image tag   │
        │   ├── "unauthorized"             → Layer 1: imagePullSecret  │
        │   └── "timeout" / "no route"    → Layer 4/5: network/NSG   │
        │                                                              │
        ├── Init:CrashLoopBackOff / Init:Error ───────────────────── │
        │   kubectl logs <pod> -c <init-container>                    │
        │   └── Init container failing     → Layer 1: fix init cmd    │
        │       (dependency not ready)     → Layer 3: service missing  │
        │                                                              │
        ├── CrashLoopBackOff / Error ─────────────────────────────── │
        │   kubectl describe pod → LastState.ExitCode                 │
        │   ├── Exit 127  → bad command/entrypoint → Layer 1          │
        │   ├── Exit 137  → OOMKilled             → Layer 2           │
        │   ├── Exit 1    → app error              → Layer 1: logs    │
        │   ├── Exit 143  → SIGTERM (probe?)       → Layer 1: liveness│
        │   └── Empty logs → check runtime layer   → Layer 2          │
        │                                                              │
        ├── Running — READY 0/1 (not Ready) ─────────────────────── │
        │   kubectl describe pod → Events                             │
        │   ├── "Readiness probe failed: 404" → Layer 1: probe path  │
        │   ├── "connection refused"          → Layer 1: probe port   │
        │   └── "timeout"                    → Layer 1: initialDelay │
        │                                                              │
        └── Running — READY 1/1 — traffic fails ─────────────────── │
            │                                                          │
            ├── "connection refused" ─────────────────────────── Layer 3
            │   kubectl get endpoints → empty?
            │   ├── Empty  → service selector mismatch
            │   └── Populated → wrong targetPort
            │
            ├── "connection timed out" ──────────────────────── Layer 4/5
            │   kubectl get networkpolicy → deny-all present?
            │   ├── Yes → NetworkPolicy blocking → Layer 4
            │   └── No  → NSG / UDR blocking    → Layer 5
            │
            └── Ingress 503 / 404 ──────────────────────────── Layer 3/5
                kubectl describe ingress → backend service correct?
                ├── Wrong service name/port → Layer 3
                └── ALB / AGIC not provisioning → Layer 5
```

---

## Layer 1 — Pod Lifecycle

**Scope:** anything you can diagnose without leaving the pod/deployment.

```bash
kubectl describe pod <pod> -n <ns>          # events + state
kubectl logs <pod> -n <ns> --previous       # app output before crash
kubectl get pod <pod> -n <ns> -o yaml       # full spec including probes, env, volumes
```

**What to look for:**
- Events section at the bottom — usually names the root cause directly
- `LastState.Terminated.ExitCode` — see exit code reference below
- `containerStatuses[].ready` — false with running = readiness probe failing
- `env` / `envFrom` — references to missing Secrets or ConfigMaps

**Exit code reference:**

| Code | Meaning |
| --- | --- |
| 0 | Clean exit — should this be a Job? |
| 1 | App error — check logs |
| 127 | Command not found — fix `command:` |
| 137 | SIGKILL — OOMKilled → Layer 2 |
| 139 | Segfault |
| 143 | SIGTERM — liveness probe too aggressive? |

---

## Layer 2 — Container Runtime

**Scope:** the process was scheduled and started but died due to kernel or runtime limits.

**Trigger:** exit code 137 (OOMKilled) or silent crash with empty logs.

```bash
kubectl describe pod <pod> -n <ns>
# Containers → Last State → Reason: OOMKilled

kubectl top pod <pod> -n <ns>
# Actual memory consumption

# On the node (SSH or kubectl debug on node):
dmesg | grep -i "killed process"            # kernel OOM killer evidence
crictl ps -a                                 # all containers including exited
journalctl -u containerd --no-pager | tail -50
```

**Fix:** raise memory limits. Add `startupProbe` if app is slow to start and liveness fires early.

---

## Layer 3 — Service Networking

**Scope:** the pod is Running and Ready but traffic does not reach it, or service discovery fails.

**The chain to verify — in order:**

```bash
# 1. Pod is Ready
kubectl get pod <pod> -n <ns>                     # READY = 1/1

# 2. Service selector matches pod labels
kubectl get svc <svc> -n <ns> -o yaml | grep -A5 selector
kubectl get pod <pod> -n <ns> --show-labels

# 3. Endpoints are populated
kubectl get endpoints <svc> -n <ns>               # must not be <none>

# 4. Port mapping is correct
kubectl describe svc <svc> -n <ns>                # targetPort matches containerPort

# 5. DNS resolves inside the cluster
kubectl run dns-test --image=busybox --rm -it --restart=Never -- \
  nslookup <svc>.<ns>.svc.cluster.local

# 6. Ingress backend points to correct service
kubectl describe ingress -n <ns>
```

**Key insight:** empty endpoints = selector problem. Populated endpoints but curl fails = port problem. Timeout with correct ports = Layer 4.

---

## Layer 4 — Cluster Infrastructure

**Scope:** nodes, CNI plugin, CoreDNS, NetworkPolicy, and cluster-level components.

**Node health:**
```bash
kubectl get nodes
kubectl describe node <node>
# Look for: Taints, Conditions (MemoryPressure, DiskPressure), Allocatable

# On the node:
systemctl status kubelet
journalctl -u kubelet -n 50 --no-pager
```

**CNI health:**
```bash
kubectl get pods -n kube-system               # CNI daemonset pods healthy?
kubectl get pods -n kube-system -l k8s-app=azure-cni   # AKS: azure-cni pods
kubectl logs -n kube-system -l k8s-app=azure-cni --tail=30

# Pod-to-pod connectivity test:
kubectl run nettest --image=nicolaka/netshoot --rm -it --restart=Never -- \
  ping <pod-ip>
```

**CoreDNS:**
```bash
kubectl get pods -n kube-system -l k8s-app=kube-dns
kubectl logs -n kube-system -l k8s-app=kube-dns --tail=30
# 5-second DNS timeout = conntrack race → consider NodeLocalDNSCache
```

**NetworkPolicy:**
```bash
kubectl get networkpolicy -A
# An Ingress policyType with no ingress rules = deny all
# Timeout (not refused) = NetworkPolicy or NSG — check here first
```

---

## Layer 5 — Azure Infrastructure

**Scope:** failures that cannot be diagnosed with `kubectl` alone. Requires Azure Portal, `az` CLI, or cloud provider logs.

**When to go here:**
- Layer 1–4 investigation is clean, but the failure persists
- `ImagePullBackOff` with timeout (not auth) — check NSG egress to ACR
- Load Balancer not provisioning — check Azure events
- PVC stuck — check Azure Disk / File availability in zone
- DNS resolution fails outside cluster — check Private DNS zones

```bash
# Azure CLI — cluster and node health
az aks show -g <rg> -n <cluster> --query 'provisioningState'
az aks get-credentials -g <rg> -n <cluster>

# Node pool events
az aks nodepool list -g <rg> --cluster-name <cluster>

# NSG rules affecting the cluster
az network nsg list -g <node-rg> -o table
az network nsg rule list -g <node-rg> --nsg-name <nsg> -o table

# Azure Load Balancer health
az network lb show -g <node-rg> -n <lb-name>
az network lb probe list -g <node-rg> --lb-name <lb-name> -o table
```

See [azure/aks-networking.md](./azure/aks-networking.md) for detailed Azure networking investigation.
See [azure/azure-observability.md](./azure/azure-observability.md) for Log Analytics and Azure Monitor queries.

---

## The Golden Debug Flow

Run these 5 commands at the start of every investigation, no matter what. They give you the full picture in under 2 minutes.

```bash
# 1. Where am I?
kubectl config current-context

# 2. What namespaces exist?
kubectl get ns

# 3. What is broken?
kubectl get pods -A --sort-by='.status.containerStatuses[0].restartCount'

# 4. What just happened?
kubectl get events -A --sort-by=.metadata.creationTimestamp | tail -30

# 5. Are the nodes healthy?
kubectl get nodes
```

---

## When to Escalate to Azure Support

Open a support ticket when:
- Node is `NotReady` and kubelet is healthy — cloud VM or host agent issue
- Load Balancer or Public IP not provisioning after 10 minutes — Azure control plane
- Azure Disk attachment fails across multiple attempts — regional storage issue
- CNI plugin (azure-cni) pod is crashing — AKS node image issue
- Cluster upgrade or node pool scaling is stuck — AKS control plane

Before escalating, collect:
```bash
az aks get-upgrades -g <rg> -n <cluster>
az aks show -g <rg> -n <cluster> > cluster-state.json
kubectl get events -A --sort-by=.metadata.creationTimestamp > events.txt
kubectl get pods -A -o wide > pods.txt
```
