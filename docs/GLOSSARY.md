# Glossary

This glossary defines terms as they are used in this guide. It is intentionally operational: the focus is how terms matter during troubleshooting.

## Admission Controller

A control-plane component that intercepts API requests before objects are persisted. Policy tools such as OPA Gatekeeper and Kyverno use admission to allow, deny, or mutate resources.

## AKS

Azure Kubernetes Service, Microsoft's managed Kubernetes service. AKS-specific troubleshooting often involves Azure CNI, NSGs, UDRs, Azure Load Balancer, ACR, managed identity, Azure Disk, and Azure Monitor.

## Argo CD

A GitOps controller and dashboard that compares desired state in Git with live cluster state. Use "Argo CD" with a space in prose.

## Bare Metal

A Kubernetes environment where the platform team owns the infrastructure layer that cloud providers usually hide: load balancer VIPs, BGP, storage backends, node hardware, routing, and control-plane endpoints.

## CNI

Container Network Interface. The plugin layer that configures pod networking. Examples include Azure CNI, AWS VPC CNI, GKE Dataplane, Calico, Cilium, and Flannel.

## CrashLoopBackOff

A pod state showing that a container repeatedly starts, exits, and is delayed before the next restart. Start with exit code, previous logs, events, command/args, probes, and config dependencies.

## CRD

CustomResourceDefinition. CRDs extend the Kubernetes API. Missing or version-skewed CRDs commonly break Helm, GitOps, operators, and platform add-ons.

## EKS

Amazon Elastic Kubernetes Service, AWS's managed Kubernetes service. EKS-specific troubleshooting often involves AWS VPC CNI, prefix delegation, security groups, ALB/NLB controllers, ECR, IRSA, EBS CSI, CloudWatch, and NAT Gateway paths.

## Endpoint

The backend pod IP and port selected by a Service. If a Service has no endpoints, debug label selectors and pod readiness before debugging ingress or DNS.

## Finalizer

Metadata that blocks deletion until a controller completes cleanup. Removing finalizers can orphan or destroy resources incorrectly, especially for storage objects.

## Flux CD

A GitOps toolkit that reconciles Git repositories, Kustomizations, Helm releases, and other sources into the cluster. Flux CD has no built-in dashboard; Weave GitOps can be installed as an optional UI.

## FQDN

Fully Qualified Domain Name. In production, applications should normally use stable DNS names instead of raw load balancer IPs, `/etc/hosts`, or long-running `kubectl port-forward` sessions.

## GKE

Google Kubernetes Engine, Google Cloud's managed Kubernetes service. GKE-specific troubleshooting often involves VPC-native networking, firewall rules, NEGs, Cloud Load Balancing, Artifact Registry, Cloud NAT, Cloud Monitoring, and Workload Identity.

## GitOps

A delivery model where Git is the desired state and controllers reconcile that state into Kubernetes. Manual live patches create drift unless the change is committed back to Git.

## HPA

Horizontal Pod Autoscaler. HPA scales replicas based on metrics and depends heavily on accurate resource requests.

## ImagePullBackOff

A pod state showing Kubernetes cannot pull the container image. Common causes include wrong tag, missing registry credentials, cloud identity problems, network egress failures, or architecture mismatch.

## Ingress

A Kubernetes API object for HTTP and HTTPS routing into Services. Ingress behavior depends heavily on the installed ingress controller and its annotations.

## IRSA

IAM Roles for Service Accounts. An EKS identity pattern that maps Kubernetes service accounts to AWS IAM roles.

## Kubelet

The node agent that starts pods through the container runtime, reports node and pod status, mounts volumes, and runs probes.

## Namespace

A Kubernetes scope used for ownership, access control, quota, and policy boundaries. Namespaces are not hard security boundaries by themselves; combine them with RBAC, NetworkPolicy, quotas, and admission policy.

## NetworkPolicy

A Kubernetes policy object that controls pod ingress and egress when the CNI enforces it. A policy's existence can change traffic behavior even when Services and endpoints look healthy.

## NodeLocal DNSCache

A node-local DNS cache that reduces DNS latency and conntrack-related UDP drop issues by keeping DNS lookups on the node.

## OOMKilled

A container termination reason indicating the process was killed for memory pressure. Kubernetes memory OOM and GPU VRAM OOM are different failure modes.

## PDB

PodDisruptionBudget. A policy that limits voluntary disruptions. PDBs protect availability but can block drains, upgrades, and autoscaler consolidation.

## PVC

PersistentVolumeClaim. A request for persistent storage. PVCs can be stuck Pending because of StorageClass, provisioner, topology, quota, or scheduling issues.

## Readiness Probe

A probe that decides whether a pod should receive traffic. A failing readiness probe removes the pod from Service endpoints.

## Service

A stable virtual IP and DNS name that selects pod endpoints by labels. If the selector does not match ready pods, traffic has nowhere to go.

## StatefulSet

A workload controller for pods that need stable identity, ordered operations, and persistent storage. StatefulSet pod identity and application quorum are related but not the same thing.

## Taint and Toleration

A taint repels pods from a node; a toleration allows a pod to schedule there. GPU, system, and dedicated node pools commonly rely on taints.

## UDR

User Defined Route in Azure. UDRs are common in AKS environments with firewalls or network virtual appliances.

## VPA

Vertical Pod Autoscaler. VPA recommends or changes CPU and memory requests. In production, recommendation mode is safer unless the team accepts eviction behavior.

## VolumeAttachment

A Kubernetes object that tracks attachment of a persistent volume to a node. Stuck VolumeAttachments often appear during node failures, zone mismatches, or CSI driver issues.
