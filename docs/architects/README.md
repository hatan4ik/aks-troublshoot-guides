# Architecture Team Guide
Design for resilience, security, and scale. Use these chapters to set guardrails and diagnose systemic issues.

## Your Lens
- Shape cluster/network/storage/multi-tenancy strategy.
- Enforce security and compliance baselines.
- Plan for performance, capacity, and DR.

## Chapters
- Patterns: [Multi-tenancy](multi-tenancy.md), [Network](network-architecture.md), [Security](security-architecture.md), [Disaster Recovery](disaster-recovery.md)
- Design Decisions: [Cluster Sizing](cluster-sizing.md), [Node Pools](node-pools.md), [Storage Architecture](storage-architecture.md), [Service Mesh](service-mesh.md)

## When Things Break
- Cluster-level health: `./scripts/diagnostics/cluster-health-check.sh`
- Security posture: `./scripts/diagnostics/security-audit.sh`
- Network/DNS: `./scripts/diagnostics/network-diagnostics.sh`
- Storage binding/attach: `./scripts/diagnostics/storage-analysis.sh`

Escalate design changes early if issues recur across teams.
