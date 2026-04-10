# Live Kubernetes Debugging Interview Guide

> **During the interview:** use [INTERVIEW.md](../INTERVIEW.md) at the repo root — it is a single-file cheat sheet with a symptom-based ToC and copy-paste fix commands. Stay in that file during the interview.
>
> **This file** is for preparation: understanding the investigation workflow, what to avoid, and how to verify fixes.

Use this guide as your operational path. Use [INTERVIEW-PREP.md](./INTERVIEW-PREP.md) for deeper theory and architecture follow-up questions.

## Goal

Show that you can:
- Triage quickly without guessing.
- Narrow the blast radius before changing anything.
- Explain your reasoning while you inspect the cluster.
- Make the smallest safe fix.
- Verify that the application is actually healthy after the change.

## How To Use This Repo For That Interview

Use the repo in this order:

1. Read this guide once before the interview and practice the command flow.
2. Use [playbooks/common-issues.md](../playbooks/common-issues.md) as a symptom-to-cause reference.
3. Use [docs/engineers/pod-startup-issues.md](./engineers/pod-startup-issues.md) and [docs/engineers/debugging-techniques.md](./engineers/debugging-techniques.md) when the issue is clearly in pod startup, probes, config, or runtime behavior.
4. Use scripts in `scripts/diagnostics/` as command inspiration, not as your first move in the interview.

## Interview-Safe Workflow

### 1. Establish Scope

Start with read-only commands and narrate what you are checking:

```bash
kubectl config current-context
kubectl get ns
kubectl get pods -A
kubectl get events -A --sort-by=.metadata.creationTimestamp | tail -50
```

What you are looking for:
- One namespace with obvious failures.
- One workload with repeated restarts, failed scheduling, failed image pulls, or readiness problems.
- Warning events that already point to the root cause.

### 2. Identify The Broken Path

Once you find the suspect namespace or workload:

```bash
kubectl get deploy,rs,po,svc,ing -n <namespace>
kubectl describe deployment <deployment> -n <namespace>
kubectl describe pod <pod> -n <namespace>
kubectl logs <pod> -n <namespace> --previous
kubectl get endpoints <service> -n <namespace>
```

Keep the investigation ordered:
- Deployment and ReplicaSet tell you the intended state.
- Pod status and events tell you what is blocking reality.
- Logs tell you whether the container starts and fails, or never starts at all.
- Service endpoints tell you whether traffic can reach any healthy pod.

### 3. Classify The Failure

#### `Pending`

Check:

```bash
kubectl describe pod <pod> -n <namespace>
kubectl get nodes
kubectl describe node <node>
kubectl get pvc -n <namespace>
```

Common causes:
- Unschedulable because of CPU or memory requests.
- Taints without tolerations.
- Node selectors or affinity rules that match no node.
- Unbound PVCs.

#### `CrashLoopBackOff` or `Error`

Check:

```bash
kubectl logs <pod> -n <namespace> --previous
kubectl describe pod <pod> -n <namespace>
kubectl get pod <pod> -n <namespace> -o yaml
```

Common causes:
- Bad command or entrypoint.
- Missing environment variable, Secret, or ConfigMap key.
- Probe failure causing restarts.
- Port mismatch between the app and the manifest.
- Resource limits too low.

#### `ImagePullBackOff` or `ErrImagePull`

Check:

```bash
kubectl describe pod <pod> -n <namespace>
```

Common causes:
- Wrong image tag.
- Missing image pull secret.
- Registry auth issue.
- Private registry network access issue.

#### Pod Is Running But App Still Fails

Check:

```bash
kubectl get pod <pod> -n <namespace> -o wide
kubectl get svc -n <namespace>
kubectl get endpoints -n <namespace>
kubectl describe svc <service> -n <namespace>
kubectl get ingress -n <namespace>
kubectl get networkpolicy -A
```

Common causes:
- Readiness probe failing, so the pod never enters service endpoints.
- Service selector does not match pod labels.
- Wrong target port or container port.
- Ingress points to the wrong service or port.
- NetworkPolicy blocks traffic.

#### DNS Or Service Discovery Issue

Check:

```bash
kubectl get pods -n kube-system
kubectl get svc -A
kubectl get endpoints -A
kubectl logs -n kube-system -l k8s-app=kube-dns --tail=50
```

Use `kubectl exec` or `kubectl debug` only if needed and only after you have already narrowed the issue:

```bash
kubectl exec -it <pod> -n <namespace> -- sh
kubectl debug -it <pod> -n <namespace> --target=<container> --image=busybox -- sh
```

In an interview, it is better to say why you need an interactive shell than to jump straight into it.

## High-Value Fixes To Be Ready For

These are the most likely issues in a practical interview:
- Wrong image tag or image name.
- Wrong port in `containerPort`, `targetPort`, probe, or Ingress backend.
- Missing or malformed environment variable.
- Secret or ConfigMap key mismatch.
- Readiness or liveness probe path mismatch.
- Resource requests too high for the cluster, or limits too low for the app.
- Service selector mismatch.
- PVC not bound or wrong storage class.

## Safe Change Strategy

Before you patch anything:
- State the current symptom.
- State the single root cause you believe is most likely.
- State the exact change you are about to make.

Then make the smallest change possible:

```bash
kubectl edit deployment <deployment> -n <namespace>
kubectl patch deployment <deployment> -n <namespace> ...
kubectl set image deployment/<deployment> <container>=<image> -n <namespace>
```

Avoid broad or destructive actions unless the interviewer asks for them.

## Verification Checklist

After the fix:

```bash
kubectl rollout status deployment/<deployment> -n <namespace>
kubectl get pods -n <namespace>
kubectl describe pod <new-pod> -n <namespace>
kubectl get endpoints <service> -n <namespace>
kubectl logs <new-pod> -n <namespace> --tail=50
```

Confirm all of these:
- New pod is scheduled and stays up.
- Readiness becomes true.
- Service endpoints are populated.
- The user-facing symptom is gone.

## What To Avoid During The Interview

- Do not start with mutation scripts from `scripts/fixes/`.
- Do not create test resources unless you can explain why they are necessary.
- Do not assume it is an AKS-specific problem unless the evidence points there.
- Do not say "I would just restart it" before you know why it failed.
- Do not rely on optional tooling like Gemini CLI.

## Best Repo Content For This Interview

- [docs/LIVE-DEBUG-INTERVIEW.md](./LIVE-DEBUG-INTERVIEW.md)
- [playbooks/common-issues.md](../playbooks/common-issues.md)
- [docs/engineers/pod-startup-issues.md](./engineers/pod-startup-issues.md)
- [docs/engineers/debugging-techniques.md](./engineers/debugging-techniques.md)
- [docs/emergency-response.md](./emergency-response.md)

## Recommended Practice

Before the interview, practice on a local cluster and deliberately break:
- Image tag
- Probe path
- Service selector
- Target port
- ConfigMap key
- Resource requests

The goal is to build a repeatable investigation loop, not to memorize commands.
