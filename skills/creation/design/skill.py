"""IRIS Design Skill — Placeholder."""
import logging
from skills.base import BaseSkill, SkillCapability
from skills.contracts.skill_request import SkillRequest
from skills.contracts.skill_result import SkillResult
from skills.contracts.capability_tags import CapabilityTags

logger = logging.getLogger(__name__)


class DesignSkill(BaseSkill):
    name = "design"
    display_name = "Design"
    description = "Design skill — not yet implemented."
    version = "0.1.0"
    category = "creation"
    icon = "🎨"
    uses_storage = False
    supports_background = False

    capabilities = [
        SkillCapability(
            name="placeholder",
            description="Placeholder capability for Design",
            tags=[CapabilityTags.DESIGN],
        ),
    ]

    def execute(self, request: SkillRequest) -> SkillResult:
        return SkillResult.fail(
            error="Design skill is not yet implemented.",
            message="Design will be available in a future update."
        )

    def can_handle(self, request: SkillRequest) -> float:
        intent = request.intent.lower()
        if "design" in intent or any(k in intent for k in ['design']):
            return 0.3
        return super().can_handle(request)
