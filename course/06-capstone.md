# Module 6: Capstone

## Goal

Students debug a broken AKS-like environment without being told the bug in advance. They must investigate, patch, and verify recovery.

## Capstone Format

Pick one of these formats:

### Option A: Multi-Issue Namespace

Apply 3-5 manifests from `practice/` into the same namespace and ask students to restore service in priority order.

Recommended set:

- `02-port-mismatch.yaml`
- `07-crashloop-bad-command.yaml`
- `10-networkpolicy-blocks-ingress.yaml`
- `13-pvc-wrong-storageclass.yaml`

### Option B: AKS Escalation Scenario

Start with a workload failure that looks like Kubernetes, then provide Azure-side evidence that proves the issue is really:

- ACR egress blockage
- Azure LB health probe mismatch
- Azure CNI or subnet IP exhaustion

## Student Deliverables

- Failure classification by layer
- Evidence trail
- Exact fix
- Verification steps
- Brief incident summary

## Minimum Verification Standard

```bash
kubectl rollout status deployment/<deployment> -n <ns>
kubectl get pods -n <ns>
kubectl get endpoints -n <ns>
kubectl logs <pod> -n <ns> --tail=50
```

## Scoring Rubric

### Excellent

- Correctly identifies the failure layer
- Uses the right evidence first
- Makes the smallest safe fix
- Verifies recovery completely
- Explains tradeoffs clearly

### Acceptable

- Finds the right root cause eventually
- Fixes the issue with limited unnecessary changes
- Performs partial verification

### Weak

- Guesses without evidence
- Applies broad or risky changes
- Cannot explain why the fix worked

## Instructor Notes

- Do not provide `practice/SOLUTIONS.md`
- Force students to narrate before they patch
- Reward method, not just speed
