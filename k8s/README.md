# Kubernetes Manifests - Production-Ready Deployment

## 📁 File Structure

```
k8s/
├── deployment.yaml     # Core deployment with security & observability
├── monitoring.yaml     # Prometheus, alerts, and health checks
├── networking.yaml     # Ingress, service mesh, network policies
├── storage.yaml        # Persistent volumes, backups, maintenance
├── autoscaling.yaml    # HPA, VPA, KEDA, resource limits
└── README.md          # This file
```

## 🚀 Deployment Guide

### Quick Deploy
```bash
# Deploy all components
kubectl apply -f k8s/

# Or deploy individually
kubectl apply -f k8s/deployment.yaml
kubectl apply -f k8s/monitoring.yaml
kubectl apply -f k8s/networking.yaml
kubectl apply -f k8s/storage.yaml
kubectl apply -f k8s/autoscaling.yaml
```

### Verification
```bash
# Check deployment status
kubectl get pods -n kube-system -l app=k8s-diagnostics-api

# Check services
kubectl get svc -n kube-system -l app=k8s-diagnostics-api

# Check autoscaling
kubectl get hpa,vpa -n kube-system
```

## 📋 Component Details

### 1. Core Deployment (`deployment.yaml`)

**Enhanced Features:**
- **High Availability**: 2 replicas with anti-affinity
- **Security**: Non-root user, read-only filesystem, dropped capabilities
- **Health Checks**: Liveness, readiness, and startup probes
- **Resource Management**: Requests and limits for CPU, memory, storage
- **Observability**: Prometheus annotations, structured logging

**Key Configurations:**
```yaml
# Security Context
securityContext:
  runAsNonRoot: true
  runAsUser: 1000
  readOnlyRootFilesystem: true

# Health Probes
livenessProbe:
  httpGet:
    path: /health
    port: http
  initialDelaySeconds: 30
```

### 2. Monitoring (`monitoring.yaml`)

**Components:**
- **ConfigMap**: Application configuration
- **ServiceMonitor**: Prometheus scraping
- **PrometheusRule**: Alerting rules
- **PodDisruptionBudget**: Availability guarantees
- **PodSecurityPolicy**: Security constraints

**Alert Rules:**
- API downtime detection
- High pod failure rates
- Cluster health degradation

### 3. Networking (`networking.yaml`)

**Features:**
- **NetworkPolicy**: Ingress/egress traffic control
- **Ingress**: External access with TLS and rate limiting
- **Service Mesh**: Istio VirtualService and DestinationRule
- **Load Balancing**: Multiple service types

**Security:**
```yaml
# Network Policy - Restrict traffic
spec:
  podSelector:
    matchLabels:
      app: k8s-diagnostics-api
  policyTypes:
  - Ingress
  - Egress
```

### 4. Storage (`storage.yaml`)

**Persistence:**
- **Data PVC**: 10Gi for diagnostics data
- **Logs PVC**: 5Gi for application logs
- **ConfigMap**: Automation scripts
- **CronJobs**: Backup and cleanup automation

**Backup Strategy:**
- Daily cluster state backup
- Weekly log cleanup
- Automated compression

### 5. Autoscaling (`autoscaling.yaml`)

**Scaling Methods:**
- **HPA**: CPU/Memory based (2-10 replicas)
- **VPA**: Automatic resource adjustment
- **KEDA**: Event-driven scaling
- **Resource Limits**: Container constraints

**Scaling Triggers:**
```yaml
# HPA Metrics
metrics:
- type: Resource
  resource:
    name: cpu
    target:
      averageUtilization: 70
```

## 🔐 RBAC Permissions

### Comprehensive Access
- **Core Resources**: Pods, nodes, services, events
- **Workloads**: Deployments, replicasets, jobs
- **Networking**: Ingress, network policies
- **Monitoring**: Metrics server access
- **Security**: RBAC resources (read-only)

### Security Boundaries
- **Namespace Isolation**: Enhanced permissions in kube-system
- **Principle of Least Privilege**: Minimal required permissions
- **Audit Trail**: All actions logged and monitored

## 🎯 Team-Specific Configurations

### For Architects
- **Security Policies**: PSP, network policies, RBAC
- **Resource Planning**: Limits, quotas, autoscaling
- **High Availability**: Anti-affinity, PDB, multi-replica

### For Engineers
- **Development**: ConfigMaps, environment variables
- **Debugging**: Enhanced logging, health checks
- **Integration**: Service discovery, API access

### For DevOps
- **CI/CD**: Deployment strategies, rolling updates
- **Automation**: CronJobs, backup scripts
- **Infrastructure**: Storage, networking, ingress

### For SREs
- **Monitoring**: Prometheus, alerts, dashboards
- **Reliability**: Health checks, autoscaling, PDB
- **Operations**: Backup, maintenance, troubleshooting

## 🔧 Customization

### Environment-Specific
```bash
# Development
kubectl apply -f k8s/ --dry-run=client

# Staging
sed 's/replicas: 2/replicas: 1/' k8s/deployment.yaml | kubectl apply -f -

# Production
kubectl apply -f k8s/
```

### Cloud Provider Adaptations
```yaml
# AWS
service.beta.kubernetes.io/aws-load-balancer-type: "nlb"

# Azure
service.beta.kubernetes.io/azure-load-balancer-internal: "true"

# GCP
cloud.google.com/neg: '{"ingress": true}'
```

## 📊 Monitoring & Observability

### Metrics Exposed
- API request rates and latency
- Cluster health scores
- Pod failure counts
- Resource utilization

### Dashboards
- Cluster health overview
- API performance metrics
- Resource utilization trends
- Alert status and history

### Logging
- Structured JSON logs
- Centralized log aggregation
- Log retention policies
- Error tracking and alerting