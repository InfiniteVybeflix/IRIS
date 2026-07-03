"""IRIS Personality Skill — Placeholder."""
import logging
from skills.base import BaseSkill, SkillCapability
from skills.contracts.skill_request import SkillRequest
from skills.contracts.skill_result import SkillResult
from skills.contracts.capability_tags import CapabilityTags

logger = logging.getLogger(__name__)


class PersonalitySkill(BaseSkill):
    name = "personality"
    display_name = "Personality"
    description = "Personality skill — not yet implemented."
    version = "0.1.0"
    category = "identity"
    icon = "🎭"
    uses_storage = False
    supports_background = False

    capabilities = [
        SkillCapability(
            name="placeholder",
            description="Placeholder capability for Personality",
            tags=[CapabilityTags.PERSONALITY],
        ),
    ]

    def execute(self, request: SkillRequest) -> SkillResult:
        return SkillResult.fail(
            error="Personality skill is not yet implemented.",
            message="Personality will be available in a future update."
        )

    def can_handle(self, request: SkillRequest) -> float:
        intent = request.intent.lower()
        if "personality" in intent or any(k in intent for k in ['personality']):
            return 0.3
        return super().can_handle(request)
