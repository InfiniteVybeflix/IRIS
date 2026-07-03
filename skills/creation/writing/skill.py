"""IRIS Writing Skill — Placeholder."""
import logging
from skills.base import BaseSkill, SkillCapability
from skills.contracts.skill_request import SkillRequest
from skills.contracts.skill_result import SkillResult
from skills.contracts.capability_tags import CapabilityTags

logger = logging.getLogger(__name__)


class WritingSkill(BaseSkill):
    name = "writing"
    display_name = "Writing"
    description = "Writing skill — not yet implemented."
    version = "0.1.0"
    category = "creation"
    icon = "✍️"
    uses_storage = False
    supports_background = False

    capabilities = [
        SkillCapability(
            name="placeholder",
            description="Placeholder capability for Writing",
            tags=[CapabilityTags.WRITING],
        ),
    ]

    def execute(self, request: SkillRequest) -> SkillResult:
        return SkillResult.fail(
            error="Writing skill is not yet implemented.",
            message="Writing will be available in a future update."
        )

    def can_handle(self, request: SkillRequest) -> float:
        intent = request.intent.lower()
        if "writing" in intent or any(k in intent for k in ['writing']):
            return 0.3
        return super().can_handle(request)
