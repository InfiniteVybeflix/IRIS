"""IRIS Copilot Skill — Placeholder."""
import logging
from skills.base import BaseSkill, SkillCapability
from skills.contracts.skill_request import SkillRequest
from skills.contracts.skill_result import SkillResult
from skills.contracts.capability_tags import CapabilityTags

logger = logging.getLogger(__name__)


class CopilotSkill(BaseSkill):
    name = "copilot"
    display_name = "Copilot"
    description = "Copilot skill — not yet implemented."
    version = "0.1.0"
    category = "orchestration"
    icon = "🧑‍✈️"
    uses_storage = False
    supports_background = False

    capabilities = [
        SkillCapability(
            name="placeholder",
            description="Placeholder capability for Copilot",
            tags=[CapabilityTags.COPILOT],
        ),
    ]

    def execute(self, request: SkillRequest) -> SkillResult:
        return SkillResult.fail(
            error="Copilot skill is not yet implemented.",
            message="Copilot will be available in a future update."
        )

    def can_handle(self, request: SkillRequest) -> float:
        intent = request.intent.lower()
        if "copilot" in intent or any(k in intent for k in ['copilot']):
            return 0.3
        return super().can_handle(request)
