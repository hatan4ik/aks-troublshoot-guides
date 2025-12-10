#!/bin/bash
# GitOps health diagnostics (Argo CD / Flux)
set -euo pipefail

echo "📦 GitOps Diagnostics"
echo "Timestamp: $(date)"

echo -e "\n🚀 Argo CD Applications (if present)"
kubectl get applications -A 2>/dev/null || echo "Argo CD not detected"

echo -e "\n🚀 Flux Kustomizations/HelmReleases (if present)"
kubectl get kustomizations -A 2>/dev/null || echo "Flux Kustomizations not detected"
kubectl get helmreleases -A 2>/dev/null || echo "Flux HelmReleases not detected"

echo -e "\n📜 Recent Controller Events"
kubectl get events -A --field-selector type=Warning --sort-by=.lastTimestamp | grep -iE "sync|git|helm|kustomize|apply" | tail -30 || true

echo -e "\n✅ Complete"
