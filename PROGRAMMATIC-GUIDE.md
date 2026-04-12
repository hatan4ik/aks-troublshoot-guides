# Programmatic Kubernetes Diagnostics
API- and CLI-first diagnostics and remediation for AKS/EKS/Kubernetes. This guide reflects the endpoints and commands that ship today—no surprises or 404s.

## Deploy the Service
```bash
# Start API locally
make api

# Build and deploy to a cluster
make build deploy
```

Mutating API endpoints are disabled by default. To enable them in a lab, apply `k8s/remediation-rbac.yaml`, set `AUTO_FIX_ENABLED=true`, configure `K8S_DIAGNOSTICS_ALLOWED_NAMESPACES`, and send the `X-API-Key` header using the value from `K8S_DIAGNOSTICS_API_KEY`.

## REST API (Available Endpoints)
```bash
# Health snapshot
curl http://localhost:8000/health

# Pod diagnostics
curl http://localhost:8000/diagnose/pod/default/my-pod

# Network/DNS diagnostics
curl http://localhost:8000/diagnose/network

# Auto-detect common issues
curl http://localhost:8000/issues/detect

# Resource metrics (if metrics-server is present)
curl http://localhost:8000/metrics/resources

# Remediations
curl -H "X-API-Key: $K8S_DIAGNOSTICS_API_KEY" -X POST http://localhost:8000/fix/restart-failed-pods
curl -H "X-API-Key: $K8S_DIAGNOSTICS_API_KEY" -X POST http://localhost:8000/fix/cleanup-evicted
curl -H "X-API-Key: $K8S_DIAGNOSTICS_API_KEY" -X POST http://localhost:8000/fix/dns
curl -H "X-API-Key: $K8S_DIAGNOSTICS_API_KEY" -X POST "http://localhost:8000/fix/scale/default/my-deploy?replicas=3"

# Heuristics and provider-aware checks
curl http://localhost:8000/ai/predict
curl -H "X-API-Key: $K8S_DIAGNOSTICS_API_KEY" -X POST http://localhost:8000/ai/heal
curl http://localhost:8000/ai/optimize
curl http://localhost:8000/diagnose/provider

# Chaos (dry-run by default)
curl -H "X-API-Key: $K8S_DIAGNOSTICS_API_KEY" -X POST "http://localhost:8000/chaos/inject?namespace=default&label_selector=app=my-app&dry_run=true"
```
`/issues/detect` reports nodes not ready, failed/pending pods, image pull errors, DNS/CoreDNS health, PVC binds, and pending load balancers.

## Python SDK (Shipped Components)
```python
from src.k8s_diagnostics.core.client import K8sClient
from src.k8s_diagnostics.automation.diagnostics import DiagnosticsEngine
from src.k8s_diagnostics.automation.fixes import AutoFixer

k8s = K8sClient()
diagnostics = DiagnosticsEngine(k8s)
fixer = AutoFixer(k8s, allowed_namespaces=["practice"])

health = k8s.get_cluster_health()
pod_info = await diagnostics.diagnose_pod("default", "my-pod")
issues = await diagnostics.detect_common_issues()
await fixer.restart_failed_pods()
await fixer.fix_dns_issues()
await fixer.cleanup_evicted_pods()
await fixer.scale_resources("default", "my-deploy", 3)
prediction = await diagnostics.predict_risk()
healing = await diagnostics.autonomous_heal()
optimize = diagnostics.optimize_costs()
provider = diagnostics.provider_diagnostics()
```

## CLI (Shipped Commands)
```bash
python k8s-diagnostics-cli.py health                    # cluster health (JSON)
python k8s-diagnostics-cli.py diagnose default my-pod   # pod diagnostics
python k8s-diagnostics-cli.py network                   # network/DNS check
python k8s-diagnostics-cli.py detect                    # auto-detect issues

# Fixes
python k8s-diagnostics-cli.py suggest                   # detect + dry-run remediation plan
python k8s-diagnostics-cli.py fix --dry-run             # dry-run safe remediations
python k8s-diagnostics-cli.py fix                       # apply safe remediations
python k8s-diagnostics-cli.py cleanup --dry-run         # preview evicted pod cleanup
python k8s-diagnostics-cli.py dnsfix --dry-run          # preview CoreDNS restart
python k8s-diagnostics-cli.py scale default my-deploy 3 --dry-run

# Heuristics / automation
python k8s-diagnostics-cli.py predict                   # risk prediction
python k8s-diagnostics-cli.py heal                      # autonomous healing
python k8s-diagnostics-cli.py optimize                  # cost hints
python k8s-diagnostics-cli.py provider                  # provider-aware diagnostics

# Chaos (dry-run default; pass live to execute)
python k8s-diagnostics-cli.py chaos default app=my-app
python k8s-diagnostics-cli.py chaos default app=my-app live
```

## Integration Recipes
### Engineers (Quality Gates)
```python
import requests

def validate_deployment(namespace, deployment):
    health = requests.get(f"http://k8s-diagnostics:8000/diagnose/pod/{namespace}/{deployment}").json()
    issues = health.get("issues", [])
    if issues:
        raise SystemExit(f"Deployment blocked: {issues}")
```

### DevOps (Pipeline Integration)
```yaml
k8s-validation:
  script:
    - curl -f http://k8s-diagnostics:8000/health
    - curl -s http://k8s-diagnostics:8000/issues/detect | jq '.issues | length' | grep -q "^0$"
```

### SRE (Background Watcher)
```python
async def health_monitor():
    issues = await diagnostics.detect_common_issues()
    for issue in issues.get("issues", []):
        if issue["severity"] == "high":
            send_alert(issue)
```

### Architects (Capacity Sketch)
```python
resp = requests.get("http://k8s-diagnostics:8000/metrics/resources").json()
node_util = calculate_utilization(resp.get("nodes_metrics", []))
report = generate_capacity_report(node_util)
```

## Automation Patterns
### Auto-heal Loop
```python
async def auto_heal():
    issues = await diagnostics.detect_common_issues()
    for issue in issues.get("issues", []):
        if issue["type"] == "failed_pods":
            await fixer.restart_failed_pods()
        if issue["type"] == "dns_unhealthy":
            await fixer.fix_dns_issues()
```

### Webhook Handler
```python
@app.post("/webhook/pod-failed")
async def handle_pod_failure(pod_info: dict):
    diag = await diagnostics.diagnose_pod(pod_info["namespace"], pod_info["name"])
    if diag.get("issues") and is_safe_to_fix(diag):
        await fixer.restart_failed_pods()
    return {"status": "handled"}
```

## Observability Hooks
```python
from prometheus_client import Gauge, Counter
cluster_health = Gauge('k8s_cluster_health', 'Cluster health score')
pod_failures = Counter('k8s_pod_failures_total', 'Total pod failures')

health = k8s.get_cluster_health()
cluster_health.set(calculate_health_score(health))
```

## Roadmap (Not Yet Implemented)
- Predictive alerts and autonomous healing
- Cost-optimization recommendations
- Chaos/testing endpoints
- Expanded provider-specific diagnostics (AKS/EKS/GKE)
