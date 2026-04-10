#!/bin/bash
set -e

echo "🚀 Welcome to the Chaos Sandbox..."
echo "📦 Starting up or using existing local cluster context..."

# We assume a kind or minikube cluster is already running as per course requirements
if ! kubectl get nodes >/dev/null 2>&1; then
    echo "❌ Error: Could not connect to a Kubernetes cluster."
    echo "💡 Please ensure 'kind' or 'minikube' is running and your KUBECONFIG is set."
    exit 1
fi

echo "🧨 Injecting Chaos..."
# We apply 5 random broken manifests from the practice directory to simulate a major cluster event
kubectl apply -f practice/01-image-pull-backoff.yaml
kubectl apply -f practice/05-missing-configmap-key.yaml
kubectl apply -f practice/11-ingress-wrong-service.yaml
kubectl apply -f practice/15-liveness-kills-healthy-app.yaml
kubectl apply -f practice/03-selector-mismatch.yaml

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
