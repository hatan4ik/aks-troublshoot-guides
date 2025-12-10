from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from ..core.client import K8sClient
from ..automation.diagnostics import DiagnosticsEngine
from ..automation.fixes import AutoFixer
import asyncio

app = FastAPI(title="K8s Diagnostics API", version="1.0.0")
k8s = K8sClient()
diagnostics = DiagnosticsEngine(k8s)
fixer = AutoFixer(k8s)

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

@app.get("/metrics/resources")
async def resource_metrics():
    """Get resource utilization metrics"""
    return await diagnostics.get_resource_metrics()

@app.get("/issues/detect")
async def detect_issues():
    """Auto-detect common issues"""
    return await diagnostics.detect_common_issues()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)