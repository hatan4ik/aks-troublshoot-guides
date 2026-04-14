"""Tests for src/k8s_diagnostics/automation/fixes.py"""

import asyncio
import pytest
from unittest.mock import MagicMock, patch
from kubernetes.client.rest import ApiException

from k8s_diagnostics.automation.fixes import AutoFixer


# ── Helpers ───────────────────────────────────────────────────────────────────


def _make_pod(
    name="mypod",
    namespace="default",
    phase="Failed",
    reason=None,
    waiting_reason=None,
    owner_references=None,
    labels=None,
    deletion_timestamp=None,
    priority_class=None,
    restart_count=0,
):
    pod = MagicMock()
    pod.metadata.name = name
    pod.metadata.namespace = namespace
    pod.metadata.labels = labels or {}
    pod.metadata.deletion_timestamp = deletion_timestamp
    pod.metadata.owner_references = owner_references or []
    pod.spec.priority_class_name = priority_class

    pod.status.phase = phase
    pod.status.reason = reason
    pod.status.conditions = []

    cs = MagicMock()
    cs.state.waiting.reason = waiting_reason
    cs.restart_count = restart_count
    pod.status.container_statuses = [cs]
    return pod


def _make_api_exception(status: int, body: str = "error body") -> ApiException:
    exc = ApiException(status=status, reason=body)
    exc.status = status
    exc.body = body
    return exc


def _make_fixer(allowed_namespaces=None):
    k8s = MagicMock()
    return AutoFixer(k8s, allowed_namespaces=allowed_namespaces)


# ── _normalize_allowed_namespaces ─────────────────────────────────────────────


class TestNormalizeAllowedNamespaces:
    def test_none_returns_none(self):
        fixer = _make_fixer()
        assert fixer.allowed_namespaces is None

    def test_empty_list_returns_none(self):
        fixer = _make_fixer([])
        assert fixer.allowed_namespaces is None

    def test_whitespace_only_entries_stripped(self):
        fixer = _make_fixer(["  ", "default", "  "])
        assert fixer.allowed_namespaces == {"default"}

    def test_strips_whitespace_from_individual_namespaces(self):
        fixer = _make_fixer(["  default  ", " production "])
        assert "default" in fixer.allowed_namespaces
        assert "production" in fixer.allowed_namespaces

    def test_returns_set_not_list(self):
        fixer = _make_fixer(["a", "b", "a"])
        assert isinstance(fixer.allowed_namespaces, set)


# ── _namespace_allowed ────────────────────────────────────────────────────────


class TestNamespaceAllowed:
    def test_none_allows_everything(self):
        fixer = _make_fixer(None)
        assert fixer._namespace_allowed("anything")
        assert fixer._namespace_allowed("kube-system")

    def test_wildcard_allows_everything(self):
        fixer = _make_fixer(["*"])
        assert fixer._namespace_allowed("any-ns")

    def test_explicit_namespace_in_allowlist(self):
        fixer = _make_fixer(["default", "production"])
        assert fixer._namespace_allowed("default")
        assert fixer._namespace_allowed("production")

    def test_namespace_not_in_allowlist(self):
        fixer = _make_fixer(["default"])
        assert not fixer._namespace_allowed("staging")


# ── _skip_disallowed_namespace ────────────────────────────────────────────────


class TestSkipDisallowedNamespace:
    def test_allowed_namespace_returns_false_and_does_not_modify_results(self):
        fixer = _make_fixer(["default"])
        results = {"dry_run": False, "skipped": [], "operations": []}
        assert fixer._skip_disallowed_namespace(results, "default", "pod/default/mypod") is False
        assert results["skipped"] == []
        assert results["operations"] == []

    def test_disallowed_namespace_returns_true(self):
        fixer = _make_fixer(["default"])
        results = {"dry_run": False, "skipped": [], "operations": []}
        assert fixer._skip_disallowed_namespace(results, "staging", "pod/staging/mypod") is True

    def test_disallowed_namespace_appends_to_skipped(self):
        fixer = _make_fixer(["default"])
        results = {"dry_run": False, "skipped": [], "operations": []}
        fixer._skip_disallowed_namespace(results, "staging", "pod/staging/mypod")
        assert any("staging" in s for s in results["skipped"])

    def test_disallowed_namespace_appends_operation(self):
        fixer = _make_fixer(["default"])
        results = {"dry_run": False, "skipped": [], "operations": []}
        fixer._skip_disallowed_namespace(results, "staging", "pod/staging/mypod")
        assert len(results["operations"]) == 1
        assert results["operations"][0]["status"] == "skipped"

    def test_none_allowlist_always_returns_false(self):
        fixer = _make_fixer(None)
        results = {"dry_run": False, "skipped": [], "operations": []}
        assert fixer._skip_disallowed_namespace(results, "any-ns", "pod/any-ns/p") is False


