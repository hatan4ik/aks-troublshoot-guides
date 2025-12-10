#!/bin/bash
# Deploy lightweight log aggregation (fluent-bit to stdout placeholder)
set -euo pipefail

NAMESPACE=${1:-logging}

echo "🪵 Deploying fluent-bit DaemonSet (basic)"
kubectl create ns "$NAMESPACE" 2>/dev/null || true

cat <<'EOF' | kubectl apply -n "$NAMESPACE" -f -
apiVersion: apps/v1
kind: DaemonSet
metadata:
  name: fluent-bit
spec:
  selector:
    matchLabels:
      app: fluent-bit
  template:
    metadata:
      labels:
        app: fluent-bit
    spec:
      serviceAccountName: default
      containers:
      - name: fluent-bit
        image: cr.fluentbit.io/fluent/fluent-bit:2.2
        resources:
          limits: {cpu: "200m", memory: "200Mi"}
          requests: {cpu: "100m", memory: "100Mi"}
        volumeMounts:
        - name: varlog
          mountPath: /var/log
        - name: varlibdocker
          mountPath: /var/lib/docker/containers
          readOnly: true
      volumes:
      - name: varlog
        hostPath: {path: /var/log}
      - name: varlibdocker
        hostPath: {path: /var/lib/docker/containers}
EOF

echo "✅ Fluent-bit deployed (configure outputs for your target: Loki/Elastic/Cloud)"
