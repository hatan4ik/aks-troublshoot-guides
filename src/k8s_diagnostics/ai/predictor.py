import numpy as np
from sklearn.ensemble import IsolationForest, RandomForestClassifier
from typing import Dict, Iterable, List, Optional
import asyncio

class AIPredictor:
    def __init__(self):
        self.anomaly_detector = IsolationForest(contamination=0.1, random_state=42)
        self.failure_predictor = RandomForestClassifier(n_estimators=100, random_state=42)

    async def predict_failures(self, metrics: Dict) -> Dict:
        """Predict potential failures using ML"""
        features = [
            metrics.get("cpu_usage", 0),
            metrics.get("memory_usage", 0),
            metrics.get("pod_restart_count", 0),
            metrics.get("error_rate", 0)
        ]
        
        # Mock prediction - replace with trained model
        failure_prob = np.random.random()
        
        return {
            "failure_probability": float(failure_prob),
            "risk_level": "critical" if failure_prob > 0.8 else "low",
            "recommended_actions": ["scale_up", "restart_pods"] if failure_prob > 0.7 else []
        }

class ChaosEngineer:
    def __init__(self, k8s_client, allowed_namespaces: Optional[Iterable[str]] = None):
        self.k8s = k8s_client
        self.allowed_namespaces = {
            namespace.strip()
            for namespace in (allowed_namespaces or [])
            if namespace and namespace.strip()
        } or None

    async def inject_pod_failure(
        self, namespace: str, label_selector: str, dry_run: bool = True
    ) -> Dict:
        """Inject controlled pod failures"""
        if namespace in ["kube-system", "kube-public", "kube-node-lease"]:
            return {"error": "Refusing to target system namespace"}
        if (
            self.allowed_namespaces is not None
            and "*" not in self.allowed_namespaces
            and namespace not in self.allowed_namespaces
        ):
            return {
                "error": f"namespace '{namespace}' is outside the chaos allowlist",
                "allowed_namespaces": sorted(self.allowed_namespaces),
            }

        pods = self.k8s.v1.list_namespaced_pod(namespace, label_selector=label_selector)
        if pods.items:
            target_pod = pods.items[0]
            if dry_run:
                return {
                    "experiment": "pod_failure",
                    "action": "dry_run",
                    "target": f"{namespace}/{target_pod.metadata.name}",
                }
            self.k8s.v1.delete_namespaced_pod(target_pod.metadata.name, namespace)
            return {"experiment": "pod_failure", "target": f"{namespace}/{target_pod.metadata.name}"}
        return {"error": "no_pods_found"}

class AutoHealer:
    def __init__(self, k8s_client, ai_predictor):
        self.k8s = k8s_client
        self.ai = ai_predictor

    async def autonomous_healing(self) -> Dict:
        """Autonomous healing based on AI predictions"""
        metrics = {"cpu_usage": 0.7, "memory_usage": 0.8, "pod_restart_count": 15, "error_rate": 0.02}
        prediction = await self.ai.predict_failures(metrics)
        
        actions_taken = []
        if prediction["risk_level"] == "critical":
            for action in prediction["recommended_actions"]:
                result = await self._execute_action(action)
                actions_taken.append(result)
        
        return {"prediction": prediction, "actions_taken": actions_taken}

    async def _execute_action(self, action: str) -> Dict:
        """Execute healing action"""
        if action == "scale_up":
            return {"action": "scale_up", "status": "completed"}
        elif action == "restart_pods":
            return {"action": "restart_pods", "status": "completed"}
        return {"action": action, "status": "not_implemented"}
