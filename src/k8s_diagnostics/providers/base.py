"""Abstract base class for cloud provider diagnostic checks."""
from abc import ABC, abstractmethod
from typing import Dict, List


class ProviderIssue:
    """A single detected provider-layer issue."""

    def __init__(
        self,
        issue_type: str,
        severity: str,
        detail: str,
        suggested_action: str,
        layer: str = "layer5",
    ):
        self.issue_type = issue_type
        self.severity = severity
        self.detail = detail
        self.suggested_action = suggested_action
        self.layer = layer

    def to_dict(self) -> Dict:
        return {
            "type": self.issue_type,
            "severity": self.severity,
            "layer": self.layer,
            "detail": self.detail,
            "suggested_action": self.suggested_action,
        }


class BaseProviderChecker(ABC):
    """All provider checkers implement this interface.

    Each check method returns a list of ProviderIssue objects.
    Checks must be self-contained: if the required SDK is not installed
    or credentials are not present, they must return [] rather than raise.
    """

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Short name: 'aks', 'eks', 'gke'."""

    @abstractmethod
    def run_all_checks(self, k8s_client) -> List[ProviderIssue]:
        """Run all provider checks and return a flat list of issues.

        Args:
            k8s_client: The K8sClient instance (for reading cluster metadata).
        """
