# AWS Observability For EKS

Production observability on EKS means knowing which AWS tool answers which question.

---

## Tool Map

| Question | Tool |
| --- | --- |
| Why did a pod restart repeatedly? | `kubectl describe`, CloudWatch Container Insights |
| Is a node saturated? | CloudWatch metrics, Container Insights |
| Why is ingress traffic failing? | ALB/NLB target health, access logs, CloudWatch |
| What network path dropped packets? | VPC Flow Logs |
| Who changed the cluster or IAM path? | CloudTrail |

---

## 1. Container Insights And CloudWatch

Use Container Insights for cluster-wide CPU, memory, and restart analysis.

```bash
kubectl get pods -n amazon-cloudwatch
```

Focus on:

- node CPU and memory pressure
- pod restart counts
- kube-system pod health

---

## 2. VPC Flow Logs

Use Flow Logs when traffic times out and the Kubernetes path looks correct.

Look for:

- dropped traffic between load balancer and nodes
- blocked egress to ECR
- subnet-level rejects

---

## 3. ALB / NLB Health

External reachability often fails because targets are unhealthy, not because the pods are missing.

```bash
aws elbv2 describe-target-health --target-group-arn <tg-arn>
```

Use this to answer:

- are nodes or pods being seen as healthy backends?
- is health failing before traffic even reaches Kubernetes?

---

## 4. CloudTrail

Use CloudTrail for:

- IAM changes
- security group edits
- load balancer changes
- EKS control plane actions

If the problem appeared suddenly, CloudTrail is often the fastest way to find the operator or automation change that triggered it.

---

## 5. Suggested Investigation Order

1. `kubectl` evidence
2. target health
3. flow logs
4. CloudWatch metrics and logs
5. CloudTrail

---

## Related References

- [EKS Debugging Framework](../EKS-DEBUGGING-FRAMEWORK.md)
- [EKS Networking Deep Dive](./eks-networking.md)

