#!/usr/bin/env bash
# Kubernetes 4-Step Troubleshooting & Remediation Tool
# Designed for AKS, EKS, GKE, and Bare Metal clusters.

set -e

echo "================================================================"
echo " 🩺 Kubernetes 4-Step Automated Troubleshooting"
echo "================================================================"
echo ""

# ------------------------------------------------------------------
# Step 1: Connect to AKS/EKS/GKE cluster
# ------------------------------------------------------------------
echo "[Step 1] Verifying connection to cluster..."
if ! kubectl cluster-info > /dev/null 2>&1; then
    echo "❌ Error: Cannot connect to Kubernetes cluster."
    echo "Please ensure you have authenticated with your cloud provider (e.g., 'az aks get-credentials' or 'aws eks update-kubeconfig')."
    exit 1
fi
CONTEXT=$(kubectl config current-context)
echo "✅ Successfully connected to cluster context: ${CONTEXT}"
echo ""

# ------------------------------------------------------------------
# Step 2: Run analytics on the events/Logs to identify issues
# ------------------------------------------------------------------
echo "[Step 2] Running analytics on events, logs, and pod statuses..."
# We use the existing python diagnostics CLI to perform deep analytics
if [ ! -f "./k8s-diagnostics-cli.py" ]; then
    echo "❌ Error: ./k8s-diagnostics-cli.py not found. Are you in the repo root?"
    exit 1
fi

# ------------------------------------------------------------------
# Step 3: Present the current issues or problems
# Step 4: Propose automated Fixes or manual command lines
# ------------------------------------------------------------------
echo "[Step 3 & 4] Presenting issues and proposing automated/manual fixes..."
echo "------------------------------------------------------------------"
# The 'suggest' command analyzes the cluster and prints out issues + proposed fixes
python3 ./k8s-diagnostics-cli.py suggest

echo ""
echo "================================================================"
echo " 🛠️  Next Steps:"
echo " - To apply an automated fix safely, run: python3 ./k8s-diagnostics-cli.py heal"
echo " - To dig deeper into a specific pod, run: python3 ./k8s-diagnostics-cli.py diagnose <ns> <pod>"
echo " - Always review the proposed 'kubectl patch' or 'kubectl set' commands before running them manually."
echo "================================================================"
