#!/bin/bash
set -euo pipefail

NAMESPACE="practice"
MANIFESTS=(
  "practice/01-image-pull-backoff.yaml"
  "practice/05-missing-configmap-key.yaml"
  "practice/11-ingress-wrong-service.yaml"
  "practice/15-liveness-kills-healthy-app.yaml"
  "practice/03-selector-mismatch.yaml"
)

echo "🚀 Welcome to the Chaos Sandbox..."
echo "📦 Starting up or using existing local cluster context..."

# We assume a kind or minikube cluster is already running as per course requirements
if ! kubectl get nodes >/dev/null 2>&1; then
    echo "❌ Error: Could not connect to a Kubernetes cluster."
    echo "💡 Please ensure 'kind' or 'minikube' is running and your KUBECONFIG is set."
    exit 1
fi

if ! kubectl get namespace "${NAMESPACE}" >/dev/null 2>&1; then
    echo "🧱 Creating namespace '${NAMESPACE}'..."
    kubectl create namespace "${NAMESPACE}" >/dev/null
fi

echo "🧨 Injecting Chaos..."
# Apply a small bundle of intentionally broken manifests into the practice namespace.
for manifest in "${MANIFESTS[@]}"; do
    if ! kubectl apply -f "${manifest}"; then
        echo "❌ Failed while applying ${manifest}"
        exit 1
    fi
done

echo "💥 Chaos injected!"
echo ""
echo "🔥 Your cluster is now broken in 5 different ways."
echo "🎯 Your mission:"
echo "   1. Diagnose the failures using 'kubectl'"
echo "   2. Narrate your findings (Identify -> Diagnose)"
echo "   3. Make the smallest safe fix (Fix)"
echo "   4. Verify the applications are healthy (Verify)"
echo ""
echo "Good luck!"