# ── _categorize_api_exception ─────────────────────────────────────────────────


class TestCategorizeApiException:
    def _exc(self, status):
        return _make_api_exception(status)

    def test_403_forbidden(self):
        result = AutoFixer._categorize_api_exception(self._exc(403))
        assert result["category"] == "forbidden"
        assert result["http_status"] == 403
        assert "RBAC" in result["hint"] or "ClusterRole" in result["hint"]

    def test_404_not_found(self):
        result = AutoFixer._categorize_api_exception(self._exc(404))
        assert result["category"] == "not_found"
        assert result["http_status"] == 404

    def test_409_conflict(self):
        result = AutoFixer._categorize_api_exception(self._exc(409))
        assert result["category"] == "conflict"
        assert "retry" in result["hint"].lower()

    def test_422_invalid_patch(self):
        result = AutoFixer._categorize_api_exception(self._exc(422))
        assert result["category"] == "invalid_patch"

    def test_429_rate_limited(self):
        result = AutoFixer._categorize_api_exception(self._exc(429))
        assert result["category"] == "rate_limited_or_unavailable"

    def test_503_rate_limited_or_unavailable(self):
        result = AutoFixer._categorize_api_exception(self._exc(503))
        assert result["category"] == "rate_limited_or_unavailable"

    def test_500_server_error(self):
        result = AutoFixer._categorize_api_exception(self._exc(500))
        assert result["category"] == "server_error"

    def test_502_server_error(self):
        result = AutoFixer._categorize_api_exception(self._exc(502))
        assert result["category"] == "server_error"

    def test_unknown_status(self):
        result = AutoFixer._categorize_api_exception(self._exc(418))
        assert result["category"] == "unknown"

    def test_result_always_has_required_keys(self):
        for status in (403, 404, 409, 422, 429, 500, 503):
            result = AutoFixer._categorize_api_exception(self._exc(status))
            assert "http_status" in result
            assert "category" in result
            assert "hint" in result
            assert "detail" in result


# ── _pdb_would_be_violated ────────────────────────────────────────────────────


class TestPdbWouldBeViolated:
    def _make_pdb(self, match_labels, disruptions_allowed, min_available=1, pdb_name="my-pdb"):
        pdb = MagicMock()
        pdb.metadata.name = pdb_name
        pdb.metadata.namespace = "default"
        pdb.spec.selector.match_labels = match_labels
        pdb.spec.min_available = min_available
        pdb.spec.max_unavailable = None
        pdb.status.disruptions_allowed = disruptions_allowed
        return pdb

    def test_returns_none_when_no_pdbs(self):
        fixer = _make_fixer()
        fixer.k8s.policy_v1.list_namespaced_pod_disruption_budget.return_value.items = []
        pod = _make_pod(labels={"app": "myapp"})
        assert fixer._pdb_would_be_violated(pod) is None

    def test_returns_none_when_pdb_does_not_match_pod_labels(self):
        fixer = _make_fixer()
        pdb = self._make_pdb({"app": "otherapp"}, disruptions_allowed=0)
        fixer.k8s.policy_v1.list_namespaced_pod_disruption_budget.return_value.items = [pdb]
        pod = _make_pod(labels={"app": "myapp"})
        assert fixer._pdb_would_be_violated(pod) is None

    def test_returns_none_when_disruptions_allowed_is_positive(self):
        fixer = _make_fixer()
        pdb = self._make_pdb({"app": "myapp"}, disruptions_allowed=1)
        fixer.k8s.policy_v1.list_namespaced_pod_disruption_budget.return_value.items = [pdb]
        pod = _make_pod(labels={"app": "myapp"})
        assert fixer._pdb_would_be_violated(pod) is None

    def test_returns_reason_string_when_zero_disruptions_allowed(self):
        fixer = _make_fixer()
        pdb = self._make_pdb({"app": "myapp"}, disruptions_allowed=0)
        fixer.k8s.policy_v1.list_namespaced_pod_disruption_budget.return_value.items = [pdb]
        pod = _make_pod(labels={"app": "myapp"})
        reason = fixer._pdb_would_be_violated(pod)
        assert reason is not None
        assert "my-pdb" in reason
        assert "0 disruptions" in reason

    def test_returns_none_when_api_exception_raised(self):
        fixer = _make_fixer()
        fixer.k8s.policy_v1.list_namespaced_pod_disruption_budget.side_effect = ApiException(status=403)
        pod = _make_pod(labels={"app": "myapp"})
        assert fixer._pdb_would_be_violated(pod) is None

    def test_returns_none_when_policy_v1_missing(self):
        fixer = _make_fixer()
        fixer.k8s.policy_v1.list_namespaced_pod_disruption_budget.side_effect = AttributeError
        pod = _make_pod(labels={"app": "myapp"})
        assert fixer._pdb_would_be_violated(pod) is None

    def test_pdb_with_empty_match_labels_is_skipped(self):
        fixer = _make_fixer()
        pdb = self._make_pdb({}, disruptions_allowed=0)
        fixer.k8s.policy_v1.list_namespaced_pod_disruption_budget.return_value.items = [pdb]
        pod = _make_pod(labels={"app": "myapp"})
        assert fixer._pdb_would_be_violated(pod) is None


