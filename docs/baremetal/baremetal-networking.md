# Bare Metal Networking

Bare-metal Kubernetes networking is where physical and logical failure modes meet. When pods are healthy but traffic still fails, you must consider switch behavior, routing, MTU, and whatever provides your service IPs.

---

## Quick Reference

| Symptom | Most likely layer |
| --- | --- |
| Service `LoadBalancer` stuck pending | no CCM, MetalLB, or VIP path |
| Traffic reaches one node only | L2 advertisement or VIP ownership issue |
| Cross-node pod traffic drops | MTU, routing, or CNI |
| API VIP flaps | Keepalived or Kube-VIP split brain |
| DNS breaks intermittently | CoreDNS or upstream resolver path |

---

## 1. Service IP Advertisement

Bare-metal clusters often use:

- MetalLB L2 mode
- MetalLB BGP mode
- Kube-VIP

Investigate:

```bash
kubectl get svc -A
kubectl get pods -n metallb-system
kubectl logs -n metallb-system deploy/controller --tail=50
```

At the network layer:

```bash
tcpdump -i <iface> arp
ip addr show
```

---

## 2. BGP And Routing

If you use MetalLB BGP or similar, check:

- peering status
- route advertisement
- route flapping

Typical tools:

```bash
birdc show protocols
ip route
```

---

## 3. MTU And CNI

Timeouts across nodes often come from MTU mismatch or encapsulation problems.

Check:

- underlay MTU
- overlay header size
- CNI daemonset health

---

## 4. Firewall And ACL Boundaries

Even without a cloud provider, traffic may still be filtered by:

- switch ACLs
- upstream firewalls
- hypervisor security policy

Use timeouts, packet captures, and route validation to isolate where packets disappear.

---

## Related References

- [Bare Metal Debugging Framework](../BAREMETAL-DEBUGGING-FRAMEWORK.md)
- [On-Prem Kubernetes Guide](../on-prem-kubernetes.md)

