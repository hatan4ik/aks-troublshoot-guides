# GCP Observability For GKE

Observability on GKE means combining Kubernetes evidence with Google Cloud logging and monitoring.

---

## Tool Map

| Question | Tool |
| --- | --- |
| Why did a pod crash? | `kubectl describe`, Cloud Logging |
| Is the node pool unhealthy? | Cloud Monitoring |
| Did the load balancer consider backends unhealthy? | backend service health + Cloud Logging |
| What firewall or network path dropped traffic? | VPC Flow Logs |
| Who changed the environment? | Cloud Audit Logs |

---

## 1. Cloud Logging

Use Cloud Logging for:

- kube-system logs
- pod logs
- control plane and ingress path signals

This is especially useful when the issue happened earlier and `kubectl logs` no longer contains the relevant evidence.

---

## 2. Cloud Monitoring

Use Cloud Monitoring for:

- node CPU and memory
- restart trends
- latency and error-rate dashboards
- control plane metrics where available

---

## 3. VPC Flow Logs

Use Flow Logs when:

- traffic times out
- firewall rules are suspected
- private-cluster egress is broken

This is the first place to confirm whether packets were rejected or never routed.

---

## 4. Cloud Audit Logs

Use Audit Logs to identify:

- IAM changes
- firewall rule changes
- load balancer changes
- cluster or node pool modifications

---

## 5. Suggested Investigation Order

1. `kubectl`
2. Cloud Logging
3. backend service health
4. VPC Flow Logs
5. Cloud Audit Logs

---

## Related References

- [GKE Debugging Framework](../GKE-DEBUGGING-FRAMEWORK.md)
- [GKE Networking Deep Dive](./gke-networking.md)

