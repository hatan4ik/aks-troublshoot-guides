from typing import Dict, List
import asyncio
from datetime import datetime, timedelta

class DiagnosticsEngine:
    def __init__(self, k8s_client):
        self.k8s = k8s_client

    async def diagnose_pod(self, namespace: str, pod_name: str) -> Dict:
        """Comprehensive pod diagnostics"""
        try:
            pod = self.k8s.v1.read_namespaced_pod(pod_name, namespace)
            
            diagnosis = {
                "pod_info": {
                    "name": pod.metadata.name,
                    "namespace": pod.metadata.namespace,
                    "phase": pod.status.phase,
                    "node": pod.spec.node_name,
                    "created": str(pod.metadata.creation_timestamp)
                },
                "containers": self._analyze_containers(pod),
                "resources": self._check_resources(pod),
                "events": self._get_pod_events(namespace, pod_name),
                "issues": self._detect_pod_issues(pod)
            }
            
            return diagnosis
        except Exception as e:
            return {"error": str(e)}

    def _analyze_containers(self, pod) -> List[Dict]:
        containers = []
        for container in pod.status.container_statuses or []:
            containers.append({
                "name": container.name,
                "ready": container.ready,
                "restart_count": container.restart_count,
                "state": str(container.state),
                "image": container.image
            })
        return containers

    def _check_resources(self, pod) -> Dict:
        resources = {"requests": {}, "limits": {}}
        for container in pod.spec.containers:
            if container.resources:
                if container.resources.requests:
                    resources["requests"][container.name] = dict(container.resources.requests)
                if container.resources.limits:
                    resources["limits"][container.name] = dict(container.resources.limits)
        return resources

    def _get_pod_events(self, namespace: str, pod_name: str) -> List[Dict]:
        events = self.k8s.v1.list_namespaced_event(namespace)
        pod_events = []
        for event in events.items:
            if event.involved_object.name == pod_name:
                pod_events.append({
                    "type": event.type,
                    "reason": event.reason,
                    "message": event.message,
                    "time": str(event.last_timestamp)
                })
        return sorted(pod_events, key=lambda x: x["time"], reverse=True)[:10]

    def _detect_pod_issues(self, pod) -> List[str]:
        issues = []
        
        # Check for common issues
        if pod.status.phase == "Pending":
            issues.append("Pod stuck in Pending state")
        
        for container in pod.status.container_statuses or []:
            if container.restart_count > 5:
                issues.append(f"Container {container.name} has high restart count: {container.restart_count}")
            
            if not container.ready:
                issues.append(f"Container {container.name} is not ready")
        
        return issues

    async def check_network(self) -> Dict:
        """Network connectivity diagnostics"""
        network_status = {
            "dns": await self._check_dns(),
            "services": self._check_service_endpoints(),
            "ingress": self._check_ingress_controllers()
        }
        return network_status

    async def _check_dns(self) -> Dict:
        # Check CoreDNS pods
        pods = self.k8s.v1.list_namespaced_pod("kube-system", label_selector="k8s-app=kube-dns")
        running_dns = sum(1 for pod in pods.items if pod.status.phase == "Running")
        
        return {
            "coredns_pods": len(pods.items),
            "running_pods": running_dns,
            "status": "healthy" if running_dns > 0 else "degraded"
        }

    def _check_service_endpoints(self) -> Dict:
        services = self.k8s.v1.list_service_for_all_namespaces()
        endpoints = self.k8s.v1.list_endpoints_for_all_namespaces()
        
        services_without_endpoints = []
        for svc in services.items:
            ep = next((e for e in endpoints.items 
                      if e.metadata.name == svc.metadata.name 
                      and e.metadata.namespace == svc.metadata.namespace), None)
            if ep and not ep.subsets:
                services_without_endpoints.append(f"{svc.metadata.namespace}/{svc.metadata.name}")
        
        return {
            "total_services": len(services.items),
            "services_without_endpoints": services_without_endpoints
        }

    def _check_ingress_controllers(self) -> Dict:
        # Check for common ingress controllers
        ingress_pods = self.k8s.v1.list_pod_for_all_namespaces(
            label_selector="app.kubernetes.io/name=ingress-nginx"
        )
        
        return {
            "nginx_ingress_pods": len(ingress_pods.items),
            "running": sum(1 for pod in ingress_pods.items if pod.status.phase == "Running")
        }

    async def get_resource_metrics(self) -> Dict:
        """Get cluster resource utilization"""
        try:
            # Try to get metrics from metrics-server
            nodes_metrics = self.k8s.metrics.list_cluster_custom_object(
                "metrics.k8s.io", "v1beta1", "nodes"
            )
            
            pods_metrics = self.k8s.metrics.list_cluster_custom_object(
                "metrics.k8s.io", "v1beta1", "pods"
            )
            
            return {
                "nodes_metrics": nodes_metrics.get("items", []),
                "pods_metrics": pods_metrics.get("items", [])
            }
        except:
            return {"error": "Metrics server not available"}

    async def detect_common_issues(self) -> Dict:
        """Auto-detect common cluster issues"""
        issues = []
        
        # Check for failed pods
        pods = self.k8s.v1.list_pod_for_all_namespaces()
        failed_pods = [p for p in pods.items if p.status.phase in ["Failed", "Pending"]]
        
        if failed_pods:
            issues.append({
                "type": "failed_pods",
                "severity": "high",
                "count": len(failed_pods),
                "details": [f"{p.metadata.namespace}/{p.metadata.name}" for p in failed_pods[:5]]
            })
        
        # Check for high restart counts
        high_restart_pods = []
        for pod in pods.items:
            for container in pod.status.container_statuses or []:
                if container.restart_count > 10:
                    high_restart_pods.append(f"{pod.metadata.namespace}/{pod.metadata.name}")
        
        if high_restart_pods:
            issues.append({
                "type": "high_restart_count",
                "severity": "medium",
                "count": len(high_restart_pods),
                "details": high_restart_pods[:5]
            })
        
        return {"issues": issues, "timestamp": datetime.now().isoformat()}