# ── _is_safe_to_restart ───────────────────────────────────────────────────────


class TestIsSafeToRestart:
    def test_regular_pod_in_default_namespace_is_safe(self):
        fixer = _make_fixer()
        pod = _make_pod(namespace="default", owner_references=[MagicMock(kind="ReplicaSet")])
        assert fixer._is_safe_to_restart(pod) is True

    def test_kube_system_pod_is_not_safe(self):
        fixer = _make_fixer()
        pod = _make_pod(namespace="kube-system")
        assert fixer._is_safe_to_restart(pod) is False

    def test_kube_public_pod_is_not_safe(self):
        fixer = _make_fixer()
        pod = _make_pod(namespace="kube-public")
        assert fixer._is_safe_to_restart(pod) is False

    def test_job_pod_is_not_safe(self):
        fixer = _make_fixer()
        pod = _make_pod(labels={"job-name": "my-job"})
        assert fixer._is_safe_to_restart(pod) is False

    def test_pod_with_deletion_timestamp_is_not_safe(self):
        fixer = _make_fixer()
        pod = _make_pod(deletion_timestamp="2024-01-01T00:00:00Z")
        assert fixer._is_safe_to_restart(pod) is False

    def test_system_cluster_critical_is_not_safe(self):
        fixer = _make_fixer()
        pod = _make_pod(priority_class="system-cluster-critical")
        assert fixer._is_safe_to_restart(pod) is False

    def test_statefulset_pod_is_not_safe(self):
        fixer = _make_fixer()
        owner = MagicMock()
        owner.kind = "StatefulSet"
        pod = _make_pod(owner_references=[owner])
        assert fixer._is_safe_to_restart(pod) is False


# ── _find_best_source_key ────────────────────────────────────────────────────


class TestFindBestSourceKey:
    def test_returns_none_for_empty_list(self):
        fixer = _make_fixer()
        assert fixer._find_best_source_key("KEY", []) is None

    def test_returns_only_key_if_single_available(self):
        fixer = _make_fixer()
        assert fixer._find_best_source_key("MISSING_KEY", ["ONLY_KEY"]) == "ONLY_KEY"

    def test_returns_close_match(self):
        fixer = _make_fixer()
        result = fixer._find_best_source_key("DATABASE_URL", ["DATABASE_URL_PROD", "REDIS_URL", "DB_URL"])
        assert result is not None

    def test_returns_none_when_no_close_match(self):
        fixer = _make_fixer()
        result = fixer._find_best_source_key("COMPLETELY_DIFFERENT", ["ABC", "XYZ"])
        assert result is None


# ── _infer_ingress_service_name ───────────────────────────────────────────────


class TestInferIngressServiceName:
    def test_returns_single_service_when_only_one(self):
        fixer = _make_fixer()
        assert fixer._infer_ingress_service_name("myapp", {"myservice"}) == "myservice"

    def test_returns_service_prefixed_with_ingress_name(self):
        fixer = _make_fixer()
        result = fixer._infer_ingress_service_name("myapp", {"myapp-svc", "other-svc"})
        assert result == "myapp-svc"

    def test_returns_none_when_ambiguous(self):
        fixer = _make_fixer()
        result = fixer._infer_ingress_service_name("myapp", {"myapp-blue", "myapp-green"})
        assert result is None

    def test_returns_none_for_empty_service_names(self):
        fixer = _make_fixer()
        result = fixer._infer_ingress_service_name("myapp", set())
        assert result is None


