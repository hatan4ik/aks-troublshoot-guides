# Module 3: Services, DNS, Ingress, And Traffic Failures

## Purpose

Teach students to debug the traffic path in order: pod readiness, service selector, endpoints, ports, ingress, and policy.

## Required Reading

- [Live Debug Runbook](../DEBUG-RUNBOOK.md)
- [Common Issues Playbook](../playbooks/common-issues.md)
- [P1 DNS Failures](../playbooks/p1-dns-failures.md)
- [AKS Networking Deep Dive](../docs/azure/aks-networking.md)

## Learning Objectives

- Diagnose selector mismatches, target port mistakes, readiness path failures, ingress backend errors, and NetworkPolicy drops
- Explain why empty endpoints and timed-out traffic point to different layers
- Know when the problem is still in Kubernetes and when it has moved into Azure LB or NSG territory

## Investigation Chain

Use this in order every time:

```bash
kubectl get pod <pod> -n <ns>
kubectl get svc <svc> -n <ns> -o yaml
kubectl get endpoints <svc> -n <ns>
kubectl describe svc <svc> -n <ns>
kubectl describe ingress <ing> -n <ns>
kubectl get networkpolicy -A
```

## Hands-On Labs

Required:

- `practice/02-port-mismatch.yaml`
- `practice/03-selector-mismatch.yaml`
- `practice/04-bad-probe.yaml`
- `practice/10-networkpolicy-blocks-ingress.yaml`
- `practice/11-ingress-wrong-service.yaml`

## AKS Overlay

After the Kubernetes path is verified, introduce Azure-side checks:

- Azure Load Balancer provisioning
- LB health probe behavior
- NSG drops vs application-level refusal
- ACR timeout vs auth failure

## Instructor Prompt

Ask students:

- Are endpoints empty or populated?
- Is the failure a timeout or a refusal?
- What is the first command that proves the service contract is wrong?
