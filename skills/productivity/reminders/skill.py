"""IRIS Reminders Skill — Placeholder."""
import logging
from skills.base import BaseSkill, SkillCapability
from skills.contracts.skill_request import SkillRequest
from skills.contracts.skill_result import SkillResult
from skills.contracts.capability_tags import CapabilityTags

logger = logging.getLogger(__name__)


class RemindersSkill(BaseSkill):
    name = "reminders"
    display_name = "Reminders"
    description = "Reminders skill — not yet implemented."
    version = "0.1.0"
    category = "productivity"
    icon = "⏰"
    uses_storage = False
    supports_background = False

    capabilities = [
        SkillCapability(
            name="placeholder",
            description="Placeholder capability for Reminders",
            tags=[CapabilityTags.REMINDERS],
        ),
    ]

    def execute(self, request: SkillRequest) -> SkillResult:
        return SkillResult.fail(
            error="Reminders skill is not yet implemented.",
            message="Reminders will be available in a future update."
        )

    def can_handle(self, request: SkillRequest) -> float:
        intent = request.intent.lower()
        if "reminders" in intent or any(k in intent for k in ['reminders']):
            return 0.3
        return super().can_handle(request)
