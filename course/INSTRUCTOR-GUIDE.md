# Instructor Guide

## Teaching Philosophy

Teach this repo as a debugging system, not a documentation tour.

Students should learn:

- a stable investigation order
- how to prove a root cause
- how to avoid jumping to Azure too early

## Recommended Teaching Pattern

For each module:

1. Explain the failure layer
2. Demo one scenario live
3. Put students into labs with symptoms only
4. Review the evidence they used
5. Close with a short AKS-specific overlay

## Timing Guide

### 5-Day Bootcamp

| Day | Focus | Lecture | Lab | Review |
| --- | --- | --- | --- | --- |
| 1 | Foundations | 45m | 45m | 30m |
| 2 | Pod lifecycle | 45m | 90m | 30m |
| 3 | Networking | 45m | 90m | 30m |
| 4 | Scheduling and storage | 45m | 90m | 30m |
| 5 | AKS platform + capstone | 60m | 120m | 30m |

### 2-Day Intensive

| Day | Focus |
| --- | --- |
| 1 | Foundations, pod lifecycle, networking |
| 2 | Scheduling, AKS platform, capstone |

## Lab Facilitation Rules

- Do not reveal the filename bug until the end
- Require students to read events first
- Ask "what layer is this?" before "what command is next?"
- Do not accept "restart it" as a diagnosis

## Suggested Lab Mapping

| Module | Required Labs |
| --- | --- |
| Foundations | 01, 04 |
| Pod lifecycle | 05, 07, 14, 15, 16, 17 |
| Networking | 02, 03, 10, 11 |
| Scheduling and storage | 06, 08, 09, 13, 18 |
| Capstone | Mix 02, 07, 10, 13 or an AKS case study |

## Instructor-Only References

- [practice/SOLUTIONS.md](../practice/SOLUTIONS.md)
- [P0 Cluster Outage](../playbooks/p0-cluster-outage.md)
- [P1 DNS Failures](../playbooks/p1-dns-failures.md)

## What To Emphasize Repeatedly

- Empty endpoints means selector or readiness, not DNS
- Timeout and refusal are different failure classes
- Probe bugs often look like app bugs
- Many AKS incidents are still fixable with pure `kubectl`
- Azure escalation starts only after Kubernetes evidence is clean
