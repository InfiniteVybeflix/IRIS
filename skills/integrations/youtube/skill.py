"""IRIS YouTube Skill — Placeholder."""
import logging
from skills.base import BaseSkill, SkillCapability
from skills.contracts.skill_request import SkillRequest
from skills.contracts.skill_result import SkillResult
from skills.contracts.capability_tags import CapabilityTags

logger = logging.getLogger(__name__)


class YoutubeSkill(BaseSkill):
    name = "youtube"
    display_name = "YouTube"
    description = "YouTube skill — not yet implemented."
    version = "0.1.0"
    category = "integrations"
    icon = "▶️"
    uses_storage = False
    supports_background = False

    capabilities = [
        SkillCapability(
            name="placeholder",
            description="Placeholder capability for YouTube",
            tags=[CapabilityTags.YOUTUBE],
        ),
    ]

    def execute(self, request: SkillRequest) -> SkillResult:
        return SkillResult.fail(
            error="YouTube skill is not yet implemented.",
            message="YouTube will be available in a future update."
        )

    def can_handle(self, request: SkillRequest) -> float:
        intent = request.intent.lower()
        if "youtube" in intent or any(k in intent for k in ['youtube']):
            return 0.3
        return super().can_handle(request)
