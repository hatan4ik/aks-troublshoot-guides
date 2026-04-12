"""Read-only AIOps operator loop.

This module is intentionally conservative: it reports risk and only previews
auto-heal actions unless AUTO_HEAL_APPLY=true is explicitly configured.
"""

import asyncio
import json
import os

from ..automation.diagnostics import DiagnosticsEngine
from ..automation.fixes import AutoFixer
from ..core.client import K8sClient


def _truthy(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


async def run_once() -> dict:
    k8s = K8sClient()
    diagnostics = DiagnosticsEngine(k8s)
    allowed_namespaces = [
        namespace.strip()
        for namespace in os.getenv("K8S_DIAGNOSTICS_ALLOWED_NAMESPACES", "").split(",")
        if namespace.strip()
    ]
    fixer = AutoFixer(k8s, allowed_namespaces=allowed_namespaces or ["__none__"])
    k8s.fixer = fixer

    result = {"risk": await diagnostics.predict_risk()}
    if _truthy(os.getenv("AUTO_HEAL_ENABLED", "false")):
        if not allowed_namespaces:
            result["auto_heal"] = {
                "status": "skipped",
                "error": "AUTO_HEAL_ENABLED requires K8S_DIAGNOSTICS_ALLOWED_NAMESPACES",
            }
            return result
        apply_changes = _truthy(os.getenv("AUTO_HEAL_APPLY", "false"))
        result["auto_heal"] = await fixer.auto_remediate(diagnostics, dry_run=not apply_changes)
    return result


async def main() -> None:
    interval_seconds = int(os.getenv("AI_OPERATOR_INTERVAL_SECONDS", "300"))
    while True:
        print(json.dumps(await run_once(), indent=2), flush=True)
        await asyncio.sleep(interval_seconds)


if __name__ == "__main__":
    asyncio.run(main())
