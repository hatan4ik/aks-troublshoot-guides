# Engineering Team Guide
Ship and debug services in Kubernetes. This guide favors short checklists and runnable commands.

## Your Lens
- Build and ship containers; own startup/runtime health.
- Debug pods, configs, and dependencies quickly.
- Keep dev/stage environments reproducible.

## Chapters
- Apps: [Pod Startup](pod-startup-issues.md), [Container Images](container-images.md), [Config Management](config-management.md), [Secrets & ConfigMaps](secrets-configmaps.md)
- Workflows: [Local Dev](local-development.md), [Debugging Techniques](debugging-techniques.md), [Testing Strategies](testing-strategies.md), [Performance Profiling](performance-profiling.md)

## Fast Commands
```bash
kubectl describe pod <pod> -n <ns>
kubectl logs <pod> -n <ns> --all-containers --tail=200
kubectl exec -it <pod> -n <ns> -- sh
kubectl port-forward <pod> -n <ns> 8080:8080
kubectl get events -n <ns> --sort-by=.lastTimestamp | tail
```

## Run These First When Things Break
- Pod-level triage: `../../scripts/diagnostics/pod-diagnostics.sh <pod> <ns>`
- Resource pressure: `../../scripts/diagnostics/resource-analysis.sh`
- Network/DNS: `../../scripts/diagnostics/network-diagnostics.sh`
- Deployment stuck: `../../scripts/diagnostics/deployment-diagnostics.sh <deploy> <ns>`
