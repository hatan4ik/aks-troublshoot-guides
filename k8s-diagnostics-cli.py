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
from src.k8s_diagnostics.automation.chaos import ChaosEngine


class DiagnosticsCLI:
    def __init__(self):
        self.k8s = K8sClient()
        self.diagnostics = DiagnosticsEngine(self.k8s)
        self.fixer = AutoFixer(self.k8s)
        self.chaos = ChaosEngine(self.k8s)
        self.k8s.fixer = self.fixer

    def health(self):
        result = self.k8s.get_cluster_health()
        print(json.dumps(result, indent=2))

    async def diagnose_pod(self, namespace, pod_name):
        result = await self.diagnostics.diagnose_pod(namespace, pod_name)
        print(json.dumps(result, indent=2))

    async def network_check(self):
        result = await self.diagnostics.check_network()
        print(json.dumps(result, indent=2))

    async def detect_issues(self):
        result = await self.diagnostics.detect_common_issues()
        print(json.dumps(result, indent=2))

    async def fix_failed_pods(self):
        result = await self.fixer.restart_failed_pods()
        print(json.dumps(result, indent=2))

    async def cleanup_evicted(self):
        result = await self.fixer.cleanup_evicted_pods()
        print(json.dumps(result, indent=2))

    async def fix_dns(self):
        result = await self.fixer.fix_dns_issues()
        print(json.dumps(result, indent=2))

    async def scale(self, namespace, deployment, replicas):
        result = await self.fixer.scale_resources(namespace, deployment, int(replicas))
        print(json.dumps(result, indent=2))

    async def predict(self):
        result = await self.diagnostics.predict_risk()
        print(json.dumps(result, indent=2))

    async def heal(self):
        result = await self.diagnostics.autonomous_heal()
        print(json.dumps(result, indent=2))

    async def optimize(self):
        result = self.diagnostics.optimize_costs()
        print(json.dumps(result, indent=2))

    async def chaos_inject(self, namespace, selector, dry_run=True):
        result = await self.chaos.inject_pod_failure(namespace, selector, dry_run)
        print(json.dumps(result, indent=2))

    async def provider_diag(self):
        result = self.diagnostics.provider_diagnostics()
        print(json.dumps(result, indent=2))


def main():
    cli = DiagnosticsCLI()

    if len(sys.argv) < 2:
        print("Usage: python k8s-diagnostics-cli.py [health|diagnose|network|detect|fix|cleanup|dnsfix|scale|predict|heal|optimize|chaos|provider]")
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
    elif command == "predict":
        asyncio.run(cli.predict())
    elif command == "heal":
        asyncio.run(cli.heal())
    elif command == "optimize":
        asyncio.run(cli.optimize())
    elif command == "chaos" and len(sys.argv) >= 4:
        dry = True
        if len(sys.argv) >= 5 and sys.argv[4].lower() == "false":
            dry = False
        asyncio.run(cli.chaos_inject(sys.argv[2], sys.argv[3], dry))
    elif command == "provider":
        asyncio.run(cli.provider_diag())
    else:
        print("Invalid command or missing arguments")
        sys.exit(1)


if __name__ == "__main__":
    main()
