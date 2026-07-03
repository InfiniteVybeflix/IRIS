"""IRIS Invoices Skill — Placeholder."""
import logging
from skills.base import BaseSkill, SkillCapability
from skills.contracts.skill_request import SkillRequest
from skills.contracts.skill_result import SkillResult
from skills.contracts.capability_tags import CapabilityTags

logger = logging.getLogger(__name__)


class InvoicesSkill(BaseSkill):
    name = "invoices"
    display_name = "Invoices"
    description = "Invoices skill — not yet implemented."
    version = "0.1.0"
    category = "commerce"
    icon = "📄"
    uses_storage = False
    supports_background = False

    capabilities = [
        SkillCapability(
            name="placeholder",
            description="Placeholder capability for Invoices",
            tags=[CapabilityTags.INVOICES],
        ),
    ]

    def execute(self, request: SkillRequest) -> SkillResult:
        return SkillResult.fail(
            error="Invoices skill is not yet implemented.",
            message="Invoices will be available in a future update."
        )

    def can_handle(self, request: SkillRequest) -> float:
        intent = request.intent.lower()
        if "invoices" in intent or any(k in intent for k in ['invoices']):
            return 0.3
        return super().can_handle(request)
