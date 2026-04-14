#!/usr/bin/env python3
"""
K8s Diagnostics CLI — Programmatic AKS/EKS/K8s troubleshooting tool.

Commands:
  health                          Cluster health summary (nodes, pods, services, events)
  diagnose <ns> <pod>             Full pod analysis: exit codes, probes, scheduling, events
  analyze  <ns> <pod>             5-layer pattern analysis: map events+logs to root cause + fix
  detect                          Scan cluster for all known issue types
  suggest                         Dry-run: show what fixes would be applied without acting
  network                         DNS, service endpoints, ingress, and LoadBalancer status
  fix           [--dry-run]       Auto-detect issues and apply safe remediations
  fix-pods      [--dry-run]       Restart failed pods (controller-managed only)
  cleanup       [--dry-run]       Remove evicted pods
  dnsfix        [--dry-run]       Restart unhealthy CoreDNS pods
  scale  <ns> <deploy> <n>  [--dry-run]  Scale a deployment
  heal          [--dry-run]       Alias for fix
  predict                         Heuristic risk score from detected issues
  optimize                        Cost-optimization hints (pod density, LoadBalancers)
  chaos  <ns> <selector> [live]   Inject pod failure (default: dry-run; pass 'live' to act)
  provider                        Detect cloud provider, CNI, pending LoadBalancers

Flags:
  --dry-run     Preview what a fix command would do without making changes.
"""

import asyncio
import json
import os
import sys
import warnings
from pathlib import Path

warnings.filterwarnings("ignore", category=FutureWarning, module=r"google\.(auth|oauth2).*")

IMPORT_ERROR = None
try:
    from src.k8s_diagnostics.core.client import K8sClient
    from src.k8s_diagnostics.automation.diagnostics import DiagnosticsEngine
    from src.k8s_diagnostics.automation.fixes import AutoFixer
    from src.k8s_diagnostics.automation.chaos import ChaosEngine
except ModuleNotFoundError as exc:
    IMPORT_ERROR = exc


def _parse_args(argv):
    """Return (positional_args, flags) where flags is a set of --flag strings."""
    positional = [a for a in argv if not a.startswith("--")]
    flags = {a for a in argv if a.startswith("--")}
    return positional, flags


