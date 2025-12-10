# Engineering Team Guide

## Overview
Development-focused troubleshooting for application deployment, debugging, and development workflows in Kubernetes.

## Key Responsibilities
- Application containerization and deployment
- Debugging application issues in Kubernetes
- Development environment setup and maintenance
- Integration with CI/CD pipelines

## Quick Reference

### Application Issues
- [Pod Startup Problems](pod-startup-issues.md)
- [Container Image Issues](container-images.md)
- [Configuration Management](config-management.md)
- [Secrets and ConfigMaps](secrets-configmaps.md)

### Development Workflows
- [Local Development Setup](local-development.md)
- [Debugging Techniques](debugging-techniques.md)
- [Testing Strategies](testing-strategies.md)
- [Performance Profiling](performance-profiling.md)

### Common Troubleshooting Commands
```bash
# Pod debugging
kubectl describe pod <pod-name>
kubectl logs <pod-name> -f
kubectl exec -it <pod-name> -- /bin/bash

# Application debugging
kubectl port-forward <pod-name> 8080:8080
kubectl get events --sort-by=.metadata.creationTimestamp
```

### Troubleshooting Focus Areas
1. **Application crashes** - Exit codes, resource limits, dependencies
2. **Connectivity issues** - Service discovery, DNS, network policies
3. **Performance problems** - Resource requests/limits, JVM tuning
4. **Configuration errors** - Environment variables, mounted volumes

## Emergency Escalation
For application-critical issues:
1. Run application diagnostics: `./scripts/diagnostics/app-health-check.sh`
2. Check resource utilization: `./scripts/diagnostics/resource-analysis.sh`
3. Escalate to Senior Engineer if code changes needed