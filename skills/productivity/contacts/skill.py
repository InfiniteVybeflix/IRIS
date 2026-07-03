"""IRIS Contacts Skill — Placeholder."""
import logging
from skills.base import BaseSkill, SkillCapability
from skills.contracts.skill_request import SkillRequest
from skills.contracts.skill_result import SkillResult
from skills.contracts.capability_tags import CapabilityTags

logger = logging.getLogger(__name__)


class ContactsSkill(BaseSkill):
    name = "contacts"
    display_name = "Contacts"
    description = "Contacts skill — not yet implemented."
    version = "0.1.0"
    category = "productivity"
    icon = "👤"
    uses_storage = False
    supports_background = False

    capabilities = [
        SkillCapability(
            name="placeholder",
            description="Placeholder capability for Contacts",
            tags=[CapabilityTags.CONTACTS],
        ),
    ]

    def execute(self, request: SkillRequest) -> SkillResult:
        return SkillResult.fail(
            error="Contacts skill is not yet implemented.",
            message="Contacts will be available in a future update."
        )

    def can_handle(self, request: SkillRequest) -> float:
        intent = request.intent.lower()
        if "contacts" in intent or any(k in intent for k in ['contacts']):
            return 0.3
        return super().can_handle(request)
