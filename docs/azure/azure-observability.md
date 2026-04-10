# Azure Observability for AKS

Production-grade observability for AKS requires knowing which tool answers which question. This guide covers Container Insights, Azure Monitor, Log Analytics KQL queries, and alerts — and when to use each.

---

## Tool Map: Which Tool Answers Which Question

| Question | Tool |
| --- | --- |
| Why did this pod OOMKill 3 times today? | Container Insights → Containers view |
| Which node is running hot on CPU? | Azure Monitor → Metrics → Node CPU |
| What were the kubectl events at 14:32? | Log Analytics → KubeEvents table |
| Which pods were evicted in the last hour? | Log Analytics → KubePodInventory |
| Is the cluster hitting API server rate limits? | Log Analytics → AzureDiagnostics |
| What is the p99 latency of my service? | App Insights / Prometheus + Grafana |
| Who deleted that deployment at 09:15? | Azure Activity Log |
| Why is my HPA not scaling? | `kubectl describe hpa` + Container Insights metrics |

---

## 1. Container Insights

Container Insights is the Azure-native monitoring solution for AKS. It collects:
- Node and pod CPU / memory metrics
- Container logs (stdout/stderr) → Log Analytics workspace
- Kubernetes events
- Health model for cluster components

### Enable Container Insights

```bash
# Enable on existing cluster
az aks enable-addons \
  -g <rg> -n <cluster> \
  --addons monitoring \
  --workspace-resource-id <log-analytics-workspace-id>

# Verify the omsagent daemonset is running
kubectl get pods -n kube-system -l component=oms-agent
kubectl get pods -n kube-system -l rsName=omsagent-rs
```

### Key Container Insights views (Azure Portal)

```
AKS cluster → Monitoring → Insights
├── Cluster tab     — node CPU/memory, node count, pod count
├── Nodes tab       — per-node breakdown, drill into pods per node
├── Controllers tab — deployments, replicasets, daemonsets
└── Containers tab  — per-container CPU/memory, live logs
```

**For a crashing container:** Containers tab → filter by namespace → click container → View live logs or Previous logs.

---

## 2. Log Analytics — KQL Queries for Common Failures

All Container Insights data lands in a Log Analytics workspace. Use these KQL queries to diagnose issues that happened in the past (not just current state).

### Find all OOMKilled pods in the last 24 hours

```kql
KubePodInventory
| where TimeGenerated > ago(24h)
| where LastTransitionTimeReady < ago(1m)
| extend ContainerStatus = parse_json(ContainerStatusReason)
| where ContainerStatusReason == "OOMKilled"
| project TimeGenerated, ClusterName, Namespace, PodName = Name, ContainerName, RestartCount
| order by TimeGenerated desc
```

### Find pods with high restart counts

```kql
KubePodInventory
| where TimeGenerated > ago(1h)
| where ContainerRestartCount > 3
| project TimeGenerated, ClusterName, Namespace, PodName = Name, ContainerName, ContainerRestartCount
| order by ContainerRestartCount desc
```

### Find all Warning events in the last hour

```kql
KubeEvents
| where TimeGenerated > ago(1h)
| where Type == "Warning"
| project TimeGenerated, ClusterName, Namespace, Name, Reason, Message
| order by TimeGenerated desc
```

### Find pods that were evicted

```kql
KubePodInventory
| where TimeGenerated > ago(24h)
| where PodStatus == "Failed"
| where ContainerStatusReason == "Evicted"
| project TimeGenerated, ClusterName, Namespace, PodName = Name, ContainerStatusReason
| order by TimeGenerated desc
```

### Find ImagePullBackOff events

```kql
KubeEvents
| where TimeGenerated > ago(1h)
| where Reason in ("Failed", "BackOff")
| where Message has "image"
| project TimeGenerated, Namespace, Name, Reason, Message
| order by TimeGenerated desc
```

### Node CPU pressure over the last 6 hours

```kql
Perf
| where TimeGenerated > ago(6h)
| where ObjectName == "K8SNode"
| where CounterName == "cpuUsageNanoCores"
| summarize AvgCPU = avg(CounterValue) by bin(TimeGenerated, 5m), Computer
| render timechart
```

### Node memory working set over time

```kql
Perf
| where TimeGenerated > ago(6h)
| where ObjectName == "K8SNode"
| where CounterName == "memoryWorkingSetBytes"
| summarize AvgMem = avg(CounterValue) / 1024 / 1024 by bin(TimeGenerated, 5m), Computer
| render timechart
```

### Container memory usage vs limit (find containers near limit)

```kql
Perf
| where TimeGenerated > ago(1h)
| where ObjectName == "K8SContainer"
| where CounterName == "memoryWorkingSetBytes"
| summarize AvgMem = avg(CounterValue) by ContainerName, Computer
| join kind=inner (
    KubePodInventory
    | where TimeGenerated > ago(1h)
    | summarize by ContainerName, ContainerID, Namespace
) on ContainerName
| project Namespace, ContainerName, AvgMemMB = AvgMem / 1024 / 1024
| order by AvgMemMB desc
```

### API server request rate and errors

```kql
AzureDiagnostics
| where Category == "kube-apiserver"
| where TimeGenerated > ago(1h)
| where log_s has "status"
| extend StatusCode = extract("\"code\":(\\d+)", 1, log_s)
| where StatusCode in ("429", "500", "503")
| summarize Count = count() by bin(TimeGenerated, 1m), StatusCode
| render timechart
```

### Find who deleted a resource (Activity Log)

```kql
AzureActivity
| where TimeGenerated > ago(24h)
| where OperationNameValue contains "DELETE"
| where ResourceProvider contains "ContainerService"
| project TimeGenerated, Caller, OperationNameValue, ResourceGroup, Resource = ResourceId
| order by TimeGenerated desc
```

