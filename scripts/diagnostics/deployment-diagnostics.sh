#!/bin/bash
# Deployment rollout diagnostics
set -euo pipefail

DEPLOYMENT=${1:-}
NAMESPACE=${2:-default}

if [[ -z "$DEPLOYMENT" ]]; then
  echo "Usage: $0 <deployment> [namespace]"
  exit 1
fi

echo "🚀 Deployment Diagnostics for $NAMESPACE/$DEPLOYMENT"
kubectl -n "$NAMESPACE" rollout status "deployment/$DEPLOYMENT" || true

echo -e "\n📋 Deployment Description"
kubectl -n "$NAMESPACE" describe "deployment/$DEPLOYMENT"

echo -e "\n📦 ReplicaSets"
kubectl -n "$NAMESPACE" get rs -l app="$DEPLOYMENT" -o wide || true

echo -e "\n📜 Recent Events"
kubectl -n "$NAMESPACE" get events --sort-by=.lastTimestamp | tail -20

echo -e "\n🩺 Pods"
kubectl -n "$NAMESPACE" get pods -l app="$DEPLOYMENT" -o wide || true

echo -e "\n✅ Done"
