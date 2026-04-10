# AKS Networking Deep Dive

Azure Kubernetes Service sits on top of Azure networking primitives. When `kubectl` shows a healthy cluster but traffic still fails, the problem is almost always in one of these layers. This guide covers each one with diagnosis commands.

---

## Quick Reference: Which Layer Is Failing?

| Symptom | Most likely layer |
| --- | --- |
| Pod `ImagePullBackOff` with timeout | NSG blocking egress to ACR |
| Pod Running, inter-pod traffic times out | NSG or UDR on node subnet |
| Service `LoadBalancer` stuck `<pending>` | Azure LB provisioning / quota |
| Ingress IP assigned but 502 | Azure LB health probe vs readiness probe mismatch |
| Pod-to-pod works, pod-to-internet fails | SNAT exhaustion or missing NAT Gateway |
| DNS resolves inside cluster, fails outside | Private DNS zone / custom DNS misconfiguration |
| Private cluster: `kubectl` fails from on-prem | Private endpoint / VNet peering / DNS |

---

## 1. Azure CNI vs Kubenet

Understanding which CNI your cluster uses changes how you debug networking failures.

### Azure CNI (default for most AKS clusters)

```
Pods get real VNet IPs from the node subnet.
No overlay — pod traffic is native VNet traffic.
NSG rules apply directly to pod IPs.
Route tables see pod CIDRs natively.
```

```bash
# Check which CNI is in use
az aks show -g <rg> -n <cluster> --query 'networkProfile.networkPlugin'
# "azure" = Azure CNI, "kubenet" = Kubenet
```

**Azure CNI failure patterns:**

| Failure | Cause | Diagnosis |
| --- | --- | --- |
| Node pool can't scale | IP exhaustion in subnet | `az network vnet subnet show` → available IPs |
| New pods stay Pending | No free IPs for CNI to assign | Check `azure-cni` pod logs |
| Cross-node traffic drops | NSG blocks pod CIDR | NSG effective rules on NIC |

```bash
# Check IP exhaustion
az network vnet subnet show -g <node-rg> \
  --vnet-name <vnet> --name <subnet> \
  --query '[availableIpAddressCount, addressPrefix]'

# Check azure-cni pod logs
kubectl logs -n kube-system -l k8s-app=azure-cni --tail=50
```

### Kubenet

```
Nodes get VNet IPs. Pods get addresses from a private pod CIDR (not routable in VNet).
Overlay via routing table — each node has a route entry for its pod CIDR.
NSG rules apply to node IPs, not pod IPs directly.
UDR can break pod routing if not configured correctly.
```

**Kubenet failure patterns:**

| Failure | Cause | Diagnosis |
| --- | --- | --- |
| Cross-node pod traffic fails | Missing or incorrect UDR route | Check route table in node resource group |
| BGP/ExpressRoute drops pod traffic | Pod CIDR not advertised | Route table propagation settings |

```bash
# Check route table entries for pod CIDRs
az network route-table list -g <node-rg> -o table
az network route-table route list -g <node-rg> --route-table-name <rt> -o table
# Each node should have a route: pod-cidr → node-ip (VirtualAppliance or VnetLocal)
```

---

## 2. NSG (Network Security Group) Troubleshooting

NSGs are the most common reason Layer 5 failures look like Layer 3 failures. The pod is healthy, endpoints exist, but traffic drops silently.

### AKS NSG architecture

```
Internet
    │
    ▼
Load Balancer (Azure LB / AGIC)
    │
    ▼
NSG on node subnet  ◄── This is where traffic gets dropped
    │
    ▼
Node NIC
    │
    ▼
Pod (Azure CNI: pod IP = VNet IP)
```

### Find the NSG

```bash
# AKS manages a node resource group (MC_*)
az aks show -g <rg> -n <cluster> --query nodeResourceGroup -o tsv

# List NSGs in the node resource group
az network nsg list -g MC_<rg>_<cluster>_<region> -o table

# Show all rules (look for DENY rules that might be catching your traffic)
az network nsg rule list -g MC_<rg>_<cluster>_<region> \
  --nsg-name <nsg-name> --include-default -o table
```

### Effective security rules on a specific node NIC

