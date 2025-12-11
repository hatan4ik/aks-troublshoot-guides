#!/bin/bash
# Network security posture scan
set -euo pipefail

echo "🛡️  Network Security Scan"
echo "Timestamp: $(date)"

echo -e "\n🔒 Namespaces without NetworkPolicies"
ALL_NS=$(kubectl get ns -o jsonpath='{.items[*].metadata.name}')
for ns in $ALL_NS; do
  count=$(kubectl get networkpolicies -n "$ns" --no-headers 2>/dev/null | wc -l | tr -d ' ')
  if [[ "$count" -eq 0 ]]; then
    echo "$ns"
  fi
done

echo -e "\n🌐 LoadBalancers with open ports"
kubectl get svc -A --field-selector spec.type=LoadBalancer -o json \
  | jq -r '.items[] | "\(.metadata.namespace)/\(.metadata.name) ports=\(.spec.ports[]?.port)"' || true

echo -e "\n⚠️  Pods using hostNetwork"
kubectl get pods -A -o json | jq -r '
  .items[] | select(.spec.hostNetwork==true) | "\(.metadata.namespace)/\(.metadata.name)"
' || true

echo -e "\n✅ Scan complete (consider default-deny NetworkPolicies + ingress/egress allowlists)"