class DiagnosticsCLI:
    def __init__(self):
        self.k8s = K8sClient()
        self.diagnostics = DiagnosticsEngine(self.k8s)
        self.fixer = AutoFixer(self.k8s)
        self.chaos = ChaosEngine(self.k8s)
        self.k8s.fixer = self.fixer

    # ─── Read-only commands ─────────────────────────────────────

    def health(self):
        print(json.dumps(self.k8s.get_cluster_health(), indent=2))

    async def diagnose_pod(self, namespace, pod_name):
        """Full pod diagnosis: exit codes, probes, scheduling analysis, events."""
        result = await self.diagnostics.diagnose_pod(namespace, pod_name)
        print(json.dumps(result, indent=2))

    async def analyze_pod(self, namespace, pod_name):
        """5-layer pattern analysis: map pod events + logs to root cause and fix command."""
        result = await self.diagnostics.diagnose_pod(namespace, pod_name)
        if "error" in result:
            print(json.dumps(result, indent=2))
            return
        matches = result.get("pattern_analysis", [])
        if not matches:
            print(json.dumps({
                "pod": f"{namespace}/{pod_name}",
                "pattern_analysis": [],
                "summary": "No known error patterns matched — check events and logs manually.",
                "next_command": f"kubectl describe pod {pod_name} -n {namespace}",
            }, indent=2))
            return
        # Group by layer for readable output
        by_layer: dict = {}
        for m in matches:
            layer = m.get("layer", "unknown")
            by_layer.setdefault(layer, []).append(m)
        print(json.dumps({
            "pod": f"{namespace}/{pod_name}",
            "phase": result.get("pod_info", {}).get("phase"),
            "patterns_found": len(matches),
            "analysis_by_layer": by_layer,
        }, indent=2))

    async def network_check(self):
        print(json.dumps(await self.diagnostics.check_network(), indent=2))

    async def detect_issues(self):
        """Scan entire cluster for known issue types including scheduling breakdowns."""
        print(json.dumps(await self.diagnostics.detect_common_issues(), indent=2))

    async def predict(self):
        print(json.dumps(await self.diagnostics.predict_risk(), indent=2))

    async def optimize(self):
        print(json.dumps(self.diagnostics.optimize_costs(), indent=2))

    async def provider_diag(self):
        print(json.dumps(self.diagnostics.provider_diagnostics(), indent=2))

    async def provider_check(self):
        """Run provider-specific cloud infrastructure checks (AKS/EKS/GKE)."""
        from src.k8s_diagnostics.providers.detector import detect_provider, run_provider_checks
        provider = detect_provider(self.k8s)
        issues = run_provider_checks(self.k8s)
        print(json.dumps({
            "provider": provider or "unknown",
            "issues_found": len([i for i in issues if i.get("severity") != "info"]),
            "issues": issues,
        }, indent=2))

    # ─── Gap 6: suggest = detect + dry-run all fixes ────────────

    async def suggest(self):
        """Show what fixes would be applied without making any changes."""
        print("Detecting issues...\n", file=sys.stderr)
        issues_report = await self.diagnostics.detect_common_issues()
        issues = issues_report.get("issues", [])

        if not issues:
            print(json.dumps({"status": "no_issues_detected"}, indent=2))
            return

        suggestions = []
        for issue in issues:
            entry = {
                "issue_type": issue["type"],
                "severity": issue.get("severity"),
                "details": issue.get("details") or issue.get("scheduling_analysis"),
            }

            # Map each detected issue type to its dry-run fix
            if issue["type"] == "failed_pods":
                fix = await self.fixer.restart_failed_pods(dry_run=True)
                entry["suggested_fix"] = fix
            elif issue["type"] == "dns_unhealthy":
                fix = await self.fixer.fix_dns_issues(dry_run=True)
                entry["suggested_fix"] = fix
            elif issue["type"] == "image_pull_errors":
                fix = await self.fixer.fix_image_pull_errors(dry_run=True)
                entry["suggested_fix"] = fix
            elif issue["type"] == "service_selector_mismatch":
                fix = await self.fixer.fix_service_selector_mismatches(dry_run=True)
                entry["suggested_fix"] = fix
            elif issue["type"] == "configmap_key_mismatch":
                fix = await self.fixer.fix_configmap_key_mismatches(dry_run=True)
                entry["suggested_fix"] = fix
            elif issue["type"] == "ingress_backend_missing_service":
                fix = await self.fixer.fix_ingress_backends(dry_run=True)
                entry["suggested_fix"] = fix
            elif issue["type"] == "aggressive_liveness_probe":
                fix = await self.fixer.fix_aggressive_liveness_probes(dry_run=True)
                entry["suggested_fix"] = fix
            elif issue["type"] == "gitops_controller_unhealthy":
                fix = await self.fixer.restart_unhealthy_gitops_controllers(dry_run=True)
                entry["suggested_fix"] = fix
            elif issue["type"] == "gitops_crd_missing":
                entry["suggested_fix"] = {
                    "action": "manual_required",
                    "hint": (
                        "Reapply the GitOps controller install manifests. "
                        "For Argo CD CRD annotation errors, use: "
                        "kubectl apply --server-side --force-conflicts -n argocd "
                        "-f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml"
                    ),
                }
            elif issue["type"] == "argocd_application_unhealthy":
                entry["suggested_fix"] = {
                    "action": "manual_required",
                    "hint": (
                        "kubectl describe application <name> -n <ns>; "
                        "inspect repo/auth/path errors, then fix Git or sync/revert in Argo CD. "
                        "The CLI does not patch Application state because Git should remain the source of truth."
                    ),
                }
            elif issue["type"] == "flux_resource_not_ready":
                entry["suggested_fix"] = {
                    "action": "manual_required",
                    "hint": (
                        "kubectl describe gitrepository <name> -n <ns> "
                        "(or describe the affected kustomization/helmrelease); "
                        "fix source auth, path, dependency, or Helm values in Git, then reconcile. "
                        "The CLI does not patch Flux custom resources because Git should remain the source of truth."
                    ),
                }
            elif issue["type"] == "pvc_not_bound":
                entry["suggested_fix"] = {
                    "action": "manual_required",
                    "hint": "kubectl describe pvc <name> — check StorageClass and provisioner",
                }
            elif issue["type"] == "load_balancer_pending":
                entry["suggested_fix"] = {
                    "action": "manual_required",
                    "hint": (
                        "Check Azure/AWS LB quota and cloud-controller-manager logs: "
                        "kubectl logs -n kube-system -l component=cloud-controller-manager"
                    ),
                }
            elif issue["type"] == "nodes_not_ready":
                entry["suggested_fix"] = {
                    "action": "manual_required",
                    "hint": (
                        "kubectl describe node <node> — check Conditions section; "
                        "journalctl -u kubelet on the node"
                    ),
                }
            elif issue["type"] == "node_pressure":
                entry["suggested_fix"] = {
                    "action": "manual_required",
                    "hint": (
                        "kubectl describe node <node> — check Conditions and Allocatable. "
                        "MemoryPressure: free memory or evict pods. "
                        "DiskPressure: clear logs/images with 'crictl rmi --prune'. "
                        "PIDPressure: check for fork-bombing processes on node. "
                        "NetworkUnavailable: check CNI plugin pods in kube-system."
                    ),
                }
            elif issue["type"] == "warning_events":
                entry["suggested_fix"] = {
                    "action": "manual_required",
                    "hint": (
                        "kubectl get events -A --field-selector type=Warning "
                        "--sort-by=.lastTimestamp | tail -30 — "
                        "then use 'diagnose <ns> <pod>' for any affected pod"
                    ),
                }
            elif issue["type"] == "control_plane_unhealthy":
                entry["suggested_fix"] = {
                    "action": "manual_required",
                    "hint": (
                        "kubectl get componentstatuses — "
                        "etcd: check etcd pod logs and disk space. "
                        "scheduler/controller-manager: check kube-system pod logs. "
                        "Note: on AKS/EKS/GKE the control plane is managed and not visible here."
                    ),
                }
            elif issue["type"] == "pending_pods":
                entry["suggested_fix"] = {
                    "action": "see_scheduling_analysis",
                    "hint": (
                        "Each pending pod's root cause is in scheduling_analysis above. "
                        "Use 'diagnose <ns> <pod>' for full detail."
                    ),
                }
            elif issue["type"] == "high_restart_count":
                # High restart count → check for aggressive liveness probes first
                fix = await self.fixer.fix_aggressive_liveness_probes(dry_run=True)
                entry["suggested_fix"] = fix
                entry["suggested_fix"]["hint"] = (
                    "Use 'diagnose <ns> <pod>' to see exit code analysis. "
                    "Exit 137=OOMKill (raise memory limits), "
                    "Exit 143=SIGTERM (fix liveness probe initialDelaySeconds)"
                )
            elif issue["type"] == "probe_failures":
                entry["suggested_fix"] = {
                    "action": "manual_required",
                    "hint": (
                        "Use 'diagnose <ns> <pod>' to get per-container probe analysis "
                        "showing mismatched ports, wrong paths, and low initialDelaySeconds"
                    ),
                }
            elif issue["type"] == "init_containers_blocked":
                entry["suggested_fix"] = {
                    "action": "manual_required",
                    "hint": (
                        "Run: kubectl logs <pod> -n <ns> -c <init-container>. "
                        "If logs say a service is not ready, verify it with: "
                        "kubectl get svc,endpoints,endpointslice -n <ns> | grep <service>. "
                        "Fix the missing Service/endpoints; remove initContainers only as a lab workaround."
                    ),
                }
            elif issue["type"] == "crashloop_backoff":
                # CrashLoopBackOff pods are caught by restart_failed_pods; dry-run it
                fix = await self.fixer.restart_failed_pods(dry_run=True)
                entry["suggested_fix"] = fix
                entry["suggested_fix"]["hint"] = (
                    "kubectl logs <pod> -n <ns> --previous for root cause; "
                    "Exit 137=OOMKill (raise memory limits), "
                    "Exit 127=bad command (check entrypoint), Exit 1=app error"
                )
            elif issue["type"] == "stuck_terminating":
                entry["suggested_fix"] = {
                    "action": "manual_required",
                    "hint": (
                        "kubectl patch pod <pod> -n <ns> "
                        "-p '{\"metadata\":{\"finalizers\":[]}}' --type=merge — "
                        "WARNING: only do this after confirming the finalizer owner is gone"
                    ),
                }
            elif issue["type"] == "missing_config_refs":
                entry["suggested_fix"] = {
                    "action": "manual_required",
                    "hint": (
                        "Create the missing ConfigMap or Secret shown above, "
                        "or set optional=true in the pod spec if the ref is non-critical"
                    ),
                }
            elif issue["type"] == "networkpolicy_deny_all":
                entry["suggested_fix"] = {
                    "action": "manual_required",
                    "hint": (
                        "kubectl get networkpolicy -n <ns> -o yaml — "
                        "add an ingress allow rule, or create a second NetworkPolicy "
                        "that explicitly allows traffic from the required sources"
                    ),
                }
            elif issue["type"] == "hpa_issues":
                entry["suggested_fix"] = {
                    "action": "manual_required",
                    "hint": (
                        "kubectl describe hpa -n <ns> — "
                        "ScalingActive=False usually means metrics-server is down or "
                        "the metric name in the HPA spec does not match what is exposed. "
                        "Check: kubectl top pods -n <ns>"
                    ),
                }
            elif issue["type"] == "tls_cert_expiring":
                entry["suggested_fix"] = {
                    "action": "manual_required",
                    "hint": (
                        "If using cert-manager: "
                        "kubectl annotate certificate <name> -n <ns> "
                        "cert-manager.io/renewal-reason=manual-$(date +%s). "
                        "If manual: replace tls.crt and tls.key in the Secret."
                    ),
                }
            elif issue["type"] == "stuck_jobs":
                entry["suggested_fix"] = {
                    "action": "manual_required",
                    "hint": (
                        "kubectl describe job <name> -n <ns> — check pod logs for exit reason. "
                        "To retry: kubectl delete job <name> -n <ns> and recreate. "
                        "Note: Jobs are immutable — you must delete and recreate to change spec."
                    ),
                }
            elif issue["type"] == "daemonset_not_fully_scheduled":
                entry["suggested_fix"] = {
                    "action": "manual_required",
                    "hint": (
                        "kubectl describe ds <name> -n <ns> — "
                        "check nodeSelector and tolerations match all target nodes. "
                        "New nodes may need labels: kubectl label node <node> <key>=<value>"
                    ),
                }
            elif issue.get("layer") == "layer5" or issue.get("provider"):
                # Provider-layer issue — the suggested_action from the detector is the hint
                entry["suggested_fix"] = {
                    "action": "manual_required",
                    "provider": issue.get("provider", "unknown"),
                    "hint": issue.get("suggested_action", "See detail above"),
                }
            else:
                entry["suggested_fix"] = {"action": "no_automated_fix", "hint": str(issue)}

            suggestions.append(entry)

        print(json.dumps({
            "mode": "dry_run_suggest",
            "issues_found": len(issues),
            "suggestions": suggestions,
            "timestamp": issues_report.get("timestamp"),
        }, indent=2))

    # ─── Mutating commands (all support --dry-run) ──────────────

    async def fix_failed_pods(self, dry_run: bool = False):
        result = await self.fixer.restart_failed_pods(dry_run=dry_run)
        print(json.dumps(result, indent=2))

    async def cleanup_evicted(self, dry_run: bool = False):
        result = await self.fixer.cleanup_evicted_pods(dry_run=dry_run)
        print(json.dumps(result, indent=2))

    async def fix_dns(self, dry_run: bool = False):
        result = await self.fixer.fix_dns_issues(dry_run=dry_run)
        print(json.dumps(result, indent=2))

    async def scale(self, namespace, deployment, replicas, dry_run: bool = False):
        result = await self.fixer.scale_resources(
            namespace, deployment, int(replicas), dry_run=dry_run
        )
        print(json.dumps(result, indent=2))

    async def heal(self, dry_run: bool = False):
        result = await self.fixer.auto_remediate(self.diagnostics, dry_run=dry_run)
        print(json.dumps(result, indent=2))

    async def chaos_inject(self, namespace, selector, dry_run=True):
        result = await self.chaos.inject_pod_failure(namespace, selector, dry_run)
        print(json.dumps(result, indent=2))


