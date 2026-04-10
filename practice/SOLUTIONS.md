# Solutions

Check these only after you have made a diagnosis and attempted a fix.

---

## Scenario 1 — ImagePullBackOff

**Bug:** Image tag `nginx:1.99.99` does not exist.

**How to find it:**
```bash
kubectl describe pod -n practice -l app=scenario-01
# Events section: "Failed to pull image ... manifest unknown"
```

**Fix:**
```bash
kubectl set image deployment/scenario-01 web=nginx:1.25 -n practice
```

---

## Scenario 2 — Port Mismatch

**Bug:** Service `targetPort: 8080` but nginx listens on port `80`.

**How to find it:**
```bash
kubectl get endpoints scenario-02 -n practice
# Endpoints exist (pod is ready), but curl still fails.
kubectl describe svc scenario-02 -n practice
# targetPort: 8080 — does not match containerPort 80.
```

**Fix:**
```bash
kubectl patch svc scenario-02 -n practice \
  --type='json' \
  -p='[{"op":"replace","path":"/spec/ports/0/targetPort","value":80}]'
```

---

## Scenario 3 — Service Selector Mismatch

**Bug:** Service selector is `app: scenario-3` (missing the trailing zero). Pod label is `app: scenario-03`.

**How to find it:**
```bash
kubectl get endpoints scenario-03 -n practice
# Output: <none>
kubectl describe svc scenario-03 -n practice
# Selector: app=scenario-3
kubectl get pods -n practice --show-labels
# Labels: app=scenario-03
# The selector does not match any pod.
```

**Fix:**
```bash
kubectl patch svc scenario-03 -n practice \
  --type='json' \
  -p='[{"op":"replace","path":"/spec/selector/app","value":"scenario-03"}]'
```

---

## Scenario 4 — Failing Readiness Probe

**Bug:** Readiness probe path is `/healthz`. nginx default image does not serve that path — it returns 404, so the probe always fails.

**How to find it:**
```bash
kubectl describe pod -n practice -l app=scenario-04
# Events: "Readiness probe failed: HTTP probe failed with statuscode: 404"
# Ready: False
```

**Fix:**
```bash
kubectl patch deployment scenario-04 -n practice \
  --type='json' \
  -p='[{"op":"replace","path":"/spec/template/spec/containers/0/readinessProbe/httpGet/path","value":"/"}]'
```

---

## Scenario 5 — Missing ConfigMap Key

**Bug:** ConfigMap defines key `DB_URL`. The Deployment references key `DATABASE_URL` (does not exist in the ConfigMap).

**How to find it:**
```bash
kubectl describe pod -n practice -l app=scenario-05
# Events: "Error: couldn't find key DATABASE_URL in ConfigMap practice/scenario-05-config"
# State: Waiting — Reason: CreateContainerConfigError
```

**Fix (option A — fix the ConfigMap key to match what the pod expects):**
```bash
kubectl patch configmap scenario-05-config -n practice \
  --type='json' \
  -p='[{"op":"add","path":"/data/DATABASE_URL","value":"postgres://db:5432/myapp"}]'
```

**Fix (option B — fix the Deployment to reference the correct key):**
```bash
kubectl patch deployment scenario-05 -n practice \
  --type='json' \
  -p='[{"op":"replace","path":"/spec/template/spec/containers/0/env/0/valueFrom/configMapKeyRef/key","value":"DB_URL"}]'
```

---

## Scenario 6 — Pending: Resource Requests Too High

**Bug:** CPU request is `96` cores — more than any node in a typical local cluster provides.

**How to find it:**
```bash
kubectl describe pod -n practice -l app=scenario-06
# Events: "0/1 nodes are available: 1 Insufficient cpu."
kubectl get nodes
kubectl describe node <node>
# Capacity: cpu: <N> — far less than 96.
```

**Fix:**
```bash
kubectl patch deployment scenario-06 -n practice \
  --type='json' \
  -p='[
    {"op":"replace","path":"/spec/template/spec/containers/0/resources/requests/cpu","value":"50m"},
    {"op":"replace","path":"/spec/template/spec/containers/0/resources/limits/cpu","value":"100m"}
  ]'
```

---

## Scenario 7 — CrashLoopBackOff: Bad Entrypoint

**Bug:** `command: ["/bin/launch-app"]` — that binary does not exist in the nginx image.

