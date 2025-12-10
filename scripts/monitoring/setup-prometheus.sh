#!/bin/bash
# Deploy Prometheus stack via kube-prometheus-stack (helm)
set -euo pipefail

RELEASE=${1:-monitoring}
NAMESPACE=${2:-monitoring}

echo "📈 Installing kube-prometheus-stack ($RELEASE) in $NAMESPACE"
kubectl create ns "$NAMESPACE" 2>/dev/null || true
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts >/dev/null
helm repo update >/dev/null
helm upgrade --install "$RELEASE" prometheus-community/kube-prometheus-stack -n "$NAMESPACE" --set grafana.enabled=true --wait

echo "✅ Prometheus/Grafana installed. Access via port-forward:"
echo "kubectl -n $NAMESPACE port-forward svc/$RELEASE-grafana 3000:80"
