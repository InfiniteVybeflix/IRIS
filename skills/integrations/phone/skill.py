"""IRIS Phone Skill — Placeholder."""
import logging
from skills.base import BaseSkill, SkillCapability
from skills.contracts.skill_request import SkillRequest
from skills.contracts.skill_result import SkillResult
from skills.contracts.capability_tags import CapabilityTags

logger = logging.getLogger(__name__)


class PhoneSkill(BaseSkill):
    name = "phone"
    display_name = "Phone"
    description = "Phone skill — not yet implemented."
    version = "0.1.0"
    category = "integrations"
    icon = "📞"
    uses_storage = False
    supports_background = False

    capabilities = [
        SkillCapability(
            name="placeholder",
            description="Placeholder capability for Phone",
            tags=[CapabilityTags.PHONE],
        ),
    ]

    def execute(self, request: SkillRequest) -> SkillResult:
        return SkillResult.fail(
            error="Phone skill is not yet implemented.",
            message="Phone will be available in a future update."
        )

    def can_handle(self, request: SkillRequest) -> float:
        intent = request.intent.lower()
        if "phone" in intent or any(k in intent for k in ['phone']):
            return 0.3
        return super().can_handle(request)
