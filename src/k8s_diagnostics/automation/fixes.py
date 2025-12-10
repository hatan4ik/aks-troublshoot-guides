from typing import Dict, List
import asyncio
from kubernetes.client.rest import ApiException

class AutoFixer:
    def __init__(self, k8s_client):
        self.k8s = k8s_client

    async def restart_failed_pods(self) -> Dict:
        """Auto-restart failed pods"""
        results = {"restarted": [], "failed": [], "skipped": []}
        
        pods = self.k8s.v1.list_pod_for_all_namespaces()
        failed_pods = [p for p in pods.items 
                      if p.status.phase in ["Failed", "CrashLoopBackOff"] 
                      and self._is_safe_to_restart(p)]
        
        for pod in failed_pods:
            try:
                # Delete pod to trigger restart (if managed by deployment/replicaset)
                if self._has_controller(pod):
                    self.k8s.v1.delete_namespaced_pod(
                        pod.metadata.name, 
                        pod.metadata.namespace
                    )
                    results["restarted"].append(f"{pod.metadata.namespace}/{pod.metadata.name}")
                else:
                    results["skipped"].append(f"{pod.metadata.namespace}/{pod.metadata.name} (no controller)")
            except ApiException as e:
                results["failed"].append(f"{pod.metadata.namespace}/{pod.metadata.name}: {str(e)}")
        
        return results

    def _is_safe_to_restart(self, pod) -> bool:
        """Check if pod is safe to restart"""
        # Don't restart system pods
        if pod.metadata.namespace in ["kube-system", "kube-public"]:
            return False
        
        # Don't restart if it's a job or has specific annotations
        if pod.metadata.labels and pod.metadata.labels.get("job-name"):
            return False
            
        return True

    def _has_controller(self, pod) -> bool:
        """Check if pod has a controller (deployment, replicaset, etc.)"""
        return bool(pod.metadata.owner_references)

    async def cleanup_evicted_pods(self) -> Dict:
        """Remove evicted pods"""
        results = {"cleaned": [], "failed": []}
        
        pods = self.k8s.v1.list_pod_for_all_namespaces()
        evicted_pods = [p for p in pods.items if p.status.phase == "Failed" 
                       and p.status.reason == "Evicted"]
        
        for pod in evicted_pods:
            try:
                self.k8s.v1.delete_namespaced_pod(
                    pod.metadata.name, 
                    pod.metadata.namespace
                )
                results["cleaned"].append(f"{pod.metadata.namespace}/{pod.metadata.name}")
            except ApiException as e:
                results["failed"].append(f"{pod.metadata.namespace}/{pod.metadata.name}: {str(e)}")
        
        return results

    async def fix_dns_issues(self) -> Dict:
        """Restart CoreDNS pods if needed"""
        results = {"action": "none", "restarted": [], "status": "ok"}
        
        # Check CoreDNS health
        dns_pods = self.k8s.v1.list_namespaced_pod(
            "kube-system", 
            label_selector="k8s-app=kube-dns"
        )
        
        unhealthy_dns = [p for p in dns_pods.items 
                        if p.status.phase != "Running" or not self._pod_ready(p)]
        
        if unhealthy_dns:
            results["action"] = "restart_coredns"
            for pod in unhealthy_dns:
                try:
                    self.k8s.v1.delete_namespaced_pod(
                        pod.metadata.name, 
                        "kube-system"
                    )
                    results["restarted"].append(pod.metadata.name)
                except ApiException as e:
                    results["status"] = f"error: {str(e)}"
        
        return results

    def _pod_ready(self, pod) -> bool:
        """Check if pod is ready"""
        if not pod.status.conditions:
            return False
        
        for condition in pod.status.conditions:
            if condition.type == "Ready":
                return condition.status == "True"
        return False

    async def scale_resources(self, namespace: str, deployment: str, replicas: int) -> Dict:
        """Scale deployment replicas"""
        try:
            # Get current deployment
            dep = self.k8s.apps_v1.read_namespaced_deployment(deployment, namespace)
            current_replicas = dep.spec.replicas
            
            # Update replicas
            dep.spec.replicas = replicas
            self.k8s.apps_v1.patch_namespaced_deployment(
                deployment, namespace, dep
            )
            
            return {
                "deployment": f"{namespace}/{deployment}",
                "previous_replicas": current_replicas,
                "new_replicas": replicas,
                "status": "scaled"
            }
        except ApiException as e:
            return {"error": str(e)}

    async def apply_resource_limits(self, namespace: str, deployment: str, 
                                  cpu_limit: str, memory_limit: str) -> Dict:
        """Apply resource limits to deployment"""
        try:
            dep = self.k8s.apps_v1.read_namespaced_deployment(deployment, namespace)
            
            # Update resource limits for all containers
            for container in dep.spec.template.spec.containers:
                if not container.resources:
                    container.resources = {}
                if not container.resources.limits:
                    container.resources.limits = {}
                
                container.resources.limits["cpu"] = cpu_limit
                container.resources.limits["memory"] = memory_limit
            
            self.k8s.apps_v1.patch_namespaced_deployment(
                deployment, namespace, dep
            )
            
            return {
                "deployment": f"{namespace}/{deployment}",
                "limits": {"cpu": cpu_limit, "memory": memory_limit},
                "status": "applied"
            }
        except ApiException as e:
            return {"error": str(e)}