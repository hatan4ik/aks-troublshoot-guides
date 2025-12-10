#!/bin/bash
# Performance bottleneck analysis
set -euo pipefail

echo "🚀 Performance Analysis"
echo "Timestamp: $(date)"

status() { echo "$1 $2"; }

echo -e "\n📈 Node & Pod Usage"
kubectl top nodes 2>/dev/null || status "⚠️" "metrics-server unavailable"
kubectl top pods -A 2>/dev/null | head -30 || true

echo -e "\n⏱️  Throttling Indicators"
kubectl describe nodes | grep -A2 -i "cpu throttling" || true
kubectl get events -A --field-selector type=Warning --sort-by=.lastTimestamp | grep -i "throttle" | tail -20 || true

echo -e "\n📊 Autoscaling State"
kubectl get hpa -A || true
kubectl get deployments -A -o custom-columns=NS:.metadata.namespace,NAME:.metadata.name,READY:.status.readyReplicas,DESIRED:.spec.replicas | head -20

echo -e "\n🌐 Network Indicators"
kubectl get nodes -o wide
kubectl get pods -A -o wide | head -20

echo -e "\n🧠 Memory Pressure / OOM"
kubectl get events -A --field-selector reason=OOMKilling --sort-by=.lastTimestamp | tail -20 || true

echo -e "\n✅ Complete"
