# Multi-Application Isolation Blueprint

Use this when several applications share one Kubernetes cluster and need clean separation for networking, security, ports, ownership, and access.

The core rule: do not separate applications by random external ports. Separate them by namespace, DNS hostname, route ownership, identity, policy, and resource boundaries.

## Target Model

```text
app-a.example.com
  -> public Gateway or Ingress
  -> app-a/web Service in namespace app-a
  -> app-a Pods

app-b.example.com
  -> public Gateway or Ingress
  -> app-b/web Service in namespace app-b
  -> app-b Pods

internal-api.example.internal
  -> private Gateway or Ingress
  -> internal-api/api Service in namespace internal-api
  -> internal-api Pods
```

## Separation Layers

| Layer | Control | Rule |
| --- | --- | --- |
| Ownership | Namespace | Use one namespace per app/team/environment unless there is a strong reason not to. |
| External access | DNS host | Use `app.example.com`, not `app.example.com:random-port`. |
| Routing | Ingress or Gateway API | Route by host/path to a `ClusterIP` Service. |
| Internal access | Service | Use named ports and stable service names. |
| Network isolation | NetworkPolicy | Default deny ingress and egress, then allow only required paths. |
| Identity | ServiceAccount + cloud workload identity | One runtime identity per app. |
| Human access | RBAC RoleBinding | Bind team groups to namespace-scoped roles. |
| Capacity | ResourceQuota + LimitRange | Prevent noisy-neighbor failures. |
| Placement | node pools, taints, tolerations | Use only for stronger workload isolation or specialized hardware. |
| Compliance | cluster boundary | Use separate clusters for strict compliance or high blast-radius workloads. |

## Port Model

Use this model for browser-facing apps:

- External public ports: `80` and `443`.
- External private ports: usually `80` and `443` on a private load balancer.
- Service port: usually `80` for HTTP, `443` for HTTPS, or a well-known protocol port.
- Pod port: whatever the process needs, but expose it through a named `targetPort`, for example `targetPort: http`.
- Avoid direct `NodePort` for app access unless you are building an explicit L4/platform path.
- Avoid one public `LoadBalancer` per application unless the app needs L4/TCP isolation or a dedicated appliance path.

Good:

```text
https://payments.example.com -> Service/payments-web:80 -> Pod targetPort:http
https://orders.example.com   -> Service/orders-web:80   -> Pod targetPort:http
```

Bad:

```text
http://cluster.example.com:30081 -> payments
http://cluster.example.com:30082 -> orders
```

## Namespace Blueprint

Every application namespace should have:

- required labels: `tenant`, `app.kubernetes.io/part-of`, `environment`
- Pod Security Admission labels
- `ResourceQuota`
- `LimitRange`
- one or more app `ServiceAccount` objects
- namespace-scoped `Role` and `RoleBinding`
- default-deny ingress and egress `NetworkPolicy`
- explicit allow policies for ingress controller, DNS, same-namespace traffic, and required dependencies

Applyable example: [k8s/multi-app-isolation/two-app-example.yaml](../k8s/multi-app-isolation/two-app-example.yaml).

## NetworkPolicy Blueprint

Start with default deny:

```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: default-deny-all
  namespace: app-a
spec:
  podSelector: {}
  policyTypes:
    - Ingress
    - Egress
```

Then add explicit allows:

- Ingress from the ingress controller namespace to the app pods.
- Egress to CoreDNS on TCP/UDP `53`.
- Same-namespace traffic if the app needs pod-to-pod communication.
- Egress to approved dependencies such as databases, queues, identity providers, or provider APIs.

Do not add a broad `0.0.0.0/0` egress allow as a default. If it is temporarily required, track it as technical debt and narrow it later with egress gateways, firewalls, or explicit CIDR/FQDN policy depending on the CNI.

## Routing Pattern

Use one shared ingress controller or Gateway for normal HTTP/S multi-app hosting.

Ingress pattern:

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: web
  namespace: app-a
  annotations:
    external-dns.alpha.kubernetes.io/hostname: app-a.example.com
spec:
  ingressClassName: nginx
  rules:
    - host: app-a.example.com
      http:
        paths:
          - path: /
            pathType: Prefix
            backend:
              service:
                name: web
                port:
                  number: 80
```

Gateway API pattern:

```yaml
apiVersion: gateway.networking.k8s.io/v1
kind: HTTPRoute
metadata:
  name: web
  namespace: app-a
spec:
  parentRefs:
    - name: public
      namespace: platform-ingress
  hostnames:
    - app-a.example.com
  rules:
    - backendRefs:
        - name: web
          port: 80
