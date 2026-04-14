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
# Step 1.5: AKS-Specific Expert Diagnostics (Brain Injected)
# ------------------------------------------------------------------
echo "[Step 1.5] Running Advanced AKS Expert Checks..."

echo -n "  🔍 API Server Latency... "
kubectl get --raw /healthz >/dev/null 2>&1 && echo "✅ Responsive" || echo "⚠️ Slow/Unresponsive"

echo "  🔍 Checking Node Status and Agent Pools..."
kubectl get nodes -o custom-columns=NAME:.metadata.name,STATUS:.status.conditions[-1].type,VERSION:.status.nodeInfo.kubeletVersion,POOL:.metadata.labels.agentpool 2>/dev/null || echo "  ⚠️ Unable to fetch nodes."

echo "  🔍 Checking CoreDNS health (critical for AKS)..."
kubectl get pods -n kube-system -l k8s-app=kube-dns 2>/dev/null || echo "  ⚠️ Unable to fetch CoreDNS pods."

echo "  🔍 Checking for Pods stuck in ContainerCreating (Azure CNI IP exhaustion?)..."
kubectl get pods -A --field-selector=status.phase=Pending 2>/dev/null | grep ContainerCreating || echo "  ✅ No pods stuck in ContainerCreating."

echo "  🔍 Checking for Problematic Pods (CrashLoopBackOff, Evicted, ImagePullBackOff)..."
kubectl get pods -A 2>/dev/null | awk '$4 ~ /CrashLoopBackOff|Evicted|ImagePullBackOff|ErrImagePull/ {print "  ⚠️  " $1, $2, $4}' || echo "  ✅ No failing pods found."

echo "  🔍 Checking for OOMKilled Pods (Resource limits too low)..."
OOM_PODS=$(kubectl get pods -A 2>/dev/null | awk '$4 == "OOMKilled" {print "  ⚠️  OOMKilled: " $1 "/" $2}' || true)
if [ -z "$OOM_PODS" ]; then echo "  ✅ No currently OOMKilled pods found."; else echo "$OOM_PODS"; fi

echo "  🔍 Checking Node memory/CPU/disk pressure conditions..."
PRESSURE=$(kubectl get nodes -o custom-columns="NAME:.metadata.name,MEM_PRESSURE:.status.conditions[?(@.type==\"MemoryPressure\")].status,DISK_PRESSURE:.status.conditions[?(@.type==\"DiskPressure\")].status,PID_PRESSURE:.status.conditions[?(@.type==\"PIDPressure\")].status" 2>/dev/null | awk 'NR>1 && ($2!="False" || $3!="False" || $4!="False") {print "  ⚠️  Node under pressure: " $0}' || true)
if [ -z "$PRESSURE" ]; then echo "  ✅ Nodes are not under pressure."; else echo "$PRESSURE"; fi

echo "  🔍 Checking Azure Disk/File PVC Attachment Issues..."
PVC_ISSUES=$(kubectl get events -A --field-selector type=Warning 2>/dev/null | grep -iE 'FailedMount|FailedAttachVolume' | tail -n 3 | awk '{print "  ⚠️  " $0}' || true)
if [ -z "$PVC_ISSUES" ]; then echo "  ✅ No persistent volume attachment issues detected."; else echo "$PVC_ISSUES"; fi

echo "  🔍 Checking Metrics Server and HPA Status..."
HPA_FAILURES=$(kubectl get hpa -A 2>/dev/null | grep -i '<unknown>' | awk '{print "  ⚠️  HPA missing metrics: " $1 "/" $2}' || true)
if [ -z "$HPA_FAILURES" ]; then echo "  ✅ HPAs are gathering metrics properly."; else echo "$HPA_FAILURES"; fi

