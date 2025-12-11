from fastapi import FastAPI
from ..core.client import K8sClient
from ..automation.diagnostics import DiagnosticsEngine
from ..automation.fixes import AutoFixer
from ..automation.chaos import ChaosEngine

app = FastAPI(title="K8s Diagnostics API", version="1.1.0")
k8s = K8sClient()
diagnostics = DiagnosticsEngine(k8s)
fixer = AutoFixer(k8s)
chaos = ChaosEngine(k8s)
k8s.fixer = fixer  # provide fixer access for autonomous heal

@app.get("/health")
async def cluster_health():
    """Get comprehensive cluster health"""
    return k8s.get_cluster_health()

@app.get("/diagnose/pod/{namespace}/{pod_name}")
async def diagnose_pod(namespace: str, pod_name: str):
    """Diagnose specific pod issues"""
    return await diagnostics.diagnose_pod(namespace, pod_name)

@app.get("/diagnose/network")
async def diagnose_network():
    """Run network diagnostics"""
    return await diagnostics.check_network()

@app.post("/fix/restart-failed-pods")
async def restart_failed_pods():
    """Auto-restart failed pods"""
    return await fixer.restart_failed_pods()

@app.post("/fix/cleanup-evicted")
async def cleanup_evicted():
    """Remove evicted pods"""
    return await fixer.cleanup_evicted_pods()

@app.post("/fix/dns")
async def fix_dns():
    """Restart unhealthy CoreDNS pods"""
    return await fixer.fix_dns_issues()

@app.post("/fix/scale/{namespace}/{deployment}")
async def scale_workload(namespace: str, deployment: str, replicas: int):
    """Scale a deployment to a desired replica count"""
    return await fixer.scale_resources(namespace, deployment, replicas)

@app.get("/metrics/resources")
async def resource_metrics():
    """Get resource utilization metrics"""
    return await diagnostics.get_resource_metrics()

@app.get("/issues/detect")
async def detect_issues():
    """Auto-detect common issues"""
    return await diagnostics.detect_common_issues()

@app.get("/ai/predict")
async def predict_risk():
    """Heuristic risk prediction from current issues"""
    return await diagnostics.predict_risk()

@app.post("/ai/heal")
async def autonomous_healing():
    """Attempt autonomous healing for common issues"""
    return await diagnostics.autonomous_heal()

@app.get("/ai/optimize")
async def optimize_cluster():
    """Cost optimization recommendations (heuristic)"""
    return diagnostics.optimize_costs()

@app.get("/diagnose/provider")
async def provider_diagnostics():
    """Provider-aware diagnostics"""
    return diagnostics.provider_diagnostics()

@app.post("/chaos/inject")
async def inject_chaos(namespace: str, label_selector: str, dry_run: bool = True):
    """Inject pod failure (dry-run by default)"""
    return await chaos.inject_pod_failure(namespace, label_selector, dry_run)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
