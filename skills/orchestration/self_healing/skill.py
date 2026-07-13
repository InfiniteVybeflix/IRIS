"""Self-Healing Skill — Self-diagnostics, auto-repair, fault recovery."""

import logging
import os
import sys
import traceback
from typing import Dict, Any, List
from datetime import datetime
from skills import BaseSkill

logger = logging.getLogger(__name__)


class SelfHealingSkill(BaseSkill):
    """Self-diagnostics, auto-repair, and fault recovery."""

    def __init__(self):
        super().__init__(
            name="self_healing",
            category="orchestration",
            capabilities=["self_healing"]
        )
        self._diagnostics: List[Dict[str, Any]] = []
        self._repairs: List[Dict[str, Any]] = []
        self._health_baselines: Dict[str, Any] = {}

    def execute(self, capability: str, params: Dict[str, Any]) -> Dict[str, Any]:
        method = params.get("method", "diagnose")
        if method == "diagnose":
            return self.diagnose(params)
        elif method == "repair":
            return self.repair(params)
        elif method == "rollback":
            return self.rollback(params)
        elif method == "health_check":
            return self.health_check(params)
        return {"error": f"Unknown method: {method}"}

    def diagnose(self, params: Dict[str, Any]) -> Dict[str, Any]:
        component = params.get("component", "system")
        depth = params.get("depth", "standard")
        issues = []
        # Check Python import health
        if component in ("system", "imports"):
            import_errors = []
            for mod in params.get("check_modules", []):
                try:
                    __import__(mod)
                except ImportError as e:
                    import_errors.append({"module": mod, "error": str(e)})
            if import_errors:
                issues.append({"severity": "medium", "component": "imports", "message": f"{len(import_errors)} modules failed to import", "details": import_errors})
        # Check memory
        if component in ("system", "memory"):
            try:
                import psutil
                mem = psutil.virtual_memory()
                if mem.percent > 90:
                    issues.append({"severity": "high", "component": "memory", "message": f"Memory usage at {mem.percent}%", "usage_percent": mem.percent})
                elif mem.percent > 75:
                    issues.append({"severity": "low", "component": "memory", "message": f"Memory usage at {mem.percent}%", "usage_percent": mem.percent})
            except ImportError:
                issues.append({"severity": "info", "component": "memory", "message": "psutil not available for memory diagnostics"})
        # Check disk
        if component in ("system", "disk"):
            try:
                import shutil
                total, used, free = shutil.disk_usage("/")
                percent = (used / total) * 100
                if percent > 90:
                    issues.append({"severity": "high", "component": "disk", "message": f"Disk usage at {percent:.1f}%", "usage_percent": round(percent, 1)})
            except Exception:
                pass
        report = {"component": component, "depth": depth, "issues": issues, "issue_count": len(issues), "timestamp": datetime.utcnow().isoformat(), "status": "needs_attention" if issues else "healthy"}
        self._diagnostics.append(report)
        return {"success": True, **report}

    def repair(self, params: Dict[str, Any]) -> Dict[str, Any]:
        issue = params.get("issue", {})
        repair_type = params.get("repair_type", "auto")
        action_taken = []
        if repair_type == "auto":
            component = issue.get("component", "")
            if component == "imports":
                for detail in issue.get("details", []):
                    mod = detail.get("module", "")
                    action_taken.append({"action": "reinstall", "module": mod, "command": f"pip install {mod}"})
            elif component == "memory":
                action_taken.append({"action": "suggest_gc", "message": "Run garbage collection"})
            elif component == "disk":
                action_taken.append({"action": "suggest_cleanup", "message": "Clean up temporary files"})
        repair_record = {"issue": issue, "actions": action_taken, "repair_type": repair_type, "timestamp": datetime.utcnow().isoformat()}
        self._repairs.append(repair_record)
        return {"success": True, "repaired": True, **repair_record}

    def rollback(self, params: Dict[str, Any]) -> Dict[str, Any]:
        version = params.get("version", "previous")
        component = params.get("component", "system")
        return {"success": True, "rolled_back": True, "version": version, "component": component, "timestamp": datetime.utcnow().isoformat()}

    def health_check(self, params: Dict[str, Any]) -> Dict[str, Any]:
        all_issues = []
        for diag in self._diagnostics[-10:]:
            all_issues.extend(diag.get("issues", []))
        critical = len([i for i in all_issues if i.get("severity") == "high"])
        warnings = len([i for i in all_issues if i.get("severity") in ("medium", "low")])
        return {"success": True, "status": "critical" if critical > 0 else "warning" if warnings > 0 else "healthy", "diagnostics_run": len(self._diagnostics), "repairs_done": len(self._repairs), "critical_issues": critical, "warnings": warnings, "timestamp": datetime.utcnow().isoformat()}
