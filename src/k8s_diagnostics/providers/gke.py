"""GKE-specific (GCP) provider checks.

Requires: google-cloud-container google-cloud-compute google-auth

All checks degrade gracefully if:
  - GCP SDK packages are not installed
  - Application Default Credentials are not configured
  - Required IAM permissions are missing

How GCP metadata is resolved:
  Node spec.providerID format:
      gce:///<project>/<zone>/<instance-name>
  Cluster name and project are read from the providerID and node labels.
"""

from typing import Dict, List, Optional
from .base import BaseProviderChecker, ProviderIssue


class GKEChecker(BaseProviderChecker):
    """Runs GCP-layer checks for GKE clusters."""

    @property
    def provider_name(self) -> str:
        return "gke"

    def run_all_checks(self, k8s_client) -> List[ProviderIssue]:
        meta = self._get_cluster_metadata(k8s_client)
        if meta is None:
            return [ProviderIssue(
                "gke_metadata_unavailable", "low",
                "Could not derive GCP metadata from node providerIDs — "
                "ensure nodes have gce:// providerID set",
                "Run: kubectl get nodes -o jsonpath='{.items[*].spec.providerID}'",
            )]

        issues: List[ProviderIssue] = []
        issues.extend(self._check_firewall_rules(meta, k8s_client))
        issues.extend(self._check_workload_identity(meta, k8s_client))
        issues.extend(self._check_artifact_registry_auth(meta, k8s_client))
        issues.extend(self._check_neg_sync(meta, k8s_client))
        issues.extend(self._check_autopilot_resource_class(k8s_client))
        return issues

    # ─────────────────────────────────────────────────────────────
    # Metadata extraction
    # ─────────────────────────────────────────────────────────────

    def _get_cluster_metadata(self, k8s_client) -> Optional[Dict]:
        try:
            nodes = k8s_client.v1.list_node().items
            if not nodes:
                return None

            provider_id = nodes[0].spec.provider_id or ""
            if not (provider_id.startswith("gce://") or
                    provider_id.startswith("google://")):
                return None

            # gce:///<project>/<zone>/<instance>
            stripped = provider_id.lstrip("gce:///").lstrip("google:///")
            parts = stripped.split("/")
            project = parts[0] if len(parts) > 0 else ""
            zone = parts[1] if len(parts) > 1 else ""
            region = "-".join(zone.split("-")[:-1]) if zone else ""

            labels = nodes[0].metadata.labels or {}
            cluster_name = (
                labels.get("cloud.google.com/gke-cluster-name") or
                labels.get("alpha.cloud.google.com/gke-cluster-name") or
                "unknown"
            )

            node_names = [n.metadata.name for n in nodes]

            return {
                "project": project,
                "zone": zone,
                "region": region,
                "cluster_name": cluster_name,
                "node_names": node_names,
                "node_count": len(nodes),
            }
        except Exception:
            return None

    def _get_gcp_credentials(self):
        """Return GCP credentials or None."""
        try:
            import google.auth
            creds, project = google.auth.default()
            return creds
        except ImportError:
            return None
        except Exception:
            return None

    # ─────────────────────────────────────────────────────────────
    # Check 1: Firewall rules blocking node-to-node traffic
    # ─────────────────────────────────────────────────────────────

    def _check_firewall_rules(self, meta: Dict, k8s_client) -> List[ProviderIssue]:
        """Detect firewall rules that block required GKE inter-node ports."""
        if not meta["project"]:
            return []

        creds = self._get_gcp_credentials()
        if creds is None:
            return [self._sdk_not_available("gke_firewall_blocking",
                "pip install google-cloud-compute google-auth")]

        REQUIRED_PORTS = [
            (443, "tcp", "API server / webhook traffic"),
            (10250, "tcp", "kubelet API"),
            (4194, "tcp", "cAdvisor metrics"),
        ]

        issues = []
        try:
            from googleapiclient.discovery import build
            import google.auth.transport.requests

            request = google.auth.transport.requests.Request()
            creds.refresh(request)

            compute = build("compute", "v1", credentials=creds)
            fw_list = compute.firewalls().list(project=meta["project"]).execute()
            rules = fw_list.get("items", [])

            # Find deny rules
            deny_rules = [r for r in rules if r.get("denied")]
            for rule in deny_rules:
                for denied in rule.get("denied", []):
                    ports = denied.get("ports", [])
                    proto = denied.get("IPProtocol", "")
                    for req_port, req_proto, purpose in REQUIRED_PORTS:
                        if proto in (req_proto, "all") and (
                            not ports or str(req_port) in ports or "0-65535" in ports
                        ):
                            issues.append(ProviderIssue(
                                "gke_firewall_blocking", "high",
                                f"Firewall rule '{rule['name']}' denies {proto}/{req_port} "
                                f"({purpose}). Node-to-node or API server communication "
                                "will fail.",
                                f"gcloud compute firewall-rules describe {rule['name']} "
                                f"--project {meta['project']} — "
                                "add an allow rule with higher priority or remove the deny rule",
                            ))
        except ImportError:
            return [self._sdk_not_available("gke_firewall_blocking",
                "pip install google-api-python-client google-auth")]
        except Exception as e:
            issues.append(self._check_error("gke_firewall_blocking", str(e)))
        return issues

    # ─────────────────────────────────────────────────────────────
    # Check 2: Workload Identity binding
    # ─────────────────────────────────────────────────────────────

    def _check_workload_identity(self, meta: Dict, k8s_client) -> List[ProviderIssue]:
        """Find pods whose ServiceAccount has a Workload Identity annotation but
        the GCP IAM binding (iam.workloadIdentityUser) may be missing.

        We detect the K8s side of the binding here (annotation present).
        The GCP IAM side requires the IAM API — we surface a warning when
        the annotation is present but we cannot verify the binding.
        """
        issues = []
        try:
            # Check for Workload Identity annotation on ServiceAccounts
            namespaces = [
                ns.metadata.name
                for ns in k8s_client.v1.list_namespace().items
                if ns.metadata.name not in ("kube-system", "kube-public", "kube-node-lease")
            ]

            creds = self._get_gcp_credentials()
            iam_available = creds is not None

            for ns in namespaces:
                sas = k8s_client.v1.list_namespaced_service_account(ns).items
                for sa in sas:
                    annotations = sa.metadata.annotations or {}
                    wi_annotation = annotations.get(
                        "iam.gke.io/gcp-service-account"
                    )
                    if not wi_annotation:
                        continue

                    if not iam_available:
                        # Cannot verify — surface as info
                        issues.append(ProviderIssue(
                            "gke_workload_identity_unverified", "info",
                            f"ServiceAccount '{ns}/{sa.metadata.name}' has Workload Identity "
                            f"annotation '{wi_annotation}' — GCP IAM binding could not be "
                            "verified (no GCP credentials available).",
                            "gcloud iam service-accounts get-iam-policy "
                            f"{wi_annotation} --project {meta['project']} "
                            "| grep workloadIdentityUser",
                        ))
                        continue

                    # Try to verify the IAM binding
                    try:
                        from googleapiclient.discovery import build
                        import google.auth.transport.requests
                        request = google.auth.transport.requests.Request()
                        creds.refresh(request)

                        iam_service = build("iam", "v1", credentials=creds)
                        resource = f"projects/-/serviceAccounts/{wi_annotation}"
                        policy = iam_service.projects().serviceAccounts().getIamPolicy(
                            resource=resource
                        ).execute()

                        member = (f"serviceAccount:{meta['project']}.svc.id.goog"
                                  f"[{ns}/{sa.metadata.name}]")
                        has_binding = any(
                            member in (b.get("members") or [])
                            for b in policy.get("bindings", [])
                            if b.get("role") == "roles/iam.workloadIdentityUser"
                        )
                        if not has_binding:
                            issues.append(ProviderIssue(
                                "gke_workload_identity_missing_binding", "high",
                                f"ServiceAccount '{ns}/{sa.metadata.name}' annotated with "
                                f"'{wi_annotation}' but the GCP IAM binding "
                                "'roles/iam.workloadIdentityUser' is missing. "
                                "Pods will get permission denied errors from GCP APIs.",
                                "gcloud iam service-accounts add-iam-policy-binding "
                                f"{wi_annotation} "
                                "--role=roles/iam.workloadIdentityUser "
                                f"--member='serviceAccount:{meta['project']}.svc.id.goog"
                                f"[{ns}/{sa.metadata.name}]'",
                            ))
                    except ImportError:
                        pass
                    except Exception:
                        pass  # IAM API call failed — skip silently
        except Exception as e:
            issues.append(self._check_error("gke_workload_identity_missing_binding", str(e)))
        return issues

    # ─────────────────────────────────────────────────────────────
    # Check 3: Artifact Registry auth
    # ─────────────────────────────────────────────────────────────

    def _check_artifact_registry_auth(self, meta: Dict, k8s_client) -> List[ProviderIssue]:
        """Detect ImagePullBackOff from Artifact Registry due to auth failure.

        For GKE with Workload Identity or default node service account,
        the node SA must have roles/artifactregistry.reader.
        We detect this by looking for ImagePullBackOff on pods referencing
        *.pkg.dev or *.gcr.io images.
        """
        issues = []
        try:
            pods = k8s_client.v1.list_pod_for_all_namespaces().items
            ar_pull_errors = []
            for pod in pods:
                for cs in (pod.status.container_statuses or []):
                    if not (cs.state and cs.state.waiting):
                        continue
                    if cs.state.waiting.reason not in ("ImagePullBackOff", "ErrImagePull"):
                        continue
                    image = cs.image or ""
                    if ".pkg.dev" in image or ".gcr.io" in image:
                        ar_pull_errors.append(
                            f"{pod.metadata.namespace}/{pod.metadata.name}: {image}"
                        )

            if ar_pull_errors:
                issues.append(ProviderIssue(
                    "gke_artifact_registry_auth", "high",
                    f"ImagePullBackOff on GCP registry images ({len(ar_pull_errors)} pod(s)): "
                    + ", ".join(ar_pull_errors[:3]),
                    "Grant the node service account Artifact Registry read access: "
                    f"gcloud projects add-iam-policy-binding {meta['project']} "
                    "--member='serviceAccount:<node-sa>@<project>.iam.gserviceaccount.com' "
                    "--role='roles/artifactregistry.reader'. "
                    "Or configure imagePullSecrets with a GCP service account key.",
                ))
        except Exception as e:
            issues.append(self._check_error("gke_artifact_registry_auth", str(e)))
        return issues

    # ─────────────────────────────────────────────────────────────
    # Check 4: NEG (Network Endpoint Group) sync
    # ─────────────────────────────────────────────────────────────

    def _check_neg_sync(self, meta: Dict, k8s_client) -> List[ProviderIssue]:
        """Detect Ingress services where the NEG is out of sync.

        GKE Ingress uses NEGs to route traffic directly to pods.
        If the cloud.google.com/neg-status annotation shows endpoints < pod count,
        traffic will be dropped for some pods.
        """
        issues = []
        try:
            services = k8s_client.v1.list_service_for_all_namespaces().items
            for svc in services:
                annotations = svc.metadata.annotations or {}
                neg_status = annotations.get("cloud.google.com/neg-status")
                if not neg_status:
                    continue

                import json
                try:
                    status = json.loads(neg_status)
                except Exception:
                    continue

                network_endpoints = status.get("network_endpoints", {})
                if not network_endpoints:
                    issues.append(ProviderIssue(
                        "gke_neg_not_synced", "high",
                        f"Service '{svc.metadata.namespace}/{svc.metadata.name}' "
                        "has NEG annotation but network_endpoints are empty. "
                        "Ingress traffic will be dropped.",
                        "kubectl describe svc "
                        f"{svc.metadata.name} -n {svc.metadata.namespace} — "
                        "check Events for NEG sync errors. "
                        "gcloud compute network-endpoint-groups list "
                        f"--project {meta['project']}",
                    ))
        except Exception as e:
            issues.append(self._check_error("gke_neg_not_synced", str(e)))
        return issues

    # ─────────────────────────────────────────────────────────────
    # Check 5: GKE Autopilot resource class mismatch
    # ─────────────────────────────────────────────────────────────

    def _check_autopilot_resource_class(self, k8s_client) -> List[ProviderIssue]:
        """Detect Pending pods in Autopilot clusters due to unsupported resource requests.

        Autopilot enforces resource class constraints. Pods requesting resources
        outside the supported ranges (e.g., non-standard CPU:memory ratios) stay Pending.
        """
        issues = []
        try:
            pods = k8s_client.v1.list_pod_for_all_namespaces().items
            pending = [p for p in pods if p.status.phase == "Pending"]

            for pod in pending:
                events = k8s_client.v1.list_namespaced_event(
                    pod.metadata.namespace,
                    field_selector=f"involvedObject.name={pod.metadata.name}"
                )
                for event in events.items:
                    msg = (event.message or "").lower()
                    if ("autopilot" in msg or "resource class" in msg or
                            "compute class" in msg):
                        issues.append(ProviderIssue(
                            "gke_autopilot_resource_mismatch", "medium",
                            f"Pod '{pod.metadata.namespace}/{pod.metadata.name}' "
                            f"rejected by Autopilot: {event.message}",
                            "Adjust pod resource requests to match a valid Autopilot "
                            "compute class. Valid classes: General-purpose, Balanced, "
                            "Scale-Out. Check: "
                            "https://cloud.google.com/kubernetes-engine/docs/concepts/"
                            "autopilot-resource-requests",
                        ))
                        break
        except Exception as e:
            issues.append(self._check_error("gke_autopilot_resource_mismatch", str(e)))
        return issues

    # ─────────────────────────────────────────────────────────────
    # Helpers
    # ─────────────────────────────────────────────────────────────

    @staticmethod
    def _sdk_not_available(issue_type: str, install_hint: str) -> ProviderIssue:
        return ProviderIssue(
            issue_type, "info",
            "GCP SDK not installed or credentials not configured — check skipped",
            f"To enable: {install_hint} && gcloud auth application-default login",
        )

    @staticmethod
    def _check_error(issue_type: str, error: str) -> ProviderIssue:
        return ProviderIssue(
            issue_type, "info",
            f"Check could not complete: {error[:200]}",
            "Ensure GCP credentials are configured: gcloud auth application-default login",
        )
