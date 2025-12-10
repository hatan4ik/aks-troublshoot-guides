# [Runbook Title]

## Overview
Purpose, trigger conditions, and expected outcomes. Include severity level and who runs this.

## Preconditions
- Access/permissions required
- Tools/contexts (kubectl context, cloud CLI)
- Data to capture before changes

## Workflow
1. **Detect** – how this runbook is triggered (alert name, metric, symptom)
2. **Validate** – commands/queries to confirm the issue
3. **Mitigate** – fast containment steps
4. **Remediate** – permanent fix
5. **Verify** – checks to prove recovery

## Detailed Steps
### Detect
```bash
# Example
kubectl get events -A --field-selector type=Warning
```

### Validate
- What “bad” looks like (logs/metrics)
- What “good” looks like

### Mitigate (Immediate)
```bash
# Minimal safe action to stop the bleeding
kubectl <command>
```

### Remediate (Permanent)
```bash
# Config change / rollout / infra change
kubectl apply -f <file>
```

### Verify
```bash
# Post-fix checks
kubectl get pods -A
```

## Rollback
- Steps to revert changes
- Data to snapshot before rollback

## Automation Hooks
- Script/API to run (`./scripts/...`, REST, CLI)
- Feature flags or toggles

## Communication
- Who to page/escalate
- Status update cadence and channels

## Post-Incident
- Required tickets/notes
- Follow-up tasks and owners

---
**Difficulty**: [Beginner/Intermediate/Advanced]  
**Platform**: [AKS/EKS/GKE/Kubernetes]  
**Component**: [Networking/Storage/Security/Compute]  
**Last Updated**: [Date]  
**Reviewed By**: [Team/Role]
