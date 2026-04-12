import os
from typing import Optional

from fastapi import Depends, FastAPI, Header, HTTPException, Response, status
from prometheus_client import CONTENT_TYPE_LATEST, Gauge, generate_latest
from ..core.client import K8sClient
from ..automation.diagnostics import DiagnosticsEngine
from ..automation.fixes import AutoFixer
from ..automation.chaos import ChaosEngine

app = FastAPI(title="K8s Diagnostics API", version="1.1.0")
k8s = K8sClient()
diagnostics = DiagnosticsEngine(k8s)
ALLOWED_NAMESPACES = {
    ns.strip()
    for ns in os.getenv("K8S_DIAGNOSTICS_ALLOWED_NAMESPACES", "").split(",")
    if ns.strip()
}
fixer = AutoFixer(k8s, allowed_namespaces=ALLOWED_NAMESPACES)
chaos = ChaosEngine(k8s, allowed_namespaces=ALLOWED_NAMESPACES)
k8s.fixer = fixer  # provide fixer access for autonomous heal

API_UP = Gauge("k8s_diagnostics_api_up", "Whether the diagnostics API can reach Kubernetes.")
TOTAL_NODES = Gauge("k8s_cluster_total_nodes", "Total nodes observed in the cluster.")
READY_NODES = Gauge("k8s_cluster_ready_nodes", "Ready nodes observed in the cluster.")
FAILED_PODS = Gauge("k8s_pod_failures_total", "Pods not in Running or Succeeded state.")
CLUSTER_HEALTH_SCORE = Gauge("k8s_cluster_health_score", "Simple health score based on ready nodes.")


def _truthy(value: Optional[str]) -> bool:
    return (value or "").strip().lower() in {"1", "true", "yes", "y", "on"}


def _mutations_enabled() -> bool:
    return _truthy(os.getenv("AUTO_FIX_ENABLED"))


def _namespace_allowed(namespace: str) -> bool:
    return "*" in ALLOWED_NAMESPACES or namespace in ALLOWED_NAMESPACES


def require_mutation_access(x_api_key: Optional[str] = Header(default=None, alias="X-API-Key")):
    """Block write endpoints unless the operator explicitly enables them."""
    if not _mutations_enabled():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Mutating endpoints are disabled. Set AUTO_FIX_ENABLED=true to enable them.",
        )

    expected_key = os.getenv("K8S_DIAGNOSTICS_API_KEY")
    if not expected_key:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Mutating endpoints require K8S_DIAGNOSTICS_API_KEY to be configured.",
        )
    if x_api_key != expected_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid X-API-Key header.",
        )

    if not ALLOWED_NAMESPACES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Mutating endpoints require K8S_DIAGNOSTICS_ALLOWED_NAMESPACES to be configured.",
        )

    return True


def require_allowed_namespace(namespace: str) -> None:
    if not _namespace_allowed(namespace):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Namespace '{namespace}' is outside the remediation allowlist.",
        )


def _refresh_metrics() -> None:
    if not k8s.available:
        API_UP.set(0)
        TOTAL_NODES.set(0)
        READY_NODES.set(0)
        FAILED_PODS.set(0)
        CLUSTER_HEALTH_SCORE.set(0)
        return

    try:
        nodes = k8s._check_nodes()
        pods = k8s._check_pods()
        total_nodes = nodes.get("total", 0)
        ready_nodes = nodes.get("ready", 0)
        failed_pods = len(pods.get("failed", []))
        score = ready_nodes / total_nodes if total_nodes else 0

        API_UP.set(1)
        TOTAL_NODES.set(total_nodes)
        READY_NODES.set(ready_nodes)
        FAILED_PODS.set(failed_pods)
        CLUSTER_HEALTH_SCORE.set(score)
    except Exception:
        API_UP.set(0)
        TOTAL_NODES.set(0)
        READY_NODES.set(0)
        FAILED_PODS.set(0)
        CLUSTER_HEALTH_SCORE.set(0)


@app.get("/livez", include_in_schema=False)
async def livez():
    """Process-level liveness probe."""
    return {"status": "alive"}


@app.get("/readyz", include_in_schema=False)
async def readyz(response: Response):
    """Readiness probe based on lightweight API connectivity."""
    if k8s.is_ready():
        return {"status": "ready"}

    response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return {
        "status": "not_ready",
        "reason": k8s.config_error or "Kubernetes API is not reachable",
    }

@app.get("/health")
async def cluster_health():
    """Get comprehensive cluster health"""
    return k8s.get_cluster_health()


@app.get("/metrics", include_in_schema=False)
async def metrics():
    """Prometheus scrape endpoint."""
    _refresh_metrics()
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)

@app.get("/diagnose/pod/{namespace}/{pod_name}")
async def diagnose_pod(namespace: str, pod_name: str):
    """Diagnose specific pod issues"""
    return await diagnostics.diagnose_pod(namespace, pod_name)

@app.get("/diagnose/network")
async def diagnose_network():
    """Run network diagnostics"""
    return await diagnostics.check_network()

@app.post("/fix/restart-failed-pods")
async def restart_failed_pods(_auth: bool = Depends(require_mutation_access)):
    """Auto-restart failed pods"""
    return await fixer.restart_failed_pods()

@app.post("/fix/cleanup-evicted")
async def cleanup_evicted(_auth: bool = Depends(require_mutation_access)):
    """Remove evicted pods"""
    return await fixer.cleanup_evicted_pods()

@app.post("/fix/dns")
async def fix_dns(_auth: bool = Depends(require_mutation_access)):
    """Restart unhealthy CoreDNS pods"""
    return await fixer.fix_dns_issues()

@app.post("/fix/scale/{namespace}/{deployment}")
async def scale_workload(
    namespace: str,
    deployment: str,
    replicas: int,
    _auth: bool = Depends(require_mutation_access),
):
    """Scale a deployment to a desired replica count"""
    require_allowed_namespace(namespace)
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
async def autonomous_healing(_auth: bool = Depends(require_mutation_access)):
    """Attempt autonomous healing for common issues"""
    return await fixer.auto_remediate(diagnostics)

@app.get("/ai/optimize")
async def optimize_cluster():
    """Cost optimization recommendations (heuristic)"""
    return diagnostics.optimize_costs()

@app.get("/diagnose/provider")
async def provider_diagnostics():
    """Provider-aware diagnostics"""
    return diagnostics.provider_diagnostics()

@app.post("/chaos/inject")
async def inject_chaos(
    namespace: str,
    label_selector: str,
    dry_run: bool = True,
    _auth: bool = Depends(require_mutation_access),
):
    """Inject pod failure (dry-run by default)"""
    require_allowed_namespace(namespace)
    return await chaos.inject_pod_failure(namespace, label_selector, dry_run)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
