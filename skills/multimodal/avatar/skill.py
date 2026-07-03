"""IRIS Avatar Skill — Placeholder."""
import logging
from skills.base import BaseSkill, SkillCapability
from skills.contracts.skill_request import SkillRequest
from skills.contracts.skill_result import SkillResult
from skills.contracts.capability_tags import CapabilityTags

logger = logging.getLogger(__name__)


class AvatarSkill(BaseSkill):
    name = "avatar"
    display_name = "Avatar"
    description = "Avatar skill — not yet implemented."
    version = "0.1.0"
    category = "multimodal"
    icon = "👤"
    uses_storage = False
    supports_background = False

    capabilities = [
        SkillCapability(
            name="placeholder",
            description="Placeholder capability for Avatar",
            tags=[CapabilityTags.AVATAR],
        ),
    ]

    def execute(self, request: SkillRequest) -> SkillResult:
        return SkillResult.fail(
            error="Avatar skill is not yet implemented.",
            message="Avatar will be available in a future update."
        )

    def can_handle(self, request: SkillRequest) -> float:
        intent = request.intent.lower()
        if "avatar" in intent or any(k in intent for k in ['avatar']):
            return 0.3
        return super().can_handle(request)
