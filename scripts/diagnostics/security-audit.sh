#!/bin/bash
# Security posture audit (RBAC, pod security, privileged usage)
set -euo pipefail

echo "🔐 Security Audit"
echo "Timestamp: $(date)"

print_warn() { echo "⚠️  $*"; }
print_ok() { echo "✅ $*"; }

echo -e "\n🔑 RBAC High-Risk Bindings (cluster-admin)"
kubectl get clusterrolebindings -o jsonpath='{range .items[*]}{@.metadata.name}{" => "}{@.roleRef.name}{" => "}{range @.subjects[*]}{@.kind}{"/"}{@.name}{"\n"}{end}{end}' | grep cluster-admin || print_ok "No cluster-admin bindings found"

echo -e "\n🛡️  Privileged/HostPath Pods"
kubectl get pods -A -o json | jq -r '.items[] | select(.spec.containers[]?.securityContext? | (.privileged==true or .allowPrivilegeEscalation==true)) | "\(.metadata.namespace)/\(.metadata.name)"' 2>/dev/null || true
kubectl get pods -A -o json | jq -r '.items[] | select(.spec.volumes[]?.hostPath) | "\(.metadata.namespace)/\(.metadata.name) uses hostPath"' 2>/dev/null || true

echo -e "\n🔒 Pod Security Admission/Policies"
kubectl get pods -A -o jsonpath='{range .items[*]}{.metadata.namespace}{" "}{.metadata.name}{" "}{.metadata.labels.pod-security\.kubernetes\.io/enforce}{"\n"}{end}' | head -20 || true

echo -e "\n📜 Recent Security Events"
kubectl get events -A --field-selector type=Warning --sort-by=.lastTimestamp | grep -i "Denied|Forbidden|Unauthorized" | tail -20 || print_ok "No recent security warnings"

echo -e "\n✅ Audit complete"
