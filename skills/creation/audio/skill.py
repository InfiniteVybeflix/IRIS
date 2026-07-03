"""IRIS Audio Skill — Placeholder."""
import logging
from skills.base import BaseSkill, SkillCapability
from skills.contracts.skill_request import SkillRequest
from skills.contracts.skill_result import SkillResult
from skills.contracts.capability_tags import CapabilityTags

logger = logging.getLogger(__name__)


class AudioSkill(BaseSkill):
    name = "audio"
    display_name = "Audio"
    description = "Audio skill — not yet implemented."
    version = "0.1.0"
    category = "creation"
    icon = "🎧"
    uses_storage = False
    supports_background = False

    capabilities = [
        SkillCapability(
            name="placeholder",
            description="Placeholder capability for Audio",
            tags=[CapabilityTags.AUDIO],
        ),
    ]

    def execute(self, request: SkillRequest) -> SkillResult:
        return SkillResult.fail(
            error="Audio skill is not yet implemented.",
            message="Audio will be available in a future update."
        )

    def can_handle(self, request: SkillRequest) -> float:
        intent = request.intent.lower()
        if "audio" in intent or any(k in intent for k in ['audio']):
            return 0.3
        return super().can_handle(request)
