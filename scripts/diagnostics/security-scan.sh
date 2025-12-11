#!/bin/bash
# Heuristic secret scan of ConfigMaps and pod env vars
set -euo pipefail

echo "🔍 Secret Scan (heuristic)"
echo "Timestamp: $(date)"

PATTERN='(?i)(password|passwd|token|secret|key)'

echo -e "\n📜 ConfigMaps with sensitive-looking keys"
kubectl get configmaps -A -o json | jq -r --arg re "$PATTERN" '
  .items[]
  | {ns:.metadata.namespace,name:.metadata.name,data:(.data // {})}
  | select([.data | keys[]? | test($re)] | any)
  | "\(.ns)/\(.name) keys=" + ((.data | keys | map(select(test($re)))) | join(","))
' || true

echo -e "\n🧪 Pod env vars with sensitive-looking keys"
kubectl get pods -A -o json | jq -r --arg re "$PATTERN" '
  .items[]
  | {ns:.metadata.namespace,name:.metadata.name,containers:.spec.containers}
  | {ns,name,envs: (.containers[]?.env // [])}
  | select([.envs[]? | .name | test($re)] | any)
  | "\(.ns)/\(.name) envs=" + ([.envs[]? | select(.name | test($re)) | .name] | join(","))
' || true

echo -e "\n✅ Scan complete (for full coverage, run dedicated secret scanners in CI/CD and logging)"
