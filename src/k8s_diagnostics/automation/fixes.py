import difflib
import json
from typing import Dict, Iterable, List, Optional

from kubernetes.client.rest import ApiException


class AutoFixer:
    def __init__(self, k8s_client, allowed_namespaces: Optional[Iterable[str]] = None):
        self.k8s = k8s_client
        self.allowed_namespaces = self._normalize_allowed_namespaces(allowed_namespaces)

    def _new_results(self, dry_run: bool, **fields) -> Dict:
        results = {"dry_run": dry_run, "operations": []}
        results.update(fields)
        return results

    def _record_operation(
        self,
        results: Dict,
        *,
        dry_run: bool,
        action: str,
        resource: str,
        api_call: str,
        kubectl_equivalent: str,
        change: Optional[Dict] = None,
        status: Optional[str] = None,
        error: Optional[str] = None,
    ) -> None:
        operation = {
            "status": status or ("planned" if dry_run else "applied"),
            "action": action,
            "resource": resource,
            "api_call": api_call,
            "kubectl_equivalent": kubectl_equivalent,
        }
        if change is not None:
            operation["change"] = change
        if error is not None:
            operation["error"] = error
        results["operations"].append(operation)

    def _json_arg(self, payload: Dict) -> str:
        return json.dumps(payload, separators=(",", ":"))

    def _normalize_allowed_namespaces(
        self, allowed_namespaces: Optional[Iterable[str]]
    ) -> Optional[set]:
        if allowed_namespaces is None:
            return None

        normalized = {
            namespace.strip()
            for namespace in allowed_namespaces
            if namespace and namespace.strip()
        }
        return normalized or None

    def _namespace_allowed(self, namespace: str) -> bool:
        return (
            self.allowed_namespaces is None
            or "*" in self.allowed_namespaces
            or namespace in self.allowed_namespaces
        )

    def _skip_disallowed_namespace(self, results: Dict, namespace: str, resource: str) -> bool:
        if self._namespace_allowed(namespace):
            return False

        message = f"{resource} (namespace '{namespace}' is outside the remediation allowlist)"
        results.setdefault("skipped", []).append(message)
        self._record_operation(
            results,
            dry_run=results.get("dry_run", False),
            status="skipped",
            action="skip_disallowed_namespace",
            resource=resource,
            api_call="allowlist_guard",
            kubectl_equivalent="not applicable",
            change={"allowed_namespaces": sorted(self.allowed_namespaces or [])},
        )
        return True

    async def restart_failed_pods(self, dry_run: bool = False) -> Dict:
        """Delete failed or crashlooping pods so their controller can recreate them."""
        results: Dict = self._new_results(
            dry_run,
            restarted=[],
            skipped=[],
            failed=[],
        )

        pods = self.k8s.v1.list_pod_for_all_namespaces()
        candidates = [
            p
            for p in pods.items
            if (p.status.phase == "Failed" or self._pod_waiting_reason(p) == "CrashLoopBackOff")
            and self._is_safe_to_restart(p)
        ]

        for pod in candidates:
            ref = f"{pod.metadata.namespace}/{pod.metadata.name}"
            if self._skip_disallowed_namespace(results, pod.metadata.namespace, f"pod/{ref}"):
                continue

            if not self._has_controller(pod):
                results["skipped"].append(f"{ref} (no controller — manual intervention required)")
                self._record_operation(
                    results,
                    dry_run=dry_run,
                    status="skipped",
                    action="delete_pod_for_controller_recreate",
                    resource=f"pod/{ref}",
                    api_call="CoreV1Api.delete_namespaced_pod",
                    kubectl_equivalent=f"kubectl delete pod {pod.metadata.name} -n {pod.metadata.namespace}",
                    change={"reason": "pod has no ownerReferences; deletion may not recreate it"},
                )
                continue

            # PDB guard — never violate a PodDisruptionBudget
            pdb_violation = self._pdb_would_be_violated(pod)
            if pdb_violation:
                results["skipped"].append(f"{ref} ({pdb_violation})")
                self._record_operation(
                    results,
                    dry_run=dry_run,
                    status="skipped",
                    action="delete_pod_for_controller_recreate",
                    resource=f"pod/{ref}",
                    api_call="CoreV1Api.delete_namespaced_pod",
                    kubectl_equivalent=f"kubectl delete pod {pod.metadata.name} -n {pod.metadata.namespace}",
                    change={"reason": pdb_violation},
                )
                continue

            if dry_run:
                results["restarted"].append(f"[DRY-RUN] would delete pod {ref}")
                self._record_operation(
                    results,
                    dry_run=dry_run,
                    action="delete_pod_for_controller_recreate",
                    resource=f"pod/{ref}",
                    api_call="CoreV1Api.delete_namespaced_pod",
                    kubectl_equivalent=f"kubectl delete pod {pod.metadata.name} -n {pod.metadata.namespace}",
                    change={"reason": "controller-owned failed/crashlooping pod"},
                )
                continue

            try:
                self.k8s.v1.delete_namespaced_pod(pod.metadata.name, pod.metadata.namespace)
                results["restarted"].append(ref)
                self._record_operation(
                    results,
                    dry_run=dry_run,
                    action="delete_pod_for_controller_recreate",
                    resource=f"pod/{ref}",
                    api_call="CoreV1Api.delete_namespaced_pod",
                    kubectl_equivalent=f"kubectl delete pod {pod.metadata.name} -n {pod.metadata.namespace}",
                    change={"reason": "controller-owned failed/crashlooping pod"},
                )
            except ApiException as e:
                err = self._categorize_api_exception(e)
                results["failed"].append({ref: err})
                self._record_operation(
                    results,
                    dry_run=dry_run,
                    status="failed",
                    action="delete_pod_for_controller_recreate",
                    resource=f"pod/{ref}",
                    api_call="CoreV1Api.delete_namespaced_pod",
                    kubectl_equivalent=f"kubectl delete pod {pod.metadata.name} -n {pod.metadata.namespace}",
                    error=err,
                )

        return results

    async def cleanup_evicted_pods(self, dry_run: bool = False) -> Dict:
        """Remove evicted pods that are clogging namespace views."""
        results: Dict = self._new_results(dry_run, cleaned=[], failed=[])

        pods = self.k8s.v1.list_pod_for_all_namespaces()
        evicted = [
            p for p in pods.items if p.status.phase == "Failed" and p.status.reason == "Evicted"
        ]

        for pod in evicted:
            ref = f"{pod.metadata.namespace}/{pod.metadata.name}"
            if self._skip_disallowed_namespace(results, pod.metadata.namespace, f"pod/{ref}"):
                continue

            if dry_run:
                results["cleaned"].append(f"[DRY-RUN] would delete evicted pod {ref}")
                self._record_operation(
                    results,
                    dry_run=dry_run,
                    action="delete_evicted_pod",
                    resource=f"pod/{ref}",
                    api_call="CoreV1Api.delete_namespaced_pod",
                    kubectl_equivalent=f"kubectl delete pod {pod.metadata.name} -n {pod.metadata.namespace}",
                    change={"reason": "pod status reason is Evicted"},
                )
                continue
            try:
                self.k8s.v1.delete_namespaced_pod(pod.metadata.name, pod.metadata.namespace)
                results["cleaned"].append(ref)
                self._record_operation(
                    results,
                    dry_run=dry_run,
                    action="delete_evicted_pod",
                    resource=f"pod/{ref}",
                    api_call="CoreV1Api.delete_namespaced_pod",
                    kubectl_equivalent=f"kubectl delete pod {pod.metadata.name} -n {pod.metadata.namespace}",
                    change={"reason": "pod status reason is Evicted"},
                )
            except ApiException as e:
                err = self._categorize_api_exception(e)
                results["failed"].append({ref: err})
                self._record_operation(
                    results,
                    dry_run=dry_run,
                    status="failed",
                    action="delete_evicted_pod",
                    resource=f"pod/{ref}",
                    api_call="CoreV1Api.delete_namespaced_pod",
                    kubectl_equivalent=f"kubectl delete pod {pod.metadata.name} -n {pod.metadata.namespace}",
                    error=err,
                )

        return results

    async def fix_dns_issues(self, dry_run: bool = False) -> Dict:
        """Restart unhealthy CoreDNS pods."""
        results: Dict = self._new_results(
            dry_run,
            action="none",
            restarted=[],
            status="ok",
        )

        dns_pods = self.k8s.v1.list_namespaced_pod(
            "kube-system", label_selector="k8s-app=kube-dns"
        )
        unhealthy = [
            p for p in dns_pods.items if p.status.phase != "Running" or not self._pod_ready(p)
        ]

        if not unhealthy:
            return results

        results["action"] = "restart_coredns"
        if not self._namespace_allowed("kube-system"):
            for pod in unhealthy:
                ref = f"kube-system/{pod.metadata.name}"
                self._skip_disallowed_namespace(results, "kube-system", f"pod/{ref}")
            results["status"] = "skipped"
            return results

        for pod in unhealthy:
            ref = pod.metadata.name
            if dry_run:
                results["restarted"].append(f"[DRY-RUN] would restart CoreDNS pod {ref}")
                self._record_operation(
                    results,
                    dry_run=dry_run,
                    action="restart_coredns_pod",
                    resource=f"pod/kube-system/{ref}",
                    api_call="CoreV1Api.delete_namespaced_pod",
                    kubectl_equivalent=f"kubectl delete pod {ref} -n kube-system",
                    change={"reason": "CoreDNS pod is not running or not ready"},
                )
                continue
            try:
                self.k8s.v1.delete_namespaced_pod(ref, "kube-system")
                results["restarted"].append(ref)
                self._record_operation(
                    results,
                    dry_run=dry_run,
                    action="restart_coredns_pod",
                    resource=f"pod/kube-system/{ref}",
                    api_call="CoreV1Api.delete_namespaced_pod",
                    kubectl_equivalent=f"kubectl delete pod {ref} -n kube-system",
                    change={"reason": "CoreDNS pod is not running or not ready"},
                )
            except ApiException as e:
                err = self._categorize_api_exception(e)
                results["status"] = f"error: {err['category']} (HTTP {err['http_status']})"
                self._record_operation(
                    results,
                    dry_run=dry_run,
                    status="failed",
                    action="restart_coredns_pod",
                    resource=f"pod/kube-system/{ref}",
                    api_call="CoreV1Api.delete_namespaced_pod",
                    kubectl_equivalent=f"kubectl delete pod {ref} -n kube-system",
                    error=str(e),
                )

        return results

    async def fix_image_pull_errors(self, dry_run: bool = False) -> Dict:
        """Patch known safe image replacements for bundled practice scenarios."""
        results: Dict = self._new_results(dry_run, patched=[], skipped=[], failed=[])
        pods = self.k8s.v1.list_pod_for_all_namespaces().items

        for pod in pods:
            if not self._namespace_allowed(pod.metadata.namespace):
                continue

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
                ref = f"{deployment.metadata.namespace}/{deployment.metadata.name}"
                kubectl_cmd = (
                    f"kubectl set image deployment/{deployment.metadata.name} "
                    f"{container.name}={replacement} -n {deployment.metadata.namespace}"
                )
                if dry_run:
                    results["patched"].append(
                        f"[DRY-RUN] would patch image on {deployment.metadata.namespace}/{deployment.metadata.name}: {current} -> {replacement}"
                    )
                    self._record_operation(
                        results,
                        dry_run=dry_run,
                        action="patch_deployment_image",
                        resource=f"deployment/{ref}",
                        api_call="AppsV1Api.patch_namespaced_deployment",
                        kubectl_equivalent=kubectl_cmd,
                        change={
                            "field": f"spec.template.spec.containers[{container.name}].image",
                            "from": current,
                            "to": replacement,
                        },
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
                    container_name = next(
                        container.name for container, old, new in changes
                        if old == current and new == replacement
                    )
                    results["patched"].append(
                        f"{deployment.metadata.namespace}/{deployment.metadata.name}: {current} -> {replacement}"
                    )
                    self._record_operation(
                        results,
                        dry_run=dry_run,
                        action="patch_deployment_image",
                        resource=f"deployment/{deployment.metadata.namespace}/{deployment.metadata.name}",
                        api_call="AppsV1Api.patch_namespaced_deployment",
                        kubectl_equivalent=(
                            f"kubectl set image deployment/{deployment.metadata.name} "
                            f"{container_name}={replacement} -n {deployment.metadata.namespace}"
                        ),
                        change={
                            "field": f"spec.template.spec.containers[{container_name}].image",
                            "from": current,
                            "to": replacement,
                        },
                    )
            except ApiException as e:
                results["failed"].append(
                    f"{deployment.metadata.namespace}/{deployment.metadata.name}: {str(e)}"
                )
                for container, current, replacement in changes:
                    self._record_operation(
                        results,
                        dry_run=dry_run,
                        status="failed",
                        action="patch_deployment_image",
                        resource=f"deployment/{deployment.metadata.namespace}/{deployment.metadata.name}",
                        api_call="AppsV1Api.patch_namespaced_deployment",
                        kubectl_equivalent=(
                            f"kubectl set image deployment/{deployment.metadata.name} "
                            f"{container.name}={replacement} -n {deployment.metadata.namespace}"
                        ),
                        change={
                            "field": f"spec.template.spec.containers[{container.name}].image",
                            "from": current,
                            "to": replacement,
                        },
                        error=str(e),
                    )

        return results

    async def fix_service_selector_mismatches(self, dry_run: bool = False) -> Dict:
        """Patch Services with empty endpoints to match their same-name Deployment selector."""
        results: Dict = self._new_results(dry_run, patched=[], skipped=[], failed=[])
        services = self.k8s.v1.list_service_for_all_namespaces().items
        endpoints = {
            (ep.metadata.namespace, ep.metadata.name): ep
            for ep in self.k8s.v1.list_endpoints_for_all_namespaces().items
        }

        for svc in services:
            if not self._namespace_allowed(svc.metadata.namespace):
                continue

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
                self._record_operation(
                    results,
                    dry_run=dry_run,
                    action="patch_service_selector",
                    resource=f"service/{svc.metadata.namespace}/{svc.metadata.name}",
                    api_call="CoreV1Api.patch_namespaced_service",
                    kubectl_equivalent=(
                        f"kubectl patch service {svc.metadata.name} -n {svc.metadata.namespace} "
                        f"--type=merge -p '{self._json_arg({'spec': {'selector': expected}})}'"
                    ),
                    change={"field": "spec.selector", "from": current, "to": expected},
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
                self._record_operation(
                    results,
                    dry_run=dry_run,
                    action="patch_service_selector",
                    resource=f"service/{svc.metadata.namespace}/{svc.metadata.name}",
                    api_call="CoreV1Api.patch_namespaced_service",
                    kubectl_equivalent=(
                        f"kubectl patch service {svc.metadata.name} -n {svc.metadata.namespace} "
                        f"--type=merge -p '{self._json_arg({'spec': {'selector': expected}})}'"
                    ),
                    change={"field": "spec.selector", "from": current, "to": expected},
                )
            except ApiException as e:
                results["failed"].append(f"{svc.metadata.namespace}/{svc.metadata.name}: {str(e)}")
                self._record_operation(
                    results,
                    dry_run=dry_run,
                    status="failed",
                    action="patch_service_selector",
                    resource=f"service/{svc.metadata.namespace}/{svc.metadata.name}",
                    api_call="CoreV1Api.patch_namespaced_service",
                    kubectl_equivalent=(
                        f"kubectl patch service {svc.metadata.name} -n {svc.metadata.namespace} "
                        f"--type=merge -p '{self._json_arg({'spec': {'selector': expected}})}'"
                    ),
                    change={"field": "spec.selector", "from": current, "to": expected},
                    error=str(e),
                )

        return results

    async def fix_configmap_key_mismatches(self, dry_run: bool = False) -> Dict:
        """Add missing ConfigMap keys when a close or single source key exists."""
        results: Dict = self._new_results(dry_run, patched=[], skipped=[], failed=[])
        pods = self.k8s.v1.list_pod_for_all_namespaces().items

        for pod in pods:
            if not self._namespace_allowed(pod.metadata.namespace):
                continue

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
                        self._record_operation(
                            results,
                            dry_run=dry_run,
                            action="patch_configmap_key",
                            resource=f"configmap/{pod.metadata.namespace}/{ref.name}",
                            api_call="CoreV1Api.patch_namespaced_config_map",
                            kubectl_equivalent=(
                                f"kubectl patch configmap {ref.name} -n {pod.metadata.namespace} "
                                f"--type=merge -p '{self._json_arg({'data': {ref.key: '<copied from ' + source_key + '>'}})}'"
                            ),
                            change={
                                "field": f"data.{ref.key}",
                                "from": None,
                                "to": f"<copied from {source_key}>",
                                "value_source_key": source_key,
                            },
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
                        self._record_operation(
                            results,
                            dry_run=dry_run,
                            action="patch_configmap_key",
                            resource=f"configmap/{pod.metadata.namespace}/{ref.name}",
                            api_call="CoreV1Api.patch_namespaced_config_map",
                            kubectl_equivalent=(
                                f"kubectl patch configmap {ref.name} -n {pod.metadata.namespace} "
                                f"--type=merge -p '{self._json_arg({'data': {ref.key: '<copied from ' + source_key + '>'}})}'"
                            ),
                            change={
                                "field": f"data.{ref.key}",
                                "from": None,
                                "to": f"<copied from {source_key}>",
                                "value_source_key": source_key,
                            },
                        )
                    except ApiException as e:
                        results["failed"].append(
                            f"{pod.metadata.namespace}/{ref.name}: {str(e)}"
                        )
                        self._record_operation(
                            results,
                            dry_run=dry_run,
                            status="failed",
                            action="patch_configmap_key",
                            resource=f"configmap/{pod.metadata.namespace}/{ref.name}",
                            api_call="CoreV1Api.patch_namespaced_config_map",
                            kubectl_equivalent=(
                                f"kubectl patch configmap {ref.name} -n {pod.metadata.namespace} "
                                f"--type=merge -p '{self._json_arg({'data': {ref.key: '<copied from ' + source_key + '>'}})}'"
                            ),
                            change={
                                "field": f"data.{ref.key}",
                                "from": None,
                                "to": f"<copied from {source_key}>",
                                "value_source_key": source_key,
                            },
                            error=str(e),
                        )

        return results

    async def fix_ingress_backends(self, dry_run: bool = False) -> Dict:
        """Patch ingresses that reference a missing backend service when a safe replacement is inferable."""
        results: Dict = self._new_results(dry_run, patched=[], skipped=[], failed=[])
        ingresses = self.k8s.networking_v1.list_ingress_for_all_namespaces().items

        for ingress in ingresses:
            if not self._namespace_allowed(ingress.metadata.namespace):
                continue

            services = self.k8s.v1.list_namespaced_service(ingress.metadata.namespace).items
            service_names = {svc.metadata.name for svc in services}
            modified = False
            pending_operations = []

            for rule_index, rule in enumerate(ingress.spec.rules or []):
                http = getattr(rule, "http", None)
                if not http:
                    continue
                for path_index, path in enumerate(http.paths or []):
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
                        patch = [{
                            "op": "replace",
                            "path": f"/spec/rules/{rule_index}/http/paths/{path_index}/backend/service/name",
                            "value": replacement,
                        }]
                        self._record_operation(
                            results,
                            dry_run=dry_run,
                            action="patch_ingress_backend_service",
                            resource=f"ingress/{ingress.metadata.namespace}/{ingress.metadata.name}",
                            api_call="NetworkingV1Api.patch_namespaced_ingress",
                            kubectl_equivalent=(
                                f"kubectl patch ingress {ingress.metadata.name} -n {ingress.metadata.namespace} "
                                f"--type=json -p '{self._json_arg(patch)}'"
                            ),
                            change={
                                "field": f"spec.rules[{rule_index}].http.paths[{path_index}].backend.service.name",
                                "from": service_name,
                                "to": replacement,
                            },
                        )
                        modified = True
                        continue

                    path.backend.service.name = replacement
                    modified = True
                    pending_operations.append((rule_index, path_index, service_name, replacement))

            if modified and not dry_run:
                try:
                    self.k8s.networking_v1.patch_namespaced_ingress(
                        ingress.metadata.name,
                        ingress.metadata.namespace,
                        ingress,
                    )
                    for rule_index, path_index, service_name, replacement in pending_operations:
                        results["patched"].append(
                            f"{ingress.metadata.namespace}/{ingress.metadata.name}: {service_name} -> {replacement}"
                        )
                        patch = [{
                            "op": "replace",
                            "path": f"/spec/rules/{rule_index}/http/paths/{path_index}/backend/service/name",
                            "value": replacement,
                        }]
                        self._record_operation(
                            results,
                            dry_run=dry_run,
                            action="patch_ingress_backend_service",
                            resource=f"ingress/{ingress.metadata.namespace}/{ingress.metadata.name}",
                            api_call="NetworkingV1Api.patch_namespaced_ingress",
                            kubectl_equivalent=(
                                f"kubectl patch ingress {ingress.metadata.name} -n {ingress.metadata.namespace} "
                                f"--type=json -p '{self._json_arg(patch)}'"
                            ),
                            change={
                                "field": f"spec.rules[{rule_index}].http.paths[{path_index}].backend.service.name",
                                "from": service_name,
                                "to": replacement,
                            },
                        )
                except ApiException as e:
                    results["failed"].append(
                        f"{ingress.metadata.namespace}/{ingress.metadata.name}: {str(e)}"
                    )
                    for rule_index, path_index, service_name, replacement in pending_operations:
                        patch = [{
                            "op": "replace",
                            "path": f"/spec/rules/{rule_index}/http/paths/{path_index}/backend/service/name",
                            "value": replacement,
                        }]
                        self._record_operation(
                            results,
                            dry_run=dry_run,
                            status="failed",
                            action="patch_ingress_backend_service",
                            resource=f"ingress/{ingress.metadata.namespace}/{ingress.metadata.name}",
                            api_call="NetworkingV1Api.patch_namespaced_ingress",
                            kubectl_equivalent=(
                                f"kubectl patch ingress {ingress.metadata.name} -n {ingress.metadata.namespace} "
                                f"--type=json -p '{self._json_arg(patch)}'"
                            ),
                            change={
                                "field": f"spec.rules[{rule_index}].http.paths[{path_index}].backend.service.name",
                                "from": service_name,
                                "to": replacement,
                            },
                            error=str(e),
                        )

        return results

    async def fix_aggressive_liveness_probes(self, dry_run: bool = False) -> Dict:
        """Increase liveness probe initial delay for restarting workloads with liveness failures."""
        results: Dict = self._new_results(dry_run, patched=[], skipped=[], failed=[])
        pods = self.k8s.v1.list_pod_for_all_namespaces().items

        for pod in pods:
            if not self._namespace_allowed(pod.metadata.namespace):
                continue
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
            for container_index, container in enumerate(deployment.spec.template.spec.containers or []):
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
                    patch = [{
                        "op": "replace",
                        "path": f"/spec/template/spec/containers/{container_index}/livenessProbe/initialDelaySeconds",
                        "value": target_delay,
                    }]
                    self._record_operation(
                        results,
                        dry_run=dry_run,
                        action="patch_liveness_probe_delay",
                        resource=f"deployment/{deployment.metadata.namespace}/{deployment.metadata.name}",
                        api_call="AppsV1Api.patch_namespaced_deployment",
                        kubectl_equivalent=(
                            f"kubectl patch deployment {deployment.metadata.name} -n {deployment.metadata.namespace} "
                            f"--type=json -p '{self._json_arg(patch)}'"
                        ),
                        change={
                            "field": f"spec.template.spec.containers[{container.name}].livenessProbe.initialDelaySeconds",
                            "from": initial_delay,
                            "to": target_delay,
                        },
                    )
                else:
                    probe.initial_delay_seconds = target_delay
                changed.append((container_index, container.name, initial_delay, target_delay))

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
                for container_index, container_name, initial_delay, target_delay in changed:
                    results["patched"].append(
                        f"{deployment.metadata.namespace}/{deployment.metadata.name}: livenessProbe.initialDelaySeconds {initial_delay} -> {target_delay}"
                    )
                    patch = [{
                        "op": "replace",
                        "path": f"/spec/template/spec/containers/{container_index}/livenessProbe/initialDelaySeconds",
                        "value": target_delay,
                    }]
                    self._record_operation(
                        results,
                        dry_run=dry_run,
                        action="patch_liveness_probe_delay",
                        resource=f"deployment/{deployment.metadata.namespace}/{deployment.metadata.name}",
                        api_call="AppsV1Api.patch_namespaced_deployment",
                        kubectl_equivalent=(
                            f"kubectl patch deployment {deployment.metadata.name} -n {deployment.metadata.namespace} "
                            f"--type=json -p '{self._json_arg(patch)}'"
                        ),
                        change={
                            "field": f"spec.template.spec.containers[{container_name}].livenessProbe.initialDelaySeconds",
                            "from": initial_delay,
                            "to": target_delay,
                        },
                    )
            except ApiException as e:
                results["failed"].append(
                    f"{deployment.metadata.namespace}/{deployment.metadata.name}: {str(e)}"
                )
                for container_index, container_name, initial_delay, target_delay in changed:
                    patch = [{
                        "op": "replace",
                        "path": f"/spec/template/spec/containers/{container_index}/livenessProbe/initialDelaySeconds",
                        "value": target_delay,
                    }]
                    self._record_operation(
                        results,
                        dry_run=dry_run,
                        status="failed",
                        action="patch_liveness_probe_delay",
                        resource=f"deployment/{deployment.metadata.namespace}/{deployment.metadata.name}",
                        api_call="AppsV1Api.patch_namespaced_deployment",
                        kubectl_equivalent=(
                            f"kubectl patch deployment {deployment.metadata.name} -n {deployment.metadata.namespace} "
                            f"--type=json -p '{self._json_arg(patch)}'"
                        ),
                        change={
                            "field": f"spec.template.spec.containers[{container_name}].livenessProbe.initialDelaySeconds",
                            "from": initial_delay,
                            "to": target_delay,
                        },
                        error=str(e),
                    )

        return results

    async def restart_unhealthy_gitops_controllers(self, dry_run: bool = False) -> Dict:
        """Restart unhealthy Argo CD / Flux controller pods when a controller will recreate them."""
        results: Dict = self._new_results(
            dry_run,
            action="none",
            restarted=[],
            skipped=[],
            failed=[],
            status="ok",
        )
        pods = self.k8s.v1.list_pod_for_all_namespaces().items
        candidates = []

        for pod in pods:
            if not self._namespace_allowed(pod.metadata.namespace):
                continue

            if pod.metadata.namespace not in ("argocd", "flux-system"):
                continue
            if pod.metadata.deletion_timestamp:
                continue
            if pod.status.phase == "Succeeded":
                continue
            if pod.status.phase == "Running" and self._pod_ready(pod):
                continue
            candidates.append(pod)

        if not candidates:
            return results

        results["action"] = "restart_gitops_controller_pods"
        for pod in candidates:
            ref = f"{pod.metadata.namespace}/{pod.metadata.name}"
            reason = self._pod_waiting_reason(pod) or f"phase={pod.status.phase}, ready={self._pod_ready(pod)}"

            if not self._has_controller(pod):
                results["skipped"].append(f"{ref} (no controller owner — manual intervention required)")
                self._record_operation(
                    results,
                    dry_run=dry_run,
                    status="skipped",
                    action="restart_gitops_controller_pod",
                    resource=f"pod/{ref}",
                    api_call="CoreV1Api.delete_namespaced_pod",
                    kubectl_equivalent=f"kubectl delete pod {pod.metadata.name} -n {pod.metadata.namespace}",
                    change={"reason": f"{reason}; pod has no ownerReferences"},
                )
                continue

            if dry_run:
                results["restarted"].append(f"[DRY-RUN] would delete pod {ref}")
                self._record_operation(
                    results,
                    dry_run=dry_run,
                    action="restart_gitops_controller_pod",
                    resource=f"pod/{ref}",
                    api_call="CoreV1Api.delete_namespaced_pod",
                    kubectl_equivalent=f"kubectl delete pod {pod.metadata.name} -n {pod.metadata.namespace}",
                    change={"reason": reason},
                )
                continue

            try:
                self.k8s.v1.delete_namespaced_pod(pod.metadata.name, pod.metadata.namespace)
                results["restarted"].append(ref)
                self._record_operation(
                    results,
                    dry_run=dry_run,
                    action="restart_gitops_controller_pod",
                    resource=f"pod/{ref}",
                    api_call="CoreV1Api.delete_namespaced_pod",
                    kubectl_equivalent=f"kubectl delete pod {pod.metadata.name} -n {pod.metadata.namespace}",
                    change={"reason": reason},
                )
            except ApiException as e:
                results["failed"].append(f"{ref}: {str(e)}")
                results["status"] = "error"
                self._record_operation(
                    results,
                    dry_run=dry_run,
                    status="failed",
                    action="restart_gitops_controller_pod",
                    resource=f"pod/{ref}",
                    api_call="CoreV1Api.delete_namespaced_pod",
                    kubectl_equivalent=f"kubectl delete pod {pod.metadata.name} -n {pod.metadata.namespace}",
                    change={"reason": reason},
                    error=str(e),
                )

        return results

    async def scale_resources(
        self, namespace: str, deployment: str, replicas: int, dry_run: bool = False
    ) -> Dict:
        """Scale a deployment to the specified replica count."""
        if not self._namespace_allowed(namespace):
            return {
                "dry_run": dry_run,
                "deployment": f"{namespace}/{deployment}",
                "status": "skipped",
                "error": f"namespace '{namespace}' is outside the remediation allowlist",
                "allowed_namespaces": sorted(self.allowed_namespaces or []),
            }

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
            return {"error": self._categorize_api_exception(e)}

    async def apply_resource_limits(
        self,
        namespace: str,
        deployment: str,
        cpu_limit: str,
        memory_limit: str,
        dry_run: bool = False,
    ) -> Dict:
        """Set CPU and memory limits on all containers in a deployment."""
        if not self._namespace_allowed(namespace):
            return {
                "dry_run": dry_run,
                "deployment": f"{namespace}/{deployment}",
                "status": "skipped",
                "error": f"namespace '{namespace}' is outside the remediation allowlist",
                "allowed_namespaces": sorted(self.allowed_namespaces or []),
            }

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
            return {"error": self._categorize_api_exception(e)}

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
            elif issue["type"] == "gitops_controller_unhealthy":
                result = await self.restart_unhealthy_gitops_controllers(dry_run=dry_run)
                actions.append({"issue": "gitops_controller_unhealthy", "result": result})

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
        if pod.metadata.deletion_timestamp:
            return False
        if pod.spec and pod.spec.priority_class_name in ("system-cluster-critical", "system-node-critical"):
            return False
        owner_kinds = {owner.kind for owner in (pod.metadata.owner_references or [])}
        if "StatefulSet" in owner_kinds:
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

    # ── ApiException helpers ────────────────────────────────────────────────

    @staticmethod
    def _categorize_api_exception(e: ApiException) -> Dict:
        """Return a structured error dict from an ApiException with actionable guidance.

        HTTP status semantics:
          403  Forbidden       — RBAC missing; check ClusterRole / ServiceAccount
          404  Not Found       — resource was deleted between list and delete/patch
          409  Conflict        — optimistic concurrency; re-read and retry
          422  Unprocessable   — invalid patch payload; logic bug
          429  Too Many Reqs   — API server rate-limit; back off and retry
          500  Internal Error  — transient API server failure; retry after brief pause
          503  Unavailable     — API server overloaded; retry
        """
        status = getattr(e, "status", None)
        body = getattr(e, "body", str(e))

        if status == 403:
            category = "forbidden"
            hint = "Check ClusterRole/ClusterRoleBinding for the service account running this tool."
        elif status == 404:
            category = "not_found"
            hint = "Resource no longer exists — it may have been deleted by another actor."
        elif status == 409:
            category = "conflict"
            hint = "Optimistic concurrency conflict — re-read the resource and retry the patch."
        elif status == 422:
            category = "invalid_patch"
            hint = "Patch payload was rejected by the API server — check field names and types."
        elif status in (429, 503):
            category = "rate_limited_or_unavailable"
            hint = "API server is rate-limiting or temporarily unavailable — retry after a pause."
        elif status and status >= 500:
            category = "server_error"
            hint = "Transient API server error — retry after a brief pause."
        else:
            category = "unknown"
            hint = "Inspect the error body for details."

        return {
            "http_status": status,
            "category": category,
            "hint": hint,
            "detail": body if isinstance(body, str) else json.dumps(body),
        }

    def _pdb_would_be_violated(self, pod) -> Optional[str]:
        """Return a human-readable reason string if deleting this pod would violate a PDB.

        Returns None if it is safe to delete the pod (no matching PDB, or disruption budget
        has remaining capacity).  Returns a non-empty string with the violation reason if
        the deletion should be skipped to protect availability.
        """
        namespace = pod.metadata.namespace
        pod_labels = pod.metadata.labels or {}

        try:
            pdbs = self.k8s.policy_v1.list_namespaced_pod_disruption_budget(namespace).items
        except ApiException:
            # If we can't read PDBs (e.g. old cluster without the API), allow the deletion.
            return None
        except AttributeError:
            # k8s client doesn't expose policy_v1 — skip PDB check gracefully.
            return None

        for pdb in pdbs:
            selector = (pdb.spec.selector or {})
            match_labels = getattr(selector, "match_labels", None) or {}
            if not match_labels:
                continue
            # Does the pod's label set satisfy the PDB selector?
            if not all(pod_labels.get(k) == v for k, v in match_labels.items()):
                continue

            # Pod matches this PDB — check disruption budget.
            status = pdb.status
            disruptions_allowed = getattr(status, "disruptions_allowed", None)
            if disruptions_allowed is not None and disruptions_allowed < 1:
                pdb_name = pdb.metadata.name
                min_available = getattr(pdb.spec, "min_available", None)
                max_unavailable = getattr(pdb.spec, "max_unavailable", None)
                return (
                    f"PDB '{namespace}/{pdb_name}' allows 0 disruptions "
                    f"(minAvailable={min_available}, maxUnavailable={max_unavailable}); "
                    "skipping to protect availability"
                )

        return None
