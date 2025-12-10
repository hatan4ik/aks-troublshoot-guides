#!/bin/bash
# Resource utilization analysis
set -euo pipefail

echo "📊 Resource Analysis"
echo "Timestamp: $(date)"

print_status() {
  local status=$1 msg=$2
  case $status in
    OK) echo "✅ $msg" ;;
    WARN) echo "⚠️  $msg" ;;
    ERR) echo "❌ $msg" ;;
  esac
}

echo -e "\n🖥️  Nodes"
kubectl top nodes 2>/dev/null || print_status WARN "metrics-server unavailable"
kubectl get nodes -o wide
kubectl describe nodes | grep -A3 -E "MemoryPressure|DiskPressure|PIDPressure" || true

echo -e "\n📦 Pods (Top consumers)"
kubectl top pods -A 2>/dev/null | head -20 || print_status WARN "metrics-server unavailable"

echo -e "\n🚦 Throttling / OOM Events"
kubectl get events -A --field-selector type=Warning --sort-by=.lastTimestamp | grep -E "KillContainer|OOMKilled|Evicted|BackOff|FailedScheduling" | tail -20 || true

echo -e "\n🛡️  Autoscaling"
kubectl get hpa -A || true
kubectl get deployment -A -o custom-columns=NS:.metadata.namespace,NAME:.metadata.name,READY:.status.readyReplicas,DESIRED:.spec.replicas | head -20

echo -e "\n✅ Done"
