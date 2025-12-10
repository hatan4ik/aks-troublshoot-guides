# Cluster Sizing Guidelines

## Overview
Right-size control plane and node pools for cost, performance, and reliability.

## Inputs
- Workload profiles (CPU/memory intensity, burst patterns)
- Peak/steady traffic and HPA targets
- Pod density constraints (ENI/IP limits, daemonsets)
- Availability requirements (AZs, PDBs)

## Quick Method
1. **Baseline utilization**: `./scripts/diagnostics/resource-analysis.sh`
2. **Density**: Max pods per node (CNI specific); ensure room for system pods and DaemonSets.
3. **Headroom**: 20–30% spare for failover and bursts.
4. **Autoscaling**: Enable cluster autoscaler with min/max per pool.

## AKS Notes
- Azure CNI pod-per-node depends on subnet IPs; consider CNI overlay.
- Use separate system/user node pools; use ephemeral OS disks where possible.

## EKS Notes
- ENI/IP caps vary by instance type; enable prefix delegation.
- Mixed instance groups for resilience and cost; Bottlerocket for minimal OS.

## Validation
```bash
./scripts/diagnostics/performance-analysis.sh
kubectl top nodes
kubectl get hpa -A
```
- Simulate load (k6/locust) and observe scaling.

## Prevention
- Enforce LimitRange defaults; set PDBs to protect during scale-down.
- Regular capacity reviews using metrics exports and `health-dashboard.sh`.
