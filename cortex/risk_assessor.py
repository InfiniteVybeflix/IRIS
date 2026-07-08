"""
IRIS v7.0 — RiskAssessor
Pre-execution risk analysis engine.

Evaluates risk of every action before execution across multiple
dimensions: operational, legal, reputational, and technical.
Generates mitigations and determines if human approval is required.

Features:
- Assess action risk with score and mitigations
- Evaluate legal compliance by jurisdiction
- Assess reputational impact
- Evaluate technical failure risk
- Generate specific risk reduction steps
- Determine if human approval is needed

Storage:
    SQLite table `risk_assessments` (JSON fallback).

Usage:
    ra = RiskAssessor()
    risk = ra.assess_action("port_scan", "192.168.1.1", {"stealth": True})
    legal = ra.assess_legal_compliance("port_scan", "US")
    mitigations = ra.generate_mitigations(risk["data"])
    needs_approval = ra.require_approval(risk["data"]["score"])

Author: IRIS Core Team
"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from .base_cortex import BaseCortex

logger = logging.getLogger("iris.cortex.risk_assessor")


class RiskAssessor(BaseCortex):
    """
    Multi-dimensional risk assessment engine.

    Evaluates actions across operational, legal, reputational, and
    technical dimensions before execution. Provides actionable
    mitigations and approval thresholds.
    """

    def __init__(
        self,
        db_path: Optional[str] = None,
        iris_core: Optional[Any] = None,
    ) -> None:
        """
        Initialize RiskAssessor.

        Args:
            db_path: Path to SQLite database. Defaults to env var
                     IRIS_RISK_DB or "iris_risk_assessor.db".
            iris_core: Reference to IRIS core.
        """
        super().__init__(
            db_path=db_path or os.getenv("IRIS_RISK_DB", "iris_risk_assessor.db"),
            iris_core=iris_core,
        )
        self._create_risk_tables()

    def _create_risk_tables(self) -> None:
        """Create risk assessment tables."""
        with self._lock:
            if self._conn:
                self._conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS risk_assessments (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        assessment_id TEXT NOT NULL UNIQUE,
                        action TEXT NOT NULL,
                        target TEXT,
                        risk_score REAL,
                        risk_category TEXT,
                        mitigations TEXT,
                        requires_approval INTEGER,
                        created_at TEXT DEFAULT CURRENT_TIMESTAMP
                    )
                    """
                )
                self._conn.commit()

    # ------------------------------------------------------------------
    # Core reasoning
    # ------------------------------------------------------------------
    def reason(self, input_data: Any, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Core reasoning: assess risk of an action.

        Args:
            input_data: Dict with action, target, and context.
            context: Optional additional context.

        Returns:
            Standard result with risk assessment.
        """
        if isinstance(input_data, dict):
            return self.assess_action(
                input_data.get("action", ""),
                input_data.get("target", ""),
                context or input_data.get("context"),
            )
        return self._result(False, "reason", errors=["Input must be dict with action and target"])

    # ------------------------------------------------------------------
    # Risk assessment methods
    # ------------------------------------------------------------------
    def assess_action(
        self,
        action: str,
        target: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Assess overall risk of an action against a target.

        Args:
            action: Action name/type.
            target: Target identifier.
            context: Optional context dict.

        Returns:
            Standard result with risk score (0.0-1.0) and mitigations.
        """
        start = time.perf_counter()
        try:
            ctx = context or {}
            action_lower = action.lower()

            # Base risk by action type
            base_risk = 0.3
            high_risk_actions = ["exploit", "attack", "disrupt", "delete", "modify", "inject"]
            medium_risk_actions = ["scan", "enumerate", "probe", "test"]
            low_risk_actions = ["reconnaissance", "monitor", "analyze", "report"]

            if any(a in action_lower for a in high_risk_actions):
                base_risk = 0.8
            elif any(a in action_lower for a in medium_risk_actions):
                base_risk = 0.5
            elif any(a in action_lower for a in low_risk_actions):
                base_risk = 0.2

            # Target sensitivity modifier
            target_sensitivity = ctx.get("target_sensitivity", 5)
            sensitivity_factor = target_sensitivity / 10.0

            # Stealth modifier
            stealth = ctx.get("stealth", False)
            stealth_factor = -0.15 if stealth else 0.0

            # Environment modifier
            env = ctx.get("environment", "production")
            env_factor = 0.2 if env == "production" else 0.0 if env == "staging" else -0.1

            # Calculate final score
            score = base_risk + (sensitivity_factor * 0.3) + stealth_factor + env_factor
            score = max(0.0, min(1.0, score))

            # Determine category
            if score >= 0.7:
                category = "high"
            elif score >= 0.4:
                category = "medium"
            else:
                category = "low"

            # Generate mitigations
            mitigations = self._generate_action_mitigations(action, score, ctx)

            result = {
                "action": action,
                "target": target,
                "risk_score": round(score, 4),
                "risk_category": category,
                "factors": {
                    "base_risk": base_risk,
                    "sensitivity": sensitivity_factor,
                    "stealth": stealth_factor,
                    "environment": env_factor,
                },
                "mitigations": mitigations,
                "requires_approval": score >= 0.7,
            }

            # Persist
            if self._conn:
                aid = f"risk_{int(time.time() * 1000)}"
                self._conn.execute(
                    """
                    INSERT INTO risk_assessments
                    (assessment_id, action, target, risk_score, risk_category, mitigations, requires_approval)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (aid, action, target, score, category, json.dumps(mitigations), 1 if score >= 0.7 else 0),
                )
                self._conn.commit()

            duration_ms = int((time.perf_counter() - start) * 1000)
            self._log_reasoning("assess_action", {"action": action, "target": target}, result, 1.0 - score, duration_ms)
            return self._result(True, "assess_action", result, confidence=1.0 - score, duration_ms=duration_ms)
        except Exception as exc:
            return self._result(False, "assess_action", errors=[str(exc)])

    def _generate_action_mitigations(self, action: str, score: float, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Generate mitigations based on action and score."""
        mitigations = []
        action_lower = action.lower()

        if score >= 0.7:
            mitigations.append({"priority": "critical", "action": "Obtain explicit authorization before execution"})
            mitigations.append({"priority": "critical", "action": "Document all actions for audit trail"})

        if any(a in action_lower for a in ["scan", "probe", "enumerate"]):
            mitigations.append({"priority": "high", "action": "Use rate limiting to avoid detection"})
            mitigations.append({"priority": "medium", "action": "Randomize scan timing"})

        if any(a in action_lower for a in ["exploit", "attack", "inject"]):
            mitigations.append({"priority": "critical", "action": "Verify target ownership and authorization"})
            mitigations.append({"priority": "high", "action": "Use isolated test environment first"})
            mitigations.append({"priority": "high", "action": "Prepare rollback procedures"})

        if context.get("stealth"):
            mitigations.append({"priority": "medium", "action": "Use proxy chains and obfuscation"})
            mitigations.append({"priority": "low", "action": "Monitor for countermeasures"})

        if context.get("environment") == "production":
            mitigations.append({"priority": "high", "action": "Schedule during maintenance window"})
            mitigations.append({"priority": "medium", "action": "Notify stakeholders in advance"})

        if not mitigations:
            mitigations.append({"priority": "low", "action": "Proceed with standard monitoring"})

        return mitigations

    def assess_legal_compliance(
        self,
        action: str,
        jurisdiction: str,
    ) -> Dict[str, Any]:
        """
        Evaluate legal risk of an action in a jurisdiction.

        Args:
            action: Action name.
            jurisdiction: Jurisdiction code (e.g., "US", "EU", "CN").

        Returns:
            Standard result with legal risk assessment.
        """
        start = time.perf_counter()
        try:
            action_lower = action.lower()
            jurisdiction_upper = jurisdiction.upper()

            # Jurisdiction-specific risk baselines
            jurisdiction_risk = {
                "US": {"cfaa": 0.7, "privacy": 0.6},
                "EU": {"gdpr": 0.8, "privacy": 0.9},
                "CN": {"cybersecurity": 0.9, "data": 0.8},
                "UK": {"computer_misuse": 0.7, "privacy": 0.7},
                "DEFAULT": {"general": 0.5},
            }

            laws = jurisdiction_risk.get(jurisdiction_upper, jurisdiction_risk["DEFAULT"])

            # Action-specific legal risk
            legal_risk = 0.3
            if any(a in action_lower for a in ["unauthorized", "bypass", "breach"]):
                legal_risk = 0.95
            elif any(a in action_lower for a in ["exploit", "attack", "inject"]):
                legal_risk = 0.85
            elif any(a in action_lower for a in ["scan", "probe", "enumerate"]):
                legal_risk = 0.5
            elif any(a in action_lower for a in ["reconnaissance", "monitor", "analyze"]):
                legal_risk = 0.2

            # Combine
            max_law_risk = max(laws.values())
            combined = max(legal_risk, max_law_risk)

            result = {
                "action": action,
                "jurisdiction": jurisdiction_upper,
                "legal_risk_score": round(combined, 4),
                "applicable_laws": list(laws.keys()),
                "risk_level": "high" if combined >= 0.7 else "medium" if combined >= 0.4 else "low",
                "recommendation": "Obtain legal counsel" if combined >= 0.7 else "Document compliance measures",
            }
            duration_ms = int((time.perf_counter() - start) * 1000)
            return self._result(True, "assess_legal_compliance", result, duration_ms=duration_ms)
        except Exception as exc:
            return self._result(False, "assess_legal_compliance", errors=[str(exc)])

    def assess_reputational_risk(
        self,
        action: str,
        client_context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Assess potential reputational impact of an action.

        Args:
            action: Action name.
            client_context: Dict with client sensitivity, public visibility.

        Returns:
            Standard result with reputational risk assessment.
        """
        start = time.perf_counter()
        try:
            ctx = client_context or {}
            action_lower = action.lower()

            base = 0.3
            if any(a in action_lower for a in ["data_breach", "leak", "expose"]):
                base = 0.95
            elif any(a in action_lower for a in ["disrupt", "denial", "deface"]):
                base = 0.8
            elif any(a in action_lower for a in ["exploit", "attack"]):
                base = 0.6

            # Client modifiers
            client_visibility = ctx.get("public_visibility", 5)
            client_sensitivity = ctx.get("client_sensitivity", 5)
            modifier = (client_visibility + client_sensitivity) / 20.0

            score = min(1.0, base + modifier * 0.3)

            result = {
                "action": action,
                "reputational_risk_score": round(score, 4),
                "risk_level": "high" if score >= 0.7 else "medium" if score >= 0.4 else "low",
                "factors": {
                    "action_base": base,
                    "client_visibility": client_visibility,
                    "client_sensitivity": client_sensitivity,
                },
                "mitigations": [
                    "Maintain confidentiality agreements",
                    "Use anonymized reporting where possible",
                    "Prepare crisis communication plan" if score >= 0.7 else "Standard reporting procedures",
                ],
            }
            duration_ms = int((time.perf_counter() - start) * 1000)
            return self._result(True, "assess_reputational_risk", result, duration_ms=duration_ms)
        except Exception as exc:
            return self._result(False, "assess_reputational_risk", errors=[str(exc)])

    def assess_technical_risk(
        self,
        action: str,
        system_context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Evaluate technical failure risk of an action.

        Args:
            action: Action name.
            system_context: Dict with system stability, redundancy, complexity.

        Returns:
            Standard result with technical risk assessment.
        """
        start = time.perf_counter()
        try:
            ctx = system_context or {}
            action_lower = action.lower()

            base = 0.2
            if any(a in action_lower for a in ["modify", "delete", "patch", "update"]):
                base = 0.5
            elif any(a in action_lower for a in ["exploit", "inject", "overflow"]):
                base = 0.7
            elif any(a in action_lower for a in ["reboot", "restart", "shutdown"]):
                base = 0.6

            # System modifiers
            stability = ctx.get("system_stability", 5)
            redundancy = ctx.get("has_redundancy", False)
            complexity = ctx.get("system_complexity", 5)

            stability_factor = (10 - stability) / 20.0
            redundancy_factor = -0.15 if redundancy else 0.0
            complexity_factor = complexity / 20.0

            score = min(1.0, base + stability_factor + complexity_factor + redundancy_factor)

            result = {
                "action": action,
                "technical_risk_score": round(score, 4),
                "risk_level": "high" if score >= 0.7 else "medium" if score >= 0.4 else "low",
                "factors": {
                    "action_base": base,
                    "stability": stability_factor,
                    "redundancy": redundancy_factor,
                    "complexity": complexity_factor,
                },
                "recommendations": [
                    "Create system snapshot before action" if score >= 0.5 else "Standard backup procedures",
                    "Test in isolated environment first" if score >= 0.7 else "Monitor during execution",
                    "Have rollback plan ready" if score >= 0.6 else "Document changes",
                ],
            }
            duration_ms = int((time.perf_counter() - start) * 1000)
            return self._result(True, "assess_technical_risk", result, duration_ms=duration_ms)
        except Exception as exc:
            return self._result(False, "assess_technical_risk", errors=[str(exc)])

    def generate_mitigations(self, risks: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Generate specific risk reduction steps from a risk assessment.

        Args:
            risks: Risk assessment dict.

        Returns:
            List of mitigation dicts.
        """
        start = time.perf_counter()
        try:
            mitigations = risks.get("mitigations", [])
            if not mitigations:
                score = risks.get("risk_score", 0.5)
                action = risks.get("action", "unknown")
                mitigations = self._generate_action_mitigations(action, score, {})
            duration_ms = int((time.perf_counter() - start) * 1000)
            return self._result(True, "generate_mitigations", mitigations, duration_ms=duration_ms)
        except Exception as exc:
            return self._result(False, "generate_mitigations", errors=[str(exc)])

    def require_approval(self, risk_level: float) -> bool:
        """
        Determine if human approval is needed based on risk level.

        Args:
            risk_level: Risk score 0.0-1.0.

        Returns:
            True if approval required (score >= 0.7).
        """
        return risk_level >= 0.7


# ------------------------------------------------------------------
# Usage example
# ------------------------------------------------------------------
if __name__ == "__main__":
    ra = RiskAssessor()
    risk = ra.assess_action("port_scan", "192.168.1.1", {"stealth": True, "environment": "production"})
    print(json.dumps(risk, indent=2))
    print("Requires approval:", ra.require_approval(risk["data"]["risk_score"]))
