"""Messaging Skill — Unified messaging hub for SMS, email, chat."""
import logging
from typing import Dict, Any
from skills import BaseSkill
logger = logging.getLogger(__name__)

class MessagingSkill(BaseSkill):
    def __init__(self):
        super().__init__(name="messaging", category="communication", capabilities=["messaging"])
        self._messages: list = []

    def execute(self, capability: str, params: Dict[str, Any]) -> Dict[str, Any]:
        method = params.get("method", "send")
        if method == "send": return self.send(params)
        elif method == "history": return self.history(params)
        return {"error": f"Unknown method: {method}"}

    def send(self, params: Dict[str, Any]) -> Dict[str, Any]:
        msg = {"to": params.get("to", ""), "content": params.get("content", ""), "channel": params.get("channel", "sms"), "sent_at": __import__('datetime').datetime.utcnow().isoformat()}
        self._messages.append(msg)
        return {"success": True, "message": msg, "note": f"Message queued for {msg['channel']}"}

    def history(self, params: Dict[str, Any]) -> Dict[str, Any]:
        contact = params.get("contact", "")
        msgs = [m for m in self._messages if not contact or m["to"] == contact]
        return {"success": True, "messages": msgs, "count": len(msgs)}
