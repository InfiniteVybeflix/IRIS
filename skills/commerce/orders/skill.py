"""IRIS Orders Skill — Placeholder."""
import logging
from skills.base import BaseSkill, SkillCapability
from skills.contracts.skill_request import SkillRequest
from skills.contracts.skill_result import SkillResult
from skills.contracts.capability_tags import CapabilityTags

logger = logging.getLogger(__name__)


class OrdersSkill(BaseSkill):
    name = "orders"
    display_name = "Orders"
    description = "Orders skill — not yet implemented."
    version = "0.1.0"
    category = "commerce"
    icon = "📦"
    uses_storage = False
    supports_background = False

    capabilities = [
        SkillCapability(
            name="placeholder",
            description="Placeholder capability for Orders",
            tags=[CapabilityTags.ORDERS],
        ),
    ]

    def execute(self, request: SkillRequest) -> SkillResult:
        return SkillResult.fail(
            error="Orders skill is not yet implemented.",
            message="Orders will be available in a future update."
        )

    def can_handle(self, request: SkillRequest) -> float:
        intent = request.intent.lower()
        if "orders" in intent or any(k in intent for k in ['orders']):
            return 0.3
        return super().can_handle(request)