# ── restart_failed_pods (dry_run=True) ────────────────────────────────────────


class TestRestartFailedPodsDryRun:
    def _make_candidate_pod(self, ns="default", name="bad-pod", owner=True):
        owner_ref = MagicMock()
        owner_ref.kind = "ReplicaSet"
        pod = _make_pod(
            name=name,
            namespace=ns,
            phase="Failed",
            owner_references=[owner_ref] if owner else [],
        )
        return pod

    def test_dry_run_returns_planned_operations(self):
        fixer = _make_fixer()
        pod = self._make_candidate_pod()
        fixer.k8s.v1.list_pod_for_all_namespaces.return_value.items = [pod]
        fixer.k8s.policy_v1.list_namespaced_pod_disruption_budget.return_value.items = []

        results = asyncio.get_event_loop().run_until_complete(
            fixer.restart_failed_pods(dry_run=True)
        )

        assert results["dry_run"] is True
        assert any("[DRY-RUN]" in s for s in results["restarted"])
        assert all(op["status"] == "planned" for op in results["operations"])
        fixer.k8s.v1.delete_namespaced_pod.assert_not_called()

    def test_pod_without_controller_is_skipped(self):
        fixer = _make_fixer()
        pod = self._make_candidate_pod(owner=False)
        fixer.k8s.v1.list_pod_for_all_namespaces.return_value.items = [pod]

        results = asyncio.get_event_loop().run_until_complete(
            fixer.restart_failed_pods(dry_run=True)
        )

        assert any("no controller" in s for s in results["skipped"])

    def test_kube_system_pod_is_excluded(self):
        fixer = _make_fixer()
        pod = self._make_candidate_pod(ns="kube-system")
        fixer.k8s.v1.list_pod_for_all_namespaces.return_value.items = [pod]

        results = asyncio.get_event_loop().run_until_complete(
            fixer.restart_failed_pods(dry_run=True)
        )

        assert results["restarted"] == []
        assert results["skipped"] == []

    def test_disallowed_namespace_is_skipped(self):
        fixer = _make_fixer(allowed_namespaces=["production"])
        pod = self._make_candidate_pod(ns="staging")
        fixer.k8s.v1.list_pod_for_all_namespaces.return_value.items = [pod]

        results = asyncio.get_event_loop().run_until_complete(
            fixer.restart_failed_pods(dry_run=True)
        )

        assert any("staging" in s for s in results["skipped"])

    def test_pdb_violation_skips_pod(self):
        fixer = _make_fixer()
        pod = self._make_candidate_pod()
        pod.metadata.labels = {"app": "myapp"}
        fixer.k8s.v1.list_pod_for_all_namespaces.return_value.items = [pod]

        pdb = MagicMock()
        pdb.metadata.name = "my-pdb"
        pdb.metadata.namespace = "default"
        pdb.spec.selector.match_labels = {"app": "myapp"}
        pdb.spec.min_available = 2
        pdb.spec.max_unavailable = None
        pdb.status.disruptions_allowed = 0
        fixer.k8s.policy_v1.list_namespaced_pod_disruption_budget.return_value.items = [pdb]

        results = asyncio.get_event_loop().run_until_complete(
            fixer.restart_failed_pods(dry_run=True)
        )

        assert results["restarted"] == []
        assert any("my-pdb" in s for s in results["skipped"])

    def test_no_candidates_returns_empty_lists(self):
        fixer = _make_fixer()
        fixer.k8s.v1.list_pod_for_all_namespaces.return_value.items = []

        results = asyncio.get_event_loop().run_until_complete(
            fixer.restart_failed_pods(dry_run=True)
        )

        assert results["restarted"] == []
        assert results["skipped"] == []
        assert results["failed"] == []


# ── cleanup_evicted_pods (dry_run=True) ───────────────────────────────────────


class TestCleanupEvictedPodsDryRun:
    def _make_evicted_pod(self, ns="default", name="evicted-pod"):
        pod = _make_pod(name=name, namespace=ns, phase="Failed", reason="Evicted")
        return pod

    def test_dry_run_does_not_call_delete(self):
        fixer = _make_fixer()
        pod = self._make_evicted_pod()
        fixer.k8s.v1.list_pod_for_all_namespaces.return_value.items = [pod]

        results = asyncio.get_event_loop().run_until_complete(
            fixer.cleanup_evicted_pods(dry_run=True)
        )

        fixer.k8s.v1.delete_namespaced_pod.assert_not_called()
        assert any("[DRY-RUN]" in s for s in results["cleaned"])

    def test_disallowed_namespace_skipped(self):
        fixer = _make_fixer(allowed_namespaces=["production"])
        pod = self._make_evicted_pod(ns="staging")
        fixer.k8s.v1.list_pod_for_all_namespaces.return_value.items = [pod]

        results = asyncio.get_event_loop().run_until_complete(
            fixer.cleanup_evicted_pods(dry_run=True)
        )

        assert results["cleaned"] == []


