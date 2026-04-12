# Cloud FQDN Service Access Runbook

Use this when a Kubernetes application must be reachable by a real URL in AKS, EKS, GKE, or bare metal.

Local Minikube is intentionally different: it uses `localhost`, port-forwarding, and local DNS shortcuts. Real cloud clusters should not depend on `kubectl port-forward`, `/etc/hosts`, or raw load balancer IPs for normal application access.

## Production Pattern

```text
Client
  -> DNS name
  -> WAF/CDN/global traffic manager when required
  -> cloud L7 load balancer or Gateway
  -> Kubernetes Ingress/Gateway route
  -> Kubernetes Service
  -> ready Pod endpoints
```

Strong platform teams standardize this path and make DNS/TLS declarative:

- Use `Ingress` or `Gateway API` for HTTP/S applications.
- Use `Service type=LoadBalancer` for TCP/UDP or simple internal services.
- Use provider DNS automation or ExternalDNS instead of manually copying IPs.
- Use managed certificates or cert-manager instead of hand-managed TLS secrets.
- Reserve static IPs only when the provider requires it or DNS automation is not available.
- Treat cloud load balancer health as a separate signal from Kubernetes pod readiness.
- Keep public and private exposure paths separate.

When several apps share one cluster, pair this route pattern with the [Multi-Application Isolation Blueprint](./multi-application-isolation-blueprint.md).

## Decision Matrix

| Need | Preferred pattern |
| --- | --- |
| Public HTTP/S app | Gateway API or cloud-native Ingress with managed DNS and TLS |
| Private internal HTTP/S app | Internal Gateway/Ingress + private DNS zone |
| TCP/UDP service | `Service type=LoadBalancer` with cloud annotations |
| Multi-cluster failover | Global DNS or global load balancer with health checks |
| Local developer lab | Minikube ingress + local DNS or port-forward |
| Bare metal | MetalLB or kube-vip + DNS + ingress controller |

## Common Kubernetes Contract

The Kubernetes side should be boring and portable:

```yaml
apiVersion: v1
kind: Service
metadata:
  name: web
  namespace: app
spec:
  type: ClusterIP
  selector:
    app: web
  ports:
    - name: http
      port: 80
      targetPort: http
---
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: web
  namespace: app
  annotations:
    external-dns.alpha.kubernetes.io/hostname: app.example.com
spec:
  ingressClassName: <provider-ingress-class>
  rules:
    - host: app.example.com
      http:
        paths:
          - path: /
            pathType: Prefix
            backend:
              service:
                name: web
                port:
                  number: 80
  tls:
    - hosts:
        - app.example.com
      secretName: web-tls
```

Provider-specific work should be isolated to:

- ingress class or gateway class
- cloud annotations
- DNS zone ownership
- TLS issuer or certificate reference
- WAF and timeout policy

## AKS Pattern

Use one of these patterns:

- New platform direction: Gateway API through AKS application routing or Application Gateway for Containers.
- Existing/simple path: AKS application routing add-on with its managed NGINX ingress class.
- Enterprise north-south path: Application Gateway for Containers or AGIC, usually with WAF and private/public frontends.

Typical AKS production flow:

```bash
az aks get-credentials --resource-group <rg> --name <cluster>

# Option: attach Azure DNS zone to AKS application routing.
ZONE_ID=$(az network dns zone show \
  --resource-group <dns-rg> \
  --name example.com \
  --query id -o tsv)

az aks approuting zone add \
  --resource-group <aks-rg> \
  --name <cluster> \
  --ids "${ZONE_ID}" \
  --attach-zones

# Option: attach Key Vault for TLS certificate access.
KEY_VAULT_ID=$(az keyvault show --name <kv-name> --query id -o tsv)

az aks approuting update \
  --resource-group <aks-rg> \
  --name <cluster> \
  --enable-kv \
  --attach-kv "${KEY_VAULT_ID}"
```

Ingress shape with AKS application routing:

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: web
  namespace: app
  annotations:
    kubernetes.azure.com/tls-cert-keyvault-uri: https://<vault>.vault.azure.net/certificates/<cert-name>
spec:
  ingressClassName: webapprouting.kubernetes.azure.com
  rules:
    - host: app.example.com
      http:
        paths:
          - path: /
            pathType: Prefix
            backend:
              service:
                name: web
                port:
                  number: 80
  tls:
    - hosts:
        - app.example.com
      secretName: keyvault-web