**How to find it:**
```bash
kubectl describe pod -n practice -l app=scenario-07
# Last State: Terminated — Exit Code: 127
# Exit code 127 = "command not found"
kubectl logs -n practice -l app=scenario-07 --previous
# (likely empty — process never started)
```

**Fix (remove the override, let nginx use its default entrypoint):**
```bash
kubectl patch deployment scenario-07 -n practice \
  --type='json' \
  -p='[{"op":"remove","path":"/spec/template/spec/containers/0/command"}]'
```

---

## Scenario 8 — Taint Without Toleration

**Bug:** A `NoSchedule` taint was applied to all nodes (`dedicated=gpu:NoSchedule`) but the pod spec has no matching toleration.

**How to find it:**
```bash
kubectl describe pod -n practice -l app=scenario-08
# Events: "0/1 nodes are available: 1 node(s) had untolerated taint {dedicated: gpu}."

kubectl describe node <node>
# Taints: dedicated=gpu:NoSchedule
```

**Fix — add toleration to the deployment:**
```bash
kubectl patch deployment scenario-08 -n practice --type='json' -p='[
  {"op":"add","path":"/spec/template/spec/tolerations","value":[
    {"key":"dedicated","operator":"Equal","value":"gpu","effect":"NoSchedule"}
  ]}
]'
```

**Remove the taint when done:**
```bash
kubectl taint nodes --all dedicated=gpu:NoSchedule-
```

---

## Scenario 9 — Node Selector No Match

**Bug:** `nodeSelector: hardware: high-memory-optimized` — no node in the cluster has this label.

**How to find it:**
```bash
kubectl describe pod -n practice -l app=scenario-09
# Events: "0/1 nodes are available: 1 node(s) didn't match Pod's node affinity/selector."

kubectl get nodes --show-labels
# No node has label hardware=high-memory-optimized
```

**Fix — remove the nodeSelector (or set it to a label that exists):**
```bash
kubectl patch deployment scenario-09 -n practice --type='json' \
  -p='[{"op":"remove","path":"/spec/template/spec/nodeSelector"}]'
```

---

## Scenario 10 — NetworkPolicy Blocks All Ingress

**Bug:** A NetworkPolicy selects the pod and declares `policyTypes: [Ingress]` with no ingress rules — this denies all inbound traffic.

**How to find it:**
```bash
kubectl get networkpolicy -n practice
# scenario-10-deny-all exists

kubectl describe networkpolicy scenario-10-deny-all -n practice
# PodSelector: app=scenario-10
# PolicyTypes: Ingress
# (no Ingress rules listed = deny all)

kubectl get endpoints scenario-10 -n practice
# Endpoints populated (pod IS ready) — traffic is blocked at policy level, not service level
```

**Fix — delete the deny-all policy:**
```bash
kubectl delete networkpolicy scenario-10-deny-all -n practice
```

**Or fix by adding an explicit allow rule:**
```bash
kubectl apply -f - <<'EOF'
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: scenario-10-allow-http
  namespace: practice
spec:
  podSelector:
    matchLabels:
      app: scenario-10
  policyTypes:
  - Ingress
  ingress:
  - ports:
    - port: 80
EOF
```

---

## Scenario 11 — Ingress Wrong Backend Service Name

**Bug:** Ingress backend references service `scenario-11-backend` which does not exist. The actual service is `scenario-11-svc`.

**How to find it:**
```bash
kubectl describe ingress scenario-11 -n practice
# Backend: scenario-11-backend:80 (<error: endpoints "scenario-11-backend" not found>)

kubectl get svc -n practice
# scenario-11-svc exists — not scenario-11-backend
```

**Fix:**
```bash
kubectl patch ingress scenario-11 -n practice --type='json' \
  -p='[{"op":"replace","path":"/spec/rules/0/http/paths/0/backend/service/name","value":"scenario-11-svc"}]'
```

---

## Scenario 12 — Missing imagePullSecret

**Bug:** The image is from a private registry (`registry.example.internal`) but no `imagePullSecrets` is configured. Kubernetes cannot authenticate to pull the image.

**How to find it:**
```bash
kubectl describe pod -n practice -l app=scenario-12
# Events: "Failed to pull image ... unauthorized: authentication required"
# or: "pull access denied"
```

**Fix — create the pull secret and patch the deployment:**
```bash
# Create the secret (use real credentials in production)
kubectl create secret docker-registry scenario-12-regcred \
  --docker-server=registry.example.internal \
  --docker-username=ci-robot \
  --docker-password=<token> \
  -n practice

# Add imagePullSecrets to the deployment
kubectl patch deployment scenario-12 -n practice --type='json' -p='[
  {"op":"add","path":"/spec/template/spec/imagePullSecrets","value":[
    {"name":"scenario-12-regcred"}
  ]}
]'
```

