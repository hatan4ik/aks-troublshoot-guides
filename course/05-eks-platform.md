# Module 5E: EKS Platform Layers

## Purpose

Teach students when to leave pure Kubernetes debugging and move into EKS and AWS diagnostics.

## Required Reading

- [EKS Debugging Framework](../docs/EKS-DEBUGGING-FRAMEWORK.md)
- [EKS Networking Deep Dive](../docs/aws/eks-networking.md)
- [AWS Observability For EKS](../docs/aws/aws-observability.md)

## Learning Objectives

- Recognize AWS-side failures without blaming AWS too early
- Understand VPC CNI, security groups, NACLs, NLB/ALB, and ECR failure patterns
- Know when VPC flow logs or target health are more useful than additional `kubectl` commands

## Topics

- VPC CNI and IP exhaustion
- ECR auth vs reachability
- NLB and ALB target health
- private subnet egress and NAT
- EBS/EFS storage boundaries

## Suggested Assessment

Give students one of these and ask for the first AWS component to inspect:

- `ImagePullBackOff` with timeout to ECR
- ingress exists, endpoints exist, traffic still times out
- EBS-backed PVC cannot attach