```

AKS verification:

```bash
kubectl get ingress -n app
kubectl describe ingress web -n app
kubectl get endpointslice -n app -l kubernetes.io/service-name=web
az network dns record-set a show -g <dns-rg> -z example.com -n app
curl -vk https://app.example.com/
```

AKS failure patterns:

| Symptom | Check |
| --- | --- |
| DNS record missing | Application routing DNS zone attachment, ExternalDNS logs, Azure DNS permissions |
| Ingress address missing | Ingress class, application routing add-on, AGIC/Application Gateway controller health |
| TLS secret/cert missing | Key Vault URI, Key Vault role assignment, Secrets Store CSI driver |
| 502/504 | backend service port, endpoints, readiness, App Gateway or LB health probe |
| Public DNS resolves but traffic times out | NSG, UDR, Azure Firewall, private/public frontend mismatch |

## EKS Pattern

Use one of these patterns:

- Public HTTP/S: AWS Load Balancer Controller creates an ALB from an `Ingress`.
- TCP/UDP or private L4: AWS Load Balancer Controller creates an NLB from a `Service`.
- DNS: Route 53 alias records, usually automated by ExternalDNS.
- TLS: ACM certificate referenced from the Ingress.

Typical EKS production flow:

```bash
aws eks update-kubeconfig --region <region> --name <cluster>

kubectl get deployment -n kube-system aws-load-balancer-controller
kubectl get ingressclass
kubectl get pods -n kube-system -l app.kubernetes.io/name=aws-load-balancer-controller
```

Ingress shape with ALB:

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: web
  namespace: app
  annotations:
    kubernetes.io/ingress.class: alb
    alb.ingress.kubernetes.io/scheme: internet-facing
    alb.ingress.kubernetes.io/target-type: ip
    alb.ingress.kubernetes.io/listen-ports: '[{"HTTP":80},{"HTTPS":443}]'
    alb.ingress.kubernetes.io/certificate-arn: arn:aws:acm:<region>:<account-id>:certificate/<id>
    external-dns.alpha.kubernetes.io/hostname: app.example.com
spec:
  rules:
    - host: app.example.com
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

EKS verification:

```bash
kubectl describe ingress web -n app
kubectl get endpointslice -n app -l kubernetes.io/service-name=web
aws elbv2 describe-load-balancers --names <alb-name>
aws elbv2 describe-target-groups --load-balancer-arn <alb-arn>
aws elbv2 describe-target-health --target-group-arn <tg-arn>
aws route53 list-resource-record-sets --hosted-zone-id <zone-id>
curl -vk https://app.example.com/
```

EKS failure patterns:

| Symptom | Check |
| --- | --- |
| ALB not created | AWS Load Balancer Controller logs, IAM role/IRSA, subnet tags |
| Route 53 record missing | ExternalDNS logs, hosted zone ID, IAM policy |
| Targets unhealthy | pod readiness, service port, security group from ALB to pod/node |
| Timeout | security groups, NACLs, route tables, private/public subnet mismatch |
| Cert not attached | ACM ARN region, Ingress annotation, listener rules |

## GKE Pattern

Use one of these patterns:

- New HTTP/S platform path: Gateway API with Google Cloud load balancing.
- Existing/simple path: GKE Ingress with Google Cloud HTTP(S) Load Balancing.
- DNS: Cloud DNS records, often automated by ExternalDNS.
- TLS: Google-managed certificates, Certificate Manager, or cert-manager.
- Stable URL: reserve a static IP before binding DNS if you are not using DNS automation.

Typical GKE production flow:

```bash
gcloud container clusters get-credentials <cluster> \
  --region <region> \
  --project <project>

kubectl get gatewayclass
kubectl get ingressclass
kubectl get ingress -A
```

Ingress shape with GKE Ingress and managed certificate:

```yaml
apiVersion: networking.gke.io/v1
kind: ManagedCertificate
metadata:
  name: web-cert
  namespace: app
spec:
  domains:
    - app.example.com
---
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: web
  namespace: app
  annotations:
    kubernetes.io/ingress.class: gce
    networking.gke.io/managed-certificates: web-cert
    kubernetes.io/ingress.global-static-ip-name: web-ip
    external-dns.alpha.kubernetes.io/hostname: app.example.com
spec:
  rules:
    - host: app.example.com
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

GKE verification:

```bash
kubectl describe ingress web -n app
kubectl describe managedcertificate web-cert -n app
kubectl get endpointslice -n app -l kubernetes.io/service-name=web
gcloud compute addresses describe web-ip --global
gcloud compute backend-services list
gcloud compute backend-services get-health <backend-service> --global
gcloud dns record-sets list --zone <zone-name> --name app.example.com.
curl -vk https://app.example.com/
```

GKE failure patterns:

| Symptom | Check |
| --- | --- |
| Ingress IP changed | Missing reserved static IP or wrong annotation |
| Certificate pending | DNS not pointing at load balancer, ManagedCertificate status |
| Backend unhealthy | NEG/backend service health, readiness, firewall health check allow rules |
| Traffic timeout | firewall rules, private/public LB mismatch, proxy-only subnet for internal LBs |
| DNS record missing | Cloud DNS zone, ExternalDNS logs, IAM permissions |

## Bare Metal Pattern

