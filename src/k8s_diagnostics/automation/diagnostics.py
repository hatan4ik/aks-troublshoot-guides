from typing import Dict, List
from datetime import datetime
from kubernetes.client import V1Pod

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
            "ingress": self._check_ingress_controllers(),
            "load_balancers": self._check_pending_load_balancers()
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
        
        # Nodes not ready
        nodes = self.k8s.v1.list_node()
        not_ready = [
            n.metadata.name for n in nodes.items
            if not any(c.type == "Ready" and c.status == "True" for c in n.status.conditions or [])
        ]
        if not_ready:
            issues.append({
                "type": "nodes_not_ready",
                "severity": "high",
                "count": len(not_ready),
                "details": not_ready[:5]
            })

        # Check for failed/pending pods
        pods = self.k8s.v1.list_pod_for_all_namespaces()
        failed_pods = [p for p in pods.items if p.status.phase in ["Failed", "Pending"]]
        
        if failed_pods:
            issues.append({
                "type": "failed_pods",
                "severity": "high",
                "count": len(failed_pods),
                "details": [f"{p.metadata.namespace}/{p.metadata.name}" for p in failed_pods[:5]]
            })
        
        # Image pull issues
        image_pull = self._find_image_pull_errors(pods.items)
        if image_pull:
            issues.append({
                "type": "image_pull_errors",
                "severity": "high",
                "count": len(image_pull),
                "details": image_pull[:5]
            })

        # Pending PVCs
        pending_pvcs = self.k8s.v1.list_persistent_volume_claim_for_all_namespaces()
        stuck_pvcs = [f"{p.metadata.namespace}/{p.metadata.name}" for p in pending_pvcs.items if p.status.phase != "Bound"]
        if stuck_pvcs:
            issues.append({
                "type": "pvc_not_bound",
                "severity": "medium",
                "count": len(stuck_pvcs),
                "details": stuck_pvcs[:5]
            })

        # DNS issues (CoreDNS not healthy)
        dns_status = await self._check_dns()
        if dns_status.get("running_pods", 0) == 0:
            issues.append({
                "type": "dns_unhealthy",
                "severity": "high",
                "details": ["CoreDNS pods not running"]
            })

        # Pending load balancers
        pending_lbs = self._check_pending_load_balancers().get("pending", [])
        if pending_lbs:
            issues.append({
                "type": "load_balancer_pending",
                "severity": "medium",
                "count": len(pending_lbs),
                "details": pending_lbs[:5]
            })

        # High restart counts
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

    def _find_image_pull_errors(self, pods: List[V1Pod]) -> List[str]:
        """Detect pods with image pull failures"""
        pull_errors = []
        for pod in pods:
            for status in pod.status.container_statuses or []:
                waiting = status.state.waiting
                if waiting and waiting.reason in ["ImagePullBackOff", "ErrImagePull"]:
                    pull_errors.append(f"{pod.metadata.namespace}/{pod.metadata.name} ({waiting.reason})")
        return pull_errors

    def _check_pending_load_balancers(self) -> Dict:
        """Identify pending load balancer services"""
        lbs = self.k8s.v1.list_service_for_all_namespaces(field_selector="spec.type=LoadBalancer")
        pending = []
        for svc in lbs.items:
            ingress = svc.status.load_balancer.ingress
            if not ingress:
                pending.append(f"{svc.metadata.namespace}/{svc.metadata.name}")
        return {"pending": pending, "total": len(lbs.items)}

    async def setup_prometheus(self) -> Dict:
        """Placeholder for prometheus setup"""
        return {
            "status": "manual_action_required",
            "message": "Automated prometheus setup is not yet implemented. Please use the helm chart.",
            "guidance": "You can use the script: `./scripts/monitoring/setup-prometheus.sh`"
        }

    async def configure_alerts(self) -> Dict:
        """Placeholder for alert configuration"""
        return {
            "status": "manual_action_required",
            "message": "Automated alert configuration is not yet implemented. Please use the script.",
            "guidance": "You can use the script: `./scripts/monitoring/configure-alerts.sh`"
        }

    async def create_grafana_dashboard(self) -> Dict:
        """Placeholder for grafana dashboard creation"""
        return {
            "status": "manual_action_required",
            "message": "Automated grafana dashboard creation is not yet implemented. Please use the script.",
            "guidance": "You can use the script: `./scripts/monitoring/health-dashboard.sh`"
        }

    async def setup_log_aggregation(self) -> Dict:
        """Placeholder for log aggregation setup"""
        return {
            "status": "manual_action_required",
            "message": "Automated log aggregation setup is not yet implemented. Please use the script.",
            "guidance": "You can use the script: `./scripts/monitoring/log-aggregation.sh`"
        }

    async def analyze_performance(self) -> Dict:
        """Placeholder for performance analysis"""
        return {
            "status": "manual_action_required",
            "message": "Automated performance analysis is not yet implemented. Please use the script.",
            "guidance": "You can use the script: `./scripts/diagnostics/performance-analysis.sh`"
        }

    async def scan_security(self) -> Dict:
        """Placeholder for security scanning"""
        return {
            "status": "manual_action_required",
            "message": "Automated security scanning is not yet implemented. Please use the scripts.",
            "guidance": "You can use the scripts in `./scripts/diagnostics/` such as `security-audit.sh`, `security-scan.sh`, `network-security-scan.sh`, and `image-security-scan.sh`"
        }

    async def predict_issues(self) -> Dict:
        """Placeholder for predictive issue detection"""
        return {
            "status": "not_implemented",
            "message": "Predictive issue detection is not yet implemented. This will use historical data to predict future issues."
        }

    async def ml_root_cause_analysis(self) -> Dict:
        """Placeholder for ML-based root cause analysis"""
        return {
            "status": "not_implemented",
            "message": "ML-based root cause analysis is not yet implemented. This will use machine learning to identify the root cause of issues."
        }

    async def intelligent_alerting(self) -> Dict:
        """Placeholder for intelligent alerting"""
        return {
            "status": "not_implemented",
            "message": "Intelligent alerting is not yet implemented. This will use machine learning to reduce alert noise and provide more context."
        }

