"""Tests for src/k8s_diagnostics/analysis/pattern_matcher.py"""

import pytest
from unittest.mock import MagicMock

from k8s_diagnostics.analysis.pattern_matcher import (
    PatternMatch,
    match,
    match_events,
    match_log_lines,
)


# ── match() ──────────────────────────────────────────────────────────────────


class TestMatch:
    def test_returns_empty_list_for_unrecognised_text(self):
        assert match("everything is fine, no errors here") == []

    def test_bad_image_tag_manifest_unknown(self):
        results = match("Failed to pull image: manifest unknown")
        assert len(results) == 1
        pm = results[0]
        assert pm.layer == "layer1"
        assert pm.error_class == "bad_image_tag"
        assert pm.severity == "high"

    def test_bad_image_tag_not_found_repository(self):
        results = match("not found: repository does not exist")
        assert any(pm.error_class == "bad_image_tag" for pm in results)

    def test_image_pull_auth_401(self):
        results = match("401 Unauthorized when pulling image from registry.io")
        assert any(pm.error_class == "image_pull_auth" for pm in results)

    def test_image_pull_auth_authentication_required(self):
        results = match("authentication required to access private registry")
        assert any(pm.error_class == "image_pull_auth" for pm in results)

    def test_image_pull_network_timeout(self):
        results = match("connection timed out during pull from registry:443")
        assert any(pm.error_class == "image_pull_network" for pm in results)
        pm = next(p for p in results if p.error_class == "image_pull_network")
        assert pm.layer == "layer5"

    def test_image_pull_backoff(self):
        results = match("Back-off pulling image nginx:1.99.99")
        assert any(pm.error_class == "image_pull_backoff" for pm in results)

    def test_image_never_pull(self):
        results = match("ErrImageNeverPull: image not present locally")
        assert any(pm.error_class == "image_never_pull" for pm in results)

    def test_bad_entrypoint(self):
        results = match("executable file not found in $PATH: /bin/app")
        assert any(pm.error_class == "bad_entrypoint" for pm in results)

    def test_entrypoint_permission(self):
        results = match("permission denied exec /entrypoint.sh")
        assert any(pm.error_class == "entrypoint_permission" for pm in results)

    def test_configmap_key_missing(self):
        results = match("couldn't find key DATABASE_URL in ConfigMap app-config")
        assert any(pm.error_class == "configmap_key_missing" for pm in results)

    def test_secret_missing(self):
        results = match('secret "app-secret" not found in namespace default')
        assert any(pm.error_class == "secret_missing" for pm in results)

    def test_configmap_missing(self):
        results = match('configmap "app-config" not found')
        assert any(pm.error_class == "configmap_missing" for pm in results)

    def test_configmap_cache_sync_timeout_is_not_configmap_missing(self):
        results = match(
            'MountVolume.SetUp failed for volume "nginx-config" : '
            "failed to sync configmap cache: timed out waiting for the condition"
        )
        assert any(pm.error_class == "configmap_cache_sync_timeout" for pm in results)
        pm = next(p for p in results if p.error_class == "configmap_cache_sync_timeout")
        assert pm.layer == "layer4"
        assert pm.confidence == "medium"

    def test_liveness_probe_killing_pod(self):
        results = match("Liveness probe failed: HTTP probe failed with statuscode: 500, killing container")
        assert any(pm.error_class == "liveness_killing_pod" for pm in results)

    def test_readiness_probe_404(self):
        results = match("Readiness probe failed: HTTP probe failed with statuscode: 404")
        assert any(pm.error_class == "probe_path_404" for pm in results)

    def test_readiness_probe_connection_refused(self):
        results = match("Readiness probe failed: dial tcp connection refused")
        assert any(pm.error_class == "probe_port_refused" for pm in results)

    def test_startup_probe_failed(self):
        results = match("Startup probe failed: connection refused on port 8080")
        assert any(pm.error_class == "startup_probe_failed" for pm in results)

    def test_init_dependency_service_not_ready_log(self):
        results = match("config-service not ready, retrying in 2s...")
        assert any(pm.error_class == "init_dependency_service_missing" for pm in results)

    def test_init_dependency_service_not_found(self):
        results = match('services "config-service" not found')
        assert any(pm.error_class == "init_dependency_service_missing" for pm in results)

    def test_match_is_case_insensitive(self):
        results = match("MANIFEST UNKNOWN when pulling image")
        assert any(pm.error_class == "bad_image_tag" for pm in results)

    def test_matched_text_truncated_at_200_chars(self):
        long_text = "manifest unknown " + "x" * 300
        results = match(long_text)
        assert len(results) > 0
        assert len(results[0].matched_text) <= 200

    def test_deduplication_same_error_class_not_repeated(self):
        # Two different phrases that both map to bad_image_tag
        text = "manifest unknown and also tag does not exist"
        results = match(text)
        error_classes = [pm.error_class for pm in results]
        assert len(error_classes) == len(set(error_classes)), "Duplicate error_class in results"

    def test_patternmatch_fields_populated(self):
        results = match("manifest unknown")
        pm = results[0]
        assert pm.layer
        assert pm.error_class
        assert pm.severity
        assert pm.signal
        assert pm.root_cause
        assert pm.next_command
        assert pm.fix_command
        assert pm.fix_description
        assert pm.confidence in ("high", "medium")


