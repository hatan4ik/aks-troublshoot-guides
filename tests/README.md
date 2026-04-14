# Test Suite

## Running the tests

```bash
# All tests
.venv/bin/python -m pytest

# Specific file
.venv/bin/python -m pytest tests/test_fixes.py
.venv/bin/python -m pytest tests/test_pattern_matcher.py

# Verbose output
.venv/bin/python -m pytest -v
```

No Kubernetes cluster required. All tests run offline.

---

## Philosophy

### Mock only the boundary, never your own logic

`AutoFixer.__init__` accepts a `k8s_client` object. In tests that object is a
`MagicMock()`. This means every test exercises the **real** filtering, allowlist,
PDB guard, and result-building logic — the only thing that is fake is the
Kubernetes API server response.

```python
fixer = AutoFixer(MagicMock(), allowed_namespaces=["default"])
fixer.k8s.v1.list_pod_for_all_namespaces.return_value.items = [pod]
```

Never patch `AutoFixer._pdb_would_be_violated` or other internal methods — that
tests the mock, not the code.

### Pure methods get direct unit tests

Methods that do not touch the k8s client are tested without any mocking:

| Method | What it covers |
|--------|---------------|
| `_categorize_api_exception` | All HTTP status codes (403/404/409/422/429/5xx) |
| `_normalize_allowed_namespaces` | Whitespace stripping, dedup, None passthrough |
| `_namespace_allowed` | Allowlist logic including `*` wildcard |
| `_skip_disallowed_namespace` | Result mutation and operation recording |
| `_find_best_source_key` | difflib fuzzy match, single-key shortcut, no-match |
| `_infer_ingress_service_name` | Prefix match, single-service shortcut, ambiguous |
| `_is_safe_to_restart` | kube-system, job pods, deletion timestamp, StatefulSet, priority class |

### Async fixer methods use dry_run=True

`dry_run=True` exercises the entire decision tree — candidate selection,
allowlist check, PDB guard, result dict construction — without any mutation.
The key assertions are:

- `fixer.k8s.v1.delete_namespaced_pod.assert_not_called()`
- The result dict contains the expected keys and values
- Skipped items appear in `results["skipped"]` with a meaningful reason string

### Pattern matcher tests are fully pure

`match()`, `match_events()`, and `match_log_lines()` operate only on strings.
No mocks at all. Tests pass realistic Kubernetes event strings:

```python
results = match("manifest unknown for image nginx:1.99.99")
assert any(pm.error_class == "bad_image_tag" for pm in results)
```

---

## Adding tests for new functionality

### New pure helper method

```python
class TestMyNewHelper:
    def test_normal_case(self):
        fixer = _make_fixer()
        assert fixer._my_new_helper("input") == "expected_output"

    def test_edge_case_returns_none(self):
        fixer = _make_fixer()
        assert fixer._my_new_helper("") is None
```

### New async fixer method

1. Find every `self.k8s.*` call the method makes.
2. Set `.return_value` on each one.
3. Call the method with `dry_run=True` and assert no mutations happened.
4. Optionally add a live-mode test by letting the mock's delete/patch calls
   succeed (default MagicMock behaviour) and assert the result reflects it.

```python
class TestMyNewFixer:
    def test_dry_run_does_not_mutate(self):
        fixer = _make_fixer()
        fixer.k8s.v1.list_something.return_value.items = [_make_some_object()]

        results = asyncio.get_event_loop().run_until_complete(
            fixer.my_new_fixer(dry_run=True)
        )

        fixer.k8s.v1.delete_something.assert_not_called()
        assert any("[DRY-RUN]" in s for s in results["fixed"])

    def test_disallowed_namespace_is_skipped(self):
        fixer = _make_fixer(allowed_namespaces=["production"])
        obj = _make_some_object(namespace="staging")
        fixer.k8s.v1.list_something.return_value.items = [obj]

        results = asyncio.get_event_loop().run_until_complete(
            fixer.my_new_fixer(dry_run=True)
        )

        assert results["fixed"] == []
        assert any("staging" in s for s in results["skipped"])

    def test_api_exception_is_categorized(self):
        fixer = _make_fixer()
        fixer.k8s.v1.list_something.return_value.items = [_make_some_object()]
        fixer.k8s.v1.delete_something.side_effect = ApiException(status=403)

        results = asyncio.get_event_loop().run_until_complete(
            fixer.my_new_fixer(dry_run=False)
        )

        assert results["failed"]
        assert results["failed"][0][...]["category"] == "forbidden"
```

### New error pattern in pattern_matcher

Add a test to `TestMatch` with the exact string that appears in a real
Kubernetes Event or container log:

```python
def test_my_new_error_class(self):
    results = match("the exact phrase from the Event message")
    assert any(pm.error_class == "my_new_error_class" for pm in results)
    pm = next(p for p in results if p.error_class == "my_new_error_class")
    assert pm.layer == "layer1"   # whichever layer applies
    assert pm.severity == "high"
```

---

## What is not covered here (intentional)

| Concern | Where it belongs |
|---------|-----------------|
| Live Kubernetes API calls | Integration tests against a real cluster (`pytest --integration`) |
| End-to-end heal → verify loop | Smoke tests in CI with `kind` or `minikube` |
| `auto_remediate` dispatch table | Covered implicitly; it only calls the leaf methods tested above |
| Provider-specific checks (AKS/EKS/GKE) | Separate `tests/test_providers/` when those grow |
