"""IRIS Tutoring Skill — Placeholder."""
import logging
from skills.base import BaseSkill, SkillCapability
from skills.contracts.skill_request import SkillRequest
from skills.contracts.skill_result import SkillResult
from skills.contracts.capability_tags import CapabilityTags

logger = logging.getLogger(__name__)


class TutoringSkill(BaseSkill):
    name = "tutoring"
    display_name = "Tutoring"
    description = "Tutoring skill — not yet implemented."
    version = "0.1.0"
    category = "intelligence"
    icon = "🎓"
    uses_storage = False
    supports_background = False

    capabilities = [
        SkillCapability(
            name="placeholder",
            description="Placeholder capability for Tutoring",
            tags=[CapabilityTags.TUTORING],
        ),
    ]

    def execute(self, request: SkillRequest) -> SkillResult:
        return SkillResult.fail(
            error="Tutoring skill is not yet implemented.",
            message="Tutoring will be available in a future update."
        )

    def can_handle(self, request: SkillRequest) -> float:
        intent = request.intent.lower()
        if "tutoring" in intent or any(k in intent for k in ['tutoring']):
            return 0.3
        return super().can_handle(request)