```bash
# Get node NIC name
az vm nic list -g MC_<rg>_<cluster>_<region> --vm-name <node-vm> -o table

# Show effective rules — this shows what is ACTUALLY applied, including inherited rules
az network nic show-effective-nsg \
  -g MC_<rg>_<cluster>_<region> \
  -n <nic-name> \
  --query 'effectiveSecurityRules[?access==`Deny`]' -o table
```

### Required AKS NSG rules (do not block these)

| Direction | Port | Protocol | Purpose |
| --- | --- | --- | --- |
| Inbound | 443 | TCP | API server to kubelet |
| Inbound | 10250 | TCP | Kubelet API (metrics, exec, logs) |
| Inbound | 30000-32767 | TCP/UDP | NodePort services |
| Outbound | 443 | TCP | ACR, MCR, Azure APIs |
| Outbound | 9000, 443 | TCP | Tunnel to AKS control plane |
| Outbound | 123 | UDP | NTP |
| Outbound | 53 | UDP/TCP | DNS |

```bash
# Test connectivity from inside a pod to ACR (common ImagePullBackOff cause)
kubectl run nettest --image=nicolaka/netshoot --rm -it --restart=Never -- \
  curl -v https://<acr-name>.azurecr.io/v2/
# "connection timed out" = NSG blocking 443 egress
# "401 Unauthorized" = NSG is fine, auth issue
```

---

## 3. Azure Load Balancer

### How AKS uses Azure LB

When you create a Service of type `LoadBalancer`, the AKS cloud controller manager provisions an Azure LB rule and backend pool automatically. The LB health probe is separate from the Kubernetes readiness probe.

```
Client → Azure LB → LB Health Probe (TCP/HTTP on NodePort) → Node → kube-proxy → Pod
                                                                         ↑
                                                              Kubernetes readiness probe
                                                              is separate from this
```

**Key insight:** the Azure LB health probe checks the NodePort on the node, not the pod's readiness directly. If the LB probe fails, traffic stops even if all pods are `Ready`.

### Diagnose a stuck LoadBalancer

```bash
# Service stuck at <pending> external IP
kubectl get svc <svc> -n <ns>
kubectl describe svc <svc> -n <ns>
# Events: "Error creating load balancer" → check Azure quota and permissions

# Check cloud controller manager logs
kubectl logs -n kube-system -l component=cloud-controller-manager --tail=50
```

### Find and inspect the Azure LB

```bash
# AKS LB is in the node resource group
az network lb list -g MC_<rg>_<cluster>_<region> -o table

# Show backend pool — should list all nodes
az network lb address-pool list \
  -g MC_<rg>_<cluster>_<region> \
  --lb-name <lb-name> -o table

# Show health probes
az network lb probe list \
  -g MC_<rg>_<cluster>_<region> \
  --lb-name <lb-name> -o table
# Protocol, port, intervalInSeconds, numberOfProbes
```

### LB health probe vs readiness probe mismatch

```bash
# The LB probes the NodePort on each node.
# If kube-proxy isn't routing to healthy pods, the probe may fail
# even when pods report Ready.

# Verify NodePort is accessible on the node
kubectl get svc <svc> -n <ns>
# Note the NodePort number (3xxxx range)

# From a node or jump host:
curl http://<node-ip>:<nodeport>/
# If this fails, kube-proxy or NetworkPolicy is blocking
```

### Common LB failures

| Symptom | Cause | Fix |
| --- | --- | --- |
| `<pending>` external IP > 10 min | Quota exhausted or missing permissions | Check `az network lb` events, check service principal permissions |
| IP assigned, 502 from LB | LB probe fails — no healthy backends | Verify NodePort reachable on node |
| IP assigned, works intermittently | Only some nodes pass LB probe | Check if some nodes have NetworkPolicy blocking NodePort |
| Annotations not applying | AGIC / ALB Controller not watching | Check AGIC pod logs in `kube-system` |

---

## 4. User-Defined Routes (UDR)

UDRs can silently break AKS networking, especially in hub-and-spoke architectures where traffic routes through a firewall (Azure Firewall / NVA).

### How UDRs break AKS

```
Symptom: pods schedule and start, but inter-cluster or egress traffic fails.
Cause:   0.0.0.0/0 UDR routes traffic through firewall that drops AKS control plane traffic.
```

