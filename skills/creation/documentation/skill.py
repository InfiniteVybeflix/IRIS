"""IRIS Documentation Skill — Placeholder."""
import logging
from skills.base import BaseSkill, SkillCapability
from skills.contracts.skill_request import SkillRequest
from skills.contracts.skill_result import SkillResult
from skills.contracts.capability_tags import CapabilityTags

logger = logging.getLogger(__name__)


class DocumentationSkill(BaseSkill):
    name = "documentation"
    display_name = "Documentation"
    description = "Documentation skill — not yet implemented."
    version = "0.1.0"
    category = "creation"
    icon = "📖"
    uses_storage = False
    supports_background = False

    capabilities = [
        SkillCapability(
            name="placeholder",
            description="Placeholder capability for Documentation",
            tags=[CapabilityTags.DOCUMENTATION],
        ),
    ]

    def execute(self, request: SkillRequest) -> SkillResult:
        return SkillResult.fail(
            error="Documentation skill is not yet implemented.",
            message="Documentation will be available in a future update."
        )

    def can_handle(self, request: SkillRequest) -> float:
        intent = request.intent.lower()
        if "documentation" in intent or any(k in intent for k in ['documentation']):
            return 0.3
        return super().can_handle(request)
