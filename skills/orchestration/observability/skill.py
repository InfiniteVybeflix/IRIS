"""IRIS Observability Skill — Placeholder."""
import logging
from skills.base import BaseSkill, SkillCapability
from skills.contracts.skill_request import SkillRequest
from skills.contracts.skill_result import SkillResult
from skills.contracts.capability_tags import CapabilityTags

logger = logging.getLogger(__name__)


class ObservabilitySkill(BaseSkill):
    name = "observability"
    display_name = "Observability"
    description = "Observability skill — not yet implemented."
    version = "0.1.0"
    category = "orchestration"
    icon = "👁️"
    uses_storage = False
    supports_background = False

    capabilities = [
        SkillCapability(
            name="placeholder",
            description="Placeholder capability for Observability",
            tags=[CapabilityTags.OBSERVABILITY],
        ),
    ]

    def execute(self, request: SkillRequest) -> SkillResult:
        return SkillResult.fail(
            error="Observability skill is not yet implemented.",
            message="Observability will be available in a future update."
        )

    def can_handle(self, request: SkillRequest) -> float:
        intent = request.intent.lower()
        if "observability" in intent or any(k in intent for k in ['observability']):
            return 0.3
        return super().can_handle(request)
