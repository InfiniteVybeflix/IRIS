"""IRIS Decision Support Skill — Placeholder."""
import logging
from skills.base import BaseSkill, SkillCapability
from skills.contracts.skill_request import SkillRequest
from skills.contracts.skill_result import SkillResult
from skills.contracts.capability_tags import CapabilityTags

logger = logging.getLogger(__name__)


class DecisionSupportSkill(BaseSkill):
    name = "decision_support"
    display_name = "Decision Support"
    description = "Decision Support skill — not yet implemented."
    version = "0.1.0"
    category = "intelligence"
    icon = "⚖️"
    uses_storage = False
    supports_background = False

    capabilities = [
        SkillCapability(
            name="placeholder",
            description="Placeholder capability for Decision Support",
            tags=[CapabilityTags.DECISION_SUPPORT],
        ),
    ]

    def execute(self, request: SkillRequest) -> SkillResult:
        return SkillResult.fail(
            error="Decision Support skill is not yet implemented.",
            message="Decision Support will be available in a future update."
        )

    def can_handle(self, request: SkillRequest) -> float:
        intent = request.intent.lower()
        if "decision support" in intent or any(k in intent for k in ['decision', 'support']):
            return 0.3
        return super().can_handle(request)
