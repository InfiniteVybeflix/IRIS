"""Journal Skill — Daily journaling with prompts and search."""
import logging
import hashlib
from typing import Dict, Any, List
from datetime import datetime
from skills import BaseSkill
logger = logging.getLogger(__name__)

class JournalSkill(BaseSkill):
    def __init__(self):
        super().__init__(name="journal", category="personal_productivity", capabilities=["journal"])
        self._entries: Dict[str, Dict[str, Any]] = {}
        self._prompts = [
            "What are you grateful for today?",
            "What was the most challenging moment?",
            "What did you learn today?",
            "What are you looking forward to?",
            "Describe a moment of joy from today.",
        ]

    def execute(self, capability: str, params: Dict[str, Any]) -> Dict[str, Any]:
        method = params.get("method", "write")
        if method == "write": return self.write_entry(params)
        elif method == "read": return self.read_entry(params)
        elif method == "search": return self.search_journal(params)
        elif method == "prompt": return self.get_prompt(params)
        return {"error": f"Unknown method: {method}"}

    def write_entry(self, params: Dict[str, Any]) -> Dict[str, Any]:
        date = params.get("date", datetime.utcnow().strftime("%Y-%m-%d"))
        entry = {"date": date, "content": params.get("content", ""), "mood": params.get("mood", ""), "tags": params.get("tags", []), "word_count": len(params.get("content", "").split()), "written_at": datetime.utcnow().isoformat()}
        self._entries[date] = entry
        return {"success": True, "entry": entry}

    def read_entry(self, params: Dict[str, Any]) -> Dict[str, Any]:
        date = params.get("date", datetime.utcnow().strftime("%Y-%m-%d"))
        entry = self._entries.get(date)
        return {"success": True, "entry": entry} if entry else {"success": False, "error": "No entry for " + date}

    def search_journal(self, params: Dict[str, Any]) -> Dict[str, Any]:
        query = params.get("query", "").lower()
        results = [e for e in self._entries.values() if query in e["content"].lower() or any(query in t.lower() for t in e.get("tags", []))]
        return {"success": True, "results": results, "count": len(results)}

    def get_prompt(self, params: Dict[str, Any]) -> Dict[str, Any]:
        import random
        prompt = random.choice(self._prompts)
        return {"success": True, "prompt": prompt}
