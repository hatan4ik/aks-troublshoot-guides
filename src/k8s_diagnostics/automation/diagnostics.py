from typing import Dict, List, Optional
from datetime import datetime
from kubernetes.client import V1Pod

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
                "events": self._get_pod_events(namespace, pod_name),
                "issues": self._detect_pod_issues(pod),
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
        failed_pods = [p for p in pods.items if p.status.phase == "Failed"]
        pending_pods = [p for p in pods.items if p.status.phase == "Pending"]

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
        image_pull = self._find_image_pull_errors(pods.items)
        if image_pull:
            issues.append({
                "type": "image_pull_errors",
                "severity": "high",
                "count": len(image_pull),
                "details": image_pull[:5],
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

        # High restart counts
        high_restart = [
            f"{pod.metadata.namespace}/{pod.metadata.name}"
            for pod in pods.items
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
        probe_failures = self._find_probe_failures(pods.items)
        if probe_failures:
            issues.append({
                "type": "probe_failures",
                "severity": "medium",
                "count": len(probe_failures),
                "details": probe_failures[:5],
                "hint": "Use 'diagnose <ns> <pod>' for per-container probe analysis",
            })

        # Warning events cluster-wide (last 1 hour)
        warning_events = self._check_warning_events()
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

        return {"issues": issues, "timestamp": datetime.now().isoformat()}

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

    # ─────────────────────────────────────────────────────────────
    # New checks: node pressure, warning events, component health
    # ─────────────────────────────────────────────────────────────

    # Pressure condition types that indicate the node is under stress.
    # Ready=False is already handled above; these are the *additional* conditions.
    _PRESSURE_CONDITIONS = ("MemoryPressure", "DiskPressure", "PIDPressure", "NetworkUnavailable")

    def _check_node_pressure(self, node_items) -> List[str]:
        """Return list of '<node>: <condition>' strings for nodes under pressure."""
        pressured = []
        for node in node_items:
            for condition in (node.status.conditions or []):
                if condition.type in self._PRESSURE_CONDITIONS and condition.status == "True":
                    pressured.append(f"{node.metadata.name}: {condition.type} ({condition.message or 'no message'})")
        return pressured

    def _check_warning_events(self) -> List[str]:
        """Return deduplicated Warning events from the last hour across all namespaces.

        Each entry is: '<namespace>/<object> — <reason>: <message>'
        Skips events with no timestamp (pre-existing, already-flushed events).
        """
        try:
            events = self.k8s.v1.list_event_for_all_namespaces(
                field_selector="type=Warning"
            )
        except Exception:
            return []

        from datetime import timezone
        now = datetime.now(tz=timezone.utc)
        results = []
        seen = set()
        for e in events.items:
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
            key = f"{e.involved_object.namespace}/{e.involved_object.name}|{e.reason}"
            if key in seen:
                continue
            seen.add(key)
            ns = e.involved_object.namespace or "cluster"
            msg = (e.message or "")[:120]
            results.append(f"{ns}/{e.involved_object.name} — {e.reason}: {msg}")
        return results

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

        actions = []
        issues = await self.detect_common_issues()
        for issue in issues.get("issues", []):
            if issue["type"] == "failed_pods":
                result = await self.k8s.fixer.restart_failed_pods()
                actions.append({"issue": "failed_pods", "result": result})
            if issue["type"] == "dns_unhealthy":
                result = await self.k8s.fixer.fix_dns_issues()
                actions.append({"issue": "dns_unhealthy", "result": result})
        return {
            "actions": actions,
            "issues": issues.get("issues", []),
            "timestamp": datetime.now().isoformat(),
        }

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
