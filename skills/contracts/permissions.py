"""Permission system for skills."""
from enum import Enum
from typing import List, Optional
from dataclasses import dataclass, field


class PermissionLevel(Enum):
    SAFE = "safe"
    NORMAL = "normal"
    SENSITIVE = "sensitive"
    DANGEROUS = "dangerous"
    ADMIN = "admin"


@dataclass
class SkillPermissions:
    level: PermissionLevel = PermissionLevel.NORMAL
    requires_auth: bool = False
    allowed_users: List[str] = field(default_factory=list)
    blocked_users: List[str] = field(default_factory=list)
    rate_limit_per_minute: int = 60
    allowed_sources: List[str] = field(default_factory=lambda: ["chat", "api", "autonomous", "cron"])
    requires_confirmation_for: List[str] = field(default_factory=list)
    auto_approve_patterns: List[str] = field(default_factory=list)
