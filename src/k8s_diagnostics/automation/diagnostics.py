from typing import Dict, List, Optional
from datetime import datetime
from kubernetes.client import V1Pod
from kubernetes.client.rest import ApiException

try:
    from ..analysis.pattern_matcher import match_events, match_log_lines, format_match
    _PM_AVAILABLE = True
except Exception:
    _PM_AVAILABLE = False

# Gap 1: Exit code → (layer, root cause, suggested action)
EXIT_CODE_MAP: Dict[int, tuple] = {
    0:   ("layer1", "Clean exit — process completed successfully",
          "Verify this should not be a Job/CronJob rather than a Deployment"),
    1:   ("layer1", "Application error",
          "Read logs: kubectl logs <pod> --previous"),
    2:   ("layer1", "Shell misuse or missing argument",
          "Check command/args in pod spec"),
    126: ("layer1", "Command found but not executable",
          "Verify file permissions inside the container image"),
    127: ("layer1", "Command not found — bad entrypoint or missing binary",
          "Fix 'command:' in pod spec; verify binary exists in image with: kubectl run debug --image=<image> -- which <binary>"),
    128: ("layer1", "Invalid exit argument",
          "Check application startup script"),
    130: ("layer1", "SIGINT — container interrupted",
          "Check for keyboard interrupt or external signal sent to process"),
    137: ("layer2", "SIGKILL — OOMKilled by kernel (exit 128+9)",
          "Raise memory limits or profile memory usage; check: kubectl describe pod <pod> | grep -A3 'Last State'"),
    139: ("layer2", "Segmentation fault (SIGSEGV — exit 128+11)",
          "Check for memory corruption in application; review recent image changes"),
    143: ("layer1", "SIGTERM — process terminated (exit 128+15)",
          "Liveness probe may be firing too early; increase initialDelaySeconds or fix probe path"),
    255: ("layer1", "Exit code 255 — generic unhandled error",
          "Check application logs; may indicate SSH or network failure inside container"),
}


