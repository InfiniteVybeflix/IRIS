"""IRIS Notes Skill Adapter — bridges legacy API routes to the NotesSkill.

The api/routes/notes.py blueprint expects a `notes_skill` singleton with
methods like `get_notes`, `create_note`, `get_note`, `update_note`,
`delete_note`, `pin_note`, `quick_note`.  This adapter implements that
interface and persists notes to disk under `config.NOTES_DIR`.
"""
from __future__ import annotations

import json
import os
import uuid
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from config import config

logger = logging.getLogger(__name__)


class _NotesSkillAdapter:
    """Adapter exposing the route-facing notes API."""

    def __init__(self) -> None:
        self._notes: Dict[str, Dict[str, Any]] = {}
        self._notes_dir = config.NOTES_DIR
        os.makedirs(self._notes_dir, exist_ok=True)
        self._load_all()

    # ─── route-facing methods ───────────────────────────────────────────
    def get_notes(self, category: Optional[str] = None,
                  search: Optional[str] = None) -> Dict[str, Any]:
        notes = list(self._notes.values())
        if category:
            notes = [n for n in notes if n.get("category") == category]
        if search:
            needle = search.lower()
            notes = [
                n for n in notes
                if needle in n.get("title", "").lower()
                or needle in n.get("content", "").lower()
            ]
        return {"success": True, "notes": notes, "count": len(notes)}

    def create_note(self, title: str, content: str = "", category: str = "general",
                    tags: Optional[List[str]] = None) -> Dict[str, Any]:
        note_id = uuid.uuid4().hex[:8]
        note = {
            "id": note_id,
            "title": title,
            "content": content,
            "category": category,
            "tags": tags or [],
            "pinned": False,
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat(),
        }
        self._notes[note_id] = note
        self._persist(note)
        return {"success": True, "note": note}

    def get_note(self, note_id: str) -> Dict[str, Any]:
        note = self._notes.get(note_id)
        if not note:
            return {"success": False, "error": "Note not found"}
        return {"success": True, "note": note}

    def update_note(self, note_id: str, title: Optional[str] = None,
                    content: Optional[str] = None,
                    category: Optional[str] = None,
                    tags: Optional[List[str]] = None) -> Dict[str, Any]:
        note = self._notes.get(note_id)
        if not note:
            return {"success": False, "error": "Note not found"}
        if title is not None:
            note["title"] = title
        if content is not None:
            note["content"] = content
        if category is not None:
            note["category"] = category
        if tags is not None:
            note["tags"] = tags
        note["updated_at"] = datetime.utcnow().isoformat()
        self._persist(note)
        return {"success": True, "note": note}

    def delete_note(self, note_id: str) -> Dict[str, Any]:
        removed = self._notes.pop(note_id, None)
        if removed:
            try:
                os.remove(os.path.join(self._notes_dir, f"{note_id}.json"))
            except OSError:
                pass
        return {"success": True, "deleted": removed is not None, "id": note_id}

    def pin_note(self, note_id: str, pinned: bool = True) -> Dict[str, Any]:
        note = self._notes.get(note_id)
        if not note:
            return {"success": False, "error": "Note not found"}
        note["pinned"] = pinned
        self._persist(note)
        return {"success": True, "note": note}

    def quick_note(self, text: str) -> Dict[str, Any]:
        if not text:
            return {"success": False, "error": "Empty quick note"}
        title = text.split("\n")[0][:60] or "Quick Note"
        return self.create_note(title=title, content=text, category="quick")

    # ─── helpers ─────────────────────────────────────────────────────────
    def _persist(self, note: Dict[str, Any]) -> None:
        try:
            path = os.path.join(self._notes_dir, f"{note['id']}.json")
            with open(path, "w") as f:
                json.dump(note, f, default=str)
        except Exception as exc:
            logger.warning(f"Failed to persist note: {exc}")

    def _load_all(self) -> None:
        try:
            for fname in os.listdir(self._notes_dir):
                if not fname.endswith(".json"):
                    continue
                with open(os.path.join(self._notes_dir, fname)) as f:
                    note = json.load(f)
                self._notes[note.get("id", fname[:-5])] = note
        except Exception as exc:
            logger.warning(f"Failed to load notes: {exc}")


notes_skill = _NotesSkillAdapter()

__all__ = ["notes_skill", "_NotesSkillAdapter"]