---

## Scenario 13 — PVC Wrong StorageClass

**Bug:** PVC requests StorageClass `ultra-fast-nvme` which does not exist in the cluster. The PVC stays in `Pending` state indefinitely, so the pod also stays `Pending`.

**How to find it:**
```bash
kubectl get pvc -n practice
# scenario-13-data   Pending

kubectl describe pvc scenario-13-data -n practice
# Events: "no persistent volumes available for this claim and no storage class is set"
# or: "storageclass.storage.k8s.io "ultra-fast-nvme" not found"

kubectl get storageclass
# ultra-fast-nvme is not listed — find the correct name (e.g. "standard", "gp2")
```

**Fix — patch the PVC storageClassName to one that exists:**
```bash
# First delete the pending PVC (PVCs cannot be patched once bound)
kubectl delete pvc scenario-13-data -n practice

# Re-create with the correct StorageClass (replace "standard" with your cluster's SC)
kubectl patch deployment scenario-13 -n practice --type='json' \
  -p='[{"op":"replace","path":"/spec/template/spec/volumes/0/persistentVolumeClaim/claimName","value":"scenario-13-data"}]'

kubectl apply -f - <<'EOF'
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: scenario-13-data
  namespace: practice
spec:
  accessModes:
  - ReadWriteOnce
  storageClassName: standard
  resources:
    requests:
      storage: 1Gi
EOF
```

---

## Scenario 14 — OOMKilled (exit 137)

**Bug:** Memory limit is 32Mi but the container allocates 200Mi. The kernel OOM killer terminates the process with SIGKILL (exit code 137).

**How to find it:**
```bash
kubectl describe pod -n practice -l app=scenario-14
# Last State: Terminated
#   Reason: OOMKilled
#   Exit Code: 137

# OOMKilled is also visible in the pod's containerStatuses:
kubectl get pod -n practice -l app=scenario-14 -o jsonpath='{.items[0].status.containerStatuses[0].lastState}'
```

**On the node (if you have access):**
```bash
# SSH to the node then:
dmesg | grep -i "killed process"
# Confirms kernel OOM killer fired
```

**Fix — raise the memory limit:**
```bash
kubectl patch deployment scenario-14 -n practice --type='json' -p='[
  {"op":"replace","path":"/spec/template/spec/containers/0/resources/requests/memory","value":"256Mi"},
  {"op":"replace","path":"/spec/template/spec/containers/0/resources/limits/memory","value":"256Mi"}
]'
```

---

## Scenario 15 — Liveness Probe Kills Healthy App

**Bug:** `initialDelaySeconds: 5` but the app takes 20 seconds to start. The liveness probe fires after 5s, fails (app not up yet), and Kubernetes kills and restarts the container. This repeats forever.

**How to find it:**
```bash
kubectl describe pod -n practice -l app=scenario-15
# Events: "Liveness probe failed: Get http://...:8080/ dial tcp ... connection refused"
# Restart count keeps incrementing

kubectl get pod -n practice -l app=scenario-15
# RESTARTS column: 2, 3, 4... (keeps going)
```

**Fix — increase `initialDelaySeconds` to allow the app to start:**
```bash
kubectl patch deployment scenario-15 -n practice --type='json' -p='[
  {"op":"replace","path":"/spec/template/spec/containers/0/livenessProbe/initialDelaySeconds","value":30},
  {"op":"replace","path":"/spec/template/spec/containers/0/livenessProbe/failureThreshold","value":3}
]'
```

**Better fix in production — add a startupProbe:**
A `startupProbe` with a high `failureThreshold` gives slow-starting apps time to boot without affecting the liveness probe once running.

---

## Scenario 16 — Init Container Failing

**Bug:** The init container runs `nc -z postgres-service 5432` but `postgres-service` does not exist in the namespace. The init container exits non-zero, blocking the main container from ever starting.

**How to find it:**
```bash
kubectl get pod -n practice -l app=scenario-16
# STATUS: Init:CrashLoopBackOff  or  Init:0/1

kubectl describe pod -n practice -l app=scenario-16
# Init Containers:
#   wait-for-db:
#     State: Terminated — Exit Code: 1

kubectl logs -n practice -l app=scenario-16 -c wait-for-db
# nc: bad address 'postgres-service'
```