def _usage(exit_code: int = 1):
    print(__doc__)
    sys.exit(exit_code)


def _maybe_reexec_project_venv() -> bool:
    """Use the project virtualenv automatically when the caller used bare python3."""
    if os.environ.get("K8S_DIAGNOSTICS_NO_VENV_REEXEC") == "1":
        return False

    repo_root = Path(__file__).resolve().parent
    venv_root = repo_root / ".venv"
    venv_python = repo_root / ".venv" / "bin" / "python"
    if not venv_python.exists():
        return False

    try:
        if Path(sys.prefix).resolve() == venv_root.resolve():
            return False
    except OSError:
        pass

    env = os.environ.copy()
    env["K8S_DIAGNOSTICS_NO_VENV_REEXEC"] = "1"
    os.execve(str(venv_python), [str(venv_python), str(Path(__file__).resolve()), *sys.argv[1:]], env)
    return True


def _exit_missing_dependency(exc: ModuleNotFoundError):
    missing = exc.name or "unknown"
    print(
        json.dumps(
            {
                "status": "dependency_error",
                "missing_module": missing,
                "message": (
                    f"Python dependency '{missing}' is not installed. "
                    "Run 'python3 -m venv .venv && .venv/bin/pip install -r requirements.txt' "
                    "before using the CLI."
                ),
            },
            indent=2,
        )
    )
    sys.exit(2)


