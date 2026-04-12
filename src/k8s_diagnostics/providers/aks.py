"""AKS-specific (Azure) provider checks.

Requires: azure-identity azure-mgmt-containerservice azure-mgmt-network
          azure-mgmt-authorization azure-mgmt-compute

All checks degrade gracefully if:
  - SDK packages are not installed
  - Azure credentials are not present (no az login / no managed identity)
  - Required permissions are missing (returns partial results)

How Azure metadata is resolved:
  Node spec.providerID format:
      azure:///subscriptions/<sub>/resourceGroups/<node-rg>/providers/
      Microsoft.Compute/virtualMachineScaleSets/<vmss>/virtualMachines/<idx>
  AKS cluster info is fetched from the node's resource group tag
  (MC_<rg>_<cluster>_<region> → cluster name and resource group are derivable).
"""

from typing import Dict, List, Optional
from .base import BaseProviderChecker, ProviderIssue

# Minimum IPs to consider a subnet healthy
_MIN_AVAILABLE_IPS = 10
# Seconds before considering an NSG check a failure (connect timeout)
_NSG_REQUIRED_PORTS = {
    "ACR_egress": (443, "outbound", "ACR / MCR image pulls"),
    "API_server": (443, "outbound", "AKS API server tunnel"),
    "tunnel": (9000, "outbound", "AKS control plane tunnel"),
    "NTP": (123, "outbound", "NTP time sync"),
    "DNS_tcp": (53, "outbound", "DNS"),
    "kubelet": (10250, "inbound", "kubelet API (metrics, exec, logs)"),
}


