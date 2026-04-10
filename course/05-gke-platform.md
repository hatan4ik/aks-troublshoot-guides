# Module 5G: GKE Platform Layers

## Purpose

Teach students when to leave pure Kubernetes debugging and move into GKE and Google Cloud diagnostics.

## Required Reading

- [GKE Debugging Framework](../docs/GKE-DEBUGGING-FRAMEWORK.md)
- [GKE Networking Deep Dive](../docs/gcp/gke-networking.md)
- [GCP Observability For GKE](../docs/gcp/gcp-observability.md)

## Learning Objectives

- Recognize firewall, load-balancer, NAT, and Artifact Registry failure patterns
- Understand where GKE Dataplane and Google Cloud boundaries meet
- Know when to shift from `kubectl` to Cloud Logging, Monitoring, and backend health

## Topics

- VPC-native networking
- Dataplane V2 and policy boundaries
- Cloud NAT and private egress
- backend services and NEG health
- Persistent Disk provisioning boundaries

## Suggested Assessment

Give students one of these and ask for the first GCP component to inspect:

- image pulls time out from private nodes
- external ingress returns timeout with healthy pods
- PD-backed PVC remains blocked by topology or provisioning