echo "  🔍 Checking for CNI/IP Exhaustion Events (FailedCreatePodSandBox, network plugin errors)..."
CNI_EVENTS=$(kubectl get events -A --field-selector type=Warning --sort-by=.lastTimestamp 2>/dev/null | grep -iE 'FailedCreatePodSandBox|network plugin' | tail -n 5 | awk '{print "  ⚠️  " $0}' || true)
if [ -z "$CNI_EVENTS" ]; then echo "  ✅ No CNI/IP exhaustion events detected recently."; else echo "$CNI_EVENTS"; fi
echo ""

# ------------------------------------------------------------------
# Step 2: Run analytics on the events/Logs to identify issues
# ------------------------------------------------------------------
echo "[Step 2] Running deep AI-driven analytics on events, logs, and pod statuses..."
# We use the existing python diagnostics CLI to perform deep analytics
if [ ! -f "./k8s-diagnostics-cli.py" ]; then
    echo "❌ Error: ./k8s-diagnostics-cli.py not found. Are you in the repo root?"
    exit 1
fi

# ------------------------------------------------------------------
# Step 3: Present the current issues or problems
# Step 4: Propose automated Fixes or manual command lines
# ------------------------------------------------------------------
echo "[Step 3 & 4] Advanced 5-Layer Pattern Analysis & Fixes..."
echo "------------------------------------------------------------------"
# The 'detect' command analyzes the cluster and prints out issues + proposed fixes
DETECT_JSON=$(python3 ./k8s-diagnostics-cli.py detect 2>/dev/null || true)

if ! command -v jq &> /dev/null; then
    echo "⚠️  'jq' is not installed. Displaying raw JSON output:"
    echo "$DETECT_JSON"
else
    # Issues
    ISSUES_FOUND=$(echo "$DETECT_JSON" | jq -r '.issues | length // 0')
    if [ "$ISSUES_FOUND" -eq 0 ]; then
        echo "  ✅ No major issues detected by the diagnostics engine."
    else
        echo "  🚨 Detected $ISSUES_FOUND base issue(s):"
        echo "$DETECT_JSON" | jq -r '
            .issues[] | 
            "    🔴 \(.type | ascii_upcase) (Severity: \(.severity))\n" +
            "       Details: \(.details[0:3] | join(", "))\n" +
            "       Hint: \(.hint // "None")\n"
        '
    fi

    # Pattern Analysis (The Bombastic Part)
    PATTERNS_FOUND=$(echo "$DETECT_JSON" | jq -r '.pattern_analysis | length // 0')
    if [ "$PATTERNS_FOUND" -gt 0 ]; then
        echo ""
        echo "  🧠 EXPERT ARCHITECTURE ANALYSIS:"
        echo "$DETECT_JSON" | jq -r '
            .pattern_analysis[] |
            "    ========================================================\n" +
            "    🎯 Layer:      \(.layer_label)\n" +
            "    ⚠️  Class:      \(.error_class | ascii_upcase) (Severity: \(.severity))\n" +
            "    🔍 Signal:     \(.signal)\n" +
            "    💡 Root Cause: \(.root_cause)\n" +
            "    🛠️  To Verify:  \n\(.next_command | split("\n") | join("\n       "))\n" +
            "    ✨ Fix:        \(.fix.description)\n" +
            "       Command:    \(.fix.command)\n" +
            "    ========================================================"
        '
    fi
fi

echo ""
echo "================================================================"
echo " 🛠️  Next Steps:"
echo " - To apply an automated fix safely, run: python3 ./k8s-diagnostics-cli.py heal"
echo " - To dig deeper into a specific pod, run: python3 ./k8s-diagnostics-cli.py diagnose <ns> <pod>"
echo " - Always review the proposed 'kubectl patch' or 'kubectl set' commands before running them manually."
echo "================================================================"

read -p "Would you like to run the automated remediation (heal) now? [y/N]: " RUN_HEAL
if [[ "$RUN_HEAL" =~ ^[Yy]$ ]]; then
    echo "Running automated remediation..."
    python3 ./k8s-diagnostics-cli.py heal
fi
