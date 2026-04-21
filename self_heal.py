"""
Self-Healing Monitor — Autonomous System Repair
Monitors all components, detects failures, auto-repairs.
Runs as background asyncio task.
"""

import asyncio
import json
import logging
import re
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Dict, List, Optional

log = logging.getLogger("synapse.selfheal")

HEALER_SYSTEM = """You are an autonomous system repair AI.
Given a component failure report, diagnose and prescribe a fix.
Return ONLY valid JSON:
{
  "diagnosis": "what went wrong",
  "severity": "low|medium|high|critical",
  "auto_fixable": true/false,
  "fix_action": "restart|reconfigure|fallback|alert",
  "fix_params": {},
  "explanation": "human-readable explanation"
}"""


class ComponentStatus(Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    FAILED = "failed"
    RECOVERING = "recovering"
    UNKNOWN = "unknown"


@dataclass
class HealthCheck:
    component: str
    status: ComponentStatus
    latency_ms: float
    error: Optional[str]
    checked_at: float


@dataclass
class RepairAction:
    component: str
    action: str
    success: bool
    message: str
    timestamp: float


class SelfHealingMonitor:
    def __init__(self, llm, config):
        self.llm = llm
        self.config = config
        self._checks: Dict[str, HealthCheck] = {}
        self._repair_log: List[RepairAction] = []
        self._components: Dict[str, Callable] = {}
        self._running = False
        self._repair_callbacks: Dict[str, Callable] = {}
        self._alert_callbacks: List[Callable] = []

    # ── Register Components ───────────────────────────────────────────────────
    def register_check(self, name: str, check_fn: Callable, repair_fn: Callable = None):
        """Register a component with its health check and optional repair function."""
        self._components[name] = check_fn
        if repair_fn:
            self._repair_callbacks[name] = repair_fn
        log.info(f"Registered health check: {name}")

    def on_alert(self, callback: Callable):
        """Register callback for critical alerts."""
        self._alert_callbacks.append(callback)

    # ── Background Monitor Loop ───────────────────────────────────────────────
    async def start(self, interval_seconds: int = 30):
        """Start background health monitoring."""
        self._running = True
        log.info(f"Self-healing monitor started (interval={interval_seconds}s)")
        while self._running:
            await self._run_all_checks()
            await asyncio.sleep(interval_seconds)

    def stop(self):
        self._running = False

    async def _run_all_checks(self):
        for name, check_fn in self._components.items():
            try:
                start = time.time()
                ok, error = await check_fn()
                latency = (time.time() - start) * 1000

                status = ComponentStatus.HEALTHY if ok else ComponentStatus.FAILED
                self._checks[name] = HealthCheck(
                    component=name,
                    status=status,
                    latency_ms=latency,
                    error=error,
                    checked_at=time.time(),
                )

                if not ok:
                    log.warning(f"❌ {name} health check failed: {error}")
                    await self._auto_repair(name, error)
                else:
                    log.debug(f"✅ {name} OK ({latency:.0f}ms)")

            except Exception as e:
                log.error(f"Health check exception [{name}]: {e}")
                self._checks[name] = HealthCheck(
                    component=name,
                    status=ComponentStatus.UNKNOWN,
                    latency_ms=0,
                    error=str(e),
                    checked_at=time.time(),
                )

    # ── Auto Repair ───────────────────────────────────────────────────────────
    async def _auto_repair(self, component: str, error: str):
        # Ask LLM for diagnosis + fix plan
        diagnosis = await self._diagnose(component, error)
        severity = diagnosis.get("severity", "medium")
        auto_fixable = diagnosis.get("auto_fixable", False)
        action = diagnosis.get("fix_action", "alert")

        log.info(f"Diagnosis [{component}]: {diagnosis.get('diagnosis')} → {action}")

        repair = RepairAction(
            component=component,
            action=action,
            success=False,
            message=diagnosis.get("explanation", ""),
            timestamp=time.time(),
        )

        if auto_fixable and component in self._repair_callbacks:
            try:
                self._checks[component] = HealthCheck(
                    component=component,
                    status=ComponentStatus.RECOVERING,
                    latency_ms=0,
                    error=error,
                    checked_at=time.time(),
                )
                await self._repair_callbacks[component](action, diagnosis.get("fix_params", {}))
                repair.success = True
                repair.message += " → Auto-repaired"
                log.info(f"✅ Auto-repaired: {component}")
            except Exception as e:
                repair.message += f" → Repair failed: {e}"
                log.error(f"Repair failed [{component}]: {e}")

        self._repair_log.append(repair)

        # Alert on critical
        if severity == "critical":
            for cb in self._alert_callbacks:
                try:
                    await cb(component, diagnosis)
                except Exception:
                    pass

    async def _diagnose(self, component: str, error: str) -> Dict:
        prompt = (
            f"Component: {component}\n"
            f"Error: {error}\n"
            f"System context: FastAPI backend + Ollama LLM + ChromaDB memory"
        )
        raw = await self.llm.complete(
            prompt, role="general", system=HEALER_SYSTEM, temperature=0.1
        )
        try:
            raw = re.sub(r"```json|```", "", raw).strip()
            return json.loads(raw)
        except Exception:
            return {
                "diagnosis": error,
                "severity": "medium",
                "auto_fixable": False,
                "fix_action": "alert",
                "fix_params": {},
                "explanation": error,
            }

    # ── Manual Repair ─────────────────────────────────────────────────────────
    async def force_repair(self, component: str) -> Dict:
        if component not in self._repair_callbacks:
            return {"success": False, "error": f"No repair handler for {component}"}
        try:
            await self._repair_callbacks[component]("restart", {})
            return {"success": True, "component": component, "action": "forced_restart"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    # ── Status Report ─────────────────────────────────────────────────────────
    def get_status(self) -> Dict:
        components = {}
        for name, check in self._checks.items():
            components[name] = {
                "status": check.status.value,
                "latency_ms": round(check.latency_ms, 1),
                "error": check.error,
                "last_check": check.checked_at,
            }

        overall = (
            ComponentStatus.HEALTHY.value
            if all(c.status == ComponentStatus.HEALTHY for c in self._checks.values())
            else ComponentStatus.DEGRADED.value
            if any(c.status == ComponentStatus.FAILED for c in self._checks.values())
            else ComponentStatus.UNKNOWN.value
        )

        return {
            "overall": overall,
            "components": components,
            "repair_log": [
                {
                    "component": r.component,
                    "action": r.action,
                    "success": r.success,
                    "message": r.message,
                    "timestamp": r.timestamp,
                }
                for r in self._repair_log[-10:]
            ],
        }

    def get_repair_log(self, limit: int = 20) -> List[Dict]:
        return [
            {
                "component": r.component,
                "action": r.action,
                "success": r.success,
                "message": r.message,
                "timestamp": r.timestamp,
            }
            for r in self._repair_log[-limit:]
        ]
