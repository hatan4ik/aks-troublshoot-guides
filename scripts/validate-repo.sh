#!/bin/bash
set -euo pipefail

export PYTHONPYCACHEPREFIX="${PYTHONPYCACHEPREFIX:-${TMPDIR:-/tmp}/k8s-diagnostics-pycache}"
mkdir -p "${PYTHONPYCACHEPREFIX}"

echo "==> Python syntax"
python3 -m compileall -q k8s-diagnostics-cli.py src

echo "==> Shell syntax"
while IFS= read -r -d '' script; do
  bash -n "$script"
done < <(find scripts -type f -name '*.sh' -print0)

echo "==> YAML parse"
YAML_PYTHON="${YAML_PYTHON:-python3}"
if ! "${YAML_PYTHON}" -c "import yaml" >/dev/null 2>&1; then
  if [ -x ".venv/bin/python" ] && .venv/bin/python -c "import yaml" >/dev/null 2>&1; then
    YAML_PYTHON=".venv/bin/python"
  else
    echo "[WARN] PyYAML not installed; skipping YAML parse. Install requirements or use YAML_PYTHON=/path/to/python."
    YAML_PYTHON=""
  fi
fi

if [ -n "${YAML_PYTHON}" ]; then
  "${YAML_PYTHON}" - <<'PY'
import pathlib
import yaml

files = list(pathlib.Path(".").rglob("*.yaml")) + list(pathlib.Path(".").rglob("*.yml"))
for path in files:
    with path.open() as handle:
        list(yaml.safe_load_all(handle))
print(f"parsed {len(files)} YAML files")
PY
fi

echo "==> Markdown links"
python3 scripts/validate-links.py

echo "==> Kustomize render"
kubectl kustomize gitops-demo/apps/argocd-app >/dev/null
kubectl kustomize gitops-demo/apps/flux-app >/dev/null

echo "Validation passed."
