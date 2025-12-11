# Programmatic Kubernetes Diagnostics

## 🚀 Zero-CLI Approach

### API-First Architecture
```bash
# Start API server
make api

# Or deploy to cluster
make build deploy
```

### REST API Endpoints
```bash
# Cluster health
curl http://localhost:8000/health

# Pod diagnostics
curl http://localhost:8000/diagnose/pod/default/my-pod

# Network diagnostics  
curl http://localhost:8000/diagnose/network

# Auto-detect issues
curl http://localhost:8000/issues/detect

# Auto-fix failed pods
curl -X POST http://localhost:8000/fix/restart-failed-pods

# Cleanup evicted pods
curl -X POST http://localhost:8000/fix/cleanup-evicted

# Fix DNS
curl -X POST http://localhost:8000/fix/dns

# Scale deployment
curl -X POST "http://localhost:8000/fix/scale/default/my-deploy?replicas=3"
```

### Python SDK Usage
```python
from src.k8s_diagnostics.core.client import K8sClient
from src.k8s_diagnostics.automation.diagnostics import DiagnosticsEngine

# Initialize
k8s = K8sClient()
diagnostics = DiagnosticsEngine(k8s)

# Get cluster health
health = k8s.get_cluster_health()

# Diagnose pod
pod_info = await diagnostics.diagnose_pod("default", "my-pod")

# Auto-detect issues
issues = await diagnostics.detect_common_issues()
# Returns nodes not ready, failed/pending pods, image pull errors, DNS/CoreDNS health, PVC binds, and pending load balancers.
```

### Programmatic CLI
```bash
# Health check (JSON output)
python k8s-diagnostics-cli.py health

# Pod diagnostics
python k8s-diagnostics-cli.py diagnose default my-pod

# Network check
python k8s-diagnostics-cli.py network

# Auto-fix
python k8s-diagnostics-cli.py fix

# Cleanup evicted pods
python k8s-diagnostics-cli.py cleanup

# Fix DNS
python k8s-diagnostics-cli.py dnsfix

# Scale a deployment
python k8s-diagnostics-cli.py scale default my-deploy 3

# Update certificates
python k8s-diagnostics-cli.py updatecerts

# Setup prometheus
python k8s-diagnostics-cli.py prom-setup

# Configure alerts
python k8s-diagnostics-cli.py config-alerts

# Create grafana dashboard
python k8s-diagnostics-cli.py create-dash

# Setup log aggregation
python k8s-diagnostics-cli.py log-setup

# Analyze performance
python k8s-diagnostics-cli.py perf-analysis

# Scan security
python k8s-diagnostics-cli.py sec-scan
```

## 🔧 Team Integration

### For Engineers
```python
# Automated debugging in CI/CD
import requests

def check_deployment_health(namespace, deployment):
    response = requests.get(f"http://k8s-diagnostics:8000/diagnose/pod/{namespace}/{deployment}")
    return response.json()

# Integration test
health_data = check_deployment_health("staging", "my-app")
if health_data.get("issues"):
    raise Exception(f"Deployment issues: {health_data['issues']}")
```

### For DevOps
```yaml
# GitLab CI integration
k8s-health-check:
  script:
    - curl -f http://k8s-diagnostics:8000/health || exit 1
    - curl -s http://k8s-diagnostics:8000/issues/detect | jq '.issues | length' | grep -q "^0$"
```

### For SREs
```python
# Monitoring integration
import asyncio
from src.k8s_diagnostics.automation.diagnostics import DiagnosticsEngine

async def health_monitor():
    diagnostics = DiagnosticsEngine(k8s)
    issues = await diagnostics.detect_common_issues()
    
    # Send to monitoring system
    for issue in issues.get("issues", []):
        if issue["severity"] == "high":
            send_alert(issue)

# Run every 5 minutes
asyncio.create_task(health_monitor())
```

### For Architects
```python
# Capacity planning
def analyze_cluster_capacity():
    response = requests.get("http://k8s-diagnostics:8000/metrics/resources")
    metrics = response.json()
    
    # Calculate utilization
    node_utilization = calculate_utilization(metrics["nodes_metrics"])
    return generate_capacity_report(node_utilization)
```

## 🤖 Automation Examples

### Auto-Healing Workflow
```python
async def auto_heal():
    # Detect issues
    issues = await diagnostics.detect_common_issues()
    
    # Auto-fix based on issue type
    for issue in issues.get("issues", []):
        if issue["type"] == "failed_pods":
            await fixer.restart_failed_pods()
        elif issue["type"] == "dns_issues":
            await fixer.fix_dns_issues()
```

### Continuous Monitoring
```python
# Webhook integration
@app.post("/webhook/pod-failed")
async def handle_pod_failure(pod_info: dict):
    # Auto-diagnose
    diagnosis = await diagnostics.diagnose_pod(
        pod_info["namespace"], 
        pod_info["name"]
    )
    
    # Auto-fix if safe
    if diagnosis.get("issues") and is_safe_to_fix(diagnosis):
        await fixer.restart_failed_pods()
    
    return {"status": "handled"}
```

## 📊 Data-Driven Insights

### Metrics Collection
```python
# Collect diagnostics data
health_data = []
for hour in range(24):
    health = k8s.get_cluster_health()
    health_data.append({
        "timestamp": datetime.now(),
        "nodes_ready": health["nodes"]["ready"],
        "pods_running": health["pods"]["running"],
        "failed_pods": len(health["pods"]["failed"])
    })

# Analyze trends
failure_rate = calculate_failure_trend(health_data)
```

### Predictive Analysis
```python
def predict_issues(historical_data):
    # ML model for issue prediction
    features = extract_features(historical_data)
    prediction = model.predict(features)
    
    if prediction > threshold:
        return {"alert": "High probability of pod failures in next hour"}
```

## 🔗 Integration Points

### Prometheus Integration
```python
from prometheus_client import Gauge, Counter

# Metrics
cluster_health_gauge = Gauge('k8s_cluster_health', 'Cluster health score')
pod_failures_counter = Counter('k8s_pod_failures_total', 'Total pod failures')

# Update metrics
health = k8s.get_cluster_health()
cluster_health_gauge.set(calculate_health_score(health))
```

### Slack/Teams Integration
```python
async def send_diagnostics_report():
    issues = await diagnostics.detect_common_issues()
    
    if issues.get("issues"):
        message = format_slack_message(issues)
        send_to_slack(message)
```

## 🎯 Benefits

- **Zero CLI dependency** - Pure API/SDK approach
- **Real-time diagnostics** - Instant issue detection
- **Automated remediation** - Self-healing capabilities  
- **Integration ready** - REST API for any system
- **Data-driven** - JSON output for analysis
- **Scalable** - Kubernetes-native deployment
