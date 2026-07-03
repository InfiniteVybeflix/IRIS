"""IRIS Sensors Skill — Placeholder."""
import logging
from skills.base import BaseSkill, SkillCapability
from skills.contracts.skill_request import SkillRequest
from skills.contracts.skill_result import SkillResult
from skills.contracts.capability_tags import CapabilityTags

logger = logging.getLogger(__name__)


class SensorsSkill(BaseSkill):
    name = "sensors"
    display_name = "Sensors"
    description = "Sensors skill — not yet implemented."
    version = "0.1.0"
    category = "environment"
    icon = "📊"
    uses_storage = False
    supports_background = False

    capabilities = [
        SkillCapability(
            name="placeholder",
            description="Placeholder capability for Sensors",
            tags=[CapabilityTags.SENSORS],
        ),
    ]

    def execute(self, request: SkillRequest) -> SkillResult:
        return SkillResult.fail(
            error="Sensors skill is not yet implemented.",
            message="Sensors will be available in a future update."
        )

    def can_handle(self, request: SkillRequest) -> float:
        intent = request.intent.lower()
        if "sensors" in intent or any(k in intent for k in ['sensors']):
            return 0.3
        return super().can_handle(request)
