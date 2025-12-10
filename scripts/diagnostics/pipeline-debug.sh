#!/bin/bash
# CI/CD pipeline troubleshooting helper
set -euo pipefail

echo "🔄 Pipeline Debug"
echo "Timestamp: $(date)"

echo -e "\n🧩 Environment"
echo "KUBECONFIG: ${KUBECONFIG:-default}"
which kubectl || echo "kubectl not found"

echo -e "\n📦 Registry Access"
if [[ -n "${REGISTRY:-}" ]]; then
  docker login "$REGISTRY" >/dev/null 2>&1 && echo "✅ Registry login ok for $REGISTRY" || echo "❌ Registry login failed for $REGISTRY"
else
  echo "REGISTRY env not set; skipping login test"
fi

echo -e "\n🛠️  Lint/Validate Manifests"
kubectl kustomize . >/dev/null 2>&1 && echo "✅ kustomize render ok" || echo "⚠️  kustomize render failed"
helm lint . >/dev/null 2>&1 && echo "✅ helm lint ok" || echo "⚠️  helm lint failed or chart not found"

echo -e "\n📡 Cluster Reachability"
kubectl cluster-info >/dev/null 2>&1 && echo "✅ cluster reachable" || echo "❌ cluster unreachable"

echo "✅ Pipeline debug complete"