---

## 3. Azure Monitor Alerts for AKS

### Recommended alert rules

```bash
# Create alert: node CPU > 80% for 5 minutes
az monitor metrics alert create \
  -g <rg> \
  -n "AKS Node CPU High" \
  --scopes <aks-resource-id> \
  --condition "avg Percentage CPU > 80" \
  --window-size 5m \
  --evaluation-frequency 1m \
  --action <action-group-id>

# Create alert: pod restart count > 5 in 15 minutes (via Log Analytics)
az monitor scheduled-query create \
  -g <rg> -n "High Pod Restarts" \
  --scopes <log-analytics-workspace-id> \
  --condition-query "KubePodInventory | where ContainerRestartCount > 5" \
  --condition-time-aggregation count \
  --condition-operator GreaterThan \
  --condition-threshold 0 \
  --evaluation-period PT15M \
  --evaluation-frequency PT5M
```

### Recommended alert thresholds

| Alert | Threshold | Window | Severity |
| --- | --- | --- | --- |
| Node CPU | > 85% avg | 10 min | P2 |
| Node memory | > 90% working set | 10 min | P1 |
| Node disk | > 85% | 15 min | P2 |
| Pod OOMKilled | Any | 5 min | P1 |
| Pod restart count | > 5 | 15 min | P2 |
| API server 5xx errors | > 10/min | 5 min | P1 |
| Node NotReady | Any | 2 min | P0 |

**The production standard:** alert on burn rate and error budget consumption, not raw CPU percentages. A node at 90% CPU doing useful work is fine. A node at 60% CPU where requests are timing out is not.

---

## 4. Diagnostic Settings

Enable diagnostic logs to capture control plane events that are not visible in `kubectl`.

```bash
# Enable all AKS diagnostic categories
az monitor diagnostic-settings create \
  --name "aks-diagnostics" \
  --resource <aks-resource-id> \
  --workspace <log-analytics-workspace-id> \
  --logs '[
    {"category": "kube-apiserver", "enabled": true},
    {"category": "kube-controller-manager", "enabled": true},
    {"category": "kube-scheduler", "enabled": true},
    {"category": "kube-audit", "enabled": true},
    {"category": "kube-audit-admin", "enabled": true},
    {"category": "guard", "enabled": true},
    {"category": "cluster-autoscaler", "enabled": true}
  ]'
```

### Query audit logs for security investigation

```kql
// Who exec'd into a pod in the last 24 hours?
AzureDiagnostics
| where Category == "kube-audit"
| where TimeGenerated > ago(24h)
| extend AuditEvent = parse_json(log_s)
| where AuditEvent.verb == "create"
| where AuditEvent.objectRef.subresource == "exec"
| project
    TimeGenerated,
    User = tostring(AuditEvent.user.username),
    Namespace = tostring(AuditEvent.objectRef.namespace),
    Pod = tostring(AuditEvent.objectRef.name),
    Command = tostring(AuditEvent.requestObject.command)
| order by TimeGenerated desc
```

---

## 5. Application Insights for Distributed Tracing

For diagnosing slow requests across microservices — the "it's slow but CPU is fine" class of problems.

```bash
# Deploy the OpenTelemetry collector as a DaemonSet
kubectl apply -f https://raw.githubusercontent.com/open-telemetry/opentelemetry-operator/main/bundle/manifests/opentelemetry.io_opentelemetrycollectors.yaml

# Or use Azure Monitor OpenTelemetry distro
# In your app: set APPLICATIONINSIGHTS_CONNECTION_STRING env var
kubectl create secret generic appinsights \
  --from-literal=connection-string="InstrumentationKey=<key>;..." \
  -n <ns>
```

### Key App Insights KQL queries

```kql
// P99 latency by operation in the last hour
requests
| where timestamp > ago(1h)
| summarize
    p50 = percentile(duration, 50),
    p95 = percentile(duration, 95),
    p99 = percentile(duration, 99),
    count = count()
  by operation_Name
| order by p99 desc

// Failed requests with traces
requests
| where timestamp > ago(1h)
| where success == false
| join kind=inner (
    traces | where timestamp > ago(1h)
) on operation_Id
| project timestamp, operation_Name, resultCode, message
| order by timestamp desc

// Dependency failures (DB, external APIs)
dependencies
| where timestamp > ago(1h)
| where success == false
| summarize FailureCount = count() by target, type, name
| order by FailureCount desc
```

---

## 6. Prometheus + Grafana on AKS

For custom metrics and dashboards beyond what Container Insights provides.

```bash
# Install kube-prometheus-stack via Helm
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo update

helm install prometheus prometheus-community/kube-prometheus-stack \
  -n monitoring --create-namespace \
  --set grafana.adminPassword=<password> \
  --set prometheus.prometheusSpec.retention=15d

# Access Grafana
kubectl port-forward -n monitoring svc/prometheus-grafana 3000:80
```

### Critical Prometheus queries for AKS

```promql
# Pod restart rate (restarts per minute)
rate(kube_pod_container_status_restarts_total[5m]) > 0

# Memory usage as % of limit (find containers near OOM)
container_memory_working_set_bytes
  / on(namespace, pod, container)
  kube_pod_container_resource_limits{resource="memory"}
> 0.8

# Node CPU saturation
1 - avg by(node) (rate(node_cpu_seconds_total{mode="idle"}[5m]))

# PVC usage > 80%
kubelet_volume_stats_used_bytes
  / kubelet_volume_stats_capacity_bytes
> 0.8

# API server error rate
rate(apiserver_request_total{code=~"5.."}[5m])
  / rate(apiserver_request_total[5m])
```
