"""IRIS WhatsApp Skill — Placeholder."""
import logging
from skills.base import BaseSkill, SkillCapability
from skills.contracts.skill_request import SkillRequest
from skills.contracts.skill_result import SkillResult
from skills.contracts.capability_tags import CapabilityTags

logger = logging.getLogger(__name__)


class WhatsappSkill(BaseSkill):
    name = "whatsapp"
    display_name = "WhatsApp"
    description = "WhatsApp skill — not yet implemented."
    version = "0.1.0"
    category = "integrations"
    icon = "💬"
    uses_storage = False
    supports_background = False

    capabilities = [
        SkillCapability(
            name="placeholder",
            description="Placeholder capability for WhatsApp",
            tags=[CapabilityTags.WHATSAPP],
        ),
    ]

    def execute(self, request: SkillRequest) -> SkillResult:
        return SkillResult.fail(
            error="WhatsApp skill is not yet implemented.",
            message="WhatsApp will be available in a future update."
        )

    def can_handle(self, request: SkillRequest) -> float:
        intent = request.intent.lower()
        if "whatsapp" in intent or any(k in intent for k in ['whatsapp']):
            return 0.3
        return super().can_handle(request)
