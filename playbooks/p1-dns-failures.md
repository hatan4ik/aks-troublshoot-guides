# P1 - DNS Failures

## Symptoms
- Pods cannot resolve services/external hostnames
- `nslookup kubernetes.default` fails
- Widespread 5xx/timeouts due to name resolution

## Immediate Actions
```bash
./scripts/diagnostics/network-diagnostics.sh   # CoreDNS health + DNS test
kubectl get pods -n kube-system -l k8s-app=kube-dns
kubectl get events -n kube-system --sort-by=.lastTimestamp | tail
```

## Mitigation
- Restart unhealthy CoreDNS pods safely:
```bash
python k8s-diagnostics-cli.py fix   # includes fix_dns flow
kubectl rollout restart deploy/coredns -n kube-system
```
- If CPU/memory constrained, temporarily scale CoreDNS: `kubectl scale deploy/coredns -n kube-system --replicas=3`.
- Remove recent faulty configmap updates; revert via GitOps if applicable.

## Verification
```bash
kubectl run dns-test --image=busybox --rm -it --restart=Never -- nslookup kubernetes.default
kubectl get endpoints -A | grep -i <svc>   # ensure endpoints present
```
- Monitor error rates/latency SLIs; ensure alerts clear.

## Prevention
- Resource requests/limits tuned for CoreDNS; autoscale if needed.
- Protect Corefile via policy and GitOps; add alert on CoreDNS restarts and DNS error rate.
