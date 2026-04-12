# EKS Networking Deep Dive

Amazon EKS sits on top of AWS VPC networking. When Kubernetes looks healthy but traffic still fails, the problem is usually in one of these outer layers.

---

## Quick Reference

| Symptom | Most likely layer |
| --- | --- |
| `ImagePullBackOff` with timeout | NAT Gateway, VPC endpoint, or SG path to ECR |
| Pods fail to get IPs | VPC CNI IP exhaustion |
| Service `LoadBalancer` pending | subnet tags, IAM, AWS controller, or quota |
| ALB/NLB exists but traffic times out | target group health, SG, or NACL |
| Cross-node traffic fails | SG, NACL, route table, or CNI problem |
| EBS mount blocked | CSI or AZ mismatch |

---

## 1. VPC CNI

EKS commonly uses the AWS VPC CNI plugin. Pods receive VPC IPs through ENIs on the nodes.

```bash
kubectl get pods -n kube-system -l k8s-app=aws-node
kubectl logs -n kube-system -l k8s-app=aws-node --tail=50
```

Typical failure modes:

- node ENI IP exhaustion
- subnet IP exhaustion
- pod sandbox creation fails because CNI cannot assign an IP

---

## 2. Security Groups And NACLs

Security groups usually control allowed traffic. NACLs can silently drop traffic at the subnet boundary.

```bash
aws ec2 describe-security-groups --group-ids <sg-id>
aws ec2 describe-network-acls --filters Name=vpc-id,Values=<vpc-id>
```

Key insight:

- connection refused usually means the packet reached the workload path
- timeout often means SG, NACL, route, or target group health

---

## 3. ECR Reachability

`ImagePullBackOff` with `unauthorized` is different from `timeout`.

- `unauthorized` -> auth or secret path
- `timeout` -> egress path to ECR or missing VPC endpoints in private environments

```bash
kubectl run nettest --image=nicolaka/netshoot --rm -it --restart=Never -- \
  curl -I https://<account>.dkr.ecr.<region>.amazonaws.com
```

---

## 4. NLB / ALB

For `LoadBalancer` services and ingress traffic, check the AWS LB path after the Kubernetes path is proven.

```bash
kubectl get svc -A
kubectl describe svc <svc> -n <ns>
aws elbv2 describe-load-balancers
aws elbv2 describe-target-groups
aws elbv2 describe-target-health --target-group-arn <tg-arn>
```

Look for:

- targets never becoming healthy
- subnet tagging issues
- SG rules missing from LB to nodes

---

## 5. Private Cluster And Routing

Private subnets require a working egress path through NAT Gateway or VPC endpoints.

Check:

- route tables for private subnets
- NAT Gateway health
- VPC endpoints for ECR and S3 where required

```bash
aws ec2 describe-route-tables --filters Name=vpc-id,Values=<vpc-id>
```

---

## Related References

- [EKS Debugging Framework](../EKS-DEBUGGING-FRAMEWORK.md)
- [AWS Observability For EKS](./aws-observability.md)
- [Cloud FQDN Service Access](../cloud-fqdn-service-access.md)
