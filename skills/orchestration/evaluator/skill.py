"""IRIS Evaluator Skill — Placeholder."""
import logging
from skills.base import BaseSkill, SkillCapability
from skills.contracts.skill_request import SkillRequest
from skills.contracts.skill_result import SkillResult
from skills.contracts.capability_tags import CapabilityTags

logger = logging.getLogger(__name__)


class EvaluatorSkill(BaseSkill):
    name = "evaluator"
    display_name = "Evaluator"
    description = "Evaluator skill — not yet implemented."
    version = "0.1.0"
    category = "orchestration"
    icon = "📊"
    uses_storage = False
    supports_background = False

    capabilities = [
        SkillCapability(
            name="placeholder",
            description="Placeholder capability for Evaluator",
            tags=[CapabilityTags.EVALUATOR],
        ),
    ]

    def execute(self, request: SkillRequest) -> SkillResult:
        return SkillResult.fail(
            error="Evaluator skill is not yet implemented.",
            message="Evaluator will be available in a future update."
        )

    def can_handle(self, request: SkillRequest) -> float:
        intent = request.intent.lower()
        if "evaluator" in intent or any(k in intent for k in ['evaluator']):
            return 0.3
        return super().can_handle(request)
