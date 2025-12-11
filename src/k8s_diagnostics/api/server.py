from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from ..core.client import K8sClient
from ..automation.diagnostics import DiagnosticsEngine
from ..automation.fixes import AutoFixer
from ..ai.predictor import AIPredictor, ChaosEngineer, AutoHealer
from ..ai.optimizer import ResourceOptimizer, AIOpsEngine
import asyncio

app = FastAPI(title="K8s Diagnostics API", version="1.0.0")
k8s = K8sClient()
diagnostics = DiagnosticsEngine(k8s)
fixer = AutoFixer(k8s)
ai_predictor = AIPredictor()
chaos_engineer = ChaosEngineer(k8s)
auto_healer = AutoHealer(k8s, ai_predictor)
optimizer = ResourceOptimizer(k8s)
aiops = AIOpsEngine(k8s)

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
async def predict_failures():
    """AI-powered failure prediction"""
    metrics = {"cpu_usage": 0.7, "memory_usage": 0.8, "pod_restart_count": 15, "error_rate": 0.02}
    return await ai_predictor.predict_failures(metrics)

@app.post("/ai/heal")
async def autonomous_healing():
    """Trigger autonomous healing"""
    return await auto_healer.autonomous_healing()

@app.post("/chaos/inject-failure")
async def inject_chaos(namespace: str, label_selector: str):
    """Inject controlled failures for chaos engineering"""
    return await chaos_engineer.inject_pod_failure(namespace, label_selector)

@app.get("/ai/optimize")
async def optimize_cluster():
    """AI-driven cluster optimization"""
    return await optimizer.optimize_cluster()

@app.get("/ai/anomalies")
async def detect_anomalies():
    """Detect anomalies using AIOps"""
    return await aiops.detect_anomalies()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
