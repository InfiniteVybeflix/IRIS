"""IRIS Video Skill — Placeholder."""
import logging
from skills.base import BaseSkill, SkillCapability
from skills.contracts.skill_request import SkillRequest
from skills.contracts.skill_result import SkillResult
from skills.contracts.capability_tags import CapabilityTags

logger = logging.getLogger(__name__)


class VideoSkill(BaseSkill):
    name = "video"
    display_name = "Video"
    description = "Video skill — not yet implemented."
    version = "0.1.0"
    category = "creation"
    icon = "🎬"
    uses_storage = False
    supports_background = False

    capabilities = [
        SkillCapability(
            name="placeholder",
            description="Placeholder capability for Video",
            tags=[CapabilityTags.VIDEO],
        ),
    ]

    def execute(self, request: SkillRequest) -> SkillResult:
        return SkillResult.fail(
            error="Video skill is not yet implemented.",
            message="Video will be available in a future update."
        )

    def can_handle(self, request: SkillRequest) -> float:
        intent = request.intent.lower()
        if "video" in intent or any(k in intent for k in ['video']):
            return 0.3
        return super().can_handle(request)
