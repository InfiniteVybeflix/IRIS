"""Master Wrapper — the single entry point for all skill operations."""
import os
import json
import logging
from typing import Any, Dict, List, Optional
from datetime import datetime

from skills.registry import SkillRegistry
from skills.base import BaseSkill
from skills.contracts.skill_request import SkillRequest
from skills.contracts.skill_result import SkillResult

logger = logging.getLogger(__name__)


class SkillRouter:
    """
    The single entry point for all skill operations in IRIS.
    IRIS talks to this, not to individual skills.
    """

    def __init__(self):
        self.registry = SkillRegistry()
        self._execution_log: List[Dict] = []
        self._max_log_entries = 1000

    # === Discovery ===
    def discover(self) -> Dict[str, Any]:
        """Return full catalog of all skills and capabilities."""
        return self.registry.get_catalog()

    def what_can_you_do(self) -> str:
        """Human-readable summary of capabilities."""
        catalog = self.discover()
        lines = [f"I have {catalog['total_skills']} skills available:"]
        for skill_meta in catalog["skills"]:
            lines.append(f"\n🔹 {skill_meta['display_name']} ({skill_meta['name']})")
            lines.append(f"   {skill_meta['description']}")
            for cap in skill_meta["capabilities"]:
                lines.append(f"   • {cap['name']}: {cap['description']}")
        return "\n".join(lines)

    def list_skills(self) -> List[str]:
        return self.registry.list_names()

    def get_skill_info(self, name: str) -> Optional[Dict[str, Any]]:
        skill = self.registry.get(name)
        return skill.get_metadata() if skill else None

    def has_capability(self, capability_name: str) -> bool:
        return len(self.registry.find_by_capability(capability_name)) > 0

    def who_handles(self, intent: str) -> Optional[str]:
        """Tell me which skill would handle this intent."""
        req = SkillRequest(intent=intent)
        skill = self.registry.route(req)
        return skill.name if skill else None

    # === Execution ===
    def call(self, skill_name: str, **params) -> SkillResult:
        """Direct call to a specific skill."""
        skill = self.registry.get(skill_name)
        if not skill:
            return SkillResult.fail(
                error=f"Skill '{skill_name}' not found",
                suggestions=["Use .list_skills() to see available skills"]
            )
        request = SkillRequest(intent=skill_name, params=params)
        return self._execute_with_logging(skill, request)

    def route_and_execute(self, intent: str, **params) -> SkillResult:
        """Let the router decide which skill handles this."""
        request = SkillRequest(intent=intent, params=params)
        skill = self.registry.route(request)
        if not skill:
            return SkillResult.fail(
                error=f"No skill found for intent: {intent}",
                suggestions=["Try being more specific", "Check .what_can_you_do()"]
            )
        return self._execute_with_logging(skill, request)

    def _execute_with_logging(self, skill: BaseSkill, request: SkillRequest) -> SkillResult:
        result = skill.execute(request)
        self._log_execution(skill.name, request, result)
        return result

    def _log_execution(self, skill_name: str, request: SkillRequest, result: SkillResult):
        entry = {
            "timestamp": datetime.now().isoformat(),
            "skill": skill_name,
            "intent": request.intent,
            "success": result.success,
            "duration_ms": result.duration_ms,
        }
        self._execution_log.append(entry)
        if len(self._execution_log) > self._max_log_entries:
            self._execution_log = self._execution_log[-self._max_log_entries:]

    # === Background ===
    def background_tick(self) -> List[SkillResult]:
        """Run all background-enabled skills. Returns notifications."""
        return self.registry.background_tick_all()

    # === Self-extension hooks ===
    def can_handle(self, intent: str) -> bool:
        """Check if ANY skill can handle this intent."""
        req = SkillRequest(intent=intent)
        return self.registry.route(req) is not None

    def suggest_skill_for_task(self, intent: str) -> Dict[str, Any]:
        """For autonomous skill creation — what would be needed?"""
        req = SkillRequest(intent=intent)
        best = None
        best_score = 0.0
        for name, skill in self.registry._skills.items():
            score = skill.can_handle(req)
            if score > best_score:
                best_score = score
                best = skill
        return {
            "intent": intent,
            "best_match": best.name if best else None,
            "confidence": best_score,
            "needs_new_skill": best_score < 0.4,
            "suggested_category": self._guess_category(intent),
        }

    def _guess_category(self, intent: str) -> str:
        intent_lower = intent.lower()
        keywords = {
            "productivity": ["calendar", "note", "task", "remind", "contact", "meeting", "schedule", "habit", "goal", "journal", "bookmark"],
            "intelligence": ["search", "research", "summarize", "math", "translate", "tutor", "recommend", "plan", "reason"],
            "environment": ["file", "storage", "download", "notification", "device", "app", "setting", "clipboard", "camera", "gallery", "battery", "location", "map", "terminal", "sensor", "smart home", "print"],
            "multimodal": ["voice", "speech", "wake", "tts", "listen", "vision", "ocr", "screen", "image", "video", "avatar", "face", "emotion"],
            "creation": ["code", "repo", "debug", "test", "doc", "document", "spreadsheet", "presentation", "form", "template", "write", "media", "audio", "video", "design", "social", "publish"],
            "commerce": ["payment", "bill", "invoice", "subscription", "order", "crm", "domain", "store", "analytics", "finance"],
            "identity": ["profile", "preference", "personality", "relationship", "trust", "permission", "privacy"],
            "orchestration": ["agent", "copilot", "autonomous", "swarm", "route", "workflow", "decompose", "session", "context", "proactive", "improve", "audit", "observe", "policy", "fallback", "evaluate"],
            "integrations": ["whatsapp", "sms", "phone", "gmail", "google", "notion", "telegram", "slack", "github", "gitlab", "browser", "cloud", "mpesa", "stripe", "tiktok", "youtube", "spotify", "api"],
        }
        for cat, words in keywords.items():
            if any(w in intent_lower for w in words):
                return cat
        return "general"

    def get_execution_log(self, limit: int = 50) -> List[Dict]:
        return self._execution_log[-limit:]


# Singleton
_router: Optional[SkillRouter] = None

def get_router() -> SkillRouter:
    global _router
    if _router is None:
        _router = SkillRouter()
    return _router
