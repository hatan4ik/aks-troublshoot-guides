#!/bin/bash
# Create a minimal Grafana dashboard for cluster health
set -euo pipefail

NAMESPACE=${1:-monitoring}
RELEASE=${2:-monitoring}

echo "📊 Creating health dashboard (placeholder JSON) in ConfigMap"

cat <<'EOF' | kubectl apply -n "$NAMESPACE" -f -
apiVersion: v1
kind: ConfigMap
metadata:
  name: cluster-health-dashboard
  labels:
    grafana_dashboard: "1"
data:
  cluster-health.json: |
    {
      "title": "Cluster Health",
      "schemaVersion": 16,
      "version": 1,
      "panels": [
        {"type": "stat", "title": "Nodes Ready", "targets":[{"expr":"sum(kube_node_status_condition{condition=\"Ready\",status=\"true\"})"}]},
        {"type": "stat", "title": "Pods Running", "targets":[{"expr":"sum(kube_pod_status_phase{phase=\"Running\"})"}]},
        {"type": "graph", "title": "API 5xx", "targets":[{"expr":"rate(apiserver_request_total{code=~\"5..\"}[5m])"}]}
      ]
    }
EOF

echo "✅ Dashboard configmap applied (Grafana sidecar will pick it up)"