# ── match_events() ────────────────────────────────────────────────────────────


class TestMatchEvents:
    def test_empty_list_returns_empty(self):
        assert match_events([]) == []

    def test_kubernetes_client_event_object(self):
        event = MagicMock()
        event.message = "manifest unknown"
        event.reason = "Failed"
        results = match_events([event])
        assert any(pm.error_class == "bad_image_tag" for pm in results)

    def test_dict_event(self):
        results = match_events([{"message": "Back-off pulling image", "reason": "BackOff"}])
        assert any(pm.error_class == "image_pull_backoff" for pm in results)

    def test_skips_non_event_objects(self):
        # Neither has `.message` nor is a dict — should be skipped gracefully
        results = match_events([42, None, object()])
        assert results == []

    def test_deduplication_across_events(self):
        events = [
            {"message": "manifest unknown for image foo", "reason": "Failed"},
            {"message": "manifest unknown for image bar", "reason": "Failed"},
        ]
        results = match_events(events)
        error_classes = [pm.error_class for pm in results]
        assert error_classes.count("bad_image_tag") == 1

    def test_combines_reason_and_message(self):
        event = MagicMock()
        event.message = "probe status 503"
        event.reason = "Liveness probe failed"
        results = match_events([event])
        assert any(pm.error_class == "liveness_killing_pod" for pm in results)

    def test_failedmount_configmap_cache_timeout_event(self):
        event = MagicMock()
        event.message = (
            'MountVolume.SetUp failed for volume "nginx-config" : '
            "failed to sync configmap cache: timed out waiting for the condition"
        )
        event.reason = "FailedMount"
        results = match_events([event])
        assert any(pm.error_class == "configmap_cache_sync_timeout" for pm in results)

    def test_multiple_event_types_detected(self):
        events = [
            {"message": "manifest unknown", "reason": "Failed"},
            {"message": "Liveness probe failed", "reason": "Unhealthy"},
        ]
        results = match_events(events)
        classes = {pm.error_class for pm in results}
        assert "bad_image_tag" in classes
        assert "liveness_killing_pod" in classes


# ── match_log_lines() ─────────────────────────────────────────────────────────


class TestMatchLogLines:
    def test_empty_string_returns_empty(self):
        assert match_log_lines("") == []

    def test_single_line_match(self):
        results = match_log_lines("manifest unknown for latest")
        assert any(pm.error_class == "bad_image_tag" for pm in results)

    def test_multiline_first_matching_line_wins(self):
        log = "\n".join([
            "2024-01-01T00:00:00Z INFO starting server",
            "2024-01-01T00:00:01Z ERROR manifest unknown for image nginx:99",
            "2024-01-01T00:00:02Z ERROR Back-off pulling image nginx:99",
        ])
        results = match_log_lines(log)
        classes = {pm.error_class for pm in results}
        assert "bad_image_tag" in classes
        assert "image_pull_backoff" in classes

    def test_init_dependency_service_not_ready_line(self):
        log = "config-service not ready, retrying in 2s...\n"
        results = match_log_lines(log)
        assert any(pm.error_class == "init_dependency_service_missing" for pm in results)

    def test_skips_blank_lines(self):
        log = "\n\n\nmanifest unknown\n\n"
        results = match_log_lines(log)
        assert len(results) == 1

    def test_deduplication_across_lines(self):
        log = "manifest unknown foo\nmanifest unknown bar\n"
        results = match_log_lines(log)
        assert sum(1 for pm in results if pm.error_class == "bad_image_tag") == 1
