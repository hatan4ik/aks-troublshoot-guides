#!/bin/bash
# Scale deployment replicas with safety checks
set -euo pipefail

DEPLOY=${1:-}
NS=${2:-default}
REPLICAS=${3:-}

if [[ -z "$DEPLOY" || -z "$REPLICAS" ]]; then
  echo "Usage: $0 <deployment> <namespace> <replicas>"
  exit 1
fi

echo "📈 Scaling $NS/$DEPLOY to $REPLICAS replicas"
kubectl -n "$NS" get deployment "$DEPLOY" || { echo "Deployment not found"; exit 1; }
kubectl -n "$NS" scale deployment "$DEPLOY" --replicas="$REPLICAS"
kubectl -n "$NS" rollout status deployment "$DEPLOY"
echo "✅ Scaled"
