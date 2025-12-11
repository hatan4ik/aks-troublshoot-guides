#!/bin/bash
# Image hygiene scan (unpinned tags / duplicates)
set -euo pipefail

echo "🖼️  Image Security Scan"
echo "Timestamp: $(date)"

echo -e "\n📦 Collecting images from running pods"
IMAGES=$(kubectl get pods -A -o jsonpath='{range .items[*]}{.spec.containers[*].image}{"\n"}{end}' | sort -u)

if [[ -z "$IMAGES" ]]; then
  echo "No images found"
  exit 0
fi

echo -e "\n⚠️  Images without digests (consider pinning)"
echo "$IMAGES" | grep -v '@sha256' || echo "All images pinned to digests"

echo -e "\n🧹 Duplicate tags across namespaces (risk of drift)"
kubectl get pods -A -o json | jq -r '
  .items[] | [.metadata.namespace, (.spec.containers[]?.image // "")] | @tsv
' | sort | uniq -c | sort -nr | head -20

echo -e "\n✅ Scan complete (for CVE scans, integrate trivy/grype in CI/CD)"
