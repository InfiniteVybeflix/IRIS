"""IRIS Voice Skill — Placeholder."""
import logging
from skills.base import BaseSkill, SkillCapability
from skills.contracts.skill_request import SkillRequest
from skills.contracts.skill_result import SkillResult
from skills.contracts.capability_tags import CapabilityTags

logger = logging.getLogger(__name__)


class VoiceSkill(BaseSkill):
    name = "voice"
    display_name = "Voice"
    description = "Voice skill — not yet implemented."
    version = "0.1.0"
    category = "multimodal"
    icon = "🎙️"
    uses_storage = False
    supports_background = False

    capabilities = [
        SkillCapability(
            name="placeholder",
            description="Placeholder capability for Voice",
            tags=[CapabilityTags.VOICE],
        ),
    ]

    def execute(self, request: SkillRequest) -> SkillResult:
        return SkillResult.fail(
            error="Voice skill is not yet implemented.",
            message="Voice will be available in a future update."
        )

    def can_handle(self, request: SkillRequest) -> float:
        intent = request.intent.lower()
        if "voice" in intent or any(k in intent for k in ['voice']):
            return 0.3
        return super().can_handle(request)
