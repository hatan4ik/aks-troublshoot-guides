# DevOps Team Guide
Run delivery, infra automation, and safe rollouts. This guide emphasizes short runbooks and reproducible steps.

## Your Lens
- Keep CI/CD green and fast.
- Automate cluster/node/network/storage baselines.
- Ship changes safely (blue/green, canary, rolling, GitOps).

## Chapters
- Pipelines: [Build Failures](build-failures.md), [Deployment Failures](deployment-failures.md), [Registry Issues](registry-issues.md), [Rollback Procedures](rollback-procedures.md)
- Infra: [Cluster Provisioning](cluster-provisioning.md), [Node Management](node-management.md), [Networking Setup](networking-setup.md), [Storage Configuration](storage-configuration.md)
- Strategies: [Blue-Green](blue-green.md), [Canary](canary.md), [Rolling Updates](rolling-updates.md), [GitOps](gitops.md)

## Run These First
```bash
../../scripts/diagnostics/cluster-health-check.sh
../../scripts/diagnostics/pipeline-debug.sh
../../scripts/diagnostics/deployment-diagnostics.sh <deployment> <namespace>
../../scripts/diagnostics/resource-analysis.sh
../../scripts/diagnostics/performance-analysis.sh
../../scripts/diagnostics/security-audit.sh
```

## Troubleshooting Focus
- Pipelines: build/test/publish failures, registry auth/rate limits.
- Deployments: rollout stalls, probe failures, image pulls, config drift.
- Infra: node readiness, CNI/DNS/ingress, storage attach/bind.
- Drift/GitOps: ensure desired state via `gitops-diagnostics.sh` and `helm-diagnostics.sh`.
