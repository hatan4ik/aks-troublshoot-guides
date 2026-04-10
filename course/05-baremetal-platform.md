# Module 5B: Bare Metal Platform Layers

## Purpose

Teach students when to leave pure Kubernetes debugging and move into the physical infrastructure they operate directly.

## Required Reading

- [Bare Metal Debugging Framework](../docs/BAREMETAL-DEBUGGING-FRAMEWORK.md)
- [On-Prem Kubernetes Guide](../docs/on-prem-kubernetes.md)
- [Bare Metal Networking](../docs/baremetal/baremetal-networking.md)
- [Bare Metal Observability](../docs/baremetal/baremetal-observability.md)

## Learning Objectives

- Recognize when the failure is in switching, routing, VIP ownership, or storage infrastructure
- Understand MetalLB, Kube-VIP, MTU, BGP, and storage-backend failure patterns
- Know what evidence proves the cluster is healthy but the physical layer is not

## Topics

- MetalLB and Kube-VIP
- BGP and route advertisement
- MTU and CNI interaction
- storage backend and provisioner failures
- node, NIC, switch, and hypervisor boundaries

## Suggested Assessment

Give students one of these and ask for the first physical component to inspect:

- service `LoadBalancer` stays pending
- traffic only reaches one node
- cross-node traffic fails with healthy pods

