#!/bin/bash

# Pod Diagnostics Script
# Comprehensive pod troubleshooting for Kubernetes

set -euo pipefail

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Usage
usage() {
    echo "Usage: $0 [OPTIONS] <pod-name> [namespace]"
    echo "Options:"
    echo "  -a, --all-pods     Diagnose all pods in namespace"
    echo "  -f, --follow-logs  Follow logs in real-time"
    echo "  -h, --help         Show this help"
    exit 1
}

# Print colored output
print_section() {
    echo -e "\n${BLUE}$1${NC}"
    echo "$(printf '=%.0s' {1..50})"
}

print_status() {
    local status=$1
    local message=$2
    case $status in
        "OK") echo -e "${GREEN}✅ $message${NC}" ;;
        "WARNING") echo -e "${YELLOW}⚠️  $message${NC}" ;;
        "ERROR") echo -e "${RED}❌ $message${NC}" ;;
        "INFO") echo -e "${BLUE}ℹ️  $message${NC}" ;;
    esac
}

# Diagnose single pod
diagnose_pod() {
    local pod_name=$1
    local namespace=${2:-"default"}
    
    print_section "🔍 Diagnosing Pod: $pod_name (namespace: $namespace)"
    
    # Check if pod exists
    if ! kubectl get pod "$pod_name" -n "$namespace" &>/dev/null; then
        print_status "ERROR" "Pod '$pod_name' not found in namespace '$namespace'"
        return 1
    fi
    
    # Basic pod information
    print_section "📋 Pod Information"
    kubectl get pod "$pod_name" -n "$namespace" -o wide
    
    # Pod status analysis
    print_section "🔍 Pod Status Analysis"
    local status=$(kubectl get pod "$pod_name" -n "$namespace" -o jsonpath='{.status.phase}')
    local ready=$(kubectl get pod "$pod_name" -n "$namespace" -o jsonpath='{.status.conditions[?(@.type=="Ready")].status}')
    
    print_status "INFO" "Phase: $status"
    print_status "INFO" "Ready: $ready"
    
    # Container status
    print_section "📦 Container Status"
    kubectl get pod "$pod_name" -n "$namespace" -o jsonpath='{range .status.containerStatuses[*]}{.name}{": "}{.state}{"\n"}{end}' | \
    while IFS= read -r line; do
        if [[ $line == *"running"* ]]; then
            print_status "OK" "$line"
        elif [[ $line == *"waiting"* ]] || [[ $line == *"terminated"* ]]; then
            print_status "WARNING" "$line"
        else
            print_status "INFO" "$line"
        fi
    done
    
    # Resource usage
    print_section "📊 Resource Usage"
    kubectl top pod "$pod_name" -n "$namespace" 2>/dev/null || print_status "WARNING" "Metrics not available"
    
    # Events
    print_section "📋 Recent Events"
    kubectl get events -n "$namespace" --field-selector involvedObject.name="$pod_name" --sort-by='.lastTimestamp' | tail -10
    
    # Detailed description
    print_section "📝 Detailed Description"
    kubectl describe pod "$pod_name" -n "$namespace"
    
    # Logs
    print_section "📜 Container Logs"
    local containers=$(kubectl get pod "$pod_name" -n "$namespace" -o jsonpath='{.spec.containers[*].name}')
    for container in $containers; do
        echo -e "\n${YELLOW}--- Logs for container: $container ---${NC}"
        if [[ "$FOLLOW_LOGS" == "true" ]]; then
            kubectl logs "$pod_name" -n "$namespace" -c "$container" -f --tail=50
        else
            kubectl logs "$pod_name" -n "$namespace" -c "$container" --tail=50
        fi
    done
    
    # Network diagnostics
    print_section "🌐 Network Diagnostics"
    local pod_ip=$(kubectl get pod "$pod_name" -n "$namespace" -o jsonpath='{.status.podIP}')
    print_status "INFO" "Pod IP: $pod_ip"
    
    # Service endpoints
    kubectl get endpoints -n "$namespace" -o wide | grep -E "(NAME|$pod_ip)" || print_status "INFO" "Pod not part of any service endpoints"
}

# Diagnose all pods in namespace
diagnose_all_pods() {
    local namespace=${1:-"default"}
    
    print_section "🔍 Diagnosing All Pods in Namespace: $namespace"
    
    # Get problematic pods
    local failed_pods=$(kubectl get pods -n "$namespace" --field-selector=status.phase!=Running,status.phase!=Succeeded --no-headers -o custom-columns=":metadata.name" 2>/dev/null)
    
    if [[ -z "$failed_pods" ]]; then
        print_status "OK" "All pods in namespace '$namespace' are running successfully"
        kubectl get pods -n "$namespace"
        return 0
    fi
    
    print_status "WARNING" "Found problematic pods in namespace '$namespace'"
    
    while IFS= read -r pod; do
        [[ -n "$pod" ]] && diagnose_pod "$pod" "$namespace"
        echo -e "\n$(printf '=%.0s' {1..80})\n"
    done <<< "$failed_pods"
}

# Parse command line arguments
FOLLOW_LOGS="false"
ALL_PODS="false"

while [[ $# -gt 0 ]]; do
    case $1 in
        -a|--all-pods)
            ALL_PODS="true"
            shift
            ;;
        -f|--follow-logs)
            FOLLOW_LOGS="true"
            shift
            ;;
        -h|--help)
            usage
            ;;
        -*)
            echo "Unknown option $1"
            usage
            ;;
        *)
            break
            ;;
    esac
done

# Main execution
main() {
    if [[ "$ALL_PODS" == "true" ]]; then
        diagnose_all_pods "${1:-default}"
    else
        if [[ $# -eq 0 ]]; then
            echo "Error: Pod name required"
            usage
        fi
        diagnose_pod "$1" "${2:-default}"
    fi
}

main "$@"