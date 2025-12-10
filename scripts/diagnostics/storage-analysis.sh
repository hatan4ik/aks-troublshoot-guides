#!/bin/bash
# Storage diagnostics for PVC/PV and volume attachment
set -euo pipefail

echo "💾 Storage Analysis"
echo "Timestamp: $(date)"

echo -e "\n📦 PVC/PV Status"
kubectl get pvc,pv -A || true

echo -e "\n⏳ Pending/Failed PVCs"
kubectl get pvc -A --field-selector status.phase!=Bound || true

echo -e "\n🔌 Volume Attach Errors (recent)"
kubectl get events -A --field-selector type=Warning --sort-by=.lastTimestamp | grep -iE "AttachVolume|MountVolume|FailedMount|FailedAttachVolume" | tail -30 || true

echo -e "\n🧭 Storage Classes"
kubectl get storageclass

echo -e "\n✅ Complete"
