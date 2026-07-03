"""Standard skill execution request."""
from typing import Any, Dict, Optional, List
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class SkillRequest:
    """Every skill receives this. No exceptions."""
    intent: str
    params: Dict[str, Any] = field(default_factory=dict)
    context: Dict[str, Any] = field(default_factory=dict)
    session_id: Optional[str] = None
    user_id: str = "owner"
    priority: int = 5
    source: str = "chat"
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    requires_confirmation: bool = False
    auto_execute: bool = False
    trace_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "intent": self.intent,
            "params": self.params,
            "context": self.context,
            "session_id": self.session_id,
            "user_id": self.user_id,
            "priority": self.priority,
            "source": self.source,
            "timestamp": self.timestamp,
            "requires_confirmation": self.requires_confirmation,
            "auto_execute": self.auto_execute,
            "trace_id": self.trace_id,
        }
