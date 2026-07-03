"""Standard skill execution result."""
from typing import Any, Dict, Optional, List
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class SkillResult:
    """Every skill returns this. No exceptions."""
    success: bool
    data: Any = None
    error: Optional[str] = None
    message: str = ""
    duration_ms: float = 0.0
    skill_name: str = ""
    capability_used: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    suggestions: List[str] = field(default_factory=list)
    follow_up_actions: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "data": self.data,
            "error": self.error,
            "message": self.message,
            "duration_ms": self.duration_ms,
            "skill_name": self.skill_name,
            "capability_used": self.capability_used,
            "metadata": self.metadata,
            "timestamp": self.timestamp,
            "suggestions": self.suggestions,
            "follow_up_actions": self.follow_up_actions,
        }

    @classmethod
    def ok(cls, message: str = "", data: Any = None, **kwargs) -> "SkillResult":
        return cls(success=True, message=message, data=data, **kwargs)

    @classmethod
    def fail(cls, error: str, message: str = "", **kwargs) -> "SkillResult":
        return cls(success=False, error=error, message=message, **kwargs)