Cloud teams still need a bare-metal answer for labs, edge clusters, and on-prem platforms:

- Install a load balancer implementation such as MetalLB or kube-vip.
- Use an ingress controller such as NGINX, HAProxy, Traefik, Envoy Gateway, or Istio ingress.
- Publish DNS records to the VIP, not to a node IP.
- Use cert-manager with ACME DNS-01 where public HTTP-01 cannot reach the cluster.

Verification:

```bash
kubectl get svc -A --field-selector spec.type=LoadBalancer
kubectl get ingress -A
kubectl get endpointslice -A
dig app.example.com
curl -vk https://app.example.com/
```

## ExternalDNS Baseline

ExternalDNS watches Kubernetes resources and writes DNS records to a provider such as Azure DNS, Route 53, or Cloud DNS. Use it when you want DNS records to follow GitOps-managed Ingress/Gateway/Service resources.

Minimum operating rules:

- Scope it with `--domain-filter=example.com`.
- Use least-privilege cloud identity.
- Run one owner ID per environment or cluster.
- Avoid multiple ExternalDNS instances managing the same zone unless owner IDs and domain filters are explicit.
- Review changes in a lower environment before production.

Typical annotations:

```yaml
metadata:
  annotations:
    external-dns.alpha.kubernetes.io/hostname: app.example.com
    external-dns.alpha.kubernetes.io/ttl: "60"
```

## Verification Ladder

Run this top-down. Do not start at DNS if Kubernetes cannot route to the pod.

```bash
# 1. Pod and Service contract
kubectl get pods -n <ns> -o wide
kubectl get svc <svc> -n <ns>
kubectl get endpointslice -n <ns> -l kubernetes.io/service-name=<svc>

# 2. Route object
kubectl get ingress -n <ns>
kubectl describe ingress <ingress> -n <ns>
kubectl get gateway,httproute -A

# 3. Controller health
kubectl get pods -A | grep -Ei 'ingress|gateway|alb|appgw|external-dns|cert-manager'
kubectl logs -n <controller-ns> deploy/<controller> --tail=100

# 4. Cloud load balancer health
# AKS: az network lb ... or az network application-gateway ...
# EKS: aws elbv2 describe-target-health ...
# GKE: gcloud compute backend-services get-health ...

# 5. DNS and TLS
dig app.example.com
curl -vk https://app.example.com/
openssl s_client -connect app.example.com:443 -servername app.example.com </dev/null
```

## Incident Triage

| Symptom | Most likely layer | First command |
| --- | --- | --- |
| Browser says NXDOMAIN | DNS | `dig app.example.com` |
| DNS resolves to old IP | DNS automation / stale record | Check ExternalDNS logs and zone records |
| TLS cert warning | certificate or SNI | `openssl s_client -connect app.example.com:443 -servername app.example.com` |
| 404 from load balancer | host/path rule mismatch | `kubectl describe ingress <name> -n <ns>` |
| 502/503/504 | backend health | endpoints + cloud target/backend health |
| Timeout | firewall/security/routing | provider firewall, NSG/SG/NACL, route table |
| Works from pod, not internet | north-south path | ingress controller and cloud LB |
| Works by LB DNS name, not vanity FQDN | DNS | hosted zone record and CNAME/alias target |

## GitOps Rules

- Keep app routes in the app repo or environment overlay.
- Keep shared ingress controllers, gateway classes, ExternalDNS, cert-manager, and WAF policies in platform infrastructure repos.
- Do not let Argo CD and Flux manage the same route object unless the lab intentionally tests controller conflict.
- Do not manually patch Ingress annotations in production if GitOps owns the object. Update Git instead.
- Store cloud provider IDs and certificate ARNs in environment overlays, not base manifests.

## Local vs Cloud Differences

| Minikube | Cloud |
| --- | --- |
| `localhost` and port-forward are acceptable | port-forward is break-glass only |
| `.localhost` can resolve automatically | use real DNS zone |
| `/etc/hosts` or dnsmasq can be fine | use Azure DNS, Route 53, Cloud DNS, or corporate DNS |
| ingress IP may be unreachable from the laptop | cloud LB IP/DNS should be reachable from intended client networks |
| self-signed certs are acceptable for labs | use managed CA certificates or approved internal CA |

## References

- AKS application routing custom domain and SSL: https://learn.microsoft.com/en-us/azure/aks/app-routing-dns-ssl
- AWS Load Balancer Controller: https://kubernetes-sigs.github.io/aws-load-balancer-controller/
- Route 53 alias records for ELB: https://docs.aws.amazon.com/Route53/latest/DeveloperGuide/routing-to-elb-load-balancer.html
- GKE Cloud DNS and external service exposure: https://cloud.google.com/kubernetes-engine/docs/how-to/cloud-dns
- ExternalDNS project: https://kubernetes-sigs.github.io/external-dns/
