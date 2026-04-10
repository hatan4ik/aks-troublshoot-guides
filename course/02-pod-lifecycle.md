# Module 2: Pod Lifecycle, Probes, Config, And Runtime Failures

## Purpose

Teach students to handle the most common AKS and Kubernetes failures: pods that never start, start and crash, or restart because probes are wrong.

## Required Reading

- [Pod Startup Issues](../docs/engineers/pod-startup-issues.md)
- [Advanced Debugging Techniques](../docs/engineers/debugging-techniques.md)
- [Common Issues Playbook](../playbooks/common-issues.md)

## Learning Objectives

- Diagnose `ImagePullBackOff`, `CrashLoopBackOff`, `OOMKilled`, and `CreateContainerConfigError`
- Use exit codes correctly
- Identify bad commands, missing config keys, probe failures, and memory limit failures
- Explain why a pod can be healthy but still fail liveness

## Lecture Arc

1. Events and pod status fields
2. `kubectl logs --previous`
3. Exit codes: `127`, `137`, `143`
4. ConfigMaps, Secrets, and entrypoint mismatches
5. Probe design: readiness, liveness, startup

## Hands-On Labs

Required:

- `practice/01-image-pull-backoff.yaml`
- `practice/05-missing-configmap-key.yaml`
- `practice/07-crashloop-bad-command.yaml`
- `practice/14-oomkilled.yaml`
- `practice/15-liveness-kills-healthy-app.yaml`

Stretch:

- `practice/16-init-container-fails.yaml`
- `practice/17-wrong-secret-name.yaml`
- `practice/19-job-backoff-exceeded.yaml`

## Teaching Notes

- Make students say the exit code before they patch anything
- When logs are empty, force them back to `describe pod`
- Treat probe failures as contract bugs, not app crashes

## Assessment Prompt

Give students a crashing pod and ask for:

1. The failure class
2. The decisive signal
3. The smallest safe fix
4. The verification command
