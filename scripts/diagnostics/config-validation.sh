#!/bin/bash
# Config validation using kubectl dry-run and drift checks
set -euo pipefail

TARGET=${1:-}

echo "🧭 Config Validation"
echo "Timestamp: $(date)"

if [[ -n "$TARGET" ]]; then
  echo -e "\n🔍 Validating manifests at: $TARGET"
  kubectl apply --dry-run=client -f "$TARGET" >/tmp/config-validate.out
  cat /tmp/config-validate.out
else
  echo -e "\nℹ️  No manifest path provided. Checking live cluster for drift signals."
fi

echo -e "\n📜 Unmanaged changes (server-side diff requires manifests)"
if [[ -n "$TARGET" ]]; then
  kubectl diff -f "$TARGET" || true
else
  echo "Provide a manifest path to run kubectl diff."
fi

echo -e "\n🛡️  ConfigMaps/Secrets with large entries (possible bloat)"
kubectl get configmaps,secrets -A -o json \
  | jq -r '.items[] | select((.data // {} | length) > 20) | "\(.kind) \(.metadata.namespace)/\(.metadata.name) entries=\((.data // {} | length))"' || true

echo -e "\n✅ Validation completed"
