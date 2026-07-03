"""IRIS Skills System — Auto-discoverable, modular, scalable."""
from skills.master_wrapper import SkillRouter, get_router
from skills.base import BaseSkill, SkillResult, SkillRequest, SkillCapability
from skills.registry import SkillRegistry

__all__ = [
    "SkillRouter",
    "get_router",
    "BaseSkill",
    "SkillResult",
    "SkillRequest",
    "SkillCapability",
    "SkillRegistry",
]