```

Gateway API gives platform teams cleaner separation:

- Platform team owns `GatewayClass` and `Gateway`.
- App team owns `HTTPRoute`.
- Admission policy controls which namespaces can attach to which Gateway.

## Public vs Private Apps

Keep public and private entry points separate:

| App type | Pattern |
| --- | --- |
| Public web app | public Gateway/Ingress + public DNS + public CA certificate |
| Internal app | private Gateway/Ingress + private DNS + internal CA or managed private certificate |
| Admin dashboard | private Gateway/Ingress, SSO, allowlist, and no public DNS |
| Machine-to-machine API | private Gateway/service mesh, mTLS, and strict authz |

Do not expose admin dashboards with a public `LoadBalancer` just because it is fast.

## RBAC Pattern

For each app namespace:

- bind developers to a namespace-scoped read or edit role
- keep deployment automation identity separate from human identity
- avoid `cluster-admin`
- use break-glass roles only with audit logging and expiry

Example:

```yaml
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  name: app-a-developers-read
  namespace: app-a
subjects:
  - kind: Group
    name: app-a-developers
    apiGroup: rbac.authorization.k8s.io
roleRef:
  kind: Role
  name: namespace-read
  apiGroup: rbac.authorization.k8s.io
```

## Cloud Provider Notes

AKS:

- Use Azure Workload Identity for app identities.
- Use Azure CNI and separate node pools for stronger IP/subnet isolation when needed.
- Use Azure DNS, Key Vault, AKS application routing, Application Gateway for Containers, or AGIC depending on platform standard.
- Use NSG and UDR controls for north-south and egress boundaries.

EKS:

- Use IRSA or EKS Pod Identity per app.
- Use AWS Load Balancer Controller for ALB/NLB.
- Use Route 53 and ExternalDNS for records.
- Use Security Groups for Pods for workloads requiring stronger network isolation.

GKE:

- Use GKE Workload Identity per app.
- Use Gateway API or GKE Ingress for HTTP/S.
- Use Cloud DNS, Google-managed certs, Certificate Manager, or cert-manager.
- Use Dataplane V2 NetworkPolicy and firewall rules as separate layers.

Bare metal:

- Use MetalLB or kube-vip for load balancer VIPs.
- Use NGINX, HAProxy, Traefik, Envoy Gateway, or Istio ingress.
- Publish DNS to VIPs, not node IPs.
- Use cert-manager with DNS-01 for certificate automation when HTTP-01 cannot reach the cluster.

## GitOps Ownership

Split ownership deliberately:

| Owner | Owns |
| --- | --- |
| Platform repo | ingress controller, GatewayClass, shared Gateway, cert-manager, ExternalDNS, policy controllers |
| App repo | Deployment, Service, HTTPRoute/Ingress, app NetworkPolicies, app ConfigMaps |
| Environment repo | hostnames, certificate IDs, cloud annotations, quotas, namespace labels |

Do not let two GitOps controllers own the same route or policy object unless you are intentionally testing drift.

## Validation Commands

Use these checks after onboarding an app:

```bash
kubectl get ns --show-labels
kubectl get resourcequota,limitrange -n <app-ns>
kubectl auth can-i get pods -n <app-ns> --as <user-or-group>
kubectl get networkpolicy -n <app-ns>
kubectl get svc,endpointslice,ingress -n <app-ns>
kubectl describe ingress <ingress> -n <app-ns>
dig <app-hostname>
curl -vk https://<app-hostname>/
```

For traffic failures, debug in this order:

1. Pod is ready.
2. Service selector points to the pod.
3. EndpointSlice has ready endpoints.
4. NetworkPolicy allows the ingress path.
5. Ingress or HTTPRoute points to the correct service and port.
6. Cloud load balancer target/backend health is green.
7. DNS resolves to the current load balancer.
8. TLS certificate matches the hostname.

## When To Split Clusters

Namespaces are not always enough. Use separate clusters when:

- regulatory boundaries require it
- different teams need incompatible cluster-level add-ons
- workload blast radius is unacceptable
- network egress policy must be physically separated
- noisy neighbors cannot be controlled with quotas and node pools
- lifecycle or upgrade cadence differs materially between tenants

## Related Docs

- [Multi-Tenancy Strategies](./architects/multi-tenancy.md)
- [Security Architecture](./architects/security-architecture.md)
- [Network Architecture](./architects/network-architecture.md)
- [Cloud FQDN Service Access](./cloud-fqdn-service-access.md)