**Fix (option A) — remove the init container if the dependency check is not needed:**
```bash
kubectl patch deployment scenario-16 -n practice --type='json' \
  -p='[{"op":"remove","path":"/spec/template/spec/initContainers"}]'
```

**Fix (option B) — point the init container at a real service:**
```bash
kubectl patch deployment scenario-16 -n practice --type='json' \
  -p='[{"op":"replace","path":"/spec/template/spec/initContainers/0/command","value":["sh","-c","echo skipping db check; exit 0"]}]'
```

---

## Scenario 17 — Secret Object Does Not Exist

**Bug:** The pod references `secretKeyRef.name: scenario-17-api-credentials` but no Secret with that name was ever created in the namespace.

**Difference from Scenario 5:** In scenario 5 the ConfigMap existed but the key was wrong. Here the Secret object itself is absent.

**How to find it:**
```bash
kubectl describe pod -n practice -l app=scenario-17
# State: Waiting
# Reason: CreateContainerConfigError
# Message: secret "scenario-17-api-credentials" not found

kubectl get secret -n practice
# scenario-17-api-credentials is not listed
```

**Fix — create the missing secret:**
```bash
kubectl create secret generic scenario-17-api-credentials \
  --from-literal=api-key=supersecretvalue \
  -n practice
```

The pod will automatically restart and pick up the new secret.

---

## Scenario 18 — StatefulSet Missing Headless Service

**Bug:** The StatefulSet declares `serviceName: scenario-18-headless` but no Service with `clusterIP: None` and that name exists. Without the headless service, pods cannot get stable DNS names (`pod-0.scenario-18-headless.practice.svc.cluster.local`).

**How to find it:**
```bash
kubectl get statefulset scenario-18 -n practice
# Shows pods may be running but DNS between pods fails

kubectl get svc -n practice
# scenario-18 exists (ClusterIP) but scenario-18-headless is missing

# Inside a pod, DNS lookup fails:
kubectl exec -n practice scenario-18-0 -- nslookup scenario-18-0.scenario-18-headless.practice.svc.cluster.local
# server can't find ...: NXDOMAIN
```

**Fix — create the headless service:**
```bash
kubectl apply -f - <<'EOF'
apiVersion: v1
kind: Service
metadata:
  name: scenario-18-headless
  namespace: practice
spec:
  clusterIP: None
  selector:
    app: scenario-18
  ports:
  - port: 80
    targetPort: 80
    name: web
EOF
```

---

## Scenario 19 — Job BackoffLimitExceeded

**Bug:** The Job command calls `/app/migrate` which does not exist in the busybox image (exit 127). After 3 retries (`backoffLimit: 3`) the Job is marked Failed.

**How to find it:**
```bash
kubectl get jobs -n practice
# scenario-19-db-migrate   0/1   <age>   BackoffLimitExceeded (in conditions)

kubectl describe job scenario-19-db-migrate -n practice
# Conditions: Failed — BackoffLimitExceeded

# Find the failed pods
kubectl get pods -n practice -l job-name=scenario-19-db-migrate
# STATUS: Error

kubectl logs -n practice -l job-name=scenario-19-db-migrate --tail=20
# sh: /app/migrate: not found
# Exit code 127
```

**Fix — correct the command (in a real migration, point to the real binary):**
```bash
# Delete the failed job first (Jobs are immutable after creation)
kubectl delete job scenario-19-db-migrate -n practice

# Re-apply with corrected command
kubectl apply -f - <<'EOF'
apiVersion: batch/v1
kind: Job
metadata:
  name: scenario-19-db-migrate
  namespace: practice
spec:
  backoffLimit: 3
  template:
    spec:
      restartPolicy: OnFailure
      containers:
      - name: migrator
        image: busybox:1.36
        command:
        - sh
        - -c
        - echo "Migration complete (simulated)"; exit 0
        resources:
          requests:
            cpu: 50m
            memory: 64Mi
          limits:
            cpu: 100m
            memory: 128Mi
EOF
```

**Key interview insight:** Jobs are immutable — you cannot patch a running or failed Job's pod template. You must delete and re-create it.

---

## Exit Code Reference

| Code | Meaning |
| --- | --- |
| 0 | Clean exit (check if it should be a Job) |
| 1 | Application error |
| 127 | Command not found (bad entrypoint) |
| 137 | SIGKILL — usually OOMKilled |
| 139 | Segmentation fault |
| 143 | SIGTERM — graceful shutdown |
