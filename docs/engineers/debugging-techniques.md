# Debugging Techniques

## Overview
Triage pod/service issues quickly with consistent steps.

## Checklist
```bash
../../scripts/diagnostics/pod-diagnostics.sh <pod> <ns>
kubectl logs <pod> -n <ns> --all-containers --tail=200
kubectl describe pod <pod> -n <ns>
```
- Exec into pod: `kubectl exec -it <pod> -n <ns> -- sh`
- Capture events and node status if scheduling issues.

## Patterns
- Separate startup vs readiness problems (use startup probes for slow boot).
- Check dependencies via port-forward to DB/cache.
- Use `kubectl debug node/...` for node-level issues.

## Deep Dive: The "Packet Walk" (kubectl exec)
Understanding `kubectl exec` helps diagnose connection drops:
1. **Client**: `kubectl` sends HTTP Upgrade (SPDY/Websocket) request to API Server.
2. **API Server**: Proxies connection to the **Kubelet** (port 10250) on the target node.
3. **Kubelet**: Calls CRI (containerd) -> `runc` to join the container's namespaces.
4. **Insight**: Traffic flows *through* the API server. Heavy data transfer via `exec`/`cp` can destabilize the control plane.

## Deep Dive: Pod Termination & Traffic
If pods fail requests *during* scaling/shutdown:
1. **Race Condition**: `SIGTERM` (app shutdown) often beats the Endpoints Controller (removing IP from Service/LB).
2. **Result**: Traffic hits a dying pod.
3. **Fix**: Add a `preStop` hook (`sleep 10`) to allow LB propagation before app stops.

## Automation
- API: `GET /diagnose/pod/{ns}/{pod}` from `src/k8s_diagnostics/api/server.py`.
- CLI: `python k8s-diagnostics-cli.py diagnose <ns> <pod>`.

## Prevention
- Structured logging with correlation IDs.
- Health/metrics exporters for visibility.
