"""IRIS Listening Mode Skill — Placeholder."""
import logging
from skills.base import BaseSkill, SkillCapability
from skills.contracts.skill_request import SkillRequest
from skills.contracts.skill_result import SkillResult
from skills.contracts.capability_tags import CapabilityTags

logger = logging.getLogger(__name__)


class ListeningModeSkill(BaseSkill):
    name = "listening_mode"
    display_name = "Listening Mode"
    description = "Listening Mode skill — not yet implemented."
    version = "0.1.0"
    category = "multimodal"
    icon = "👁️"
    uses_storage = False
    supports_background = False

    capabilities = [
        SkillCapability(
            name="placeholder",
            description="Placeholder capability for Listening Mode",
            tags=[CapabilityTags.LISTENING_MODE],
        ),
    ]

    def execute(self, request: SkillRequest) -> SkillResult:
        return SkillResult.fail(
            error="Listening Mode skill is not yet implemented.",
            message="Listening Mode will be available in a future update."
        )

    def can_handle(self, request: SkillRequest) -> float:
        intent = request.intent.lower()
        if "listening mode" in intent or any(k in intent for k in ['listening', 'mode']):
            return 0.3
        return super().can_handle(request)
