"""IRIS Bookmarks Skill — Placeholder."""
import logging
from skills.base import BaseSkill, SkillCapability
from skills.contracts.skill_request import SkillRequest
from skills.contracts.skill_result import SkillResult
from skills.contracts.capability_tags import CapabilityTags

logger = logging.getLogger(__name__)


class BookmarksSkill(BaseSkill):
    name = "bookmarks"
    display_name = "Bookmarks"
    description = "Bookmarks skill — not yet implemented."
    version = "0.1.0"
    category = "productivity"
    icon = "🔖"
    uses_storage = False
    supports_background = False

    capabilities = [
        SkillCapability(
            name="placeholder",
            description="Placeholder capability for Bookmarks",
            tags=[CapabilityTags.BOOKMARKS],
        ),
    ]

    def execute(self, request: SkillRequest) -> SkillResult:
        return SkillResult.fail(
            error="Bookmarks skill is not yet implemented.",
            message="Bookmarks will be available in a future update."
        )

    def can_handle(self, request: SkillRequest) -> float:
        intent = request.intent.lower()
        if "bookmarks" in intent or any(k in intent for k in ['bookmarks']):
            return 0.3
        return super().can_handle(request)