# ── scale_resources ───────────────────────────────────────────────────────────


class TestScaleResources:
    def test_dry_run_returns_current_and_would_set(self):
        fixer = _make_fixer()
        dep = MagicMock()
        dep.spec.replicas = 2
        fixer.k8s.apps_v1.read_namespaced_deployment.return_value = dep

        result = asyncio.get_event_loop().run_until_complete(
            fixer.scale_resources("default", "myapp", 5, dry_run=True)
        )

        assert result["dry_run"] is True
        assert result["current_replicas"] == 2
        assert result["would_set_replicas"] == 5
        fixer.k8s.apps_v1.patch_namespaced_deployment.assert_not_called()

    def test_disallowed_namespace_returns_skipped(self):
        fixer = _make_fixer(allowed_namespaces=["production"])
        result = asyncio.get_event_loop().run_until_complete(
            fixer.scale_resources("staging", "myapp", 3, dry_run=True)
        )
        assert result["status"] == "skipped"

    def test_api_exception_returns_categorized_error(self):
        fixer = _make_fixer()
        fixer.k8s.apps_v1.read_namespaced_deployment.side_effect = _make_api_exception(404)

        result = asyncio.get_event_loop().run_until_complete(
            fixer.scale_resources("default", "missing-dep", 2)
        )

        assert "error" in result
        assert result["error"]["category"] == "not_found"


# ── apply_resource_limits ─────────────────────────────────────────────────────


class TestApplyResourceLimits:
    def test_dry_run_returns_would_set_limits(self):
        fixer = _make_fixer()
        container = MagicMock()
        container.name = "app"
        dep = MagicMock()
        dep.spec.template.spec.containers = [container]
        fixer.k8s.apps_v1.read_namespaced_deployment.return_value = dep

        result = asyncio.get_event_loop().run_until_complete(
            fixer.apply_resource_limits("default", "myapp", "500m", "512Mi", dry_run=True)
        )

        assert result["dry_run"] is True
        assert result["would_set_limits"] == {"cpu": "500m", "memory": "512Mi"}
        fixer.k8s.apps_v1.patch_namespaced_deployment.assert_not_called()

    def test_disallowed_namespace_returns_skipped(self):
        fixer = _make_fixer(allowed_namespaces=["production"])
        result = asyncio.get_event_loop().run_until_complete(
            fixer.apply_resource_limits("staging", "myapp", "100m", "128Mi")
        )
        assert result["status"] == "skipped"


# ── fix_oomkilled_pods ────────────────────────────────────────────────────────


class TestFixOOMKilledPods:
    def _make_oom_pod(self, ns="default", name="oom-pod", container_name="app"):
        pod = _make_pod(name=name, namespace=ns, phase="Failed")
        cs = MagicMock()
        cs.name = container_name
        cs.state.terminated.reason = "OOMKilled"
        pod.status.container_statuses = [cs]
        return pod

    def test_dry_run_patches_oomkilled(self):
        fixer = _make_fixer()
        pod = self._make_oom_pod()
        pod.metadata.labels = {"app": "myapp"}
        fixer.k8s.v1.list_pod_for_all_namespaces.return_value.items = [pod]

        dep = MagicMock()
        dep.metadata.name = "myapp"
        dep.metadata.namespace = "default"
        dep.spec.selector.match_labels = {"app": "myapp"}
        container = MagicMock()
        container.name = "app"
        container.resources.limits = {"memory": "256Mi"}
        dep.spec.template.spec.containers = [container]
        
        fixer.k8s.apps_v1.list_namespaced_deployment.return_value.items = [dep]

        result = asyncio.get_event_loop().run_until_complete(
            fixer.fix_oomkilled_pods(dry_run=True)
        )

        assert result["dry_run"] is True
        assert len(result["patched"]) == 1
        assert "512Mi" in result["patched"][0]
        fixer.k8s.apps_v1.patch_namespaced_deployment.assert_not_called()
