#!/bin/bash
# Restart unhealthy CoreDNS pods and validate DNS
set -euo pipefail

echo "🌐 Fixing DNS (CoreDNS)"

unhealthy=$(kubectl get pods -n kube-system -l k8s-app=kube-dns --no-headers 2>/dev/null | grep -v Running | awk '{print $1}')
for pod in $unhealthy; do
  echo "Deleting CoreDNS pod $pod"
  kubectl delete pod "$pod" -n kube-system
done

echo "Testing DNS resolution"
kubectl run dns-quicktest --image=busybox --rm -it --restart=Never -- nslookup kubernetes.default || echo "⚠️  DNS test failed"

echo "✅ Complete"
