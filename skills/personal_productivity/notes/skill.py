"""Notes Skill — Full note-taking with search, tags, and organization."""

import hashlib
import logging
from typing import Dict, Any, List
from datetime import datetime
from skills import BaseSkill

logger = logging.getLogger(__name__)


class NotesSkill(BaseSkill):
    """Note-taking with full-text search, tags, folders, and markdown support."""

    def __init__(self):
        super().__init__(name="notes", category="personal_productivity", capabilities=["notes"])
        self._notes: Dict[str, Dict[str, Any]] = {}

    def execute(self, capability: str, params: Dict[str, Any]) -> Dict[str, Any]:
        method = params.get("method", "create")
        if method == "create":
            return self.create_note(params)
        elif method == "read":
            return self.read_note(params)
        elif method == "update":
            return self.update_note(params)
        elif method == "delete":
            return self.delete_note(params)
        elif method == "search":
            return self.search_notes(params)
        elif method == "list":
            return self.list_notes(params)
        return {"error": f"Unknown method: {method}"}

    def create_note(self, params: Dict[str, Any]) -> Dict[str, Any]:
        title = params.get("title", "Untitled Note")
        note_id = hashlib.md5(f"{title}{datetime.utcnow().isoformat()}".encode()).hexdigest()[:8]
        note = {"id": note_id, "title": title, "content": params.get("content", ""), "folder": params.get("folder", "General"), "tags": params.get("tags", []), "created_at": datetime.utcnow().isoformat(), "updated_at": datetime.utcnow().isoformat(), "pinned": params.get("pinned", False)}
        self._notes[note_id] = note
        return {"success": True, "note": note}

    def read_note(self, params: Dict[str, Any]) -> Dict[str, Any]:
        note_id = params.get("note_id", "")
        note = self._notes.get(note_id)
        return {"success": True, "note": note} if note else {"success": False, "error": "Note not found"}

    def update_note(self, params: Dict[str, Any]) -> Dict[str, Any]:
        note_id = params.get("note_id", "")
        if note_id not in self._notes:
            return {"success": False, "error": "Note not found"}
        for key in ["title", "content", "folder", "tags", "pinned"]:
            if key in params:
                self._notes[note_id][key] = params[key]
        self._notes[note_id]["updated_at"] = datetime.utcnow().isoformat()
        return {"success": True, "note": self._notes[note_id]}

    def delete_note(self, params: Dict[str, Any]) -> Dict[str, Any]:
        note_id = params.get("note_id", "")
        removed = self._notes.pop(note_id, None)
        return {"success": True, "deleted": removed is not None}

    def search_notes(self, params: Dict[str, Any]) -> Dict[str, Any]:
        query = params.get("query", "").lower()
        folder = params.get("folder", "")
        results = [n for n in self._notes.values() if (not folder or n.get("folder") == folder) and (not query or query in n["title"].lower() or query in n["content"].lower() or any(query in t.lower() for t in n.get("tags", [])))]
        return {"success": True, "results": results, "count": len(results)}

    def list_notes(self, params: Dict[str, Any]) -> Dict[str, Any]:
        folder = params.get("folder", "")
        notes = [n for n in self._notes.values() if not folder or n.get("folder") == folder]
        folders = list(set(n.get("folder", "General") for n in self._notes.values()))
        return {"success": True, "notes": notes, "folders": folders, "count": len(notes)}
