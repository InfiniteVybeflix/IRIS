"""IRIS Memory Skill — Placeholder."""
import logging
from skills.base import BaseSkill, SkillCapability
from skills.contracts.skill_request import SkillRequest
from skills.contracts.skill_result import SkillResult
from skills.contracts.capability_tags import CapabilityTags

logger = logging.getLogger(__name__)


class MemorySkill(BaseSkill):
    name = "memory"
    display_name = "Memory"
    description = "Memory skill — not yet implemented."
    version = "0.1.0"
    category = "intelligence"
    icon = "🧠"
    uses_storage = False
    supports_background = False

    capabilities = [
        SkillCapability(
            name="placeholder",
            description="Placeholder capability for Memory",
            tags=[CapabilityTags.MEMORY],
        ),
    ]

    def execute(self, request: SkillRequest) -> SkillResult:
        return SkillResult.fail(
            error="Memory skill is not yet implemented.",
            message="Memory will be available in a future update."
        )

    def can_handle(self, request: SkillRequest) -> float:
        intent = request.intent.lower()
        if "memory" in intent or any(k in intent for k in ['memory']):
            return 0.3
        return super().can_handle(request)
