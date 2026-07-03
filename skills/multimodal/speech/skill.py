"""IRIS Speech Skill — Placeholder."""
import logging
from skills.base import BaseSkill, SkillCapability
from skills.contracts.skill_request import SkillRequest
from skills.contracts.skill_result import SkillResult
from skills.contracts.capability_tags import CapabilityTags

logger = logging.getLogger(__name__)


class SpeechSkill(BaseSkill):
    name = "speech"
    display_name = "Speech"
    description = "Speech skill — not yet implemented."
    version = "0.1.0"
    category = "multimodal"
    icon = "🗣️"
    uses_storage = False
    supports_background = False

    capabilities = [
        SkillCapability(
            name="placeholder",
            description="Placeholder capability for Speech",
            tags=[CapabilityTags.SPEECH],
        ),
    ]

    def execute(self, request: SkillRequest) -> SkillResult:
        return SkillResult.fail(
            error="Speech skill is not yet implemented.",
            message="Speech will be available in a future update."
        )

    def can_handle(self, request: SkillRequest) -> float:
        intent = request.intent.lower()
        if "speech" in intent or any(k in intent for k in ['speech']):
            return 0.3
        return super().can_handle(request)
