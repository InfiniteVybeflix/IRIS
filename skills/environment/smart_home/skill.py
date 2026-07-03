"""IRIS Smart Home Skill — Placeholder."""
import logging
from skills.base import BaseSkill, SkillCapability
from skills.contracts.skill_request import SkillRequest
from skills.contracts.skill_result import SkillResult
from skills.contracts.capability_tags import CapabilityTags

logger = logging.getLogger(__name__)


class SmartHomeSkill(BaseSkill):
    name = "smart_home"
    display_name = "Smart Home"
    description = "Smart Home skill — not yet implemented."
    version = "0.1.0"
    category = "environment"
    icon = "🏠"
    uses_storage = False
    supports_background = False

    capabilities = [
        SkillCapability(
            name="placeholder",
            description="Placeholder capability for Smart Home",
            tags=[CapabilityTags.SMART_HOME],
        ),
    ]

    def execute(self, request: SkillRequest) -> SkillResult:
        return SkillResult.fail(
            error="Smart Home skill is not yet implemented.",
            message="Smart Home will be available in a future update."
        )

    def can_handle(self, request: SkillRequest) -> float:
        intent = request.intent.lower()
        if "smart home" in intent or any(k in intent for k in ['smart', 'home']):
            return 0.3
        return super().can_handle(request)
