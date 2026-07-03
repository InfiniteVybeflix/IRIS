"""IRIS Summarizer Skill — Placeholder."""
import logging
from skills.base import BaseSkill, SkillCapability
from skills.contracts.skill_request import SkillRequest
from skills.contracts.skill_result import SkillResult
from skills.contracts.capability_tags import CapabilityTags

logger = logging.getLogger(__name__)


class SummarizerSkill(BaseSkill):
    name = "summarizer"
    display_name = "Summarizer"
    description = "Summarizer skill — not yet implemented."
    version = "0.1.0"
    category = "intelligence"
    icon = "📝"
    uses_storage = False
    supports_background = False

    capabilities = [
        SkillCapability(
            name="placeholder",
            description="Placeholder capability for Summarizer",
            tags=[CapabilityTags.SUMMARIZER],
        ),
    ]

    def execute(self, request: SkillRequest) -> SkillResult:
        return SkillResult.fail(
            error="Summarizer skill is not yet implemented.",
            message="Summarizer will be available in a future update."
        )

    def can_handle(self, request: SkillRequest) -> float:
        intent = request.intent.lower()
        if "summarizer" in intent or any(k in intent for k in ['summarizer']):
            return 0.3
        return super().can_handle(request)
