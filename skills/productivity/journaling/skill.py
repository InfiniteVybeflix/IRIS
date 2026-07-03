"""IRIS Journaling Skill — Placeholder."""
import logging
from skills.base import BaseSkill, SkillCapability
from skills.contracts.skill_request import SkillRequest
from skills.contracts.skill_result import SkillResult
from skills.contracts.capability_tags import CapabilityTags

logger = logging.getLogger(__name__)


class JournalingSkill(BaseSkill):
    name = "journaling"
    display_name = "Journaling"
    description = "Journaling skill — not yet implemented."
    version = "0.1.0"
    category = "productivity"
    icon = "📔"
    uses_storage = False
    supports_background = False

    capabilities = [
        SkillCapability(
            name="placeholder",
            description="Placeholder capability for Journaling",
            tags=[CapabilityTags.JOURNALING],
        ),
    ]

    def execute(self, request: SkillRequest) -> SkillResult:
        return SkillResult.fail(
            error="Journaling skill is not yet implemented.",
            message="Journaling will be available in a future update."
        )

    def can_handle(self, request: SkillRequest) -> float:
        intent = request.intent.lower()
        if "journaling" in intent or any(k in intent for k in ['journaling']):
            return 0.3
        return super().can_handle(request)
