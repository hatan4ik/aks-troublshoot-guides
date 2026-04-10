# Module 5: Provider Overlays

## Purpose

The first four modules are shared Kubernetes core. This module is where the course branches by platform.

Choose the provider overlay that matches the environment you run most often:

- AKS
- EKS
- GKE
- bare metal / on-prem

## Why This Module Exists

The debugging workflow should not be re-taught four times. Pods, services, endpoints, probes, DNS, and scheduling work the same way everywhere.

The provider overlay exists to answer one question:

**When the Kubernetes path is clean, what outer infrastructure should you investigate next?**

## Shared Learning Objectives

- Recognize when the problem has moved beyond pure Kubernetes
- Understand the provider-specific control points around networking, storage, identity, and observability
- Know what evidence to collect before escalating to platform or cloud teams

## Choose One Or Compare Several

- [AKS Platform Layers](./05-aks-platform.md)
- [EKS Platform Layers](./05-eks-platform.md)
- [GKE Platform Layers](./05-gke-platform.md)
- [Bare Metal Platform Layers](./05-baremetal-platform.md)

## Teaching Recommendation

- Single-provider course: teach one provider track deeply
- Multi-cloud course: teach one provider deeply, then compare the others at the framework level
- Platform architecture course: compare all four by failure boundary rather than by CLI syntax

## Core Rule

Do not turn provider overlays into duplicate Kubernetes content. Reuse the shared debugging core and teach only the provider-specific outer layers here.

