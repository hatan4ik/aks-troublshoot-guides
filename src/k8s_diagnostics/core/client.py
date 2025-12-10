from kubernetes import client, config
from typing import Dict, List, Optional
import json

class K8sClient:
    def __init__(self):
        try:
            config.load_incluster_config()
        except:
            config.load_kube_config()
        
        self.v1 = client.CoreV1Api()
        self.apps_v1 = client.AppsV1Api()
        self.metrics = client.CustomObjectsApi()

    def get_cluster_health(self) -> Dict:
        """Get comprehensive cluster health status"""
        health = {
            "nodes": self._check_nodes(),
            "pods": self._check_pods(),
            "services": self._check_services(),
            "events": self._get_recent_events()
        }
        return health

    def _check_nodes(self) -> Dict:
        nodes = self.v1.list_node()
        total = len(nodes.items)
        ready = sum(1 for node in nodes.items 
                   if any(c.status == "True" and c.type == "Ready" 
                         for c in node.status.conditions))
        return {"total": total, "ready": ready, "status": "healthy" if ready == total else "degraded"}

    def _check_pods(self) -> Dict:
        pods = self.v1.list_pod_for_all_namespaces()
        total = len(pods.items)
        running = sum(1 for pod in pods.items if pod.status.phase == "Running")
        failed = [{"name": p.metadata.name, "namespace": p.metadata.namespace, 
                  "phase": p.status.phase} for p in pods.items 
                 if p.status.phase not in ["Running", "Succeeded"]]
        return {"total": total, "running": running, "failed": failed}

    def _check_services(self) -> Dict:
        services = self.v1.list_service_for_all_namespaces()
        endpoints = self.v1.list_endpoints_for_all_namespaces()
        
        no_endpoints = []
        for svc in services.items:
            ep = next((e for e in endpoints.items 
                      if e.metadata.name == svc.metadata.name 
                      and e.metadata.namespace == svc.metadata.namespace), None)
            if ep and not ep.subsets:
                no_endpoints.append(f"{svc.metadata.namespace}/{svc.metadata.name}")
        
        return {"total": len(services.items), "without_endpoints": no_endpoints}

    def _get_recent_events(self) -> List[Dict]:
        events = self.v1.list_event_for_all_namespaces()
        warnings = [{"namespace": e.namespace, "object": e.involved_object.name,
                    "reason": e.reason, "message": e.message, "time": str(e.last_timestamp)}
                   for e in events.items if e.type == "Warning"]
        return warnings[-10:]  # Last 10 warnings