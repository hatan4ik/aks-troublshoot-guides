# EKS Debugging Framework

The structured mental model for diagnosing failures in an Amazon EKS cluster. Use this before opening a runbook. It tells you which layer to investigate and in what order.

---

## The 5-Layer Model

Every EKS failure lives in one of these layers. Diagnose top-down. Most failures are still in layers 1-3 and fixable with `kubectl` alone.

```text
Layer 1 │ Pod Lifecycle      │ Scheduling, image pull, startup, probes, config
Layer 2 │ Container Runtime  │ OOM, cgroups, exit codes, containerd
Layer 3 │ Service Networking │ Selector, endpoints, ports, DNS, Ingress
Layer 4 │ Cluster Infra      │ Nodes, VPC CNI, CoreDNS, kube-proxy, NetworkPolicy
Layer 5 │ AWS Infra          │ Security Groups, NACLs, NLB/ALB, Route Tables, NAT, ECR, EBS/EFS
```

**The key discipline:** do not jump to VPC, ELB, or IAM because traffic is failing. First prove the pod, service, and endpoints are correct.

---

## Decision Tree

Start here every time:

```bash
kubectl get pods -A
kubectl get events -A --sort-by=.metadata.creationTimestamp | tail -30
```

Use these branches:

- `Pending`
  - `Insufficient cpu/memory` -> Layer 1
  - `Untolerated taint` -> Layer 1
  - `node affinity/selector` -> Layer 1
  - `Unbound PVC` -> Layer 5 if the EBS/EFS storage path is the blocker
- `ImagePullBackOff` / `ErrImagePull`
  - `manifest unknown` / wrong tag -> Layer 1
  - `unauthorized` -> Layer 1 auth or secret
  - `timeout` / network unreachable -> Layer 4 or 5, often NAT, VPC endpoint, or SG to ECR
- `CrashLoopBackOff`
  - exit `127` -> Layer 1 bad command
  - exit `137` -> Layer 2 OOMKilled
  - exit `1` -> Layer 1 app/config
- Pod Running, traffic fails
  - endpoints empty -> Layer 3 selector or readiness
  - endpoints populated, connection refused -> Layer 3 port/listener mismatch
  - endpoints populated, timeout -> Layer 4 or 5, often NetworkPolicy, SG, NACL, or target group health

---

## Layer 4 — Cluster Infrastructure

**Scope:** EKS-managed Kubernetes components and node-level cluster services.

### Node and kube-system checks

```bash
kubectl get nodes
kubectl describe node <node>
kubectl get pods -n kube-system
```

### VPC CNI health

```bash
kubectl get pods -n kube-system -l k8s-app=aws-node
kubectl logs -n kube-system -l k8s-app=aws-node --tail=50
```

Look for:

- IP exhaustion on node ENIs
- CNI pod crashes
- Pod sandbox creation failures

### CoreDNS and kube-proxy

```bash
kubectl get pods -n kube-system -l k8s-app=kube-dns
kubectl logs -n kube-system -l k8s-app=kube-dns --tail=30
kubectl logs -n kube-system -l k8s-app=kube-proxy --tail=30
```

---

## Layer 5 — AWS Infrastructure

**Scope:** failures that remain after the Kubernetes service path is proven healthy.

### Common EKS-specific failure patterns

- `ImagePullBackOff` with timeout, not auth -> NAT Gateway, private subnet egress, or ECR VPC endpoint
- Service of type `LoadBalancer` stays pending -> cloud controller or AWS Load Balancer Controller, IAM, subnet tagging, or quota
- Pod is healthy but external traffic times out -> security group, NACL, target group health, or ALB/NLB wiring
- PVC stuck or mount fails -> EBS CSI driver, AZ mismatch, or EFS mount target/security group

### AWS checks

```bash
aws eks describe-cluster --name <cluster> --region <region>

# Security groups and networking
aws ec2 describe-security-groups --group-ids <sg-id>
aws ec2 describe-route-tables --filters Name=vpc-id,Values=<vpc-id>

# Load balancer health
aws elbv2 describe-load-balancers
aws elbv2 describe-target-groups
aws elbv2 describe-target-health --target-group-arn <tg-arn>
```

**When to escalate to AWS-side investigation:**

- Endpoints are correct, pod is healthy, and traffic still times out
- ECR access times out from private subnets
- EBS/EFS provisioning is blocked by AWS infrastructure or AZ layout
- NLB/ALB is provisioned but targets never become healthy

---

## Key References

- [AWS Networking For EKS](./aws/eks-networking.md)
- [AWS Observability For EKS](./aws/aws-observability.md)
- [Live Debug Runbook](../DEBUG-RUNBOOK.md)
- [Live Debugging Workflow](./LIVE-DEBUG-WORKFLOW.md)

