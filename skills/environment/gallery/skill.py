"""IRIS Gallery Skill — Placeholder."""
import logging
from skills.base import BaseSkill, SkillCapability
from skills.contracts.skill_request import SkillRequest
from skills.contracts.skill_result import SkillResult
from skills.contracts.capability_tags import CapabilityTags

logger = logging.getLogger(__name__)


class GallerySkill(BaseSkill):
    name = "gallery"
    display_name = "Gallery"
    description = "Gallery skill — not yet implemented."
    version = "0.1.0"
    category = "environment"
    icon = "🖼️"
    uses_storage = False
    supports_background = False

    capabilities = [
        SkillCapability(
            name="placeholder",
            description="Placeholder capability for Gallery",
            tags=[CapabilityTags.GALLERY],
        ),
    ]

    def execute(self, request: SkillRequest) -> SkillResult:
        return SkillResult.fail(
            error="Gallery skill is not yet implemented.",
            message="Gallery will be available in a future update."
        )

    def can_handle(self, request: SkillRequest) -> float:
        intent = request.intent.lower()
        if "gallery" in intent or any(k in intent for k in ['gallery']):
            return 0.3
        return super().can_handle(request)
