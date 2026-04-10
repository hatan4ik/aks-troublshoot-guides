# GKE Networking Deep Dive

Google Kubernetes Engine runs on top of Google Cloud networking primitives. When pods are healthy but traffic still fails, the problem is often in the Google Cloud layer around the cluster.

---

## Quick Reference

| Symptom | Most likely layer |
| --- | --- |
| `ImagePullBackOff` with timeout | Cloud NAT, Private Google Access, or Artifact Registry path |
| Service or ingress exists but traffic fails | backend service, NEG, or firewall |
| Cross-node traffic drops | Dataplane, routing, or policy |
| Private cluster access fails | authorized networks, DNS, or control plane access path |
| PVC / PD attach fails | zone or CSI issue |

---

## 1. VPC-Native And Dataplane

Many GKE clusters use VPC-native networking with alias IPs. Dataplane V2 changes how networking and policy are enforced.

Check:

```bash
kubectl get nodes
kubectl get pods -n kube-system
kubectl get networkpolicy -A
```

Look for:

- pod-to-pod traffic issues
- policy enforcement failures
- kube-dns/CoreDNS degradation

---

## 2. Firewall Rules

Google Cloud firewall rules often explain timeouts when Kubernetes objects are correct.

```bash
gcloud compute firewall-rules list
```

Use firewall investigation when:

- health checks fail externally
- traffic reaches the load balancer but not the nodes
- private control plane access is blocked

---

## 3. Cloud NAT And Private Egress

If nodes are private and images or external dependencies time out, inspect:

- Cloud NAT
- Private Google Access
- Artifact Registry reachability

```bash
kubectl run nettest --image=nicolaka/netshoot --rm -it --restart=Never -- \
  curl -I https://<region>-docker.pkg.dev
```

---

## 4. Load Balancing And NEGs

GKE ingress often depends on Google Cloud backend services and NEGs.

```bash
gcloud compute backend-services list
gcloud compute backend-services get-health <backend-service> --global
```

Look for:

- unhealthy backends
- service/ingress mismatch
- firewall rules blocking health probes

---

## Related References

- [GKE Debugging Framework](../GKE-DEBUGGING-FRAMEWORK.md)
- [GCP Observability For GKE](./gcp-observability.md)

