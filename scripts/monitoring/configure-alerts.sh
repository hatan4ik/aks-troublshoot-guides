#!/bin/bash
# Apply baseline alert rules for Kubernetes
set -euo pipefail

NAMESPACE=${1:-monitoring}
RELEASE=${2:-monitoring}

echo "🚨 Applying baseline alerts to $NAMESPACE/$RELEASE"
cat <<'EOF' | kubectl apply -n "$NAMESPACE" -f -
apiVersion: monitoring.coreos.com/v1
kind: PrometheusRule
metadata:
  name: k8s-baseline-alerts
spec:
  groups:
  - name: k8s-baseline
    rules:
    - alert: NodeNotReady
      expr: kube_node_status_condition{condition="Ready",status="true"} == 0
      for: 5m
      labels: {severity: critical}
      annotations:
        summary: "Node not ready"
    - alert: PodCrashLooping
      expr: rate(kube_pod_container_status_restarts_total[5m]) > 0.1
      for: 10m
      labels: {severity: warning}
      annotations:
        summary: "Pods restarting frequently"
    - alert: APIServerErrors
      expr: rate(apiserver_request_total{code=~"5.."}[5m]) > 1
      for: 5m
      labels: {severity: critical}
      annotations:
        summary: "API server returning errors"
EOF

echo "✅ Alerts applied"