def main():
    if IMPORT_ERROR is not None:
        _maybe_reexec_project_venv()
        _exit_missing_dependency(IMPORT_ERROR)

    if len(sys.argv) < 2:
        _usage()

    args, flags = _parse_args(sys.argv[1:])
    dry_run = "--dry-run" in flags
    command = args[0] if args else ""

    if "--help" in flags or command in ("-h", "help"):
        _usage(0)

    cli = DiagnosticsCLI()

    if command == "health":
        cli.health()

    elif command == "diagnose":
        if len(args) < 3:
            print("Usage: diagnose <namespace> <pod-name>")
            sys.exit(1)
        asyncio.run(cli.diagnose_pod(args[1], args[2]))

    elif command == "analyze":
        if len(args) < 3:
            print("Usage: analyze <namespace> <pod-name>")
            sys.exit(1)
        asyncio.run(cli.analyze_pod(args[1], args[2]))

    elif command == "network":
        asyncio.run(cli.network_check())

    elif command == "detect":
        asyncio.run(cli.detect_issues())

    # Gap 6: suggest command
    elif command == "suggest":
        asyncio.run(cli.suggest())

    elif command == "fix":
        asyncio.run(cli.heal(dry_run=dry_run))

    elif command == "fix-pods":
        asyncio.run(cli.fix_failed_pods(dry_run=dry_run))

    elif command == "cleanup":
        asyncio.run(cli.cleanup_evicted(dry_run=dry_run))

    elif command == "dnsfix":
        asyncio.run(cli.fix_dns(dry_run=dry_run))

    elif command == "scale":
        if len(args) < 4:
            print("Usage: scale <namespace> <deployment> <replicas> [--dry-run]")
            sys.exit(1)
        asyncio.run(cli.scale(args[1], args[2], args[3], dry_run=dry_run))

    elif command == "predict":
        asyncio.run(cli.predict())

    elif command == "heal":
        asyncio.run(cli.heal(dry_run=dry_run))

    elif command == "optimize":
        asyncio.run(cli.optimize())

    elif command == "chaos":
        if len(args) < 3:
            print("Usage: chaos <namespace> <label-selector> [live]")
            sys.exit(1)
        # Default to dry-run; pass 'live' as 4th arg to act for real
        live = len(args) >= 4 and args[3].lower() == "live"
        asyncio.run(cli.chaos_inject(args[1], args[2], dry_run=not live))

    elif command == "provider":
        asyncio.run(cli.provider_diag())

    elif command == "provider-check":
        asyncio.run(cli.provider_check())

    else:
        print(f"Unknown command: '{command}'")
        _usage()


if __name__ == "__main__":
    main()
