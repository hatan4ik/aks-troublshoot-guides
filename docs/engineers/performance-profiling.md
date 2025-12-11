# Performance Profiling

## Overview
Identify CPU/memory/I/O hotspots and latency paths in Kubernetes workloads.

## Diagnostics
```bash
../../scripts/diagnostics/performance-analysis.sh
kubectl top pods -n <ns>
kubectl get hpa -n <ns>
```
- Capture pprof/Flamegraphs; trace with OpenTelemetry.
- Check throttling: `kubectl describe node <name> | grep -i throttling -A2`

## Fixes
- Tune requests/limits to avoid throttling; add HPA/VPA.
- Optimize queries/cache; reduce chattiness between services.
- Profile runtime (py-spy, go tool pprof, perf).

## Prevention
- Load tests pre-release; budgets for latency and error rate.
- Continuous profiling in staging; alert on regressions.
