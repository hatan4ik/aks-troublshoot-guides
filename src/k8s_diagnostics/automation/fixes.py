from typing import Dict, List
from kubernetes.client.rest import ApiException


class AutoFixer:
    def __init__(self, k8s_client):
        self.k8s = k8s_client

    # ─────────────────────────────────────────────────────────────
    # Gap 6: All mutating methods support dry_run=True.
    # When dry_run=True the method returns what it *would* do
    # without making any API calls that modify cluster state.
    # ─────────────────────────────────────────────────────────────

    async def restart_failed_pods(self, dry_run: bool = False) -> Dict:
        """Delete failed pods so their controller can recreate them.

        Args:
            dry_run: If True, return what would be restarted without acting.
        """
        results: Dict = {
            "dry_run": dry_run,
            "restarted": [],
            "skipped": [],
            "failed": [],
        }

        pods = self.k8s.v1.list_pod_for_all_namespaces()
        candidates = [
            p for p in pods.items
            if p.status.phase in ("Failed", "CrashLoopBackOff")
            and self._is_safe_to_restart(p)
        ]

        for pod in candidates:
            ref = f"{pod.metadata.namespace}/{pod.metadata.name}"
            if not self._has_controller(pod):
                results["skipped"].append(f"{ref} (no controller — manual intervention required)")
                continue

            if dry_run:
                results["restarted"].append(f"[DRY-RUN] would delete pod {ref}")
                continue

            try:
                self.k8s.v1.delete_namespaced_pod(pod.metadata.name, pod.metadata.namespace)
                results["restarted"].append(ref)
            except ApiException as e:
                results["failed"].append(f"{ref}: {str(e)}")

        return results

    async def cleanup_evicted_pods(self, dry_run: bool = False) -> Dict:
        """Remove evicted pods that are clogging namespace views.

        Args:
            dry_run: If True, return what would be cleaned without acting.
        """
        results: Dict = {"dry_run": dry_run, "cleaned": [], "failed": []}

        pods = self.k8s.v1.list_pod_for_all_namespaces()
        evicted = [
            p for p in pods.items
            if p.status.phase == "Failed" and p.status.reason == "Evicted"
        ]

        for pod in evicted:
            ref = f"{pod.metadata.namespace}/{pod.metadata.name}"
            if dry_run:
                results["cleaned"].append(f"[DRY-RUN] would delete evicted pod {ref}")
                continue
            try:
                self.k8s.v1.delete_namespaced_pod(pod.metadata.name, pod.metadata.namespace)
                results["cleaned"].append(ref)
            except ApiException as e:
                results["failed"].append(f"{ref}: {str(e)}")

        return results

    async def fix_dns_issues(self, dry_run: bool = False) -> Dict:
        """Restart unhealthy CoreDNS pods.

        Args:
            dry_run: If True, return what would be restarted without acting.
        """
        results: Dict = {
            "dry_run": dry_run,
            "action": "none",
            "restarted": [],
            "status": "ok",
        }

        dns_pods = self.k8s.v1.list_namespaced_pod(
            "kube-system", label_selector="k8s-app=kube-dns"
        )
        unhealthy = [
            p for p in dns_pods.items
            if p.status.phase != "Running" or not self._pod_ready(p)
        ]

        if not unhealthy:
            return results

        results["action"] = "restart_coredns"
        for pod in unhealthy:
            ref = pod.metadata.name
            if dry_run:
                results["restarted"].append(f"[DRY-RUN] would restart CoreDNS pod {ref}")
                continue
            try:
                self.k8s.v1.delete_namespaced_pod(ref, "kube-system")
                results["restarted"].append(ref)
            except ApiException as e:
                results["status"] = f"error: {str(e)}"

        return results

    async def scale_resources(
        self, namespace: str, deployment: str, replicas: int, dry_run: bool = False
    ) -> Dict:
        """Scale a deployment to the specified replica count.

        Args:
            dry_run: If True, return the planned change without applying it.
        """
        try:
            dep = self.k8s.apps_v1.read_namespaced_deployment(deployment, namespace)
            current = dep.spec.replicas

            if dry_run:
                return {
                    "dry_run": True,
                    "deployment": f"{namespace}/{deployment}",
                    "current_replicas": current,
                    "would_set_replicas": replicas,
                }

            dep.spec.replicas = replicas
            self.k8s.apps_v1.patch_namespaced_deployment(deployment, namespace, dep)
            return {
                "dry_run": False,
                "deployment": f"{namespace}/{deployment}",
                "previous_replicas": current,
                "new_replicas": replicas,
                "status": "scaled",
            }
        except ApiException as e:
            return {"error": str(e)}

    async def apply_resource_limits(
        self,
        namespace: str,
        deployment: str,
        cpu_limit: str,
        memory_limit: str,
        dry_run: bool = False,
    ) -> Dict:
        """Set CPU and memory limits on all containers in a deployment.

        Args:
            dry_run: If True, return the planned change without applying it.
        """
        try:
            dep = self.k8s.apps_v1.read_namespaced_deployment(deployment, namespace)
            containers = [c.name for c in dep.spec.template.spec.containers]

            if dry_run:
                return {
                    "dry_run": True,
                    "deployment": f"{namespace}/{deployment}",
                    "would_set_limits": {"cpu": cpu_limit, "memory": memory_limit},
                    "containers_affected": containers,
                }

            for container in dep.spec.template.spec.containers:
                if not container.resources:
                    container.resources = {}
                if not container.resources.limits:
                    container.resources.limits = {}
                container.resources.limits["cpu"] = cpu_limit
                container.resources.limits["memory"] = memory_limit

            self.k8s.apps_v1.patch_namespaced_deployment(deployment, namespace, dep)
            return {
                "dry_run": False,
                "deployment": f"{namespace}/{deployment}",
                "limits": {"cpu": cpu_limit, "memory": memory_limit},
                "status": "applied",
            }
        except ApiException as e:
            return {"error": str(e)}

    async def auto_remediate(self, diagnostics_engine, dry_run: bool = False) -> Dict:
        """Detect issues and apply safe remediations.

        Args:
            dry_run: If True, show what would be done without making changes.
        """
        detected = await diagnostics_engine.detect_common_issues()
        issues = detected.get("issues", [])

        if not issues:
            return {"dry_run": dry_run, "status": "no_issues_detected", "actions": []}

        actions = []
        for issue in issues:
            if issue["type"] == "failed_pods":
                result = await self.restart_failed_pods(dry_run=dry_run)
                actions.append({"issue": "failed_pods", "result": result})
            elif issue["type"] == "dns_unhealthy":
                result = await self.fix_dns_issues(dry_run=dry_run)
                actions.append({"issue": "dns_unhealthy", "result": result})

        return {
            "dry_run": dry_run,
            "status": "completed",
            "issues_found": len(issues),
            "actions": actions,
        }

    async def update_certificates(self) -> Dict:
        return {
            "status": "manual_action_required",
            "message": (
                "Automated certificate renewal is not implemented. "
                "If using cert-manager, trigger renewal with: "
                "kubectl annotate certificate <name> -n <ns> "
                "cert-manager.io/renewal-reason=\"manual-$(date +%s)\""
            ),
        }

    # ─────────────────────────────────────────────────────────────
    # Internal helpers
    # ─────────────────────────────────────────────────────────────

    def _is_safe_to_restart(self, pod) -> bool:
        if pod.metadata.namespace in ("kube-system", "kube-public", "kube-node-lease"):
            return False
        if pod.metadata.labels and pod.metadata.labels.get("job-name"):
            return False
        return True

    def _has_controller(self, pod) -> bool:
        return bool(pod.metadata.owner_references)

    def _pod_ready(self, pod) -> bool:
        for condition in (pod.status.conditions or []):
            if condition.type == "Ready":
                return condition.status == "True"
        return False
