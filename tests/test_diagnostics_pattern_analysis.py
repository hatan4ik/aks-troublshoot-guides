"""Tests for diagnostics pattern analysis integration."""

from types import SimpleNamespace
from unittest.mock import MagicMock

from k8s_diagnostics.automation.diagnostics import DiagnosticsEngine


def test_pattern_analysis_reads_init_container_logs():
    k8s = MagicMock()
    k8s.v1.read_namespaced_pod_log.return_value = (
        "config-service not ready, retrying in 2s...\n"
    )

    pod = MagicMock()
    pod.metadata.name = "nginx-app-abc"
    pod.status.init_container_statuses = [MagicMock(name="status")]
    pod.status.init_container_statuses[0].name = "init-config"
    pod.status.container_statuses = []

    engine = DiagnosticsEngine(k8s)
    results = engine._pattern_analyse_pod(pod, [], "interview")

    assert any(r["error_class"] == "init_dependency_service_missing" for r in results)
    k8s.v1.read_namespaced_pod_log.assert_called_once_with(
        "nginx-app-abc",
        "interview",
        container="init-config",
        tail_lines=150,
    )


def test_find_init_container_blockers_reports_non_completed_init_container():
    pod = SimpleNamespace(
        metadata=SimpleNamespace(namespace="interview", name="nginx-app-abc"),
        status=SimpleNamespace(
            init_container_statuses=[
                SimpleNamespace(
                    name="init-config",
                    state=SimpleNamespace(
                        running=SimpleNamespace(started_at="now"),
                        waiting=None,
                        terminated=None,
                    ),
                )
            ]
        ),
    )

    engine = DiagnosticsEngine(MagicMock())
    blockers = engine._find_init_container_blockers([pod])

    assert blockers == ["interview/nginx-app-abc (init: init-config, state: running)"]
