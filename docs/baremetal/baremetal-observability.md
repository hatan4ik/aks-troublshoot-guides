# Bare Metal Observability

Bare-metal observability depends less on provider consoles and more on the telemetry stack you operate yourself.

---

## Tool Map

| Question | Tool |
| --- | --- |
| Why did the pod restart? | `kubectl describe`, logs, Prometheus |
| Is the node under pressure? | node_exporter, Prometheus, `journalctl` |
| Did traffic hit the cluster at all? | blackbox exporter, ingress logs, packet capture |
| Is the host NIC or kernel failing? | `dmesg`, `journalctl`, switch counters |
| Did a route or VIP move? | BGP daemon logs, Kube-VIP or MetalLB logs |

---

## 1. Cluster Metrics

Prometheus and Grafana should answer:

- node CPU, memory, disk pressure
- pod restart and OOM patterns
- kube-state metrics for workload health

---

## 2. Logs

Typical sources:

- pod logs
- Loki or Elasticsearch
- `journalctl -u kubelet`
- `journalctl -u containerd`

If you cannot answer "when did it start?" from logs, the observability stack is incomplete.

---

## 3. Network And Edge Signals

Use:

- blackbox exporter for ingress reachability
- switch/router logs
- packet capture on nodes

These are often the only way to prove whether a bare-metal networking issue is inside Kubernetes or outside it.

---

## 4. Hardware And Host Signals

Do not stop at Kubernetes when the node itself is unstable.

Check:

- `dmesg`
- NIC driver state
- disk SMART data
- BMC/IPMI alerts

---

## Related References

- [Bare Metal Debugging Framework](../BAREMETAL-DEBUGGING-FRAMEWORK.md)
- [On-Prem Kubernetes Guide](../on-prem-kubernetes.md)

