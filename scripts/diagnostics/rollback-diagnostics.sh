#!/bin/bash
# Diagnose rollback failures for a deployment
set -euo pipefail

DEPLOY=${1:-}
NS=${2:-default}

if [[ -z "$DEPLOY" ]]; then
  echo "Usage: $0 <deployment> [namespace]"
  exit 1
fi

echo "↩️  Rollback Diagnostics for $NS/$DEPLOY"

echo -e "\n📜 Rollout history"
kubectl -n "$NS" rollout history "deployment/$DEPLOY" || true

echo -e "\n📦 ReplicaSets (current vs previous)"
kubectl -n "$NS" get rs -l app="$DEPLOY" -o wide || true

echo -e "\n🧭 Events"
kubectl -n "$NS" get events --sort-by=.lastTimestamp | tail -20

echo -e "\n🩺 Health"
kubectl -n "$NS" rollout status "deployment/$DEPLOY" || true

echo -e "\n✅ Done"
