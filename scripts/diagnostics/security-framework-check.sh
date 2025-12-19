#!/bin/bash
# Security Control Framework (SCF) Health Check
# Validates the presence and health of standard K8s security components.

set -e

echo "🔒 Starting Security Control Framework (SCF) Audit..."
echo "==================================================="

# 1. Check Admission Controllers (Policy as Code)
echo -n "[*] Checking Policy Engine (OPA/Kyverno)... "
if kubectl get ns gatekeeper-system >/dev/null 2>&1; then
    echo "✅ OPA Gatekeeper found."
    kubectl get pods -n gatekeeper-system
elif kubectl get ns kyverno >/dev/null 2>&1; then
    echo "✅ Kyverno found."
    kubectl get pods -n kyverno
else
    echo "⚠️  NO Policy Engine found! (Compliance Risk: High)"
fi

# 2. Check Runtime Security
echo -n "[*] Checking Runtime Security (Falco/Tetragon)... "
if kubectl get pods -A -l app=falco >/dev/null 2>&1; then
    echo "✅ Falco found."
elif kubectl get pods -A -l app.kubernetes.io/name=falco >/dev/null 2>&1; then
    echo "✅ Falco found."
else
    echo "⚠️  Falco NOT found (Runtime Visibility: Low)"
fi

# 3. RBAC "Shadow Admin" Check
echo "[*] Scanning for 'Shadow Admin' ClusterRoles..."
# Look for ClusterRoles with '*' verbs on '*' resources
kubectl get clusterroles -o json | jq -r '
  .items[] | 
  select(.rules[]? | select(.verbs[]? == "*" and .resources[]? == "*")) | 
  .metadata.name
' | while read role; do
    if [[ "$role" != "cluster-admin" && "$role" != "system:"* ]]; then
        echo "   🚨 WARNING: Non-standard ClusterRole with Full Admin Access: $role"
    fi
done

# 4. Check for Privileged Pods (Simulated)
echo "[*] Sampling for Privileged Pods in 'default' namespace..."
PRIV_PODS=$(kubectl get pods -n default -o jsonpath='{range .items[*]}{.metadata.name}{" "}{.spec.containers[*].securityContext.privileged}{"\n"}{end}' | grep "true" || true)

if [ -z "$PRIV_PODS" ]; then
    echo "✅ No privileged pods found in default namespace."
else
    echo "⚠️  Privileged pods found:"
    echo "$PRIV_PODS"
fi

# 5. Check API Server Security (Simulated - checks for anonymous access)
echo "[*] Checking Anonymous Auth..."
AUTH_CHECK=$(kubectl auth can-i "*" "*" --as=system:anonymous 2>&1)
if [[ "$AUTH_CHECK" == "yes" ]]; then
    echo "🚨 CRITICAL: Anonymous user has admin access!"
else
    echo "✅ Anonymous access correctly restricted."
fi

echo "==================================================="
echo "Audit Complete. Review warnings above."
