# Kubernetes Live Debug — Operations Runbook

---

## Quick Navigation

| What `kubectl get pods` shows | Jump to |
| --- | --- |
| `Pending` | [Scheduling](#scheduling) |
| `ImagePullBackOff` / `ErrImagePull` | [Image Pull](#image-pull) |
| `CrashLoopBackOff` / `Error` | [Container Crash](#container-crash) |
| `OOMKilled` — or exit code 137 | [OOM Killed](#oom-killed) |
| `Init:CrashLoopBackOff` / `Init:Error` / `Init:0/1` | [Init Container](#init-container) |
| Pod `Running` but `0/1` — not Ready | [Readiness Probe](#readiness-probe) |
| `ContainerCreating` — stuck | [Volume Mount](#volume-mount) |
| Pod Running, traffic fails / connection refused | [Service Networking](#service-networking) |
| Ingress returns `503` / `404` | [Ingress](#ingress) |
| Traffic times out, pod is reachable directly | [NetworkPolicy](#networkpolicy) |
| PVC shows `Pending` | [Storage / PVC](#storage--pvc) |
| Job shows `Failed` / `BackoffLimitExceeded` | [Jobs](#jobs) |
| Node shows `NotReady` | [Node NotReady](#node-notready) |

---

## Engineering Mental Models

Apply these principles when debugging. They reflect systems thinking, not command memorization.

**On your debugging approach:**
> "Most guides are case-based, but I prefer a layered model — I start from pod health, then service routing, then cluster networking, then cloud infrastructure like NSGs and load balancers. That way I never jump to the network layer when the problem is actually a missing ConfigMap key."

**On where to start:**
> "Before I run a single command I read the events — events tell me *why* something failed, `kubectl top` tells me *what* the state is. I want the why first."

**On not guessing:**
> "I won't make a change until I can state the symptom, the root cause, and the exact field I'm about to patch. If I can't do all three, I'm still in the investigation phase."

**On the two failure paths:**
> "Every failure is either a scheduling problem — the pod never ran — or a runtime problem — it ran and then broke. That split tells me immediately whether to look at node capacity and taints, or at logs and probes."

**On connection refused vs timeout:**
> "Connection refused means the app layer rejected it — wrong port, app not listening, probe path wrong. Timeout means the network layer dropped it — NetworkPolicy, NSG, routing. That one distinction cuts the search space in half before I run anything."

**On monitoring blind spots:**
> "If someone says OOMKilled but Prometheus shows 60% memory usage, I don't argue with Prometheus — I explain that it scrapes every 30 seconds. A memory spike that kills the pod in 100ms simply won't appear in the graph."

**On immutability gotchas:**
> "Two things that catch everyone in production: Jobs and PVCs are both immutable after creation. You cannot patch them — you delete and re-create. Knowing that saves five minutes of confused `kubectl patch` failures."

**On readiness vs liveness:**
> "Readiness answers: should this pod receive traffic? Liveness answers: should this pod be restarted? Mixing them up is the most common probe mistake I see in production — a liveness probe that's too aggressive will restart a healthy app on every slow startup."

---

## Step 0 — Always Run First

Before touching anything. Takes 60 seconds. Narrate what you see.

```bash
kubectl config current-context                                           # confirm you're in the right cluster
kubectl get ns                                                           # find the relevant namespace
kubectl get pods -A                                                      # spot what's broken
kubectl get events -A --sort-by=.metadata.creationTimestamp | tail -30  # events often name the root cause directly
```

---

## Scheduling

**Symptom:** Pod stays `Pending`. No container ever starts.

```bash
kubectl describe pod <pod> -n <ns>
# Read the Events section at the bottom — it names the exact reason

kubectl get nodes
kubectl describe node <node>
# Look for: Taints, Allocatable resources, Conditions
```

**Events tell you which sub-case:**

| Event message | Cause | Fix |
| --- | --- | --- |
| `Insufficient cpu` / `Insufficient memory` | Requests exceed node capacity | Lower requests or add nodes |
| `node(s) had untolerated taint` | Taint with no toleration | Add `tolerations:` to pod spec |
| `didn't match Pod's node affinity/selector` | nodeSelector / affinity no match | Remove or fix `nodeSelector`, or label a node |
| `pod has unbound PersistentVolumeClaims` | PVC not bound | See [Storage](#storage--pvc) |

**Fix — resource requests too high:**
```bash
kubectl patch deployment <deploy> -n <ns> --type='json' -p='[
  {"op":"replace","path":"/spec/template/spec/containers/0/resources/requests/cpu","value":"100m"},
  {"op":"replace","path":"/spec/template/spec/containers/0/resources/limits/cpu","value":"200m"}
]'
```

**Fix — taint with no toleration:**
```bash
kubectl patch deployment <deploy> -n <ns> --type='json' -p='[
  {"op":"add","path":"/spec/template/spec/tolerations","value":[
    {"key":"<taint-key>","operator":"Equal","value":"<taint-value>","effect":"NoSchedule"}
  ]}
]'
```

**Fix — nodeSelector matches no node:**
```bash
kubectl patch deployment <deploy> -n <ns> --type='json' \
  -p='[{"op":"remove","path":"/spec/template/spec/nodeSelector"}]'
```

→ Deeper: [docs/engineers/pod-startup-issues.md](docs/engineers/pod-startup-issues.md)

---

## Image Pull

**Symptom:** `ImagePullBackOff` or `ErrImagePull`

```bash
kubectl describe pod <pod> -n <ns>
# Events: "Failed to pull image..." — read the exact error message
```

| Error message | Cause | Fix |
| --- | --- | --- |
| `manifest unknown` / `tag does not exist` | Wrong image tag | Fix the image tag |
| `unauthorized` / `authentication required` | Missing or wrong imagePullSecret | Add `imagePullSecrets:` |
| `connection refused` / `no route to host` | Network / firewall to registry | Check egress NetworkPolicy or firewall |
| `toomanyrequests` | Docker Hub rate limit | Use authenticated pull or a mirror |

**Fix — wrong tag:**
```bash
kubectl set image deployment/<deploy> <container>=<image>:<correct-tag> -n <ns>
```

**Fix — missing imagePullSecret:**
```bash
kubectl create secret docker-registry <secret-name> \
  --docker-server=<registry> \
  --docker-username=<user> \
  --docker-password=<token> \
  -n <ns>

kubectl patch deployment <deploy> -n <ns> --type='json' -p='[
  {"op":"add","path":"/spec/template/spec/imagePullSecrets","value":[{"name":"<secret-name>"}]}
]'
```

→ Deeper: [docs/devops/registry-issues.md](docs/devops/registry-issues.md)

---

## Container Crash

**Symptom:** `CrashLoopBackOff` or `Error`

> **Principle:** "My first move is always the exit code, not the logs. If the process never wrote to stdout, logs are empty — but the exit code is always there."

**First: read the exit code — it tells you the category of failure.**

```bash
kubectl describe pod <pod> -n <ns>
# Last State → Terminated → Exit Code

kubectl logs <pod> -n <ns> --previous
# App output before crash — often shows the exact error
```

| Exit code | Meaning | Where to look |
| --- | --- | --- |
| `0` | App exited cleanly — wrong for long-running service | Should this be a Job? |
| `1` | App error — bad config, unhandled exception | App logs |
| `127` | Command not found — bad entrypoint | Check `command:` / `args:` in spec |
| `137` | SIGKILL — OOMKilled | See [OOM Killed](#oom-killed) |
| `139` | Segfault | Binary or library issue |
| `143` | SIGTERM — graceful shutdown triggered unexpectedly | Liveness probe? `preStop`? |

**Fix — bad entrypoint (exit 127):**
```bash
# Remove the command override — let the image use its default entrypoint
kubectl patch deployment <deploy> -n <ns> --type='json' \
  -p='[{"op":"remove","path":"/spec/template/spec/containers/0/command"}]'
```

**Fix — missing env / config (exit 1, logs show missing var):**
```bash
kubectl get pod <pod> -n <ns> -o yaml | grep -A5 env
# Verify env vars match what the app expects

kubectl get configmap <cm> -n <ns> -o yaml
kubectl get secret <secret> -n <ns> -o yaml
```

→ Deeper: [docs/engineers/debugging-techniques.md](docs/engineers/debugging-techniques.md)

---

## OOM Killed

**Symptom:** Pod restarts with exit code `137`. `kubectl describe` shows `OOMKilled: true`.

> **Principle:** "If someone points to Prometheus showing 60% memory usage — Prometheus scrapes every 30s. A spike that kills the pod in under a second won't appear in the graph. The exit code 137 is the ground truth."

```bash
kubectl describe pod <pod> -n <ns>
# Containers → Last State → Reason: OOMKilled
# Containers → Limits → memory: <current limit>

kubectl top pod -n <ns>
# Actual memory usage vs limit
```

**On the node (if you have SSH access):**
```bash
dmesg | grep -i "killed process"
# Confirms kernel OOM killer fired and names the process
```

**Fix — raise the memory limit:**
```bash
kubectl patch deployment <deploy> -n <ns> --type='json' -p='[
  {"op":"replace","path":"/spec/template/spec/containers/0/resources/requests/memory","value":"512Mi"},
  {"op":"replace","path":"/spec/template/spec/containers/0/resources/limits/memory","value":"512Mi"}
]'
```

→ Deeper: [docs/engineers/debugging-techniques.md](docs/engineers/debugging-techniques.md)

---

## Init Container

**Symptom:** `Init:CrashLoopBackOff`, `Init:Error`, or `Init:0/1`

The main container never starts until **all** init containers exit 0.

```bash
kubectl get pod <pod> -n <ns>
# STATUS: Init:0/2 means 0 of 2 init containers completed

kubectl describe pod <pod> -n <ns>
# Init Containers section — check State and Exit Code of each one

kubectl logs <pod> -n <ns> -c <init-container-name>
kubectl logs <pod> -n <ns> -c <init-container-name> --previous
# Logs from the failing init container
```

**Common causes:**
- Init container checks for a service that does not exist yet
- Init container runs a migration against a database that is unreachable
- Wrong command or binary path in init container spec

**Interview trap — ConfigMap warning, but init dependency is the blocker:**

If events show a warning like `failed to sync configmap cache: timed out waiting for the condition`, first verify whether the ConfigMap actually exists. That warning can be a stale or secondary kubelet/API-cache symptom.

```bash
kubectl get configmap <cm-name> -n <ns>
kubectl get pod <pod> -n <ns>
```

If the pod is still `Init:0/1`, the next decisive signal is the init container log:

```bash
kubectl logs <pod> -n <ns> -c <init-container> --tail=30
# Example: config-service not ready, retrying in 2s...
```

Then verify the dependency Service and endpoints:

```bash
kubectl get svc,endpoints,endpointslice -n <ns> | grep <service-name>
kubectl describe svc <service-name> -n <ns>
kubectl get pods -n <ns> --show-labels
```

If the Service is missing, create it with the correct backing pods. If the Service exists but endpoints are empty, fix the Service selector or the backing pods' readiness.

**Fix — remove init container (for testing only):**
```bash
kubectl patch deployment <deploy> -n <ns> --type='json' \
  -p='[{"op":"remove","path":"/spec/template/spec/initContainers"}]'
```

→ Deeper: [docs/engineers/pod-startup-issues.md](docs/engineers/pod-startup-issues.md)

---

## Readiness Probe

**Symptom:** Pod is `Running` but shows `0/1` READY. Service has no endpoints.

```bash
kubectl describe pod <pod> -n <ns>
# Events: "Readiness probe failed: ..."
# Containers → Ready: False

kubectl get endpoints <svc> -n <ns>
# <none> — pod not added to service because it is not Ready
```

| Probe error | Cause | Fix |
| --- | --- | --- |
| `HTTP probe failed: 404` | Wrong path in probe | Fix `readinessProbe.httpGet.path` |
| `connection refused` | Wrong port in probe | Fix `readinessProbe.httpGet.port` |
| `context deadline exceeded` | App too slow / `initialDelaySeconds` too low | Increase `initialDelaySeconds` |
| Liveness also failing → restarts | Liveness fires before app is ready | Increase `initialDelaySeconds` or add `startupProbe` |

**Fix — wrong probe path:**
```bash
kubectl patch deployment <deploy> -n <ns> --type='json' -p='[
  {"op":"replace","path":"/spec/template/spec/containers/0/readinessProbe/httpGet/path","value":"/health"}
]'
```

**Fix — liveness probe kills app before it finishes starting:**
```bash
kubectl patch deployment <deploy> -n <ns> --type='json' -p='[
  {"op":"replace","path":"/spec/template/spec/containers/0/livenessProbe/initialDelaySeconds","value":60},
  {"op":"replace","path":"/spec/template/spec/containers/0/livenessProbe/failureThreshold","value":5}
]'
```

→ Deeper: [docs/engineers/pod-startup-issues.md](docs/engineers/pod-startup-issues.md)

---

## Volume Mount

**Symptom:** Pod stuck in `ContainerCreating`

```bash
kubectl describe pod <pod> -n <ns>
# Events: "Unable to mount volumes" or "AttachVolume failed" or "secret not found"

kubectl get pvc -n <ns>
# If PVC is Pending → see Storage section below

kubectl get events -n <ns> --sort-by=.metadata.creationTimestamp | tail -20
```

**Common causes:**
- PVC not bound — see [Storage](#storage--pvc)
- RWO volume still attached to a different (dead) node
- ConfigMap or Secret referenced in a volume does not exist

**Fix — ConfigMap or Secret volume reference missing:**
```bash
kubectl get pod <pod> -n <ns> -o yaml | grep -A8 volumes
# Find the name, then verify:
kubectl get secret <name> -n <ns>
kubectl get configmap <name> -n <ns>
# Create the missing object, pod will auto-retry mounting
```

---

## Service Networking

**Symptom:** Pod `Running` and `Ready`. Service exists. `curl` returns `connection refused` or no response.

> **Principle:** "I always work the chain in order — pod Ready, selector matches labels, endpoints populated, targetPort correct. I never skip a step because each one eliminates an entire class of causes."

**Work the chain: pod → labels → service selector → endpoints → port.**

```bash
# 1. Is the pod actually Ready?
kubectl get pod <pod> -n <ns>                         # READY must be 1/1

# 2. Does the service selector match pod labels?
kubectl get svc <svc> -n <ns> -o yaml | grep -A5 selector
kubectl get pod <pod> -n <ns> --show-labels           # labels must match selector exactly

# 3. Are endpoints populated?
kubectl get endpoints <svc> -n <ns>                   # must not be <none>

# 4. Is targetPort correct?
kubectl describe svc <svc> -n <ns>                    # targetPort must match containerPort
kubectl get pod <pod> -n <ns> -o yaml | grep -A3 ports
```

**Fix — selector mismatch (endpoints are empty):**
```bash
kubectl patch svc <svc> -n <ns> --type='json' \
  -p='[{"op":"replace","path":"/spec/selector/app","value":"<correct-label-value>"}]'
```

**Fix — wrong targetPort (endpoints exist but curl fails):**
```bash
kubectl patch svc <svc> -n <ns> --type='json' \
  -p='[{"op":"replace","path":"/spec/ports/0/targetPort","value":<correct-port>}]'
```

→ Deeper: [docs/engineers/debugging-techniques.md](docs/engineers/debugging-techniques.md)

---

## Ingress

**Symptom:** Ingress returns `503`, `404`, or upstream error.

```bash
kubectl describe ingress <ingress> -n <ns>
# Rules → backend service name and port — verify both are correct
# Look for: "service not found" or "no endpoints" warnings

kubectl get svc -n <ns>
# Verify the backend service name in the Ingress actually exists

kubectl get endpoints <backend-svc> -n <ns>
# Must be populated — if <none>, fix the service/readiness issue first

kubectl logs -n ingress-nginx -l app.kubernetes.io/name=ingress-nginx --tail=50
# Nginx access/error logs — shows upstream status codes
```

| Symptom | Cause | Fix |
| --- | --- | --- |
| `503` | Backend service has no endpoints | Fix service selector or readiness probe |
| `404` | Path not matched by any Ingress rule | Fix `path:` in Ingress spec |
| Service not found | Service name typo in Ingress | Fix `backend.service.name` |
| Upstream connect error | Wrong backend port | Fix `backend.service.port.number` |

**Fix — wrong backend service name:**
```bash
kubectl patch ingress <ingress> -n <ns> --type='json' \
  -p='[{"op":"replace","path":"/spec/rules/0/http/paths/0/backend/service/name","value":"<correct-svc-name>"}]'
```

→ Deeper: [docs/devops/networking-setup.md](docs/devops/networking-setup.md)

---

## NetworkPolicy

**Symptom:** Pod `Running` and `Ready`, endpoints populated, but traffic **times out** (not connection refused).

> **Principle:** "Connection refused is the app layer — wrong port, app not up. Timeout is the network layer — something is dropping the packet. I use that split before running a single command. If I see timeout with healthy endpoints, I go straight to NetworkPolicy."
> Key distinction: `connection refused` = app not listening on that port. `Timeout` = network path is dropping packets → suspect NetworkPolicy.

```bash
kubectl get networkpolicy -n <ns>
# List all policies — their existence alone changes traffic behaviour

kubectl describe networkpolicy <policy> -n <ns>
# PodSelector: which pods this policy applies to
# PolicyTypes: Ingress / Egress
# An Ingress type with NO ingress rules = deny ALL inbound

kubectl get pods -n <ns> --show-labels
# Check whether the policy's podSelector matches your pod
```

**Fix — delete a deny-all policy:**
```bash
kubectl delete networkpolicy <policy> -n <ns>
```

**Fix — add an explicit allow rule instead of deleting:**
```bash
kubectl apply -f - <<'EOF'
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: allow-http
  namespace: <ns>
spec:
  podSelector:
    matchLabels:
      app: <app-label>
  policyTypes:
  - Ingress
  ingress:
  - ports:
    - port: 80
EOF
```

→ Deeper: [docs/architects/network-architecture.md](docs/architects/network-architecture.md)

---

## Storage / PVC

**Symptom:** PVC stays `Pending`. Pod stays `Pending` or `ContainerCreating`.

```bash
kubectl get pvc -n <ns>
# STATUS must be Bound — Pending means no PV was matched

kubectl describe pvc <pvc> -n <ns>
# Events: "no persistent volumes available" or "storageclass not found"

kubectl get storageclass
# List available StorageClasses — compare to what the PVC requests
```

| Event message | Cause | Fix |
| --- | --- | --- |
| `storageclass.storage.k8s.io not found` | Wrong StorageClass name | Fix `storageClassName` in PVC |
| `no persistent volumes available` | No PV satisfies the PVC | Use correct SC or create a PV |
| `Volume is already exclusively attached` | RWO disk stuck on dead node | Force-delete pod (confirm node is dead first) |

**Fix — wrong StorageClass (must delete and re-create PVC — PVCs are immutable once created):**
```bash
kubectl delete pvc <pvc> -n <ns>

kubectl apply -f - <<'EOF'
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: <pvc>
  namespace: <ns>
spec:
  accessModes: [ReadWriteOnce]
  storageClassName: standard        # use: kubectl get storageclass
  resources:
    requests:
      storage: 1Gi
EOF
```

**Fix — RWO volume stuck on dead node (confirm node is truly dead — risk of data corruption if node comes back):**
```bash
kubectl delete pod <pod> -n <ns> --grace-period=0 --force
```

→ Deeper: [docs/devops/storage-configuration.md](docs/devops/storage-configuration.md)

---

## Jobs

**Symptom:** `kubectl get jobs` shows `COMPLETIONS 0/1`, status `Failed` or `BackoffLimitExceeded`

```bash
kubectl describe job <job> -n <ns>
# Conditions: Failed — BackoffLimitExceeded

kubectl get pods -n <ns> -l job-name=<job>
# Find the failed pods

kubectl logs -n <ns> -l job-name=<job> --tail=50
# What did the job output before failing?

kubectl describe pod <failed-pod> -n <ns>
# Exit Code from Last State → tells you the failure category
```

> **Key rule: Jobs are immutable. You cannot patch a failed Job's pod template. You must delete and re-create.**

```bash
kubectl delete job <job> -n <ns>
# Fix the manifest, then:
kubectl apply -f <fixed-job.yaml>
```

→ Deeper: [docs/engineers/debugging-techniques.md](docs/engineers/debugging-techniques.md)

---

## Node NotReady

**Symptom:** `kubectl get nodes` shows `NotReady`

```bash
kubectl describe node <node>
# Conditions section: MemoryPressure, DiskPressure, PIDPressure, Ready=False/Unknown
# Events section: kubelet error messages
```

**On the node (if you have SSH access):**
```bash
systemctl status kubelet
journalctl -u kubelet --no-pager | tail -50

df -h        # disk pressure
free -m      # memory pressure
crictl ps    # container runtime health
```

| Condition | Cause | Fix |
| --- | --- | --- |
| `MemoryPressure=True` | Node OOM — kubelet evicting pods | Drain node, fix workload limits |
| `DiskPressure=True` | Disk full — logs or images | `crictl rmi --prune` / clean logs |
| `PIDPressure=True` | Too many processes | Drain node, investigate fork bomb |
| `Ready=False`, kubelet stopped | kubelet crashed | `systemctl restart kubelet` |
| `Ready=Unknown` | Node unreachable | Check network / VM health in cloud console |

**Safely drain a NotReady node:**
```bash
kubectl cordon <node>                                              # stop new scheduling
kubectl drain <node> --ignore-daemonsets --delete-emptydir-data   # evict pods
```

→ Deeper: [docs/devops/node-management.md](docs/devops/node-management.md)

---

## Verification — After Every Fix

Run in order before saying you're done:

```bash
kubectl rollout status deployment/<deploy> -n <ns>    # rollout completes cleanly
kubectl get pods -n <ns>                              # all pods Running and Ready
kubectl describe pod <new-pod> -n <ns>                # no warning events
kubectl get endpoints <svc> -n <ns>                   # endpoints populated
kubectl logs <new-pod> -n <ns> --tail=20              # no errors in logs
```

---

## Safe Change Rules

1. State the symptom out loud before touching anything.
2. State the single root cause you believe is responsible.
3. State the exact change you are about to make.
4. Make the **smallest** change possible.
5. Run the verification checklist.

```bash
# Prefer targeted patches over broad edits:
kubectl patch deployment <deploy> -n <ns> --type='json' -p='[...]'
kubectl set image deployment/<deploy> <container>=<image>:<tag> -n <ns>

# For multi-field edits:
kubectl edit deployment <deploy> -n <ns>

# Rollback if the fix made things worse:
kubectl rollout undo deployment/<deploy> -n <ns>
```
