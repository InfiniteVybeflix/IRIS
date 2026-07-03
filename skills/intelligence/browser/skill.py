"""IRIS Browser Skill — Placeholder."""
import logging
from skills.base import BaseSkill, SkillCapability
from skills.contracts.skill_request import SkillRequest
from skills.contracts.skill_result import SkillResult
from skills.contracts.capability_tags import CapabilityTags

logger = logging.getLogger(__name__)


class BrowserSkill(BaseSkill):
    name = "browser"
    display_name = "Browser"
    description = "Browser skill — not yet implemented."
    version = "0.1.0"
    category = "intelligence"
    icon = "🌐"
    uses_storage = False
    supports_background = False

    capabilities = [
        SkillCapability(
            name="placeholder",
            description="Placeholder capability for Browser",
            tags=[CapabilityTags.BROWSER],
        ),
    ]

    def execute(self, request: SkillRequest) -> SkillResult:
        return SkillResult.fail(
            error="Browser skill is not yet implemented.",
            message="Browser will be available in a future update."
        )

    def can_handle(self, request: SkillRequest) -> float:
        intent = request.intent.lower()
        if "browser" in intent or any(k in intent for k in ['browser']):
            return 0.3
        return super().can_handle(request)
