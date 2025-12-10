# Debugging Techniques

## Overview
Triage pod/service issues quickly with consistent steps.

## Checklist
```bash
./scripts/diagnostics/pod-diagnostics.sh <pod> <ns>
kubectl logs <pod> -n <ns> --all-containers --tail=200
kubectl describe pod <pod> -n <ns>
```
- Exec into pod: `kubectl exec -it <pod> -n <ns> -- sh`
- Capture events and node status if scheduling issues.

## Patterns
- Separate startup vs readiness problems (use startup probes for slow boot).
- Check dependencies via port-forward to DB/cache.
- Use `kubectl debug node/...` for node-level issues.

## Automation
- API: `GET /diagnose/pod/{ns}/{pod}` from `src/k8s_diagnostics/api/server.py`.
- CLI: `python k8s-diagnostics-cli.py diagnose <ns> <pod>`.

## Prevention
- Structured logging with correlation IDs.
- Health/metrics exporters for visibility.
