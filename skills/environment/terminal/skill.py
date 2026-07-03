"""IRIS Terminal Skill — Placeholder."""
import logging
from skills.base import BaseSkill, SkillCapability
from skills.contracts.skill_request import SkillRequest
from skills.contracts.skill_result import SkillResult
from skills.contracts.capability_tags import CapabilityTags

logger = logging.getLogger(__name__)


class TerminalSkill(BaseSkill):
    name = "terminal"
    display_name = "Terminal"
    description = "Terminal skill — not yet implemented."
    version = "0.1.0"
    category = "environment"
    icon = "💻"
    uses_storage = False
    supports_background = False

    capabilities = [
        SkillCapability(
            name="placeholder",
            description="Placeholder capability for Terminal",
            tags=[CapabilityTags.TERMINAL],
        ),
    ]

    def execute(self, request: SkillRequest) -> SkillResult:
        return SkillResult.fail(
            error="Terminal skill is not yet implemented.",
            message="Terminal will be available in a future update."
        )

    def can_handle(self, request: SkillRequest) -> float:
        intent = request.intent.lower()
        if "terminal" in intent or any(k in intent for k in ['terminal']):
            return 0.3
        return super().can_handle(request)
