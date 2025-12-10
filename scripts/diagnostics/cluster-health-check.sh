#!/bin/bash

# Kubernetes Cluster Health Check Script
# Comprehensive cluster health assessment for AKS/EKS/K8s

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
NAMESPACE=${1:-""}
OUTPUT_FILE="cluster-health-$(date +%Y%m%d-%H%M%S).log"

echo "🔍 Kubernetes Cluster Health Check"
echo "=================================="
echo "Timestamp: $(date)"
echo "Output file: $OUTPUT_FILE"
echo ""

# Function to print status
print_status() {
    local status=$1
    local message=$2
    case $status in
        "OK") echo -e "${GREEN}✅ $message${NC}" ;;
        "WARNING") echo -e "${YELLOW}⚠️  $message${NC}" ;;
        "ERROR") echo -e "${RED}❌ $message${NC}" ;;
    esac
}

# Check kubectl connectivity
check_kubectl() {
    echo "🔗 Checking kubectl connectivity..."
    if kubectl cluster-info &>/dev/null; then
        print_status "OK" "kubectl connectivity established"
        kubectl cluster-info | head -2
    else
        print_status "ERROR" "kubectl connectivity failed"
        return 1
    fi
}

# Check cluster nodes
check_nodes() {
    echo -e "\n🖥️  Checking cluster nodes..."
    local not_ready=$(kubectl get nodes --no-headers | grep -v Ready | wc -l)
    local total_nodes=$(kubectl get nodes --no-headers | wc -l)
    
    if [ "$not_ready" -eq 0 ]; then
        print_status "OK" "All $total_nodes nodes are Ready"
    else
        print_status "WARNING" "$not_ready out of $total_nodes nodes are not Ready"
    fi
    
    kubectl get nodes -o wide
}

# Check system pods
check_system_pods() {
    echo -e "\n🏗️  Checking system pods..."
    local failed_pods=$(kubectl get pods -A --field-selector=status.phase!=Running,status.phase!=Succeeded --no-headers | wc -l)
    
    if [ "$failed_pods" -eq 0 ]; then
        print_status "OK" "All system pods are running"
    else
        print_status "WARNING" "$failed_pods pods are not in Running/Succeeded state"
        kubectl get pods -A --field-selector=status.phase!=Running,status.phase!=Succeeded
    fi
}

# Check resource usage
check_resources() {
    echo -e "\n📊 Checking resource usage..."
    kubectl top nodes 2>/dev/null || print_status "WARNING" "Metrics server not available"
    
    # Check for resource pressure
    kubectl describe nodes | grep -A 5 "Conditions:" | grep -E "(MemoryPressure|DiskPressure|PIDPressure)" || true
}

# Check persistent volumes
check_storage() {
    echo -e "\n💾 Checking storage..."
    local failed_pvs=$(kubectl get pv --no-headers 2>/dev/null | grep -v Bound | wc -l)
    
    if [ "$failed_pvs" -eq 0 ]; then
        print_status "OK" "All PVs are bound"
    else
        print_status "WARNING" "$failed_pvs PVs are not bound"
        kubectl get pv | grep -v Bound || true
    fi
}

# Check network connectivity
check_network() {
    echo -e "\n🌐 Checking network connectivity..."
    
    # Check CoreDNS
    local coredns_pods=$(kubectl get pods -n kube-system -l k8s-app=kube-dns --no-headers | grep Running | wc -l)
    if [ "$coredns_pods" -gt 0 ]; then
        print_status "OK" "CoreDNS pods are running ($coredns_pods pods)"
    else
        print_status "ERROR" "CoreDNS pods are not running"
    fi
    
    # Test DNS resolution
    kubectl run dns-test --image=busybox --rm -it --restart=Never -- nslookup kubernetes.default &>/dev/null && \
        print_status "OK" "DNS resolution working" || \
        print_status "ERROR" "DNS resolution failed"
}

# Check events for errors
check_events() {
    echo -e "\n📋 Checking recent events..."
    local warning_events=$(kubectl get events -A --field-selector type=Warning --no-headers | wc -l)
    
    if [ "$warning_events" -eq 0 ]; then
        print_status "OK" "No warning events found"
    else
        print_status "WARNING" "$warning_events warning events found"
        kubectl get events -A --field-selector type=Warning | tail -10
    fi
}

# Main execution
main() {
    {
        check_kubectl || exit 1
        check_nodes
        check_system_pods
        check_resources
        check_storage
        check_network
        check_events
        
        echo -e "\n📝 Health check completed at $(date)"
        echo "Full report saved to: $OUTPUT_FILE"
    } | tee "$OUTPUT_FILE"
}

main "$@"