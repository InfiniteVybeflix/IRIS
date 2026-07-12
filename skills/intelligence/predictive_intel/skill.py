"""IRIS v7 Predictive Intel Skill — Predictive Analysis"""
import json
import logging
import os
import statistics
import threading
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

from skills.base import BaseSkill, SkillCapability
from skills.contracts.skill_request import SkillRequest
from skills.contracts.skill_result import SkillResult
from skills.contracts.capability_tags import CapabilityTags

logger = logging.getLogger(__name__)


class PredictiveIntelSkill(BaseSkill):
    name = "predictive_intel"
    display_name = "Predictive Intelligence"
    description = "Predictive analysis — system failure prediction, security breach prediction, performance bottleneck forecasting, anomaly prediction, and risk scoring."
    version = "7.0.0"
    category = "intelligence"
    icon = "🔮"
    uses_storage = True
    storage_dir = "data/skills/predictive_intel"
    storage_file = "data/skills/predictive_intel/models.json"

    capabilities = [
        SkillCapability(name="predict_failure", description="Predict system failure", input_schema={"metrics": "list"}, tags=[CapabilityTags.OBSERVABILITY]),
        SkillCapability(name="predict_breach", description="Predict security breach", input_schema={"indicators": "list"}, tags=[CapabilityTags.TRUST_SAFETY]),
        SkillCapability(name="predict_bottleneck", description="Predict performance bottleneck", input_schema={"performance_data": "list"}, tags=[CapabilityTags.OBSERVABILITY]),
        SkillCapability(name="anomaly_forecast", description="Forecast anomalies", input_schema={"time_series": "list"}, tags=[CapabilityTags.OBSERVABILITY]),
        SkillCapability(name="risk_score", description="Calculate risk score", input_schema={"factors": "dict"}, tags=[CapabilityTags.DECISION_SUPPORT]),
    ]

    def execute(self, request):
        intent = request.intent.lower()
        p = request.params
        try:
            if "failure" in intent: return self._failure(p.get("metrics", []))
            elif "breach" in intent: return self._breach(p.get("indicators", []))
            elif "bottleneck" in intent: return self._bottleneck(p.get("performance_data", []))
            elif "anomal" in intent: return self._anomaly(p.get("time_series", []))
            elif "risk" in intent: return self._risk(p.get("factors", {}))
            return SkillResult.fail(error=f"Unknown: {intent}")
        except Exception as e:
            return SkillResult.fail(error=str(e))

    def can_handle(self, request):
        return 0.9 if any(k in request.intent.lower() for k in ["predict", "forecast", "risk_score", "anomaly"]) else super().can_handle(request)

    def _failure(self, metrics: list) -> SkillResult:
        if len(metrics) < 3: return SkillResult.ok(message="Need more data", data={})
        trend = metrics[-1] - metrics[0]
        predicted = metrics[-1] + trend * 0.5
        risk = "HIGH" if predicted > 90 else "MEDIUM" if predicted > 75 else "LOW"
        return SkillResult.ok(message=f"Failure prediction: {risk}", data={"predicted_value": round(predicted, 2), "risk": risk, "confidence": min(0.95, 0.5 + len(metrics) * 0.05), "recommendation": "Scale resources immediately" if risk == "HIGH" else "Monitor closely"})

    def _breach(self, indicators: list) -> SkillResult:
        score = 0
        weights = {"failed_login": 5, "privilege_escalation": 20, "data_access": 15, "malware_detected": 25, "lateral_movement": 20, "exfiltration": 25}
        for ind in indicators:
            score += weights.get(ind.lower(), 10)
        risk = "CRITICAL" if score > 60 else "HIGH" if score > 40 else "MEDIUM" if score > 20 else "LOW"
        return SkillResult.ok(message=f"Breach prediction: {risk} ({score}/100)", data={"score": score, "risk": risk, "top_indicators": indicators[:3], "recommendation": "Activate incident response" if risk in ("CRITICAL", "HIGH") else "Increase monitoring"})

    def _bottleneck(self, data: list) -> SkillResult:
        if not data: return SkillResult.fail(error="Data required")
        avg = statistics.mean(data)
        std = statistics.stdev(data) if len(data) > 1 else 0
        threshold = avg + 2 * std
        peaks = [v for v in data if v > threshold]
        return SkillResult.ok(message=f"Bottleneck: {len(peaks)} peaks detected", data={"average": round(avg, 2), "threshold": round(threshold, 2), "peak_count": len(peaks), "predicted_location": "Database layer" if avg > 80 else "API layer"})

    def _anomaly(self, series: list) -> SkillResult:
        if len(series) < 5: return SkillResult.ok(message="Need more data points", data={})
        mean = statistics.mean(series)
        std = statistics.stdev(series)
        anomalies = [{"index": i, "value": v, "deviation": round(abs(v - mean) / std, 2)} for i, v in enumerate(series) if abs(v - mean) > 2 * std]
        return SkillResult.ok(message=f"Anomaly forecast: {len(anomalies)} anomalies", data={"anomalies": anomalies, "mean": round(mean, 2), "std": round(std, 2), "forecast": "Increasing anomaly rate" if len(anomalies) > len(series) * 0.1 else "Stable"})

    def _risk(self, factors: dict) -> SkillResult:
        if not factors: return SkillResult.fail(error="Factors required")
        total_score = sum(v * w for v, w in [(factors.get("critical_assets", 5), 3), (factors.get("threat_exposure", 5), 2), (factors.get("vuln_count", 0), 5), (factors.get("patch_lag_days", 0), 0.5), (factors.get("incident_history", 0), 10)])
        risk_level = "CRITICAL" if total_score > 80 else "HIGH" if total_score > 50 else "MEDIUM" if total_score > 25 else "LOW"
        return SkillResult.ok(message=f"Risk score: {total_score}/100 ({risk_level})", data={"score": total_score, "level": risk_level, "factors": factors, "priority_actions": ["Patch critical vulns", "Enable MFA", "Review access controls"] if risk_level in ("CRITICAL", "HIGH") else ["Continue monitoring"]})
