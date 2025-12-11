# Emergency Response Guide

## Overview
Standard response for P0/P1 Kubernetes/AKS/EKS incidents. Goal: restore service fast, capture data, and communicate clearly.

## Roles
- **Incident Commander (IC)**: Coordinates response and comms.
- **Ops Lead**: Executes mitigations in cluster/cloud.
- **Comms**: Stakeholder updates.
- **Scribe**: Notes and timeline.

## Initial Actions (First 5 Minutes)
1. Declare incident, assign IC.
2. Page on-call and open bridge/channel.
3. Run quick health checks:
```bash
../scripts/diagnostics/cluster-health-check.sh
../scripts/diagnostics/network-diagnostics.sh
../scripts/diagnostics/pod-diagnostics.sh -a <namespace>
```
4. Capture events/logs; avoid speculative changes.

## Stabilize (Containment)
- Roll back breaking deploys: `kubectl rollout undo` or GitOps revert.
- Scale out healthy versions; drain bad nodes; restart failed critical pods via `python k8s-diagnostics-cli.py fix`.
- Disable non-critical workloads if resource starved.

## Communicate
- Cadence: every 15–30 minutes for P0/P1.
- Channels: Slack/Teams + status page if user-visible.
- Include: impact, scope, actions, ETA/next update.

## Escalation
- Cloud provider ticket (AKS/EKS) if control plane/infra suspected.
- Security on-call if breach indicators.

## Verification
- Rerun diagnostics scripts; check SLIs (latency, availability, errors).
- Confirm alerts cleared; validate customer journeys.

## Post-Incident
- Open post-mortem using `../templates/post-mortem-template.md`.
- Create action items (prevent/detect/mitigate).
