"""Provider auto-detector.

Reads node providerIDs to determine the cloud provider, then runs the
appropriate checker. Returns a structured result compatible with the
detect_common_issues() issues list format.
"""

from typing import Dict, List, Optional
from .aks import AKSChecker
from .eks import EKSChecker
from .gke import GKEChecker
from .base import BaseProviderChecker, ProviderIssue


def detect_provider(k8s_client) -> Optional[str]:
    """Return 'aks', 'eks', 'gke', or None based on node providerIDs."""
    try:
        nodes = k8s_client.v1.list_node().items
        if not nodes:
            return None
        pid = nodes[0].spec.provider_id or ""
        if pid.startswith("azure://"):
            return "aks"
        if pid.startswith("aws://"):
            return "eks"
        if pid.startswith("gce://") or pid.startswith("google://"):
            return "gke"
    except Exception:
        pass
    return None


_CHECKERS: Dict[str, BaseProviderChecker] = {
    "aks": AKSChecker(),
    "eks": EKSChecker(),
    "gke": GKEChecker(),
}


def run_provider_checks(k8s_client) -> List[Dict]:
    """Auto-detect provider and run all cloud-layer checks.

    Returns a list of issue dicts in the same format as detect_common_issues(),
    ready to be appended directly to the issues list.

    Issues with severity='info' (SDK not available) are included so the caller
    can choose to filter them from the output.
    """
    provider = detect_provider(k8s_client)
    if provider is None:
        return [{
            "type": "provider_unknown",
            "severity": "info",
            "detail": "Could not determine cloud provider from node providerIDs — "
                      "provider-specific checks skipped. "
                      "Bare metal / kubeadm / kind clusters are not provider-checked.",
            "suggested_action": (
                "kubectl get nodes -o jsonpath='{.items[*].spec.providerID}'"
            ),
        }]

    checker = _CHECKERS.get(provider)
    if checker is None:
        return []

    raw_issues: List[ProviderIssue] = checker.run_all_checks(k8s_client)

    return [
        {
            "type": issue.issue_type,
            "severity": issue.severity,
            "layer": issue.layer,
            "provider": provider,
            "detail": issue.detail,
            "suggested_action": issue.suggested_action,
        }
        for issue in raw_issues
    ]
