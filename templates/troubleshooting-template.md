# [Issue Title] Troubleshooting Guide
Concise, task-first template in the O’Reilly style.

## Overview
What is broken, who it hurts, and the observed impact.

## Symptoms
- Primary signals (errors, statuses, user impact)
- Scope (namespaces/services/components affected)

## Prerequisites
- Required tools/context (kubectl context, cloud CLI)
- Access level (RBAC/IAM)
- Data to capture before changes

## Common Causes
1. **Cause 1** — why it happens; likelihood
2. **Cause 2** — why it happens; likelihood
3. **Cause 3** — why it happens; likelihood

## Diagnose
```bash
# 1) Baseline status
kubectl get <resource>

# 2) Details and events
kubectl describe <resource> <name>

# 3) Logs
kubectl logs <pod-name>
```
- Add any provider-specific checks (AKS/EKS) here.

## Resolve
### Quick Fix (stabilize)
```bash
kubectl <command>
```

### Permanent Fix (eliminate root cause)
1. **Step 1**: Explanation + command
   ```bash
   kubectl <command>
   ```
2. **Step 2**: Config change
   ```yaml
   # YAML snippet
   ```
3. **Step 3**: Verify
   ```bash
   kubectl get <resource>
   ```

## Prevention
- Guardrails, alerts, and policies
- Config or coding practices to avoid recurrence

## Automation
- Scripts/API endpoints to run
- Alerts to configure; self-heal hooks

## Related
- Linked guides, dependencies, follow-on issues

## Escalation
- When to page; required evidence; contacts

---
**Difficulty**: [Beginner/Intermediate/Advanced]  
**Platform**: [AKS/EKS/GKE/Kubernetes]  
**Component**: [Networking/Storage/Security/Compute]  
**Last Updated**: [Date]  
**Reviewed By**: [Team/Role]
