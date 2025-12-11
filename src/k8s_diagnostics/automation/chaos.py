from typing import Dict
from kubernetes.client.rest import ApiException


class ChaosEngine:
    """Simple chaos injector with optional dry-run"""

    def __init__(self, k8s_client):
        self.k8s = k8s_client

    async def inject_pod_failure(self, namespace: str, label_selector: str, dry_run: bool = True) -> Dict:
        if namespace in ["kube-system", "kube-public", "kube-node-lease"]:
            return {"error": "Refusing to target system namespace"}

        pods = self.k8s.v1.list_namespaced_pod(namespace, label_selector=label_selector)
        if not pods.items:
            return {"error": "No pods matched", "namespace": namespace, "selector": label_selector}

        target = pods.items[0]
        target_ref = f"{namespace}/{target.metadata.name}"

        if dry_run:
            return {"action": "dry_run", "target": target_ref}

        try:
            self.k8s.v1.delete_namespaced_pod(target.metadata.name, namespace)
            return {"action": "deleted_pod", "target": target_ref}
        except ApiException as e:
            return {"error": str(e), "target": target_ref}
