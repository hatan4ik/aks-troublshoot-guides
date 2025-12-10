#!/usr/bin/env python3
"""
K8s Diagnostics CLI - Programmatic interface
Usage: python k8s-diagnostics-cli.py [command] [options]
"""

import asyncio
import json
import sys
from src.k8s_diagnostics.core.client import K8sClient
from src.k8s_diagnostics.automation.diagnostics import DiagnosticsEngine
from src.k8s_diagnostics.automation.fixes import AutoFixer

class DiagnosticsCLI:
    def __init__(self):
        self.k8s = K8sClient()
        self.diagnostics = DiagnosticsEngine(self.k8s)
        self.fixer = AutoFixer(self.k8s)

    def health(self):
        """Get cluster health"""
        result = self.k8s.get_cluster_health()
        print(json.dumps(result, indent=2))

    async def diagnose_pod(self, namespace, pod_name):
        """Diagnose specific pod"""
        result = await self.diagnostics.diagnose_pod(namespace, pod_name)
        print(json.dumps(result, indent=2))

    async def network_check(self):
        """Run network diagnostics"""
        result = await self.diagnostics.check_network()
        print(json.dumps(result, indent=2))

    async def detect_issues(self):
        """Auto-detect issues"""
        result = await self.diagnostics.detect_common_issues()
        print(json.dumps(result, indent=2))

    async def fix_failed_pods(self):
        """Auto-fix failed pods"""
        result = await self.fixer.restart_failed_pods()
        print(json.dumps(result, indent=2))

    async def cleanup_evicted(self):
        """Cleanup evicted pods"""
        result = await self.fixer.cleanup_evicted_pods()
        print(json.dumps(result, indent=2))

    async def fix_dns(self):
        """Restart unhealthy CoreDNS pods"""
        result = await self.fixer.fix_dns_issues()
        print(json.dumps(result, indent=2))

    async def scale(self, namespace, deployment, replicas):
        """Scale a deployment"""
        result = await self.fixer.scale_resources(namespace, deployment, int(replicas))
        print(json.dumps(result, indent=2))

def main():
    cli = DiagnosticsCLI()
    
    if len(sys.argv) < 2:
        print("Usage: python k8s-diagnostics-cli.py [health|diagnose|network|detect|fix|cleanup|dnsfix|scale]")
        sys.exit(1)
    
    command = sys.argv[1]
    
    if command == "health":
        cli.health()
    elif command == "diagnose" and len(sys.argv) >= 4:
        asyncio.run(cli.diagnose_pod(sys.argv[2], sys.argv[3]))
    elif command == "network":
        asyncio.run(cli.network_check())
    elif command == "detect":
        asyncio.run(cli.detect_issues())
    elif command == "fix":
        asyncio.run(cli.fix_failed_pods())
    elif command == "cleanup":
        asyncio.run(cli.cleanup_evicted())
    elif command == "dnsfix":
        asyncio.run(cli.fix_dns())
    elif command == "scale" and len(sys.argv) >= 5:
        asyncio.run(cli.scale(sys.argv[2], sys.argv[3], sys.argv[4]))
    else:
        print("Invalid command or missing arguments")
        sys.exit(1)

if __name__ == "__main__":
    main()