class AKSChecker(BaseProviderChecker):
    """Runs Azure-layer checks for AKS clusters."""

    @property
    def provider_name(self) -> str:
        return "aks"

    def run_all_checks(self, k8s_client) -> List[ProviderIssue]:
        """Auto-discover cluster metadata from nodes, then run all Azure checks."""
        meta = self._get_cluster_metadata(k8s_client)
        if meta is None:
            return [ProviderIssue(
                "aks_metadata_unavailable", "low",
                "Could not derive Azure metadata from node providerIDs — "
                "ensure nodes have azure:// providerID set",
                "Run: kubectl get nodes -o jsonpath='{.items[*].spec.providerID}'",
            )]

        issues: List[ProviderIssue] = []
        issues.extend(self._check_cni_ip_exhaustion(meta))
        issues.extend(self._check_nsg_rules(meta))
        issues.extend(self._check_acr_pull_role(meta, k8s_client))
        issues.extend(self._check_lb_health_probes(meta, k8s_client))
        issues.extend(self._check_vmss_provisioning(meta))
        issues.extend(self._check_private_dns(meta))
        issues.extend(self._check_disk_zone_mismatch(meta, k8s_client))
        return issues

    # ─────────────────────────────────────────────────────────────
    # Metadata extraction
    # ─────────────────────────────────────────────────────────────

    def _get_cluster_metadata(self, k8s_client) -> Optional[Dict]:
        """Extract Azure subscription, node resource group, and cluster info from nodes."""
        try:
            nodes = k8s_client.v1.list_node().items
            if not nodes:
                return None

            # Parse the first node's providerID:
            # azure:///subscriptions/<sub>/resourceGroups/<node-rg>/providers/...
            provider_id = nodes[0].spec.provider_id or ""
            if not provider_id.startswith("azure://"):
                return None

            parts = provider_id.removeprefix("azure:///").split("/")
            # parts: ['subscriptions', <sub>, 'resourceGroups', <rg>, 'providers', ...]
            if len(parts) < 4 or parts[0] != "subscriptions":
                return None

            subscription_id = parts[1]
            node_resource_group = parts[3]  # MC_<rg>_<cluster>_<region>

            # Derive cluster resource group and name from MC_ naming convention:
            # MC_<resource-group>_<cluster-name>_<region>
            cluster_rg, cluster_name, region = None, None, None
            if node_resource_group.startswith("MC_"):
                # Split on _ — cluster name may contain _
                segments = node_resource_group[3:].split("_")
                # Last segment is region, second-to-last is cluster name,
                # everything before is resource group (may contain _)
                if len(segments) >= 3:
                    region = segments[-1]
                    cluster_name = segments[-2]
                    cluster_rg = "_".join(segments[:-2])

            # Collect node names for VMSS check
            node_names = [n.metadata.name for n in nodes]
            node_labels = {n.metadata.name: (n.metadata.labels or {}) for n in nodes}

            return {
                "subscription_id": subscription_id,
                "node_resource_group": node_resource_group,
                "cluster_resource_group": cluster_rg,
                "cluster_name": cluster_name,
                "region": region,
                "node_names": node_names,
                "node_labels": node_labels,
                "node_count": len(nodes),
            }
        except Exception:
            return None

    def _get_azure_clients(self, subscription_id: str):
        """Return (credential, network_client, compute_client, auth_client, container_client).
        Returns None if SDK not installed or credentials unavailable.
        """
        try:
            from azure.identity import DefaultAzureCredential
            from azure.mgmt.network import NetworkManagementClient
            from azure.mgmt.compute import ComputeManagementClient
            from azure.mgmt.authorization import AuthorizationManagementClient
            from azure.mgmt.containerservice import ContainerServiceClient

            cred = DefaultAzureCredential()
            return (
                cred,
                NetworkManagementClient(cred, subscription_id),
                ComputeManagementClient(cred, subscription_id),
                AuthorizationManagementClient(cred, subscription_id),
                ContainerServiceClient(cred, subscription_id),
            )
        except ImportError:
            return None
        except Exception:
            return None

    # ─────────────────────────────────────────────────────────────
    # Check 1: Azure CNI IP exhaustion
    # ─────────────────────────────────────────────────────────────

    def _check_cni_ip_exhaustion(self, meta: Dict) -> List[ProviderIssue]:
        """Detect subnet IP exhaustion that causes ContainerCreating pods."""
        clients = self._get_azure_clients(meta["subscription_id"])
        if clients is None:
            return [self._sdk_not_available("aks_cni_ip_exhaustion",
                "pip install azure-identity azure-mgmt-network")]

        _, network_client, _, _, _ = clients
        issues = []
        try:
            # List VNets in the node resource group and check subnets
            vnets = list(network_client.virtual_networks.list(meta["node_resource_group"]))
            for vnet in vnets:
                for subnet in (vnet.subnets or []):
                    available = subnet.ip_configurations  # None when IPs remain
                    # available_ip_address_count is on the subnet object
                    count = getattr(subnet, "available_ip_address_count", None)
                    if count is not None and count < _MIN_AVAILABLE_IPS:
                        issues.append(ProviderIssue(
                            "aks_cni_ip_exhaustion", "high",
                            f"Subnet '{vnet.name}/{subnet.name}' has only {count} IPs remaining "
                            f"(threshold: {_MIN_AVAILABLE_IPS}). "
                            "New pods will be stuck in ContainerCreating.",
                            "Expand subnet address space or add a new node pool in a larger subnet. "
                            "Check: az network vnet subnet show -g <node-rg> "
                            "--vnet-name <vnet> --name <subnet> "
                            "--query availableIpAddressCount",
                        ))
        except Exception as e:
            issues.append(self._check_error("aks_cni_ip_exhaustion", str(e)))
        return issues

    # ─────────────────────────────────────────────────────────────
    # Check 2: NSG rules blocking required ports
    # ─────────────────────────────────────────────────────────────

    def _check_nsg_rules(self, meta: Dict) -> List[ProviderIssue]:
        """Detect NSG deny rules that block AKS-required ports."""
        clients = self._get_azure_clients(meta["subscription_id"])
        if clients is None:
            return [self._sdk_not_available("aks_nsg_blocking",
                "pip install azure-identity azure-mgmt-network")]

        _, network_client, _, _, _ = clients
        issues = []
        try:
            nsgs = list(network_client.network_security_groups.list(
                meta["node_resource_group"]
            ))
            for nsg in nsgs:
                deny_rules = [
                    r for r in (nsg.security_rules or []) + (nsg.default_security_rules or [])
                    if r.access and r.access.lower() == "deny"
                ]
                blocked = set()
                for name, (port, direction, purpose) in _NSG_REQUIRED_PORTS.items():
                    for rule in deny_rules:
                        rule_dir = (rule.direction or "").lower()
                        if rule_dir != direction:
                            continue

                        dest_ports = []
                        if rule.destination_port_range:
                            dest_ports.append(str(rule.destination_port_range))
                        dest_ports.extend(
                            str(value)
                            for value in (getattr(rule, "destination_port_ranges", None) or [])
                        )
                        if any(self._port_matches(port, candidate) for candidate in dest_ports):
                            blocked.add(f"port {port}/{direction} ({purpose})")
                if blocked:
                    issues.append(ProviderIssue(
                        "aks_nsg_blocking", "high",
                        f"NSG '{nsg.name}': deny rules may block required AKS ports: "
                        + ", ".join(sorted(blocked)),
                        "Review NSG rules: az network nsg rule list -g "
                        f"{meta['node_resource_group']} --nsg-name {nsg.name} "
                        "--include-default -o table",
                    ))
        except Exception as e:
            issues.append(self._check_error("aks_nsg_blocking", str(e)))
        return issues

    @staticmethod
    def _port_matches(port: int, candidate: str) -> bool:
        if candidate == "*" or candidate == str(port):
            return True
        if "-" not in candidate:
            return False
        start, end = candidate.split("-", 1)
        return start.isdigit() and end.isdigit() and int(start) <= port <= int(end)

    # ─────────────────────────────────────────────────────────────
    # Check 3: AcrPull role on kubelet identity
    # ─────────────────────────────────────────────────────────────

    def _check_acr_pull_role(self, meta: Dict, k8s_client) -> List[ProviderIssue]:
        """Verify the kubelet managed identity has AcrPull on linked ACRs."""
        if not meta.get("cluster_resource_group") or not meta.get("cluster_name"):
            return []

        clients = self._get_azure_clients(meta["subscription_id"])
        if clients is None:
            return [self._sdk_not_available("aks_acr_pull_missing",
                "pip install azure-identity azure-mgmt-authorization azure-mgmt-containerservice")]

        _, _, _, auth_client, container_client = clients
        issues = []
        try:
            cluster = container_client.managed_clusters.get(
                meta["cluster_resource_group"], meta["cluster_name"]
            )
            # Get kubelet identity principal ID
            kubelet_identity = None
            if cluster.identity_profile:
                ki = cluster.identity_profile.get("kubeletidentity")
                if ki:
                    kubelet_identity = ki.object_id

            if not kubelet_identity:
                return []

            # List role assignments for this principal
            assignments = list(auth_client.role_assignments.list(
                filter=f"principalId eq '{kubelet_identity}'"
            ))
            assigned_roles = {a.role_definition_id.split("/")[-1] for a in assignments
                              if a.role_definition_id}

            # AcrPull role definition ID is well-known
            ACRPULL_ROLE_ID = "7f951dda-4ed3-4680-a7ca-43fe172d538d"
            if ACRPULL_ROLE_ID not in assigned_roles:
                issues.append(ProviderIssue(
                    "aks_acr_pull_missing", "high",
                    f"Kubelet identity (objectId: {kubelet_identity}) does not have "
                    "the AcrPull role. ImagePullBackOff errors will occur for ACR images.",
                    "az role assignment create --assignee "
                    f"{kubelet_identity} "
                    "--role AcrPull --scope /subscriptions/"
                    f"{meta['subscription_id']}/resourceGroups/<acr-rg>"
                    "/providers/Microsoft.ContainerRegistry/registries/<acr-name>",
                ))
        except Exception as e:
            issues.append(self._check_error("aks_acr_pull_missing", str(e)))
        return issues

    # ─────────────────────────────────────────────────────────────
    # Check 4: Azure LB health probe vs K8s readiness mismatch
    # ─────────────────────────────────────────────────────────────

    def _check_lb_health_probes(self, meta: Dict, k8s_client) -> List[ProviderIssue]:
        """Find Azure LBs whose health probe port does not match a NodePort service."""
        clients = self._get_azure_clients(meta["subscription_id"])
        if clients is None:
            return [self._sdk_not_available("aks_lb_probe_mismatch",
                "pip install azure-identity azure-mgmt-network")]

        _, network_client, _, _, _ = clients
        issues = []
        try:
            lbs = list(network_client.load_balancers.list(meta["node_resource_group"]))

            # Get all NodePort services
            svc_list = k8s_client.v1.list_service_for_all_namespaces()
            node_ports = {
                svc.spec.ports[0].node_port
                for svc in svc_list.items
                if svc.spec.type in ("LoadBalancer", "NodePort")
                and svc.spec.ports
                and svc.spec.ports[0].node_port
            }

            for lb in lbs:
                for probe in (lb.probes or []):
                    probe_port = probe.port
                    if probe_port and probe_port not in node_ports and probe_port not in (80, 443):
                        issues.append(ProviderIssue(
                            "aks_lb_probe_mismatch", "medium",
                            f"Azure LB '{lb.name}' health probe uses port {probe_port} "
                            "which does not match any known NodePort or standard port. "
                            "This will cause traffic to stop even if pods are Ready.",
                            "az network lb probe list -g "
                            f"{meta['node_resource_group']} --lb-name {lb.name} -o table — "
                            "verify probe port matches the Service NodePort",
                        ))
        except Exception as e:
            issues.append(self._check_error("aks_lb_probe_mismatch", str(e)))
        return issues

    # ─────────────────────────────────────────────────────────────
    # Check 5: VMSS provisioning failures (nodes not joining)
    # ─────────────────────────────────────────────────────────────

    def _check_vmss_provisioning(self, meta: Dict) -> List[ProviderIssue]:
        """Find VMSS instances stuck in a failed provisioning state."""
        clients = self._get_azure_clients(meta["subscription_id"])
        if clients is None:
            return [self._sdk_not_available("aks_vmss_provisioning_failed",
                "pip install azure-identity azure-mgmt-compute")]

        _, _, compute_client, _, _ = clients
        issues = []
        try:
            vmsses = list(compute_client.virtual_machine_scale_sets.list(
                meta["node_resource_group"]
            ))
            for vmss in vmsses:
                instances = list(compute_client.virtual_machine_scale_set_vms.list(
                    meta["node_resource_group"], vmss.name
                ))
                failed = [
                    i.name for i in instances
                    if i.provisioning_state and
                    i.provisioning_state.lower() not in ("succeeded", "creating")
                ]
                if failed:
                    issues.append(ProviderIssue(
                        "aks_vmss_provisioning_failed", "high",
                        f"VMSS '{vmss.name}': {len(failed)} instance(s) in failed "
                        f"provisioning state: {failed[:3]}. "
                        "These nodes will not join the cluster.",
                        "az vmss list-instances -g "
                        f"{meta['node_resource_group']} --name {vmss.name} "
                        "-o table — then: az aks nodepool upgrade or delete+recreate "
                        "the affected node pool",
                    ))
        except Exception as e:
            issues.append(self._check_error("aks_vmss_provisioning_failed", str(e)))
        return issues

    # ─────────────────────────────────────────────────────────────
    # Check 6: Private cluster DNS resolution
    # ─────────────────────────────────────────────────────────────

    def _check_private_dns(self, meta: Dict) -> List[ProviderIssue]:
        """Verify private DNS zone is linked to the cluster VNet."""
        if not meta.get("cluster_resource_group") or not meta.get("cluster_name"):
            return []

        clients = self._get_azure_clients(meta["subscription_id"])
        if clients is None:
            return [self._sdk_not_available("aks_private_dns_unlinked",
                "pip install azure-identity azure-mgmt-network")]

        _, network_client, _, _, _ = clients
        issues = []
        try:
            from azure.mgmt.privatedns import PrivateDnsManagementClient
            from azure.identity import DefaultAzureCredential
            cred = DefaultAzureCredential()
            dns_client = PrivateDnsManagementClient(cred, meta["subscription_id"])

            zones = list(dns_client.private_zones.list())
            aks_zones = [z for z in zones if "azmk8s.io" in (z.name or "")]

            for zone in aks_zones:
                rg = zone.id.split("/resourceGroups/")[1].split("/")[0]
                links = list(dns_client.virtual_network_links.list(rg, zone.name))
                broken = [
                    lk.name for lk in links
                    if (lk.provisioning_state or "").lower() != "succeeded"
                ]
                if broken:
                    issues.append(ProviderIssue(
                        "aks_private_dns_unlinked", "high",
                        f"Private DNS zone '{zone.name}': VNet link(s) not in Succeeded state: "
                        f"{broken}. kubectl will fail to resolve the API server FQDN.",
                        "az network private-dns link vnet list -g "
                        f"{rg} --zone-name {zone.name} -o table — "
                        "delete and recreate the broken link, or use: "
                        "az aks command invoke -g <rg> -n <cluster> --command 'kubectl get pods'",
                    ))
        except ImportError:
            pass  # azure-mgmt-privatedns not installed — skip silently
        except Exception as e:
            issues.append(self._check_error("aks_private_dns_unlinked", str(e)))
        return issues

    # ─────────────────────────────────────────────────────────────
    # Check 7: Azure Disk PV zone mismatch
    # ─────────────────────────────────────────────────────────────

    def _check_disk_zone_mismatch(self, meta: Dict, k8s_client) -> List[ProviderIssue]:
        """Detect pods stuck because their Azure Disk PV is in a different zone."""
        issues = []
        try:
            pvs = k8s_client.v1.list_persistent_volume().items
            pods = k8s_client.v1.list_pod_for_all_namespaces().items
            pending_pods = [p for p in pods if p.status.phase == "Pending"]

            # Build map: pvc name → PV zone label
            pv_zones: Dict[str, str] = {}
            for pv in pvs:
                if not pv.spec.claim_ref:
                    continue
                zone_label = (pv.metadata.labels or {}).get(
                    "topology.kubernetes.io/zone") or (
                    pv.metadata.labels or {}).get("failure-domain.beta.kubernetes.io/zone")
                if zone_label:
                    pv_zones[pv.spec.claim_ref.name] = zone_label

            for pod in pending_pods:
                pod_zone = (pod.metadata.labels or {}).get(
                    "topology.kubernetes.io/zone") or (
                    pod.spec.node_selector or {}).get("topology.kubernetes.io/zone")

                for vol in (pod.spec.volumes or []):
                    if not vol.persistent_volume_claim:
                        continue
                    claim = vol.persistent_volume_claim.claim_name
                    pv_zone = pv_zones.get(claim)
                    if pv_zone and pod_zone and pv_zone != pod_zone:
                        issues.append(ProviderIssue(
                            "aks_disk_zone_mismatch", "high",
                            f"Pod '{pod.metadata.namespace}/{pod.metadata.name}' "
                            f"in zone '{pod_zone}' references PVC '{claim}' "
                            f"whose disk is in zone '{pv_zone}'. "
                            "Pod will stay Pending indefinitely.",
                            "Move the pod to the same zone as the disk using nodeAffinity, "
                            "or recreate the PVC in the correct zone. "
                            "Check: kubectl get pv -o wide",
                        ))
        except Exception as e:
            issues.append(self._check_error("aks_disk_zone_mismatch", str(e)))
        return issues

    # ─────────────────────────────────────────────────────────────
    # Helpers
    # ─────────────────────────────────────────────────────────────

    @staticmethod
    def _sdk_not_available(issue_type: str, install_hint: str) -> ProviderIssue:
        return ProviderIssue(
            issue_type, "info",
            "Azure SDK not installed or credentials not configured — check skipped",
            f"To enable: {install_hint} && az login (or configure managed identity)",
        )

    @staticmethod
    def _check_error(issue_type: str, error: str) -> ProviderIssue:
        return ProviderIssue(
            issue_type, "info",
            f"Check could not complete: {error[:200]}",
            "Ensure Azure credentials are configured: az login or managed identity",
        )
