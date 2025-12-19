# Stateful Workloads on Kubernetes (FAANG Level)

## The Problem
Stateless apps are "cattle". Stateful apps (Postgres, Kafka, Cassandra, Elastic) are "pets" that require surgery when sick.

## 1. StatefulSet Primitives
**Why not Deployment?**
*   **Stable Network ID:** `pod-0`, `pod-1`. (DNS: `pod-0.service.ns`). Essential for cluster discovery (e.g., Zookeeper/Raft).
*   **Stable Storage:** `volumeClaimTemplates` ensure `pvc-0` always re-attaches to `pod-0`, even if it moves nodes.
*   **Ordered Deployment:** `pod-0` starts -> Ready -> `pod-1` starts. (Crucial for Leader -> Follower startup).

## 2. Storage & PVCs
*   **Access Modes:**
    *   `ReadWriteOnce` (RWO): Block storage (EBS/Azure Disk). Only one node can mount.
    *   `ReadWriteMany` (RWX): File storage (EFS/Azure Files). Performance penalty, but shared.
*   **Expansion:** `allowVolumeExpansion: true`. Edit PVC size -> K8s resizes cloud disk -> Kubelet resizes filesystem (xfs_growfs) online.
*   **The "Stuck" Volume:** If a node dies, the cloud provider volume might fail to detach (AttachDetachController timeout = 6mins).
    *   *Fix:* `kubectl delete pod <pod> --force --grace-period=0` (Dangerous! Only if you know the node is gone).

## 3. Leader Election & Split Brain
**Scenario:** You run a Postgres Primary/Replica setup.
*   **Problem:** Network partition. Both pods think they are Master.
*   **Solution:** Distributed Consensus (Raft/Paxos) or K8s Leases.
    *   **Sidecar Pattern:** A sidecar (Patroni/Stolon) talks to K8s API (or etcd) to hold a "Lease" (Lock).
    *   **Fencing:** If lease expires, the old master *must* kill itself (STONITH) or downgrade to read-only.

## 4. Databases on K8s: The "Operator" Pattern
**Don't write YAML manually.** Use Operators (CNPG, Strimzi, ECK).
*   **Backup:** Operator handles point-in-time recovery (WAL archiving to S3).
*   **Failover:** Operator watches for pod death and promotes a replica automatically.
*   **Upgrades:** Operator performs rolling upgrades of the DB binary with zero downtime.

## Interview Questions
*   "How do you resize a production database disk on K8s without downtime?" (Answer: PVC expansion + StorageClass `allowVolumeExpansion`).
*   "A StatefulSet pod is stuck Terminating. The volume is attached to a dead node. What do you do?" (Answer: Check volume attachment, potentially force delete pod if data safety is confirmed).
