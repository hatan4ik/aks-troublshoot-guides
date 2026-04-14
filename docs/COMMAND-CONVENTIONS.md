# Command Conventions

Use this page to interpret commands throughout the guide. It keeps examples consistent and reduces accidental production impact.

## Shell Assumptions

Most examples assume:

- A POSIX-like shell such as `bash` or `zsh`.
- `kubectl` is installed and points at the intended cluster.
- You have enough RBAC to read the resources being queried.
- You understand whether the current context is local, staging, or production.

Always check context before changing cluster state:

```bash
kubectl config current-context
kubectl get ns
```

## Placeholders

Angle-bracket values must be replaced before running the command:

```bash
kubectl describe pod <pod> -n <namespace>
kubectl logs deployment/<deployment> -n <namespace>
```

Do not include the angle brackets in the final command.

## Read-Only Commands

Read-only commands inspect state and are generally safe:

```bash
kubectl get pods -A
kubectl describe pod <pod> -n <namespace>
kubectl get events -A --sort-by=.metadata.creationTimestamp
kubectl logs <pod> -n <namespace> --tail=200
```

Read-only does not mean low-impact in every cluster. Large `list` calls can be expensive in very large clusters. Prefer namespace-scoped commands during incidents when the namespace is known.

## State-Changing Commands

State-changing commands mutate the cluster:

```bash
kubectl apply -f <file>
kubectl delete pod <pod> -n <namespace>
kubectl rollout restart deployment/<deployment> -n <namespace>
kubectl patch deployment <deployment> -n <namespace> --type merge -p '<json>'
```

Before running them:

- Confirm namespace and context.
- Prefer `--dry-run=server` where the API supports it.
- Understand whether GitOps will revert the change.
- Record what changed and how to roll it back.

## Dry-Run Preference

Use dry-run for manifests and remediation previews:

```bash
kubectl apply --dry-run=client -f <file>
kubectl apply --dry-run=server -f <file>
python3 ./k8s-diagnostics-cli.py fix --dry-run
```

Client dry-run catches local schema and rendering errors. Server dry-run catches API server, admission, and cluster-version behavior.

## GitOps-Owned Resources

If Argo CD or Flux CD owns a resource, the durable fix normally belongs in Git:

```bash
kubectl get applications -A
kubectl get gitrepositories,kustomizations,helmreleases -A
```

Manual `kubectl patch` is acceptable for emergency mitigation only when the team accepts temporary drift. Reconcile the fix back into Git afterward.

## Destructive Commands

Treat these as high-risk:

```bash
kubectl delete pvc <claim> -n <namespace>
kubectl delete pv <volume>
kubectl delete namespace <namespace>
kubectl delete pod <pod> -n <namespace> --grace-period=0 --force
```

Before using them, confirm data ownership, backups, quorum state, and provider-level attachment state. For storage incidents, use [Storage and Stateful Workload Incident Playbook](./storage-stateful-incident-playbook.md).

## Output Truncation

Many commands use `tail` to keep incident output readable:

```bash
kubectl get events -A --sort-by=.metadata.creationTimestamp | tail -50
```

Increase the number only when the first output suggests older events are relevant.

## Local Lab Exceptions

Some commands are intended only for local Minikube or Docker Desktop labs, such as local port-forwarding or `dnsmasq` setup. Do not apply those patterns directly to production clusters.

Use [Local Cluster Debugging](./LOCAL-CLUSTER-DEBUGGING.md) and [GitOps Minikube Install](./GITOPS-MINIKUBE-INSTALL.md) for local-only workflows.
