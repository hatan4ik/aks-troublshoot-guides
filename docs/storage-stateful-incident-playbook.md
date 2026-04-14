# Storage and Stateful Workload Incident Playbook

## Scope

Use this playbook when PersistentVolumeClaims, PersistentVolumes, VolumeAttachments, StatefulSets, or storage-backed applications are degraded.

Storage incidents are high-risk because the unsafe fix can destroy data. First identify the failure mode, then choose the smallest reversible action.

## Fast Triage

```bash
kubectl get storageclass
kubectl get pvc,pv -A
kubectl get volumeattachment
kubectl get statefulset -A
kubectl get pods -A -o wide | grep -Ei "pending|crashloop|terminating|init|containercreating"
kubectl get events -A --sort-by=.metadata.creationTimestamp | tail -100
```

For a specific workload:

```bash
kubectl describe pod <pod> -n <namespace>
kubectl describe pvc <claim> -n <namespace>
kubectl describe statefulset <name> -n <namespace>
kubectl get events -n <namespace> --sort-by=.metadata.creationTimestamp | tail -60
```

Repo diagnostics:

```bash
./scripts/diagnostics/storage-analysis.sh
./scripts/diagnostics/resource-analysis.sh
```

## Safety Rules

- Do not remove PVC or PV finalizers until data ownership and backups are confirmed.
- Do not force delete StatefulSet pods during quorum incidents unless the application owner confirms recovery behavior.
- Do not scale stateful quorum systems down or up blindly.
- Snapshot or backup first when the storage backend supports it and time allows.
- Prefer fixing attachment, scheduling, and identity failures before replacing disks.

## PVC Pending

Common causes:

- StorageClass does not exist.
- Dynamic provisioner is not installed or unhealthy.
- Cloud CSI driver cannot authenticate or create the disk.
- `WaitForFirstConsumer` is waiting for a schedulable pod.
- Zone topology prevents disk placement.

Commands:

```bash
kubectl describe pvc <claim> -n <namespace>
kubectl get storageclass <storageclass> -o yaml
kubectl get pods -n kube-system | grep -Ei "csi|disk|ebs|efs|azure|gce|pd"
kubectl get events -n <namespace> --sort-by=.metadata.creationTimestamp | tail -60
```

Safe actions:

- Fix the StorageClass reference if it is a manifest error.
- Fix CSI controller/node plugin health if provisioning is broken cluster-wide.
- For `WaitForFirstConsumer`, debug pod scheduling rather than changing storage first.

## PVC or PV Stuck Terminating

Common causes:

- Finalizer is waiting for cleanup.
- Pod still references the claim.
- CSI provisioner cannot delete cloud disk.
- Namespace deletion is stuck.

Commands:

```bash
kubectl get pvc <claim> -n <namespace> -o yaml
kubectl get pv <pv> -o yaml
kubectl get pods -n <namespace> -o yaml | grep -B5 -A5 "<claim>"
kubectl describe pv <pv>
```

Safe actions:

- Confirm no live pod uses the claim.
- Confirm the reclaim policy and backup state.
- Escalate to storage/platform owner before finalizer removal.

Finalizer removal is a last resort because it can orphan or delete the backing disk incorrectly.

## VolumeAttachment Stuck or Multi-Attach

Common causes:

- Pod moved to a new node while the disk is still attached to the old node.
- Node is NotReady and the attach-detach controller is waiting.
- ReadWriteOnce disk is used by multiple pods across nodes.
- CSI driver is unhealthy.

Commands:

```bash
kubectl get volumeattachment
kubectl describe volumeattachment <name>
kubectl get pod <pod> -n <namespace> -o wide
kubectl describe node <node>
kubectl get pods -A | grep -Ei "csi|disk|ebs|azure|gce|pd"
```

Safe actions:

- If the old node is NotReady, follow node recovery or drain process.
- If the workload accidentally has multiple replicas using one ReadWriteOnce PVC, fix the controller spec.
- If CSI is unhealthy cluster-wide, fix CSI before deleting pods.

## StatefulSet Quorum Loss

Common causes:

- Too many replicas down at once.
- PDB missing or too permissive.
- Anti-affinity or topology spread not enforced.
- Storage attach failures after node loss.
- Application-level replication is degraded.

Commands:

```bash
kubectl get statefulset <name> -n <namespace> -o yaml
kubectl get pods -n <namespace> -o wide
kubectl get pdb -n <namespace>
kubectl describe pdb <pdb> -n <namespace>
kubectl describe pod <pod> -n <namespace>
```

Safe actions:

- Restore enough original members to regain quorum if possible.
- Avoid deleting PVCs for quorum members unless the application recovery procedure explicitly says so.
- Use application-native repair tooling after Kubernetes health is restored.

## Disk Full or Filesystem Resize

Common causes:

- PVC reached capacity.
- Filesystem did not expand after PVC resize.
- Application logs or temp files are written to persistent storage.
- Database compaction or retention policy failed.

Commands:

```bash
kubectl describe pvc <claim> -n <namespace>
kubectl exec -n <namespace> <pod> -- df -h
kubectl exec -n <namespace> <pod> -- du -sh <path>
kubectl get storageclass <storageclass> -o yaml | grep allowVolumeExpansion
```

Safe actions:

- Expand PVC only if the StorageClass supports expansion.
- Clean application data only with application owner approval.
- Add retention and alerting after recovery.

## Provider Notes

### AKS

- Azure Disk is zone-bound and usually ReadWriteOnce.
- Check Azure Disk CSI driver health for attach/provisioning failures.
- Key Vault CSI failures are identity/secret mount issues, not PVC failures.

### EKS

- EBS volumes are Availability Zone-bound and usually ReadWriteOnce.
- AWS EBS CSI failures often involve IAM permissions or node/pod identity.
- EFS behaves differently from EBS and is better suited for ReadWriteMany patterns.

### GKE

- Persistent Disk is zone or regional depending on StorageClass.
- Workload Identity can affect application access to object storage, but not normal PD attachment.
- Regional PD improves availability but does not remove application quorum requirements.

### Bare Metal

- Validate the storage backend first: Ceph, Longhorn, NFS, local PV, or SAN.
- Local PV ties data to node identity. Node loss can become data loss without replication.
- Network storage incidents often overlap with MTU, DNS, routing, or switch failures.

## Interview Signals

A strong answer should explain:

- Why `WaitForFirstConsumer` can make a PVC look stuck while the real issue is pod scheduling.
- Why ReadWriteOnce multi-attach errors are often workload design issues.
- Why removing finalizers is dangerous.
- Why StatefulSet identity and application quorum are separate but related concepts.