class DiagnosticsEngine:
    def __init__(self, k8s_client):
        self.k8s = k8s_client

    # ─────────────────────────────────────────────────────────────
    # Public: Pod diagnosis (exit codes + probes + scheduling)
    # ─────────────────────────────────────────────────────────────

    async def diagnose_pod(self, namespace: str, pod_name: str) -> Dict:
        """Comprehensive pod diagnostics including exit code, probe, and scheduling analysis."""
        try:
            pod = self.k8s.v1.read_namespaced_pod(pod_name, namespace)

            raw_events = self.k8s.v1.list_namespaced_event(namespace)
            pod_event_objs = [e for e in raw_events.items if e.involved_object.name == pod_name]

            diagnosis = {
                "pod_info": {
                    "name": pod.metadata.name,
                    "namespace": pod.metadata.namespace,
                    "phase": pod.status.phase,
                    "node": pod.spec.node_name,
                    "created": str(pod.metadata.creation_timestamp),
                },
                "containers": self._analyze_containers(pod),
                "exit_code_analysis": self._analyze_exit_codes(pod),
                "probe_analysis": self._analyze_probes(pod),
                "scheduling_analysis": (
                    self._analyze_scheduling(pod) if pod.status.phase == "Pending" else None
                ),
                "resources": self._check_resources(pod),
                "events": sorted(
                    [
                        {"type": e.type, "reason": e.reason,
                         "message": e.message, "time": str(e.last_timestamp)}
                        for e in pod_event_objs
                    ],
                    key=lambda x: x["time"], reverse=True
                )[:10],
                "issues": self._detect_pod_issues(pod),
                "pattern_analysis": self._pattern_analyse_pod(pod, pod_event_objs, namespace),
            }
            return diagnosis
        except Exception as e:
            return {"error": str(e)}

    # ─────────────────────────────────────────────────────────────
    # Gap 1: Exit code interpretation
    # ─────────────────────────────────────────────────────────────

    def _analyze_exit_codes(self, pod) -> List[Dict]:
        """Map each container's last exit code to a root cause and suggested action."""
        results = []
        for cs in pod.status.container_statuses or []:
            if not cs.last_state or not cs.last_state.terminated:
                continue
            term = cs.last_state.terminated
            exit_code = term.exit_code
            layer, cause, action = EXIT_CODE_MAP.get(
                exit_code,
                ("layer1", f"Unknown exit code {exit_code}", "Check application logs for context"),
            )
            results.append({
                "container": cs.name,
                "exit_code": exit_code,
                "layer": layer,
                "cause": cause,
                "suggested_action": action,
                "reason": term.reason or "unknown",
                "finished_at": str(term.finished_at),
            })
        return results

    # ─────────────────────────────────────────────────────────────
    # Gap 3: Probe failure analysis
    # ─────────────────────────────────────────────────────────────

    def _analyze_probes(self, pod) -> List[Dict]:
        """
        For containers that are Running but not Ready, inspect readiness/liveness
        probe config and surface likely misconfigurations.
        """
        results = []
        cs_by_name = {cs.name: cs for cs in (pod.status.container_statuses or [])}

        for container in pod.spec.containers:
            cs = cs_by_name.get(container.name)
            # Only analyse containers that are running but not ready
            if not cs or cs.ready:
                continue
            if not (cs.state and cs.state.running):
                continue

            container_ports = {p.container_port for p in (container.ports or [])}
            analysis: Dict = {
                "container": container.name,
                "ready": False,
                "container_ports": [
                    {"name": p.name, "port": p.container_port, "protocol": p.protocol}
                    for p in (container.ports or [])
                ],
                "readiness_probe": None,
                "liveness_probe": None,
                "issues": [],
            }

            # Readiness probe
            if container.readiness_probe:
                rp_info = self._describe_probe(container.readiness_probe)
                analysis["readiness_probe"] = rp_info
                probe_port = rp_info.get("port")
                if probe_port and container_ports and probe_port not in container_ports:
                    analysis["issues"].append(
                        f"Readiness probe port {probe_port} does not match any containerPort "
                        f"{sorted(container_ports)} — traffic will never reach the app"
                    )
                init_delay = container.readiness_probe.initial_delay_seconds or 0
                if init_delay < 5:
                    analysis["issues"].append(
                        f"readiness initialDelaySeconds={init_delay} is very low — "
                        "probe may fire before app finishes starting"
                    )
            else:
                analysis["issues"].append(
                    "No readiness probe configured — pod Ready status is unreliable"
                )

            # Liveness probe
            if container.liveness_probe:
                lp_info = self._describe_probe(container.liveness_probe)
                analysis["liveness_probe"] = lp_info
                init_delay = container.liveness_probe.initial_delay_seconds or 0
                if init_delay < 10:
                    analysis["issues"].append(
                        f"Liveness probe initialDelaySeconds={init_delay} is very low — "
                        "container may be killed before it finishes starting up"
                    )
                # Liveness probe port mismatch
                lp_port = lp_info.get("port")
                if lp_port and container_ports and lp_port not in container_ports:
                    analysis["issues"].append(
                        f"Liveness probe port {lp_port} does not match any containerPort "
                        f"{sorted(container_ports)}"
                    )

            if not analysis["issues"]:
                analysis["issues"].append(
                    "Container running but not Ready — check probe path returns 2xx and probe port is correct"
                )

            results.append(analysis)
        return results

    def _describe_probe(self, probe) -> Dict:
        """Extract structured fields from a probe object."""
        info: Dict = {
            "initial_delay_seconds": probe.initial_delay_seconds,
            "period_seconds": probe.period_seconds,
            "timeout_seconds": probe.timeout_seconds,
            "failure_threshold": probe.failure_threshold,
        }
        if probe.http_get:
            info["type"] = "httpGet"
            info["path"] = probe.http_get.path
            port = probe.http_get.port
            info["port"] = port if isinstance(port, int) else None
            info["port_name"] = port if isinstance(port, str) else None
        elif probe.tcp_socket:
            info["type"] = "tcpSocket"
            port = probe.tcp_socket.port
            info["port"] = port if isinstance(port, int) else None
            info["port_name"] = port if isinstance(port, str) else None
        elif probe.exec:
            info["type"] = "exec"
            info["command"] = probe.exec.command
        else:
            info["type"] = "grpc"
        return info

    # ─────────────────────────────────────────────────────────────
    # Gap 2: Scheduling analysis (why is this pod Pending?)
    # ─────────────────────────────────────────────────────────────

    def _analyze_scheduling(self, pod) -> Dict:
        """
        Determine why a Pending pod cannot be scheduled.
        Checks: unbound PVCs, nodeSelector mismatch, taint/toleration mismatch,
        and resource pressure (requests vs allocatable).
        Note: resource comparison is against node allocatable, not remaining capacity.
        """
        reasons = []

        try:
            nodes = self.k8s.v1.list_node().items
        except Exception as e:
            return {"error": f"Could not list nodes: {e}"}

        # Check 1: Unbound or missing PVCs
        if pod.spec.volumes:
            try:
                pvcs = {
                    p.metadata.name: p
                    for p in self.k8s.v1.list_namespaced_persistent_volume_claim(
                        pod.metadata.namespace
                    ).items
                }
            except Exception:
                pvcs = {}

            for vol in pod.spec.volumes:
                if not vol.persistent_volume_claim:
                    continue
                claim_name = vol.persistent_volume_claim.claim_name
                pvc = pvcs.get(claim_name)
                if pvc is None:
                    reasons.append({
                        "reason": "pvc_missing",
                        "detail": f"PVC '{claim_name}' does not exist in namespace '{pod.metadata.namespace}'",
                        "layer": "layer5",
                        "suggested_action": (
                            f"Create PVC '{claim_name}' or check StorageClass availability: "
                            f"kubectl get storageclass"
                        ),
                    })
                elif pvc.status.phase != "Bound":
                    reasons.append({
                        "reason": "pvc_unbound",
                        "detail": f"PVC '{claim_name}' phase='{pvc.status.phase}' (need Bound)",
                        "layer": "layer5",
                        "suggested_action": (
                            f"kubectl describe pvc {claim_name} -n {pod.metadata.namespace} "
                            "— check StorageClass provisioner and available capacity"
                        ),
                    })

        # Check 2: nodeSelector — does any node match?
        if pod.spec.node_selector:
            selector = pod.spec.node_selector
            matching = [
                n.metadata.name for n in nodes
                if n.metadata.labels and all(
                    n.metadata.labels.get(k) == v for k, v in selector.items()
                )
            ]
            if not matching:
                reasons.append({
                    "reason": "node_selector_no_match",
                    "detail": f"nodeSelector {selector} matches 0 of {len(nodes)} nodes",
                    "layer": "layer1",
                    "suggested_action": (
                        "Fix nodeSelector labels in pod spec, or label a node: "
                        + "kubectl label node <node> "
                        + " ".join(f"{k}={v}" for k, v in selector.items())
                    ),
                })

        # Check 3: Taints — can any node accept this pod?
        tolerations = pod.spec.tolerations or []
        taint_blocked: List[Dict] = []
        for node in nodes:
            for taint in (node.spec.taints or []):
                if taint.effect in ("NoSchedule", "NoExecute"):
                    if not self._pod_tolerates_taint(tolerations, taint):
                        taint_blocked.append({
                            "node": node.metadata.name,
                            "taint": f"{taint.key}={taint.value}:{taint.effect}",
                        })
                        break  # one blocking taint per node is enough

        if taint_blocked and len(taint_blocked) == len(nodes):
            reasons.append({
                "reason": "taint_no_toleration",
                "detail": f"All {len(nodes)} nodes have NoSchedule/NoExecute taints the pod does not tolerate",
                "examples": taint_blocked[:3],
                "layer": "layer1",
                "suggested_action": (
                    "Add a toleration to the pod spec matching the taint key/effect shown above"
                ),
            })

        # Check 4: Resource pressure — can any node fit the pod's requests?
        cpu_req_m = 0.0
        mem_req_bytes = 0.0
        for container in pod.spec.containers:
            if container.resources and container.resources.requests:
                reqs = container.resources.requests
                cpu_req_m += self._parse_cpu_millis(reqs.get("cpu"))
                mem_req_bytes += self._parse_memory_bytes(reqs.get("memory"))

        if cpu_req_m > 0 or mem_req_bytes > 0:
            node_summaries = []
            can_fit = False
            for node in nodes:
                alloc = node.status.allocatable or {}
                cpu_alloc_m = self._parse_cpu_millis(alloc.get("cpu"))
                mem_alloc_bytes = self._parse_memory_bytes(alloc.get("memory"))
                fits = (cpu_req_m <= cpu_alloc_m) and (mem_req_bytes <= mem_alloc_bytes)
                if fits:
                    can_fit = True
                node_summaries.append({
                    "node": node.metadata.name,
                    "allocatable_cpu_m": int(cpu_alloc_m),
                    "allocatable_mem_mi": int(mem_alloc_bytes / (1024 * 1024)),
                    "fits_pod_request": fits,
                })

            if not can_fit:
                reasons.append({
                    "reason": "insufficient_resources",
                    "detail": (
                        f"Pod requests cpu={int(cpu_req_m)}m "
                        f"memory={int(mem_req_bytes / (1024*1024))}Mi — "
                        "no node has enough allocatable capacity "
                        "(note: this is total allocatable, not remaining)"
                    ),
                    "nodes": node_summaries,
                    "layer": "layer1",
                    "suggested_action": (
                        "Lower resource requests, add a larger node pool, or scale out the cluster"
                    ),
                })

        if not reasons:
            reasons.append({
                "reason": "unknown",
                "detail": "No obvious scheduling blocker found by static analysis",
                "suggested_action": (
                    "Run: kubectl describe pod <pod> -n <ns> and read Events for FailedScheduling details"
                ),
            })

        return {"pending_reasons": reasons, "nodes_checked": len(nodes)}

    def _pod_tolerates_taint(self, tolerations, taint) -> bool:
        """Return True if at least one toleration matches the taint."""
        for t in tolerations:
            key_match = (not t.key) or (t.key == taint.key) or (t.operator == "Exists" and not t.key)
            if t.operator == "Exists":
                key_match = (not t.key) or (t.key == taint.key)
                value_match = True
            else:
                key_match = t.key == taint.key
                value_match = t.value == taint.value
            effect_match = (not t.effect) or (t.effect == taint.effect)
            if key_match and value_match and effect_match:
                return True
        return False

    def _parse_cpu_millis(self, qty) -> float:
        """Parse a Kubernetes CPU quantity string to millicores."""
        if not qty:
            return 0.0
        s = str(qty)
        try:
            if s.endswith("m"):
                return float(s[:-1])
            elif s.endswith("n"):          # nanocores → millicores
                return float(s[:-1]) / 1_000_000
            else:
                return float(s) * 1000    # whole cores → millicores
        except (ValueError, TypeError):
            return 0.0

    def _parse_memory_bytes(self, qty) -> float:
        """Parse a Kubernetes memory quantity string to bytes."""
        if not qty:
            return 0.0
        s = str(qty)
        suffixes = {
            "Ki": 1024, "Mi": 1024**2, "Gi": 1024**3, "Ti": 1024**4,
            "k": 1000,  "M": 1000**2,  "G": 1000**3,  "T": 1000**4,
        }
        try:
            for suffix, mult in suffixes.items():
                if s.endswith(suffix):
                    return float(s[: -len(suffix)]) * mult
            return float(s)
        except (ValueError, TypeError):
            return 0.0

    # ─────────────────────────────────────────────────────────────
    # Existing helpers (retained, minor guard additions)
    # ─────────────────────────────────────────────────────────────

    def _analyze_containers(self, pod) -> List[Dict]:
        containers = []
        for cs in pod.status.container_statuses or []:
            containers.append({
                "name": cs.name,
                "ready": cs.ready,
                "restart_count": cs.restart_count,
                "state": str(cs.state),
                "image": cs.image,
            })
        return containers

    def _check_resources(self, pod) -> Dict:
        resources: Dict = {"requests": {}, "limits": {}}
        for container in pod.spec.containers:
            if container.resources:
                if container.resources.requests:
                    resources["requests"][container.name] = dict(container.resources.requests)
                if container.resources.limits:
                    resources["limits"][container.name] = dict(container.resources.limits)
        return resources

    def _get_pod_events(self, namespace: str, pod_name: str) -> List[Dict]:
        events = self.k8s.v1.list_namespaced_event(namespace)
        pod_events = [
            {
                "type": e.type,
                "reason": e.reason,
                "message": e.message,
                "time": str(e.last_timestamp),
            }
            for e in events.items
            if e.involved_object.name == pod_name
        ]
        return sorted(pod_events, key=lambda x: x["time"], reverse=True)[:10]

    def _detect_pod_issues(self, pod) -> List[str]:
        issues = []
        if pod.status.phase == "Pending":
            issues.append("Pod stuck in Pending state — use scheduling_analysis for root cause")
        for cs in pod.status.container_statuses or []:
            if cs.restart_count > 5:
                issues.append(f"Container '{cs.name}' has high restart count: {cs.restart_count}")
            if not cs.ready:
                issues.append(f"Container '{cs.name}' is not ready")
        return issues

    def _pattern_analyse_pod(self, pod, pod_event_objs: list, namespace: str) -> List[Dict]:
        """Run the 5-layer pattern matcher against pod events and container logs.

        Returns a list of format_match() dicts, deduplicated by error_class.
        Returns [] if the pattern matcher package is not installed.
        """
        if not _PM_AVAILABLE:
            return []
        seen_classes: set = set()
        results = []

        # Match against pod events
        for pm in match_events(pod_event_objs):
            if pm.error_class not in seen_classes:
                seen_classes.add(pm.error_class)
                results.append(format_match(pm))

        # Match against live init + app container logs (last 150 lines per container).
        # Init-only failures never reach the main container, so skipping init logs
        # hides the decisive signal for Init:0/1 pods.
        container_statuses = list(pod.status.init_container_statuses or [])
        container_statuses.extend(pod.status.container_statuses or [])
        for cs in container_statuses:
            try:
                logs = self.k8s.v1.read_namespaced_pod_log(
                    pod.metadata.name, namespace,
                    container=cs.name, tail_lines=150,
                )
                for pm in match_log_lines(logs or ""):
                    if pm.error_class not in seen_classes:
                        seen_classes.add(pm.error_class)
                        results.append(format_match(pm))
            except Exception:
                pass

        return results

    # ─────────────────────────────────────────────────────────────
    # Cluster-wide detection (updated to include scheduling detail)
    # ─────────────────────────────────────────────────────────────

    async def check_network(self) -> Dict:
        return {
            "dns": await self._check_dns(),
            "services": self._check_service_endpoints(),
            "ingress": self._check_ingress_controllers(),
            "load_balancers": self._check_pending_load_balancers(),
        }

    async def _check_dns(self) -> Dict:
        pods = self.k8s.v1.list_namespaced_pod("kube-system", label_selector="k8s-app=kube-dns")
        running = sum(1 for p in pods.items if p.status.phase == "Running")
        return {
            "coredns_pods": len(pods.items),
            "running_pods": running,
            "status": "healthy" if running > 0 else "degraded",
        }

    def _check_service_endpoints(self) -> Dict:
        services = self.k8s.v1.list_service_for_all_namespaces()
        endpoints = self.k8s.v1.list_endpoints_for_all_namespaces()
        no_ep = [
            f"{svc.metadata.namespace}/{svc.metadata.name}"
            for svc in services.items
            if (ep := next(
                (e for e in endpoints.items
                 if e.metadata.name == svc.metadata.name
                 and e.metadata.namespace == svc.metadata.namespace), None
            )) and not ep.subsets
        ]
        return {"total_services": len(services.items), "services_without_endpoints": no_ep}

    def _check_ingress_controllers(self) -> Dict:
        pods = self.k8s.v1.list_pod_for_all_namespaces(
            label_selector="app.kubernetes.io/name=ingress-nginx"
        )
        return {
            "nginx_ingress_pods": len(pods.items),
            "running": sum(1 for p in pods.items if p.status.phase == "Running"),
        }

    async def detect_common_issues(self) -> Dict:
        """Auto-detect cluster issues. Pending pods now include a scheduling breakdown."""
        issues = []

        # Nodes not ready + node pressure conditions
        nodes = self.k8s.v1.list_node()
        not_ready = [
            n.metadata.name for n in nodes.items
            if not any(
                c.type == "Ready" and c.status == "True"
                for c in (n.status.conditions or [])
            )
        ]
        if not_ready:
            issues.append({
                "type": "nodes_not_ready",
                "severity": "high",
                "count": len(not_ready),
                "details": not_ready[:5],
            })

        # Check 2a: Node pressure conditions (MemoryPressure, DiskPressure, PIDPressure, NetworkUnavailable)
        node_pressure = self._check_node_pressure(nodes.items)
        if node_pressure:
            issues.append({
                "type": "node_pressure",
                "severity": "high",
                "count": len(node_pressure),
                "details": node_pressure[:5],
                "hint": "kubectl describe node <node> — check Conditions and Allocatable",
            })

        # Failed / Pending pods — with scheduling breakdown for Pending ones
        pods = self.k8s.v1.list_pod_for_all_namespaces()
        active_pods = [p for p in pods.items if not p.metadata.deletion_timestamp]
        failed_pods = [p for p in active_pods if p.status.phase == "Failed"]
        pending_pods = [p for p in active_pods if p.status.phase == "Pending"]

        if failed_pods:
            issues.append({
                "type": "failed_pods",
                "severity": "high",
                "count": len(failed_pods),
                "details": [
                    f"{p.metadata.namespace}/{p.metadata.name}" for p in failed_pods[:5]
                ],
            })

        if pending_pods:
            scheduling_details = []
            for pod in pending_pods[:5]:
                analysis = self._analyze_scheduling(pod)
                scheduling_details.append({
                    "pod": f"{pod.metadata.namespace}/{pod.metadata.name}",
                    "pending_reasons": analysis.get("pending_reasons", []),
                })
            issues.append({
                "type": "pending_pods",
                "severity": "high",
                "count": len(pending_pods),
                "scheduling_analysis": scheduling_details,
            })

        # ImagePullBackOff
        image_pull = self._find_image_pull_errors(active_pods)
        if image_pull:
            issues.append({
                "type": "image_pull_errors",
                "severity": "high",
                "count": len(image_pull),
                "details": image_pull[:5],
            })

        selector_mismatches = self._detect_service_selector_mismatches()
        if selector_mismatches:
            issues.append({
                "type": "service_selector_mismatch",
                "severity": "high",
                "count": len(selector_mismatches),
                "details": selector_mismatches[:5],
            })

        config_key_mismatches = self._detect_configmap_key_mismatches(active_pods)
        if config_key_mismatches:
            issues.append({
                "type": "configmap_key_mismatch",
                "severity": "high",
                "count": len(config_key_mismatches),
                "details": config_key_mismatches[:5],
            })

        # Pending PVCs
        pending_pvcs = self.k8s.v1.list_persistent_volume_claim_for_all_namespaces()
        stuck_pvcs = [
            f"{p.metadata.namespace}/{p.metadata.name}"
            for p in pending_pvcs.items
            if p.status.phase != "Bound"
        ]
        if stuck_pvcs:
            issues.append({
                "type": "pvc_not_bound",
                "severity": "medium",
                "count": len(stuck_pvcs),
                "details": stuck_pvcs[:5],
            })

        # CoreDNS
        dns_status = await self._check_dns()
        if dns_status.get("running_pods", 0) == 0:
            issues.append({
                "type": "dns_unhealthy",
                "severity": "high",
                "details": ["CoreDNS pods not running"],
            })

        # Pending LoadBalancers
        pending_lbs = self._check_pending_load_balancers().get("pending", [])
        if pending_lbs:
            issues.append({
                "type": "load_balancer_pending",
                "severity": "medium",
                "count": len(pending_lbs),
                "details": pending_lbs[:5],
            })

        ingress_backend_issues = self._detect_ingress_backend_missing_services()
        if ingress_backend_issues:
            issues.append({
                "type": "ingress_backend_missing_service",
                "severity": "high",
                "count": len(ingress_backend_issues),
                "details": ingress_backend_issues[:5],
            })

        # High restart counts
        high_restart = [
            f"{pod.metadata.namespace}/{pod.metadata.name}"
            for pod in active_pods
            for cs in (pod.status.container_statuses or [])
            if cs.restart_count > 10
        ]
        if high_restart:
            issues.append({
                "type": "high_restart_count",
                "severity": "medium",
                "count": len(high_restart),
                "details": high_restart[:5],
            })

        # Probe failures (running but not ready)
        probe_failures = self._find_probe_failures(active_pods)
        if probe_failures:
            issues.append({
                "type": "probe_failures",
                "severity": "medium",
                "count": len(probe_failures),
                "details": probe_failures[:5],
                "hint": "Use 'diagnose <ns> <pod>' for per-container probe analysis",
            })

        init_blockers = self._find_init_container_blockers(active_pods)
        if init_blockers:
            issues.append({
                "type": "init_containers_blocked",
                "severity": "high",
                "count": len(init_blockers),
                "details": init_blockers[:5],
                "hint": (
                    "kubectl logs <pod> -n <ns> -c <init-container>; "
                    "then check any dependency Service/endpoints the init container waits for"
                ),
            })

        aggressive_liveness = self._detect_aggressive_liveness_probes(active_pods)
        if aggressive_liveness:
            issues.append({
                "type": "aggressive_liveness_probe",
                "severity": "high",
                "count": len(aggressive_liveness),
                "details": aggressive_liveness[:5],
            })

        gitops_controller_issues = self._detect_gitops_controller_issues(active_pods)
        if gitops_controller_issues:
            issues.append({
                "type": "gitops_controller_unhealthy",
                "severity": "high",
                "count": len(gitops_controller_issues),
                "details": gitops_controller_issues[:10],
                "hint": "kubectl get pods -n argocd; kubectl get pods -n flux-system",
            })

        gitops_crd_issues = self._detect_gitops_crd_issues()
        if gitops_crd_issues:
            issues.append({
                "type": "gitops_crd_missing",
                "severity": "high",
                "count": len(gitops_crd_issues),
                "details": gitops_crd_issues[:10],
                "hint": "Reinstall the controller manifests; use server-side apply for large Argo CD CRDs.",
            })

        argocd_issues = self._detect_argocd_application_issues()
        if argocd_issues:
            issues.append({
                "type": "argocd_application_unhealthy",
                "severity": "medium",
                "count": len(argocd_issues),
                "details": argocd_issues[:10],
                "hint": "kubectl get applications -A; kubectl describe application <name> -n <ns>",
            })

        flux_issues = self._detect_flux_resource_issues()
        if flux_issues:
            issues.append({
                "type": "flux_resource_not_ready",
                "severity": "medium",
                "count": len(flux_issues),
                "details": flux_issues[:10],
                "hint": "kubectl get gitrepositories,kustomizations,helmreleases -A; describe the NotReady object.",
            })

        # Warning events cluster-wide (last 1 hour)
        active_warning_events = self._active_warning_events(active_pods)
        warning_events = self._format_warning_events(active_warning_events)
        if warning_events:
            issues.append({
                "type": "warning_events",
                "severity": "medium",
                "count": len(warning_events),
                "details": warning_events[:10],
                "hint": "kubectl get events -A --field-selector type=Warning --sort-by=.lastTimestamp",
            })

        # Control plane component health (etcd, scheduler, controller-manager)
        component_issues = self._check_component_health()
        if component_issues:
            issues.append({
                "type": "control_plane_unhealthy",
                "severity": "high",
                "count": len(component_issues),
                "details": component_issues,
                "hint": "kubectl get componentstatuses",
            })

        # CrashLoopBackOff (phase=Running but waiting.reason=CrashLoopBackOff)
        crashloop = self._find_crashloop_pods(active_pods)
        if crashloop:
            issues.append({
                "type": "crashloop_backoff",
                "severity": "high",
                "count": len(crashloop),
                "details": crashloop[:5],
                "hint": "kubectl logs <pod> --previous -n <ns> — check exit code with diagnose <ns> <pod>",
            })

        # Terminating pods stuck with finalizers
        stuck_terminating = self._find_stuck_terminating(pods.items)
        if stuck_terminating:
            issues.append({
                "type": "stuck_terminating",
                "severity": "medium",
                "count": len(stuck_terminating),
                "details": stuck_terminating[:5],
                "hint": "kubectl get pod <pod> -o yaml | grep finalizers — remove finalizer to unblock",
            })

        # Missing ConfigMaps/Secrets referenced by pods
        missing_refs = self._find_missing_config_refs(active_pods)
        if missing_refs:
            issues.append({
                "type": "missing_config_refs",
                "severity": "high",
                "count": len(missing_refs),
                "details": missing_refs[:5],
                "hint": "Create the missing ConfigMap or Secret, or remove the reference from the pod spec",
            })

        # NetworkPolicy deny-all (ingress policyType with no ingress rules)
        deny_all_ns = self._find_deny_all_networkpolicies()
        if deny_all_ns:
            issues.append({
                "type": "networkpolicy_deny_all",
                "severity": "medium",
                "count": len(deny_all_ns),
                "details": deny_all_ns[:5],
                "hint": "kubectl get networkpolicy -n <ns> -o yaml — add ingress rules or an allow policy",
            })

        # HPA not scaling (metrics unavailable or misconfigured)
        hpa_issues = self._find_hpa_issues()
        if hpa_issues:
            issues.append({
                "type": "hpa_issues",
                "severity": "medium",
                "count": len(hpa_issues),
                "details": hpa_issues[:5],
                "hint": "kubectl describe hpa -n <ns> — check if metrics-server is running and metric name is correct",
            })

        # TLS Secret certificates expiring within 7 days or already expired
        cert_issues = self._find_expiring_tls_certs()
        if cert_issues:
            issues.append({
                "type": "tls_cert_expiring",
                "severity": "high",
                "count": len(cert_issues),
                "details": cert_issues[:5],
                "hint": "Renew TLS certificates; if using cert-manager: kubectl annotate certificate <name> -n <ns> cert-manager.io/renewal-reason=manual",
            })

        # Jobs/CronJobs stuck (backoffLimit exhausted or active+complete stalled)
        job_issues = self._find_stuck_jobs()
        if job_issues:
            issues.append({
                "type": "stuck_jobs",
                "severity": "medium",
                "count": len(job_issues),
                "details": job_issues[:5],
                "hint": "kubectl describe job <name> -n <ns> — check backoffLimit, pod logs, and whether the job command exits 0",
            })

        # DaemonSet pods not scheduled on all eligible nodes
        ds_issues = self._find_daemonset_gaps()
        if ds_issues:
            issues.append({
                "type": "daemonset_not_fully_scheduled",
                "severity": "medium",
                "count": len(ds_issues),
                "details": ds_issues[:5],
                "hint": "kubectl describe ds <name> -n <ns> — check nodeSelector and tolerations; new nodes may need labels",
            })

        # Phase 2: cloud provider layer (AKS/EKS/GKE)
        try:
            from ..providers.detector import run_provider_checks
            provider_issues = run_provider_checks(self.k8s)
            # Filter out info-level SDK-unavailable or provider-unknown notices.
            # The explicit provider commands still expose those details, but the
            # general detector should stay focused on active cluster failures.
            actionable = [i for i in provider_issues if i.get("severity") != "info"]
            issues.extend(actionable)
        except Exception:
            pass  # provider layer must never crash detect_common_issues()

        # 5-layer pattern analysis on cluster Warning events
        pattern_matches: List[Dict] = []
        if _PM_AVAILABLE and active_warning_events:
            try:
                pattern_matches = [
                    format_match(pm) for pm in match_events(active_warning_events)
                ]
            except Exception:
                pass

        return {
            "issues": issues,
            "pattern_analysis": pattern_matches,
            "timestamp": datetime.now().isoformat(),
        }

    def _find_probe_failures(self, pods: List[V1Pod]) -> List[str]:
        failures = []
        for pod in pods:
            if pod.status.phase != "Running":
                continue
            for cs in (pod.status.container_statuses or []):
                if not cs.ready and cs.state and cs.state.running:
                    failures.append(
                        f"{pod.metadata.namespace}/{pod.metadata.name} (container: {cs.name})"
                    )
        return failures

    def _find_init_container_blockers(self, pods: List[V1Pod]) -> List[str]:
        blockers = []
        for pod in pods:
            init_statuses = pod.status.init_container_statuses or []
            for cs in init_statuses:
                state = getattr(cs, "state", None)
                if not state:
                    continue

                terminated = getattr(state, "terminated", None)
                if terminated:
                    exit_code = getattr(terminated, "exit_code", None)
                    if exit_code == 0:
                        continue
                    reason = f"terminated exit={exit_code}"
                elif getattr(state, "waiting", None):
                    waiting = state.waiting
                    reason = f"waiting:{getattr(waiting, 'reason', 'unknown')}"
                elif getattr(state, "running", None):
                    reason = "running"
                else:
                    reason = "not-complete"

                blockers.append(
                    f"{pod.metadata.namespace}/{pod.metadata.name} "
                    f"(init: {cs.name}, state: {reason})"
                )
                break
        return blockers

    def _detect_service_selector_mismatches(self) -> List[str]:
        issues = []
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
            except Exception:
                continue

            expected = dep.spec.selector.match_labels or {}
            current = svc.spec.selector or {}
            if expected and expected != current:
                issues.append(
                    f"{svc.metadata.namespace}/{svc.metadata.name} — selector {current} does not match deployment selector {expected}"
                )

        return issues

    def _detect_configmap_key_mismatches(self, pods: List[V1Pod]) -> List[str]:
        issues = []
        for pod in pods:
            waiting_reasons = {
                cs.state.waiting.reason
                for cs in (pod.status.container_statuses or [])
                if cs.state and cs.state.waiting and cs.state.waiting.reason
            }
            if "CreateContainerConfigError" not in waiting_reasons:
                continue

            for container in pod.spec.containers or []:
                for env in container.env or []:
                    ref = getattr(getattr(env, "value_from", None), "config_map_key_ref", None)
                    if not ref or not ref.name or not ref.key:
                        continue

                    try:
                        cm = self.k8s.v1.read_namespaced_config_map(
                            ref.name, pod.metadata.namespace
                        )
                    except Exception:
                        continue

                    data = cm.data or {}
                    if ref.key in data:
                        continue

                    issues.append(
                        f"{pod.metadata.namespace}/{pod.metadata.name} — ConfigMap {ref.name} missing key {ref.key}; available keys: {sorted(data.keys())}"
                    )

        return issues

    def _detect_ingress_backend_missing_services(self) -> List[str]:
        issues = []
        ingresses = self.k8s.networking_v1.list_ingress_for_all_namespaces().items
        services_by_ns = {}

        for ingress in ingresses:
            namespace = ingress.metadata.namespace
            if namespace not in services_by_ns:
                services_by_ns[namespace] = {
                    svc.metadata.name
                    for svc in self.k8s.v1.list_namespaced_service(namespace).items
                }

            for rule in ingress.spec.rules or []:
                http = getattr(rule, "http", None)
                if not http:
                    continue
                for path in http.paths or []:
                    backend = getattr(path, "backend", None)
                    service = getattr(backend, "service", None)
                    service_name = getattr(service, "name", None)
                    if service_name and service_name not in services_by_ns[namespace]:
                        issues.append(
                            f"{namespace}/{ingress.metadata.name} — backend service {service_name} does not exist"
                        )

        return issues

    def _detect_aggressive_liveness_probes(self, pods: List[V1Pod]) -> List[str]:
        issues = []
        for pod in pods:
            if pod.metadata.namespace in ("kube-system", "kube-public", "kube-node-lease"):
                continue

            if not any((cs.restart_count or 0) > 0 for cs in (pod.status.container_statuses or [])):
                continue

            pod_events = self._get_pod_events(pod.metadata.namespace, pod.metadata.name)
            if not any(
                event["reason"] == "Unhealthy" and "Liveness probe failed" in event["message"]
                for event in pod_events
            ):
                continue

            for container in pod.spec.containers or []:
                probe = container.liveness_probe
                if not probe:
                    continue
                initial_delay = probe.initial_delay_seconds or 0
                if initial_delay < 10:
                    issues.append(
                        f"{pod.metadata.namespace}/{pod.metadata.name} — liveness probe initialDelaySeconds={initial_delay} is too low for a restarting workload"
                    )

        return issues

    # ─────────────────────────────────────────────────────────────
    # New checks: node pressure, warning events, component health
    # ─────────────────────────────────────────────────────────────

    # Pressure condition types that indicate the node is under stress.
    # Ready=False is already handled above; these are the *additional* conditions.
    _PRESSURE_CONDITIONS = ("MemoryPressure", "DiskPressure", "PIDPressure", "NetworkUnavailable")
    _GITOPS_NAMESPACES = ("argocd", "flux-system")

    _FLUX_RESOURCE_CHECKS = (
        ("source.toolkit.fluxcd.io", ("v1", "v1beta2"), "gitrepositories", "GitRepository"),
        ("source.toolkit.fluxcd.io", ("v1", "v1beta2"), "helmrepositories", "HelmRepository"),
        ("source.toolkit.fluxcd.io", ("v1", "v1beta2"), "ocirepositories", "OCIRepository"),
        ("kustomize.toolkit.fluxcd.io", ("v1", "v1beta2"), "kustomizations", "Kustomization"),
        ("helm.toolkit.fluxcd.io", ("v2", "v2beta2", "v2beta1"), "helmreleases", "HelmRelease"),
    )

    def _check_node_pressure(self, node_items) -> List[str]:
        """Return list of '<node>: <condition>' strings for nodes under pressure."""
        pressured = []
        for node in node_items:
            for condition in (node.status.conditions or []):
                if condition.type in self._PRESSURE_CONDITIONS and condition.status == "True":
                    pressured.append(f"{node.metadata.name}: {condition.type} ({condition.message or 'no message'})")
        return pressured

    def _active_warning_events(self, active_pods: List[V1Pod] = None) -> List:
        """Return deduplicated Warning events from the last hour across all namespaces.

        Skips events with no timestamp (pre-existing, already-flushed events).
        Skips pod events when the pod no longer exists or is already fully ready.
        """
        try:
            events = self.k8s.v1.list_event_for_all_namespaces(
                field_selector="type=Warning"
            )
        except Exception:
            return []

        from datetime import timezone
        now = datetime.now(tz=timezone.utc)
        active_pod_map = {
            (pod.metadata.namespace, pod.metadata.name): pod
            for pod in (active_pods or [])
        }
        results = []
        seen = set()
        for e in events.items:
            involved = e.involved_object
            if involved.kind == "Pod":
                pod = active_pod_map.get((involved.namespace, involved.name))
                if pod is None or self._pod_is_ready(pod):
                    continue

            # Filter to last hour using last_timestamp or event_time
            ts = e.last_timestamp or e.event_time
            if ts is None:
                continue
            # Make tz-aware for comparison
            if hasattr(ts, "tzinfo") and ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            age_seconds = (now - ts).total_seconds()
            if age_seconds > 3600:
                continue
            key = f"{involved.namespace}/{involved.name}|{e.reason}"
            if key in seen:
                continue
            seen.add(key)
            results.append(e)
        return results

    def _format_warning_events(self, events: List) -> List[str]:
        """Format active Warning events as '<namespace>/<object> — <reason>: <message>'."""
        results = []
        for e in events:
            involved = e.involved_object
            ns = involved.namespace or "cluster"
            msg = (e.message or "")[:120]
            results.append(f"{ns}/{involved.name} — {e.reason}: {msg}")
        return results

    def _pod_is_ready(self, pod: V1Pod) -> bool:
        if pod.status.phase != "Running":
            return False
        statuses = pod.status.container_statuses or []
        return bool(statuses) and all(cs.ready for cs in statuses)

    def _detect_gitops_controller_issues(self, pods: List[V1Pod]) -> List[str]:
        issues = []
        for pod in pods:
            if pod.metadata.namespace not in self._GITOPS_NAMESPACES:
                continue
            if self._pod_is_ready(pod):
                continue

            waiting_reasons = []
            for cs in pod.status.container_statuses or []:
                if cs.state and cs.state.waiting and cs.state.waiting.reason:
                    waiting_reasons.append(f"{cs.name}:{cs.state.waiting.reason}")
                elif not cs.ready:
                    waiting_reasons.append(f"{cs.name}:not-ready")

            reason = ", ".join(waiting_reasons) if waiting_reasons else "pod not ready"
            issues.append(
                f"{pod.metadata.namespace}/{pod.metadata.name}: "
                f"phase={pod.status.phase}, reason={reason}"
            )
        return issues

    def _detect_gitops_crd_issues(self) -> List[str]:
        issues = []
        if self._namespace_exists("argocd") and not self._custom_resource_exists(
            "argoproj.io", "v1alpha1", "applications"
        ):
            issues.append(
                "argocd namespace exists but Application CRD is missing; "
                "reapply Argo CD with server-side apply if CRD annotations are too large"
            )

        if self._namespace_exists("flux-system") and not self._any_custom_resource_exists(
            "kustomize.toolkit.fluxcd.io", ("v1", "v1beta2"), "kustomizations"
        ):
            issues.append(
                "flux-system namespace exists but Flux Kustomization CRD is missing; "
                "reapply the Flux install manifest"
            )
        return issues

    def _detect_argocd_application_issues(self) -> List[str]:
        apps, error = self._list_cluster_custom_objects(
            "argoproj.io", "v1alpha1", "applications"
        )
        if error or not apps:
            return []

        issues = []
        for app in apps:
            status = app.get("status", {})
            sync_status = (status.get("sync") or {}).get("status")
            health_status = (status.get("health") or {}).get("status")
            conditions = status.get("conditions") or []
            ref = self._custom_object_ref(app, "Application")

            unhealthy = []
            if sync_status and sync_status != "Synced":
                unhealthy.append(f"sync={sync_status}")
            if health_status in ("Degraded", "Missing", "Unknown", "Suspended"):
                unhealthy.append(f"health={health_status}")
            for condition in conditions:
                condition_type = condition.get("type")
                message = condition.get("message") or condition.get("reason") or ""
                if condition_type:
                    unhealthy.append(f"{condition_type}: {message[:120]}")

            if unhealthy:
                issues.append(f"{ref}: {', '.join(unhealthy)}")
        return issues

    def _detect_flux_resource_issues(self) -> List[str]:
        issues = []
        for group, versions, plural, kind in self._FLUX_RESOURCE_CHECKS:
            objects = []
            for version in versions:
                items, error = self._list_cluster_custom_objects(group, version, plural)
                if error:
                    continue
                objects = items
                break

            for obj in objects:
                ready = self._ready_condition(obj)
                if not ready or ready.get("status") == "True":
                    continue
                ref = self._custom_object_ref(obj, kind)
                reason = ready.get("reason") or "not ready"
                message = (ready.get("message") or "")[:160]
                issues.append(f"{ref}: Ready={ready.get('status')} — {reason}: {message}")
        return issues

    def _list_cluster_custom_objects(self, group: str, version: str, plural: str):
        try:
            result = self.k8s.metrics.list_cluster_custom_object(group, version, plural)
            return result.get("items", []), None
        except ApiException as e:
            if e.status == 404:
                return [], e
            return [], e
        except Exception as e:
            return [], e

    def _custom_resource_exists(self, group: str, version: str, plural: str) -> bool:
        _, error = self._list_cluster_custom_objects(group, version, plural)
        if error is None:
            return True
        if isinstance(error, ApiException) and error.status == 404:
            return False
        return True

    def _any_custom_resource_exists(self, group: str, versions: tuple, plural: str) -> bool:
        return any(self._custom_resource_exists(group, version, plural) for version in versions)

    def _namespace_exists(self, namespace: str) -> bool:
        try:
            self.k8s.v1.read_namespace(namespace)
            return True
        except ApiException as e:
            if e.status == 404:
                return False
            return False
        except Exception:
            return False

    def _ready_condition(self, obj: Dict) -> Optional[Dict]:
        for condition in (obj.get("status", {}).get("conditions") or []):
            if condition.get("type") == "Ready":
                return condition
        return None

    def _custom_object_ref(self, obj: Dict, kind: str) -> str:
        metadata = obj.get("metadata", {})
        namespace = metadata.get("namespace") or "cluster"
        return f"{kind}/{namespace}/{metadata.get('name', 'unknown')}"

    def _check_component_health(self) -> List[str]:
        """Check control plane components via the ComponentStatus API.

        Returns list of unhealthy component descriptions.
        Note: ComponentStatus is deprecated in K8s 1.19+ but still works on most clusters
        including minikube. On managed clusters (AKS/EKS/GKE) the control plane
        components are not visible this way — an empty list does not mean they are healthy.
        """
        unhealthy = []
        try:
            components = self.k8s.v1.list_component_status()
            for cs in components.items:
                for condition in (cs.conditions or []):
                    if condition.type == "Healthy" and condition.status != "True":
                        unhealthy.append(
                            f"{cs.metadata.name}: {condition.message or condition.error or 'not healthy'}"
                        )
        except Exception as e:
            # ComponentStatus may be unavailable on managed clusters — not an error
            if "404" not in str(e) and "not found" not in str(e).lower():
                unhealthy.append(f"ComponentStatus API unavailable: {e}")
        return unhealthy

    # ─────────────────────────────────────────────────────────────
    # Universal gap checks (Phase 1)
    # ─────────────────────────────────────────────────────────────

    def _find_crashloop_pods(self, pods: List[V1Pod]) -> List[str]:
        """Detect CrashLoopBackOff containers.

        phase=Running pods can still have containers in waiting state with
        reason=CrashLoopBackOff — these are invisible to the failed_pods check.
        """
        result = []
        for pod in pods:
            for cs in (pod.status.container_statuses or []):
                if (cs.state and cs.state.waiting
                        and cs.state.waiting.reason == "CrashLoopBackOff"):
                    result.append(
                        f"{pod.metadata.namespace}/{pod.metadata.name} "
                        f"(container: {cs.name}, restarts: {cs.restart_count})"
                    )
        return result

    def _find_stuck_terminating(self, pods: List[V1Pod]) -> List[str]:
        """Find pods stuck in Terminating (deletion timestamp set but pod still present).

        A pod is stuck if it has been in Terminating for more than 5 minutes,
        which almost always means a finalizer is blocking deletion.
        """
        from datetime import timezone
        now = datetime.now(tz=timezone.utc)
        stuck = []
        for pod in pods:
            if not pod.metadata.deletion_timestamp:
                continue
            ts = pod.metadata.deletion_timestamp
            if hasattr(ts, "tzinfo") and ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            age_minutes = (now - ts).total_seconds() / 60
            if age_minutes > 5:
                finalizers = pod.metadata.finalizers or []
                stuck.append(
                    f"{pod.metadata.namespace}/{pod.metadata.name} "
                    f"(terminating {int(age_minutes)}m, finalizers: {finalizers or 'none'})"
                )
        return stuck

    def _find_missing_config_refs(self, pods: List[V1Pod]) -> List[str]:
        """Find pods referencing ConfigMaps or Secrets that do not exist.

        Checks env.valueFrom.configMapKeyRef, env.valueFrom.secretKeyRef,
        envFrom.configMapRef, envFrom.secretRef, and volume.configMap/secret sources.
        Only checks pods that are not Running (Pending/Init/etc.) to reduce noise.
        """
        missing = []
        # Collect all existing configmaps and secrets per namespace (lazy, per namespace)
        cm_cache: Dict[str, set] = {}
        sec_cache: Dict[str, set] = {}

        def _cms(ns: str) -> set:
            if ns not in cm_cache:
                try:
                    items = self.k8s.v1.list_namespaced_config_map(ns).items
                    cm_cache[ns] = {i.metadata.name for i in items}
                except Exception:
                    cm_cache[ns] = set()
            return cm_cache[ns]

        def _secs(ns: str) -> set:
            if ns not in sec_cache:
                try:
                    items = self.k8s.v1.list_namespaced_secret(ns).items
                    sec_cache[ns] = {i.metadata.name for i in items}
                except Exception:
                    sec_cache[ns] = set()
            return sec_cache[ns]

        for pod in pods:
            # Only check non-running pods to surface actionable issues
            if pod.status.phase == "Running":
                continue
            ns = pod.metadata.namespace
            pod_ref = f"{ns}/{pod.metadata.name}"
            found: List[str] = []

            for container in (pod.spec.containers or []) + (pod.spec.init_containers or []):
                # env valueFrom refs
                for env in (container.env or []):
                    if not env.value_from:
                        continue
                    if env.value_from.config_map_key_ref:
                        name = env.value_from.config_map_key_ref.name
                        if name and name not in _cms(ns):
                            found.append(f"ConfigMap '{name}' (env {env.name})")
                    if env.value_from.secret_key_ref:
                        name = env.value_from.secret_key_ref.name
                        optional = env.value_from.secret_key_ref.optional
                        if name and not optional and name not in _secs(ns):
                            found.append(f"Secret '{name}' (env {env.name})")
                # envFrom refs
                for ef in (container.env_from or []):
                    if ef.config_map_ref:
                        name = ef.config_map_ref.name
                        optional = ef.config_map_ref.optional
                        if name and not optional and name not in _cms(ns):
                            found.append(f"ConfigMap '{name}' (envFrom)")
                    if ef.secret_ref:
                        name = ef.secret_ref.name
                        optional = ef.secret_ref.optional
                        if name and not optional and name not in _secs(ns):
                            found.append(f"Secret '{name}' (envFrom)")

            # Volume refs
            for vol in (pod.spec.volumes or []):
                if vol.config_map and vol.config_map.name not in _cms(ns):
                    optional = vol.config_map.optional
                    if not optional:
                        found.append(f"ConfigMap '{vol.config_map.name}' (volume {vol.name})")
                if vol.secret and vol.secret.secret_name not in _secs(ns):
                    optional = vol.secret.optional
                    if not optional:
                        found.append(f"Secret '{vol.secret.secret_name}' (volume {vol.name})")

            if found:
                # Deduplicate within a pod
                deduped = list(dict.fromkeys(found))
                missing.append(f"{pod_ref}: missing {', '.join(deduped[:3])}")

        return missing

    def _find_deny_all_networkpolicies(self) -> List[str]:
        """Detect NetworkPolicies that impose a deny-all by selecting all pods
        with an Ingress policyType but providing zero ingress rules.

        This is the most common silent traffic-drop pattern:
          policyTypes: [Ingress]   # with no ingress: [] block
        """
        deny_all = []
        try:
            policies = self.k8s.networking_v1.list_network_policy_for_all_namespaces()
        except Exception:
            return []

        for np in policies.items:
            spec = np.spec
            if not spec:
                continue
            policy_types = spec.policy_types or []
            if "Ingress" not in policy_types:
                continue
            # An empty ingress list (or absent ingress key) with Ingress policyType = deny all
            if not spec.ingress:
                deny_all.append(
                    f"{np.metadata.namespace}/{np.metadata.name} "
                    f"(podSelector: {spec.pod_selector.match_labels or 'all pods'})"
                )
        return deny_all

    def _find_hpa_issues(self) -> List[str]:
        """Detect HPAs that are unable to scale.

        Looks for HPAs where currentReplicas == desiredReplicas == maxReplicas
        (maxed out and stuck), or where conditions indicate ScalingActive=False
        (metrics unavailable or metric name wrong).
        """
        issues = []
        try:
            hpas = self.k8s.autoscaling_v2.list_horizontal_pod_autoscaler_for_all_namespaces()
        except Exception:
            try:
                hpas = self.k8s.autoscaling_v1.list_horizontal_pod_autoscaler_for_all_namespaces()
            except Exception:
                return []

        for hpa in hpas.items:
            ref = f"{hpa.metadata.namespace}/{hpa.metadata.name}"
            status = hpa.status
            if not status:
                continue

            # Check conditions (v2 only)
            if hasattr(status, "conditions"):
                for cond in (status.conditions or []):
                    if cond.type == "ScalingActive" and cond.status == "False":
                        issues.append(
                            f"{ref}: ScalingActive=False — {cond.reason}: {cond.message}"
                        )
                    elif cond.type == "AbleToScale" and cond.status == "False":
                        issues.append(
                            f"{ref}: AbleToScale=False — {cond.reason}: {cond.message}"
                        )

            # Check if maxed out (may need scale-out that is blocked)
            max_replicas = hpa.spec.max_replicas if hpa.spec else None
            current = status.current_replicas or 0
            desired = status.desired_replicas or 0
            if max_replicas and current == max_replicas and desired >= max_replicas:
                issues.append(
                    f"{ref}: at maxReplicas ({max_replicas}) — "
                    "load may still be high; review max or reduce resource usage"
                )

        return issues

    def _find_expiring_tls_certs(self) -> List[str]:
        """Find TLS Secrets whose certificates expire within 7 days or are already expired."""
        import base64
        from datetime import timezone
        expiring = []
        now = datetime.now(tz=timezone.utc)
        warn_threshold_days = 7

        try:
            secrets = self.k8s.v1.list_secret_for_all_namespaces(
                field_selector="type=kubernetes.io/tls"
            )
        except Exception:
            return []

        for secret in secrets.items:
            cert_data = (secret.data or {}).get("tls.crt")
            if not cert_data:
                continue
            try:
                cert_bytes = base64.b64decode(cert_data)
                # Use cryptography library if available, otherwise skip parsing
                try:
                    from cryptography import x509 as cx509
                    from cryptography.hazmat.backends import default_backend
                    raw = cert_bytes if b"BEGIN CERTIFICATE" in cert_bytes else base64.b64decode(cert_data)
                    cert_obj = cx509.load_pem_x509_certificate(raw, default_backend())
                    expiry = cert_obj.not_valid_after_utc if hasattr(cert_obj, "not_valid_after_utc") else cert_obj.not_valid_after.replace(tzinfo=timezone.utc)
                    days_left = (expiry - now).days
                    if days_left <= warn_threshold_days:
                        ref = f"{secret.metadata.namespace}/{secret.metadata.name}"
                        status = "EXPIRED" if days_left < 0 else f"expires in {days_left}d"
                        expiring.append(f"{ref}: {status} ({expiry.date()})")
                except ImportError:
                    # cryptography not installed — skip cert parsing, note it once
                    expiring.append(
                        "TLS cert check skipped: install 'cryptography' package to enable"
                    )
                    break
            except Exception:
                continue

        return expiring

    def _find_stuck_jobs(self) -> List[str]:
        """Find Jobs where backoffLimit is exhausted or that have been active
        far longer than their activeDeadlineSeconds (if set).
        """
        from datetime import timezone
        stuck = []
        try:
            jobs = self.k8s.batch_v1.list_job_for_all_namespaces()
        except Exception:
            return []

        now = datetime.now(tz=timezone.utc)
        for job in jobs.items:
            ref = f"{job.metadata.namespace}/{job.metadata.name}"
            status = job.status
            spec = job.spec
            if not status or not spec:
                continue

            # Job failed (backoffLimit exhausted)
            if status.failed and spec.backoff_limit is not None:
                if status.failed > spec.backoff_limit:
                    stuck.append(
                        f"{ref}: failed {status.failed} times (backoffLimit={spec.backoff_limit}) — "
                        "check pod logs for root cause"
                    )
                    continue

            # Job has been active longer than activeDeadlineSeconds
            if spec.active_deadline_seconds and status.start_time and status.active:
                start = status.start_time
                if hasattr(start, "tzinfo") and start.tzinfo is None:
                    start = start.replace(tzinfo=timezone.utc)
                elapsed = (now - start).total_seconds()
                if elapsed > spec.active_deadline_seconds * 1.2:  # 20% grace
                    stuck.append(
                        f"{ref}: active {int(elapsed)}s, deadline={spec.active_deadline_seconds}s"
                    )

        return stuck

    def _find_daemonset_gaps(self) -> List[str]:
        """Find DaemonSets where desiredNumberScheduled != numberReady.

        This detects DaemonSet pods that are not scheduled on new/all eligible nodes.
        """
        gaps = []
        try:
            daemonsets = self.k8s.apps_v1.list_daemon_set_for_all_namespaces()
        except Exception:
            return []

        for ds in daemonsets.items:
            status = ds.status
            if not status:
                continue
            desired = status.desired_number_scheduled or 0
            ready = status.number_ready or 0
            if desired > 0 and ready < desired:
                gaps.append(
                    f"{ds.metadata.namespace}/{ds.metadata.name}: "
                    f"{ready}/{desired} ready "
                    f"(misscheduled: {status.number_misscheduled or 0})"
                )
        return gaps

    async def predict_risk(self) -> Dict:
        """Heuristic risk score from detected issues."""
        issues = await self.detect_common_issues()
        score = sum(
            3 if i["severity"] == "high" else 2 if i["severity"] == "medium" else 1
            for i in issues.get("issues", [])
        )
        risk = "low" if score < 3 else "medium" if score < 6 else "high"
        return {
            "risk_level": risk,
            "score": score,
            "issues_considered": issues.get("issues", []),
            "timestamp": datetime.now().isoformat(),
        }

    async def autonomous_heal(self) -> Dict:
        """Attempt safe remediations for detected issues."""
        if not getattr(self.k8s, "fixer", None):
            return {"error": "Auto-heal unavailable: fixer not configured"}
        return await self.k8s.fixer.auto_remediate(self)

    def optimize_costs(self) -> Dict:
        recs = []
        pods = self.k8s.v1.list_pod_for_all_namespaces().items
        nodes = self.k8s.v1.list_node().items
        services = self.k8s.v1.list_service_for_all_namespaces().items
        pod_density = len(pods) / max(len(nodes), 1)
        if pod_density < 5:
            recs.append("Pod density is low (<5 pods/node). Consider consolidating or using smaller nodes.")
        lb_services = [s for s in services if s.spec.type == "LoadBalancer"]
        if len(lb_services) > 10:
            recs.append(
                f"{len(lb_services)} LoadBalancer services detected. Review necessity to reduce costs."
            )
        return {
            "summary": "Cost optimization hints (heuristic)",
            "pod_density": pod_density,
            "load_balancers": len(lb_services),
            "recommendations": recs,
            "timestamp": datetime.now().isoformat(),
        }

    def provider_diagnostics(self) -> Dict:
        nodes = self.k8s.v1.list_node().items
        provider = "unknown"
        if nodes:
            pid = nodes[0].spec.provider_id or ""
            if "azure" in pid:
                provider = "aks"
            elif "aws" in pid:
                provider = "eks"
            elif "gce" in pid or "google" in pid:
                provider = "gke"
        return {
            "provider": provider,
            "cni": self._detect_cni(),
            "load_balancers": self._check_pending_load_balancers(),
            "notes": "Heuristic provider detection based on node providerID and common CNI pods.",
        }

    def _detect_cni(self) -> Dict:
        pods = self.k8s.v1.list_pod_for_all_namespaces().items
        known = {
            "aws-node": "aws-cni",
            "azure-cni": "azure-cni",
            "calico-node": "calico",
            "cilium": "cilium",
            "kube-flannel-ds": "flannel",
            "weave-net": "weave",
        }
        detected = [
            (v, pod.status.phase)
            for pod in pods
            for k, v in known.items()
            if k in pod.metadata.name
        ]
        return {
            "detected": list({d[0] for d in detected}),
            "running": sum(1 for d in detected if d[1] == "Running"),
            "total": len(detected),
        }

    def _find_image_pull_errors(self, pods: List[V1Pod]) -> List[str]:
        errors = []
        for pod in pods:
            for cs in (pod.status.container_statuses or []):
                if cs.state and cs.state.waiting and cs.state.waiting.reason in (
                    "ImagePullBackOff", "ErrImagePull"
                ):
                    errors.append(
                        f"{pod.metadata.namespace}/{pod.metadata.name} ({cs.state.waiting.reason})"
                    )
        return errors

    def _check_pending_load_balancers(self) -> Dict:
        lbs = self.k8s.v1.list_service_for_all_namespaces(field_selector="spec.type=LoadBalancer")
        pending = [
            f"{svc.metadata.namespace}/{svc.metadata.name}"
            for svc in lbs.items
            if not (svc.status.load_balancer and svc.status.load_balancer.ingress)
        ]
        return {"pending": pending, "total": len(lbs.items)}

    async def get_resource_metrics(self) -> Dict:
        try:
            return {
                "nodes_metrics": self.k8s.metrics.list_cluster_custom_object(
                    "metrics.k8s.io", "v1beta1", "nodes"
                ).get("items", []),
                "pods_metrics": self.k8s.metrics.list_cluster_custom_object(
                    "metrics.k8s.io", "v1beta1", "pods"
                ).get("items", []),
            }
        except Exception:
            return {"error": "Metrics server not available"}
