#!/bin/bash
# Helm release diagnostics
set -euo pipefail

RELEASE=${1:-}
NAMESPACE=${2:-default}

if [[ -z "$RELEASE" ]]; then
  echo "Usage: $0 <release> [namespace]"
  exit 1
fi

echo "⛵ Helm Diagnostics for $NAMESPACE/$RELEASE"
helm status "$RELEASE" -n "$NAMESPACE" || true
helm history "$RELEASE" -n "$NAMESPACE" || true
echo -e "\n📜 Recent Events"
kubectl -n "$NAMESPACE" get events --sort-by=.lastTimestamp | tail -20
echo -e "\n✅ Done"