```bash
# Check route table on the node subnet
az network vnet subnet show \
  -g <vnet-rg> --vnet-name <vnet> --name <node-subnet> \
  --query routeTable.id -o tsv

# List routes — look for 0.0.0.0/0 pointing to NVA/Firewall
az network route-table route list \
  -g <rg> --route-table-name <rt-name> -o table
```

### Required egress FQDNs (must be allowed through firewall)

| FQDN | Port | Purpose |
| --- | --- | --- |
| `*.hcp.<region>.azmk8s.io` | 443 | AKS API server |
| `mcr.microsoft.com` | 443 | Microsoft Container Registry |
| `*.data.mcr.microsoft.com` | 443 | MCR data endpoint |
| `management.azure.com` | 443 | Azure Resource Manager |
| `login.microsoftonline.com` | 443 | Azure AD |
| `packages.microsoft.com` | 443 | Node package updates |
| `acs-mirror.azureedge.net` | 443 | AKS component downloads |

```bash
# Test egress through firewall from a node
kubectl run egress-test --image=nicolaka/netshoot --rm -it --restart=Never -- \
  curl -v https://mcr.microsoft.com/v2/
```

---

## 5. Private Clusters and Private Endpoints

A private AKS cluster has no public API server endpoint. All `kubectl` access must go through private networking.

### How private cluster DNS works

```
kubectl (your machine)
    │
    ├── Needs to resolve: <cluster>.privatelink.<region>.azmk8s.io
    │
    ▼
Private DNS Zone: privatelink.<region>.azmk8s.io
    │   (linked to cluster VNet)
    │
    ▼
Private Endpoint IP (10.x.x.x) → AKS API Server
```

### Diagnose private cluster access failures

```bash
# Test DNS resolution for the API server
nslookup <cluster-fqdn>
# Should return a private IP (10.x.x.x), not a public IP

# Check private DNS zone link
az network private-dns zone list -o table
az network private-dns link vnet list \
  -g <rg> --zone-name privatelink.<region>.azmk8s.io -o table
# VirtualNetworkLinkState should be: Succeeded

# Check private endpoint
az network private-endpoint list -g <rg> -o table
```

### Common private cluster failures

| Symptom | Cause | Fix |
| --- | --- | --- |
| `kubectl` times out | No VNet peering / VPN to cluster VNet | Set up VNet peering or use `az aks command invoke` |
| `kubectl` resolves public IP | Custom DNS not forwarding to Azure DNS | Configure DNS forwarder for `privatelink.*` |
| Works from Azure VM, fails from on-prem | ExpressRoute/VPN not routing to private endpoint subnet | Check BGP routes and UDR |

```bash
# Emergency: run kubectl commands without direct access
az aks command invoke \
  -g <rg> -n <cluster> \
  --command "kubectl get pods -A"
```

---

## 6. Azure DNS and Custom DNS

By default AKS nodes use Azure DNS (168.63.129.16) for name resolution. Custom DNS servers must forward Azure-internal names to Azure DNS.

```bash
# Check what DNS servers the nodes use
az aks show -g <rg> -n <cluster> --query 'networkProfile.dnsServiceIp'
# This is the CoreDNS cluster IP (usually 10.0.0.10)

# Nodes resolve via:
# Pod → CoreDNS (cluster IP) → Node DNS → Azure DNS / Custom DNS → Internet
```

### Custom DNS misconfiguration symptoms

| Symptom | Cause |
| --- | --- |
| `nslookup kubernetes.default` fails inside pod | CoreDNS unhealthy |
| Pod can resolve `kubernetes.default` but not `service.namespace` | CoreDNS ConfigMap wrong |
| Pod resolves cluster names, fails on external domains | Custom DNS server blocking or not forwarding |
| 5-second random latency on first connection | conntrack race on UDP DNS — use NodeLocalDNSCache |

```bash
# Test DNS from inside a pod
kubectl run dns-test --image=busybox --rm -it --restart=Never -- \
  sh -c 'nslookup kubernetes.default && nslookup google.com'

# Check CoreDNS ConfigMap
kubectl get configmap coredns -n kube-system -o yaml

# Check CoreDNS logs for SERVFAIL or NXDOMAIN errors
kubectl logs -n kube-system -l k8s-app=kube-dns --tail=50
```
