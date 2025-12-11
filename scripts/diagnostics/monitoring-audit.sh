#!/bin/bash
# Audit monitoring/logging footprint (cost hints)
set -euo pipefail

echo "💰 Monitoring/Logging Audit"
echo "Timestamp: $(date)"

echo -e "\n📈 Monitoring/Logging Pods (prometheus|grafana|loki|fluent|vector|filebeat|datadog)"
kubectl get pods -A | grep -Ei "prometheus|grafana|loki|fluent|vector|filebeat|datadog|newrelic|splunk" || echo "No monitoring/logging pods matched"

echo -e "\n💾 PVCs for monitoring/logging namespaces"
kubectl get pvc -A | grep -Ei "monitoring|logging|loki|prometheus|elastic" || echo "No PVCs found for monitoring/logging components"

echo -e "\n🚥 Large ConfigMaps (could inflate Prometheus scrape targets or dashboards)"
kubectl get configmaps -A -o json | jq -r '
  .items[]
  | select((.data // {} | length) > 30 or (.binaryData // {} | length) > 0)
  | "\(.metadata.namespace)/\(.metadata.name) entries=\((.data // {} | length))"
' || true

echo -e "\n📊 Prometheus scrape targets count (approx.)"
kubectl get endpoints -A | wc -l | xargs -I{} echo "Endpoints (upper bound on scrape targets): {}"

echo -e "\n✅ Audit complete (tune retention/scrape intervals in Prometheus/agents to control cost)"
