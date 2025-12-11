#!/bin/bash
# HPA configuration and effectiveness check
set -euo pipefail

echo "📈 HPA Check"
echo "Timestamp: $(date)"

echo -e "\n🔍 Listing HPAs"
kubectl get hpa -A || { echo "No HPAs found"; exit 0; }

echo -e "\n⚠️  HPAs missing metrics or stuck"
kubectl get hpa -A -o json | jq -r '
  .items[]
  | {ns:.metadata.namespace,name:.metadata.name,min:.spec.minReplicas,max:.spec.maxReplicas,desired:.status.desiredReplicas,current:.status.currentReplicas,conditions:.status.conditions,metrics:.spec.metrics}
  | select((.metrics == null) or (.metrics == []) or (.desired == 0) or (.conditions[]? | select(.type=="AbleToScale" and .status=="False")))
  | "\(.ns)/\(.name) desired=\(.desired) current=\(.current) min=\(.min) max=\(.max) metrics=\(.metrics)"
' || true

echo -e "\n🚦 HPAs hitting max or min"
kubectl get hpa -A -o json | jq -r '
  .items[]
  | {ns:.metadata.namespace,name:.metadata.name,min:.spec.minReplicas,max:.spec.maxReplicas,desired:.status.desiredReplicas,current:.status.currentReplicas}
  | select(.desired==.max or .desired==.min)
  | "\(.ns)/\(.name) desired=\(.desired) current=\(.current) min=\(.min) max=\(.max)"
' || true

echo -e "\n🧭 Missing recommended resources (CPU/memory requests)"
kubectl get deploy,statefulset -A -o json | jq -r '
  .items[]
  | {kind:.kind,ns:.metadata.namespace,name:.metadata.name,containers:.spec.template.spec.containers}
  | select(.containers[]? | (.resources.requests.cpu==null or .resources.requests.memory==null))
  | "\(.kind) \(.ns)/\(.name) has containers without CPU/memory requests (HPA may misbehave)"
' || true

echo -e "\n✅ HPA check complete"
