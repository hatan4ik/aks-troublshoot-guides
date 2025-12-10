#!/bin/bash

# AKS/EKS/Kubernetes Troubleshooting Guide Setup Script
# Initializes the troubleshooting environment and validates prerequisites

set -euo pipefail

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}"
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║           Kubernetes Troubleshooting Guide Setup            ║"
echo "║                    From Zero to Hero                         ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo -e "${NC}"

# Check prerequisites
check_prerequisites() {
    echo -e "\n${YELLOW}🔍 Checking Prerequisites...${NC}"
    
    local missing_tools=()
    
    # Check kubectl
    if command -v kubectl &> /dev/null; then
        echo -e "${GREEN}✅ kubectl found${NC}"
        kubectl version --client --short 2>/dev/null || true
    else
        echo -e "${RED}❌ kubectl not found${NC}"
        missing_tools+=("kubectl")
    fi
    
    # Check cluster connectivity
    if kubectl cluster-info &> /dev/null; then
        echo -e "${GREEN}✅ Kubernetes cluster accessible${NC}"
        kubectl cluster-info | head -1
    else
        echo -e "${YELLOW}⚠️  No Kubernetes cluster connection${NC}"
    fi
    
    # Check optional tools
    for tool in "docker" "helm" "jq" "curl"; do
        if command -v "$tool" &> /dev/null; then
            echo -e "${GREEN}✅ $tool found${NC}"
        else
            echo -e "${YELLOW}⚠️  $tool not found (optional)${NC}"
        fi
    done
    
    # Check cloud CLIs
    if command -v az &> /dev/null; then
        echo -e "${GREEN}✅ Azure CLI found${NC}"
    else
        echo -e "${YELLOW}⚠️  Azure CLI not found (needed for AKS)${NC}"
    fi
    
    if command -v aws &> /dev/null; then
        echo -e "${GREEN}✅ AWS CLI found${NC}"
    else
        echo -e "${YELLOW}⚠️  AWS CLI not found (needed for EKS)${NC}"
    fi
    
    if [[ ${#missing_tools[@]} -gt 0 ]]; then
        echo -e "\n${RED}❌ Missing required tools: ${missing_tools[*]}${NC}"
        echo "Please install missing tools and run setup again."
        return 1
    fi
}

# Setup directory permissions
setup_permissions() {
    echo -e "\n${YELLOW}🔧 Setting up permissions...${NC}"
    
    # Make all scripts executable
    find scripts/ -name "*.sh" -exec chmod +x {} \;
    echo -e "${GREEN}✅ Scripts made executable${NC}"
    
    # Create output directories
    mkdir -p logs reports
    echo -e "${GREEN}✅ Output directories created${NC}"
}

# Validate cluster access
validate_cluster() {
    echo -e "\n${YELLOW}🔍 Validating cluster access...${NC}"
    
    if ! kubectl auth can-i get pods &> /dev/null; then
        echo -e "${RED}❌ Insufficient permissions to get pods${NC}"
        return 1
    fi
    
    if ! kubectl auth can-i get nodes &> /dev/null; then
        echo -e "${YELLOW}⚠️  Cannot access nodes (may need cluster-admin)${NC}"
    else
        echo -e "${GREEN}✅ Node access available${NC}"
    fi
    
    echo -e "${GREEN}✅ Basic cluster access validated${NC}"
}

# Create quick reference
create_quick_reference() {
    echo -e "\n${YELLOW}📋 Creating quick reference...${NC}"
    
    cat > quick-reference.md << 'EOF'
# Quick Reference

## Emergency Commands
```bash
# Cluster health check
./scripts/diagnostics/cluster-health-check.sh

# Pod diagnostics
./scripts/diagnostics/pod-diagnostics.sh <pod-name> [namespace]

# Network diagnostics
./scripts/diagnostics/network-diagnostics.sh

# All pods in namespace
./scripts/diagnostics/pod-diagnostics.sh -a [namespace]
```

## Team Quick Access
- **Architects**: `cd docs/architects && ls`
- **Engineers**: `cd docs/engineers && ls`
- **DevOps**: `cd docs/devops && ls`
- **SREs**: `cd docs/sre && ls`
- **Writers**: `cd docs/copywriters && ls`

## Common Troubleshooting
- **Pod Issues**: See `playbooks/common-issues.md`
- **Network Problems**: Run `./scripts/diagnostics/network-diagnostics.sh`
- **Resource Issues**: Check `kubectl top nodes && kubectl top pods -A`

## Getting Help
- Check the main README.md for comprehensive guide
- Use templates in `templates/` for new documentation
- Follow playbooks in `playbooks/` for step-by-step guidance
EOF

    echo -e "${GREEN}✅ Quick reference created${NC}"
}

# Run initial health check
run_health_check() {
    echo -e "\n${YELLOW}🏥 Running initial health check...${NC}"
    
    if [[ -f "scripts/diagnostics/cluster-health-check.sh" ]]; then
        echo "Running cluster health check..."
        ./scripts/diagnostics/cluster-health-check.sh > logs/initial-health-check.log 2>&1 || true
        echo -e "${GREEN}✅ Health check completed (see logs/initial-health-check.log)${NC}"
    else
        echo -e "${YELLOW}⚠️  Health check script not found${NC}"
    fi
}

# Main setup function
main() {
    echo -e "\n${BLUE}Starting setup process...${NC}"
    
    check_prerequisites || exit 1
    setup_permissions
    validate_cluster || echo -e "${YELLOW}⚠️  Cluster validation failed - some features may not work${NC}"
    create_quick_reference
    run_health_check
    
    echo -e "\n${GREEN}🎉 Setup completed successfully!${NC}"
    echo -e "\n${BLUE}Next steps:${NC}"
    echo "1. Review the main README.md for comprehensive guide"
    echo "2. Check quick-reference.md for common commands"
    echo "3. Explore team-specific guides in docs/"
    echo "4. Run diagnostic scripts in scripts/diagnostics/"
    echo -e "\n${YELLOW}Happy troubleshooting! 🚀${NC}"
}

main "$@"