"""IRIS Forms Skill — Placeholder."""
import logging
from skills.base import BaseSkill, SkillCapability
from skills.contracts.skill_request import SkillRequest
from skills.contracts.skill_result import SkillResult
from skills.contracts.capability_tags import CapabilityTags

logger = logging.getLogger(__name__)


class FormsSkill(BaseSkill):
    name = "forms"
    display_name = "Forms"
    description = "Forms skill — not yet implemented."
    version = "0.1.0"
    category = "creation"
    icon = "📝"
    uses_storage = False
    supports_background = False

    capabilities = [
        SkillCapability(
            name="placeholder",
            description="Placeholder capability for Forms",
            tags=[CapabilityTags.FORMS],
        ),
    ]

    def execute(self, request: SkillRequest) -> SkillResult:
        return SkillResult.fail(
            error="Forms skill is not yet implemented.",
            message="Forms will be available in a future update."
        )

    def can_handle(self, request: SkillRequest) -> float:
        intent = request.intent.lower()
        if "forms" in intent or any(k in intent for k in ['forms']):
            return 0.3
        return super().can_handle(request)
