import difflib
from typing import Dict, List, Optional

from kubernetes.client.rest import ApiException


class AutoFixer:
    def __init__(self, k8s_client):
        self.k8s = k8s_client

    async def restart_failed_pods(self, dry_run: bool = False) -> Dict:
        """Delete failed or crashlooping pods so their controller can recreate them."""
        results: Dict = {
            "dry_run": dry_run,
            "restarted": [],
            "skipped": [],
            "failed": [],
        }

        pods = self.k8s.v1.list_pod_for_all_namespaces()
        candidates = [
            p
            for p in pods.items
            if (p.status.phase == "Failed" or self._pod_waiting_reason(p) == "CrashLoopBackOff")
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
        """Remove evicted pods that are clogging namespace views."""
        results: Dict = {"dry_run": dry_run, "cleaned": [], "failed": []}

        pods = self.k8s.v1.list_pod_for_all_namespaces()
        evicted = [
            p for p in pods.items if p.status.phase == "Failed" and p.status.reason == "Evicted"
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
        """Restart unhealthy CoreDNS pods."""
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
            p for p in dns_pods.items if p.status.phase != "Running" or not self._pod_ready(p)
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

    async def fix_image_pull_errors(self, dry_run: bool = False) -> Dict:
        """Patch known safe image replacements for bundled practice scenarios."""
        results: Dict = {"dry_run": dry_run, "patched": [], "skipped": [], "failed": []}
        pods = self.k8s.v1.list_pod_for_all_namespaces().items

        for pod in pods:
            waiting_reason = self._pod_waiting_reason(pod)
            if waiting_reason not in ("ImagePullBackOff", "ErrImagePull"):
                continue

            deployment = self._find_matching_deployment_for_pod(pod)
            if not deployment:
                results["skipped"].append(
                    f"{pod.metadata.namespace}/{pod.metadata.name} (no owning deployment found)"
                )
                continue

            changes = []
            for container in deployment.spec.template.spec.containers or []:
                replacement = self._suggest_fixed_image(
                    deployment.metadata.namespace,
                    deployment.metadata.name,
                    container.image,
                )
                if replacement:
                    changes.append((container, container.image, replacement))

            if not changes:
                results["skipped"].append(
                    f"{deployment.metadata.namespace}/{deployment.metadata.name} (no safe image replacement found)"
                )
                continue

            for container, current, replacement in changes:
                if dry_run:
                    results["patched"].append(
                        f"[DRY-RUN] would patch image on {deployment.metadata.namespace}/{deployment.metadata.name}: {current} -> {replacement}"
                    )
                else:
                    container.image = replacement

            if dry_run:
                continue

            try:
                self.k8s.apps_v1.patch_namespaced_deployment(
                    deployment.metadata.name,
                    deployment.metadata.namespace,
                    deployment,
                )
                for _, current, replacement in changes:
                    results["patched"].append(
                        f"{deployment.metadata.namespace}/{deployment.metadata.name}: {current} -> {replacement}"
                    )
            except ApiException as e:
                results["failed"].append(
                    f"{deployment.metadata.namespace}/{deployment.metadata.name}: {str(e)}"
                )

        return results

    async def fix_service_selector_mismatches(self, dry_run: bool = False) -> Dict:
        """Patch Services with empty endpoints to match their same-name Deployment selector."""
        results: Dict = {"dry_run": dry_run, "patched": [], "skipped": [], "failed": []}
        services = self.k8s.v1.list_service_for_all_namespaces().items
        endpoints = {
            (ep.metadata.namespace, ep.metadata.name): ep
            for ep in self.k8s.v1.list_endpoints_for_all_namespaces().items
        }

        for svc in services:
            if not svc.spec.selector:
                continue

            ep = endpoints.get((svc.metadata.namespace, svc.metadata.name))
            if ep and ep.subsets:
                continue

            try:
                dep = self.k8s.apps_v1.read_namespaced_deployment(
                    svc.metadata.name, svc.metadata.namespace
                )
            except ApiException:
                results["skipped"].append(
                    f"{svc.metadata.namespace}/{svc.metadata.name} (no same-name deployment to infer selector from)"
                )
                continue

            expected = dep.spec.selector.match_labels or {}
            current = svc.spec.selector or {}
            if not expected or expected == current:
                continue

            if dry_run:
                results["patched"].append(
                    f"[DRY-RUN] would patch selector on {svc.metadata.namespace}/{svc.metadata.name}: {current} -> {expected}"
                )
                continue

            try:
                self.k8s.v1.patch_namespaced_service(
                    svc.metadata.name,
                    svc.metadata.namespace,
                    {"spec": {"selector": expected}},
                )
                results["patched"].append(
                    f"{svc.metadata.namespace}/{svc.metadata.name}: {current} -> {expected}"
                )
            except ApiException as e:
                results["failed"].append(f"{svc.metadata.namespace}/{svc.metadata.name}: {str(e)}")

        return results

    async def fix_configmap_key_mismatches(self, dry_run: bool = False) -> Dict:
        """Add missing ConfigMap keys when a close or single source key exists."""
        results: Dict = {"dry_run": dry_run, "patched": [], "skipped": [], "failed": []}
        pods = self.k8s.v1.list_pod_for_all_namespaces().items

        for pod in pods:
            if self._pod_waiting_reason(pod) != "CreateContainerConfigError":
                continue

            for container in pod.spec.containers or []:
                for env in container.env or []:
                    ref = getattr(getattr(env, "value_from", None), "config_map_key_ref", None)
                    if not ref or not ref.name or not ref.key:
                        continue

                    try:
                        config_map = self.k8s.v1.read_namespaced_config_map(
                            ref.name, pod.metadata.namespace
                        )
                    except ApiException as e:
                        results["failed"].append(
                            f"{pod.metadata.namespace}/{ref.name}: {str(e)}"
                        )
                        continue

                    data = dict(config_map.data or {})
                    if ref.key in data:
                        continue

                    source_key = self._find_best_source_key(ref.key, list(data.keys()))
                    if not source_key:
                        results["skipped"].append(
                            f"{pod.metadata.namespace}/{ref.name} (no safe source key for missing key {ref.key})"
                        )
                        continue

                    if dry_run:
                        results["patched"].append(
                            f"[DRY-RUN] would add key {ref.key} to {pod.metadata.namespace}/{ref.name} using value from {source_key}"
                        )
                        continue

                    try:
                        self.k8s.v1.patch_namespaced_config_map(
                            ref.name,
                            pod.metadata.namespace,
                            {"data": {ref.key: data[source_key]}},
                        )
                        results["patched"].append(
                            f"{pod.metadata.namespace}/{ref.name}: added key {ref.key} from {source_key}"
                        )
                    except ApiException as e:
                        results["failed"].append(
                            f"{pod.metadata.namespace}/{ref.name}: {str(e)}"
                        )

        return results

    async def fix_ingress_backends(self, dry_run: bool = False) -> Dict:
        """Patch ingresses that reference a missing backend service when a safe replacement is inferable."""
        results: Dict = {"dry_run": dry_run, "patched": [], "skipped": [], "failed": []}
        ingresses = self.k8s.networking_v1.list_ingress_for_all_namespaces().items

        for ingress in ingresses:
            services = self.k8s.v1.list_namespaced_service(ingress.metadata.namespace).items
            service_names = {svc.metadata.name for svc in services}
            modified = False

            for rule in ingress.spec.rules or []:
                http = getattr(rule, "http", None)
                if not http:
                    continue
                for path in http.paths or []:
                    backend = getattr(path, "backend", None)
                    service = getattr(backend, "service", None)
                    service_name = getattr(service, "name", None)
                    if not service_name or service_name in service_names:
                        continue

                    replacement = self._infer_ingress_service_name(
                        ingress.metadata.name, service_names
                    )
                    if not replacement:
                        results["skipped"].append(
                            f"{ingress.metadata.namespace}/{ingress.metadata.name} (cannot infer replacement for backend {service_name})"
                        )
                        continue

                    if dry_run:
                        results["patched"].append(
                            f"[DRY-RUN] would patch ingress {ingress.metadata.namespace}/{ingress.metadata.name}: {service_name} -> {replacement}"
                        )
                        modified = True
                        continue

                    path.backend.service.name = replacement
                    modified = True
                    results["patched"].append(
                        f"{ingress.metadata.namespace}/{ingress.metadata.name}: {service_name} -> {replacement}"
                    )

            if modified and not dry_run:
                try:
                    self.k8s.networking_v1.patch_namespaced_ingress(
                        ingress.metadata.name,
                        ingress.metadata.namespace,
                        ingress,
                    )
                except ApiException as e:
                    results["failed"].append(
                        f"{ingress.metadata.namespace}/{ingress.metadata.name}: {str(e)}"
                    )

        return results

    async def fix_aggressive_liveness_probes(self, dry_run: bool = False) -> Dict:
        """Increase liveness probe initial delay for restarting workloads with liveness failures."""
        results: Dict = {"dry_run": dry_run, "patched": [], "skipped": [], "failed": []}
        pods = self.k8s.v1.list_pod_for_all_namespaces().items

        for pod in pods:
            if pod.metadata.namespace in ("kube-system", "kube-public", "kube-node-lease"):
                continue
            if not any((cs.restart_count or 0) > 0 for cs in (pod.status.container_statuses or [])):
                continue

            pod_events = self.k8s.v1.list_namespaced_event(pod.metadata.namespace).items
            has_liveness_failure = any(
                event.involved_object.name == pod.metadata.name
                and event.reason == "Unhealthy"
                and "Liveness probe failed" in (event.message or "")
                for event in pod_events
            )
            if not has_liveness_failure:
                continue

            deployment = self._find_matching_deployment_for_pod(pod)
            if not deployment:
                results["skipped"].append(
                    f"{pod.metadata.namespace}/{pod.metadata.name} (no owning deployment found)"
                )
                continue

            changed = []
            for container in deployment.spec.template.spec.containers or []:
                probe = container.liveness_probe
                if not probe:
                    continue
                initial_delay = probe.initial_delay_seconds or 0
                if initial_delay >= 30:
                    continue
                target_delay = max(30, initial_delay)
                if dry_run:
                    results["patched"].append(
                        f"[DRY-RUN] would patch livenessProbe.initialDelaySeconds on {deployment.metadata.namespace}/{deployment.metadata.name}: {initial_delay} -> {target_delay}"
                    )
                else:
                    probe.initial_delay_seconds = target_delay
                changed.append((initial_delay, target_delay))

            if not changed:
                continue

            if dry_run:
                continue

            try:
                self.k8s.apps_v1.patch_namespaced_deployment(
                    deployment.metadata.name,
                    deployment.metadata.namespace,
                    deployment,
                )
                for initial_delay, target_delay in changed:
                    results["patched"].append(
                        f"{deployment.metadata.namespace}/{deployment.metadata.name}: livenessProbe.initialDelaySeconds {initial_delay} -> {target_delay}"
                    )
            except ApiException as e:
                results["failed"].append(
                    f"{deployment.metadata.namespace}/{deployment.metadata.name}: {str(e)}"
                )

        return results

    async def scale_resources(
        self, namespace: str, deployment: str, replicas: int, dry_run: bool = False
    ) -> Dict:
        """Scale a deployment to the specified replica count."""
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
        """Set CPU and memory limits on all containers in a deployment."""
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
        """Detect issues and apply safe remediations."""
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
            elif issue["type"] == "image_pull_errors":
                result = await self.fix_image_pull_errors(dry_run=dry_run)
                actions.append({"issue": "image_pull_errors", "result": result})
            elif issue["type"] == "service_selector_mismatch":
                result = await self.fix_service_selector_mismatches(dry_run=dry_run)
                actions.append({"issue": "service_selector_mismatch", "result": result})
            elif issue["type"] == "configmap_key_mismatch":
                result = await self.fix_configmap_key_mismatches(dry_run=dry_run)
                actions.append({"issue": "configmap_key_mismatch", "result": result})
            elif issue["type"] == "ingress_backend_missing_service":
                result = await self.fix_ingress_backends(dry_run=dry_run)
                actions.append({"issue": "ingress_backend_missing_service", "result": result})
            elif issue["type"] == "aggressive_liveness_probe":
                result = await self.fix_aggressive_liveness_probes(dry_run=dry_run)
                actions.append({"issue": "aggressive_liveness_probe", "result": result})

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

    def _pod_waiting_reason(self, pod) -> Optional[str]:
        for cs in pod.status.container_statuses or []:
            if cs.state and cs.state.waiting and cs.state.waiting.reason:
                return cs.state.waiting.reason
        return None

    def _find_matching_deployment_for_pod(self, pod):
        labels = pod.metadata.labels or {}
        deployments = self.k8s.apps_v1.list_namespaced_deployment(pod.metadata.namespace).items
        matches = []

        for deployment in deployments:
            selector = deployment.spec.selector.match_labels or {}
            if selector and all(labels.get(key) == value for key, value in selector.items()):
                matches.append(deployment)

        if len(matches) == 1:
            return matches[0]

        app_label = labels.get("app")
        for deployment in matches:
            if app_label and deployment.metadata.name == app_label:
                return deployment

        return None

    def _suggest_fixed_image(
        self, namespace: str, deployment_name: str, current_image: str
    ) -> Optional[str]:
        practice_fixes = {
            ("practice", "scenario-01", "nginx:1.99.99"): "nginx:1.25",
        }
        return practice_fixes.get((namespace, deployment_name, current_image))

    def _find_best_source_key(self, missing_key: str, available_keys: List[str]) -> Optional[str]:
        if not available_keys:
            return None
        if len(available_keys) == 1:
            return available_keys[0]

        matches = difflib.get_close_matches(missing_key, available_keys, n=1, cutoff=0.4)
        return matches[0] if matches else None

    def _infer_ingress_service_name(
        self, ingress_name: str, service_names: set
    ) -> Optional[str]:
        matching = sorted(name for name in service_names if name.startswith(ingress_name))
        if len(matching) == 1:
            return matching[0]
        if len(service_names) == 1:
            return next(iter(service_names))
        return None
