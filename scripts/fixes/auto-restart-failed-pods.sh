#!/bin/bash
# Restart failed/CrashLoop pods that are controller-managed
set -euo pipefail

echo "🔄 Auto-restart failed pods"
pods=$(kubectl get pods -A --field-selector=status.phase!=Running,status.phase!=Succeeded -o jsonpath='{range .items[*]}{.metadata.namespace}{" "}{.metadata.name}{" "}{@.status.phase}{" "}{.metadata.ownerReferences[*].kind}{"\n"}{end}')

while read -r ns name phase owner; do
  [[ -z "$name" ]] && continue
  if [[ -z "$owner" ]]; then
    echo "Skipping $ns/$name (no controller)"
    continue
  fi
  echo "Deleting $ns/$name ($phase) to trigger restart"
  kubectl delete pod "$name" -n "$ns" --grace-period=0 --force
done <<< "$pods"

echo "✅ Complete"
