"""Skill contracts — shared types and interfaces."""
from skills.contracts.skill_result import SkillResult
from skills.contracts.skill_request import SkillRequest
from skills.contracts.permissions import PermissionLevel, SkillPermissions
from skills.contracts.capability_tags import CapabilityTags

__all__ = [
    "SkillResult",
    "SkillRequest",
    "PermissionLevel",
    "SkillPermissions",
    "CapabilityTags",
]
