#!/bin/bash
# Cleanup evicted pods
set -euo pipefail

echo "🧹 Cleaning evicted pods"
kubectl get pods -A --field-selector=status.reason=Evicted -o custom-columns=NS:.metadata.namespace,NAME:.metadata.name | tail -n +2 | while read -r ns name; do
  [[ -z "$name" ]] && continue
  echo "Deleting $ns/$name"
  kubectl delete pod "$name" -n "$ns" --ignore-not-found
done

echo "✅ Complete"
