#!/bin/bash

# Network Diagnostics Script
# Comprehensive network troubleshooting for Kubernetes

set -euo pipefail

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

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

# Check DNS functionality
check_dns() {
    print_section "🌐 DNS Diagnostics"
    
    # Check CoreDNS pods
    local coredns_pods=$(kubectl get pods -n kube-system -l k8s-app=kube-dns --no-headers | wc -l)
    local running_coredns=$(kubectl get pods -n kube-system -l k8s-app=kube-dns --no-headers | grep Running | wc -l)
    
    if [[ $running_coredns -eq $coredns_pods ]] && [[ $coredns_pods -gt 0 ]]; then
        print_status "OK" "CoreDNS pods are running ($running_coredns/$coredns_pods)"
    else
        print_status "ERROR" "CoreDNS issues detected ($running_coredns/$coredns_pods running)"
    fi
    
    # Test DNS resolution
    print_status "INFO" "Testing DNS resolution..."
    kubectl run dns-test-$(date +%s) --image=busybox --rm -it --restart=Never -- nslookup kubernetes.default 2>/dev/null && \
        print_status "OK" "DNS resolution working" || \
        print_status "ERROR" "DNS resolution failed"
    
    # Check DNS configuration
    kubectl get configmap coredns -n kube-system -o yaml | grep -A 20 "Corefile:"
}

# Check service connectivity
check_services() {
    print_section "🔗 Service Connectivity"
    
    # List all services
    kubectl get services -A -o wide
    
    # Check for services without endpoints
    print_status "INFO" "Checking services without endpoints..."
    kubectl get endpoints -A | awk 'NR>1 && $3=="<none>" {print $1, $2}' | while read ns svc; do
        [[ -n "$ns" ]] && print_status "WARNING" "Service $svc in namespace $ns has no endpoints"
    done
}

# Check network policies
check_network_policies() {
    print_section "🛡️  Network Policies"
    
    local policy_count=$(kubectl get networkpolicies -A --no-headers | wc -l)
    if [[ $policy_count -eq 0 ]]; then
        print_status "INFO" "No network policies found (default allow-all)"
    else
        print_status "INFO" "Found $policy_count network policies"
        kubectl get networkpolicies -A
    fi
}

# Check ingress controllers
check_ingress() {
    print_section "🚪 Ingress Controllers"
    
    # Check for ingress controllers
    local ingress_pods=$(kubectl get pods -A -l app.kubernetes.io/name=ingress-nginx --no-headers | wc -l)
    if [[ $ingress_pods -gt 0 ]]; then
        print_status "OK" "Found $ingress_pods ingress controller pods"
        kubectl get pods -A -l app.kubernetes.io/name=ingress-nginx
    else
        print_status "INFO" "No nginx ingress controllers found"
    fi
    
    # List ingress resources
    kubectl get ingress -A
}

# Check pod-to-pod connectivity
check_pod_connectivity() {
    print_section "🔄 Pod-to-Pod Connectivity"
    
    # Create test pods for connectivity testing
    print_status "INFO" "Creating test pods for connectivity testing..."
    
    cat <<EOF | kubectl apply -f -
apiVersion: v1
kind: Pod
metadata:
  name: netshoot-test
  labels:
    app: netshoot-test
spec:
  containers:
  - name: netshoot
    image: nicolaka/netshoot
    command: ["sleep", "3600"]
EOF

    # Wait for pod to be ready
    kubectl wait --for=condition=ready pod/netshoot-test --timeout=60s || {
        print_status "ERROR" "Failed to create test pod"
        return 1
    }
    
    # Test connectivity to kubernetes service
    kubectl exec netshoot-test -- nslookup kubernetes.default && \
        print_status "OK" "DNS resolution from pod working" || \
        print_status "ERROR" "DNS resolution from pod failed"
    
    # Cleanup
    kubectl delete pod netshoot-test --ignore-not-found=true
}

# Check CNI and node networking
check_cni() {
    print_section "🔌 CNI and Node Networking"
    
    # Check node network configuration
    kubectl get nodes -o wide
    
    # Check for CNI pods
    local cni_pods=$(kubectl get pods -n kube-system | grep -E "(calico|flannel|weave|cilium)" | wc -l)
    if [[ $cni_pods -gt 0 ]]; then
        print_status "OK" "Found $cni_pods CNI pods"
        kubectl get pods -n kube-system | grep -E "(calico|flannel|weave|cilium)"
    else
        print_status "WARNING" "No common CNI pods found"
    fi
}

# Check load balancer services
check_load_balancers() {
    print_section "⚖️  Load Balancer Services"
    
    local lb_services=$(kubectl get services -A --field-selector spec.type=LoadBalancer --no-headers | wc -l)
    if [[ $lb_services -gt 0 ]]; then
        print_status "INFO" "Found $lb_services LoadBalancer services"
        kubectl get services -A --field-selector spec.type=LoadBalancer
        
        # Check for pending load balancers
        local pending_lbs=$(kubectl get services -A --field-selector spec.type=LoadBalancer -o jsonpath='{range .items[*]}{.metadata.namespace}{" "}{.metadata.name}{" "}{.status.loadBalancer.ingress}{"\n"}{end}' | grep -c "null" || true)
        if [[ $pending_lbs -gt 0 ]]; then
            print_status "WARNING" "$pending_lbs LoadBalancer services are pending"
        fi
    else
        print_status "INFO" "No LoadBalancer services found"
    fi
}

# Main execution
main() {
    echo "🌐 Kubernetes Network Diagnostics"
    echo "================================="
    echo "Timestamp: $(date)"
    echo ""
    
    check_dns
    check_services
    check_network_policies
    check_ingress
    check_pod_connectivity
    check_cni
    check_load_balancers
    
    echo -e "\n✅ Network diagnostics completed at $(date)"
}

main "$@"