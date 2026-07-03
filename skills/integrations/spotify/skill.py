"""IRIS Spotify Skill — Placeholder."""
import logging
from skills.base import BaseSkill, SkillCapability
from skills.contracts.skill_request import SkillRequest
from skills.contracts.skill_result import SkillResult
from skills.contracts.capability_tags import CapabilityTags

logger = logging.getLogger(__name__)


class SpotifySkill(BaseSkill):
    name = "spotify"
    display_name = "Spotify"
    description = "Spotify skill — not yet implemented."
    version = "0.1.0"
    category = "integrations"
    icon = "🎧"
    uses_storage = False
    supports_background = False

    capabilities = [
        SkillCapability(
            name="placeholder",
            description="Placeholder capability for Spotify",
            tags=[CapabilityTags.SPOTIFY],
        ),
    ]

    def execute(self, request: SkillRequest) -> SkillResult:
        return SkillResult.fail(
            error="Spotify skill is not yet implemented.",
            message="Spotify will be available in a future update."
        )

    def can_handle(self, request: SkillRequest) -> float:
        intent = request.intent.lower()
        if "spotify" in intent or any(k in intent for k in ['spotify']):
            return 0.3
        return super().can_handle(request)
