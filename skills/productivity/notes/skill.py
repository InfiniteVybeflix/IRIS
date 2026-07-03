"""IRIS Notes Skill — Full implementation with search, tags, categories, pinning."""
import os
import re
import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from skills.base import BaseSkill, SkillCapability
from skills.contracts.skill_request import SkillRequest
from skills.contracts.skill_result import SkillResult
from skills.contracts.capability_tags import CapabilityTags
from skills._utils.storage import SkillStorage

logger = logging.getLogger(__name__)


class NotesSkill(BaseSkill):
    name = "notes"
    display_name = "Notes"
    description = "Smart note-taking with categories, tags, search, pinning, and export."
    version = "2.0.0"
    category = "productivity"
    icon = "📝"
    uses_storage = True
    supports_background = False

    capabilities = [
        SkillCapability(
            name="create_note",
            description="Create a new note",
            input_schema={"title": "str", "content": "str", "category": "str", "tags": "list[str]"},
            output_schema={"note_id": "int", "title": "str"},
            tags=[CapabilityTags.NOTES],
        ),
        SkillCapability(
            name="get_note",
            description="Get a single note by ID",
            input_schema={"note_id": "int"},
            output_schema={"note": "dict"},
            tags=[CapabilityTags.NOTES],
        ),
        SkillCapability(
            name="list_notes",
            description="List notes with optional filtering",
            input_schema={"category": "str", "search": "str"},
            output_schema={"notes": "list", "count": "int"},
            tags=[CapabilityTags.NOTES],
        ),
        SkillCapability(
            name="update_note",
            description="Update an existing note",
            input_schema={"note_id": "int", "title": "str", "content": "str", "category": "str", "tags": "list[str]"},
            output_schema={"success": "bool", "message": "str"},
            tags=[CapabilityTags.NOTES],
        ),
        SkillCapability(
            name="delete_note",
            description="Delete a note by ID",
            input_schema={"note_id": "int"},
            output_schema={"success": "bool", "message": "str"},
            tags=[CapabilityTags.NOTES],
        ),
        SkillCapability(
            name="pin_note",
            description="Pin or unpin a note",
            input_schema={"note_id": "int", "pinned": "bool"},
            output_schema={"success": "bool", "message": "str"},
            tags=[CapabilityTags.NOTES],
        ),
        SkillCapability(
            name="search_notes",
            description="Search notes by title or content",
            input_schema={"query": "str", "category": "str"},
            output_schema={"notes": "list", "count": "int"},
            tags=[CapabilityTags.NOTES],
        ),
        SkillCapability(
            name="quick_note",
            description="Create a quick note with auto-title",
            input_schema={"text": "str", "category": "str"},
            output_schema={"note_id": "int", "title": "str"},
            tags=[CapabilityTags.NOTES],
        ),
        SkillCapability(
            name="export_note",
            description="Export a note to markdown or text",
            input_schema={"note_id": "int", "format": "str: markdown|text|json"},
            output_schema={"content": "str", "format": "str"},
            tags=[CapabilityTags.NOTES],
        ),
        SkillCapability(
            name="get_categories",
            description="Get all note categories",
            input_schema={},
            output_schema={"categories": "list"},
            tags=[CapabilityTags.NOTES],
        ),
    ]

    def __init__(self):
        super().__init__()
        self.storage = SkillStorage(self.name)

    def execute(self, request: SkillRequest) -> SkillResult:
        intent = request.intent.lower()
        params = request.params

        if intent in ("create_note", "add_note", "notes_create"):
            return self._create(params)
        elif intent in ("get_note", "notes_get"):
            return self._get(params)
        elif intent in ("list_notes", "get_notes", "notes_list"):
            return self._list(params)
        elif intent in ("update_note", "edit_note", "notes_update"):
            return self._update(params)
        elif intent in ("delete_note", "remove_note", "notes_delete"):
            return self._delete(params)
        elif intent in ("pin_note", "notes_pin"):
            return self._pin(params)
        elif intent in ("search_notes", "find_notes", "notes_search"):
            return self._search(params)
        elif intent in ("quick_note", "notes_quick"):
            return self._quick(params)
        elif intent in ("export_note", "notes_export"):
            return self._export(params)
        elif intent in ("get_categories", "notes_categories"):
            return self._categories()
        else:
            return SkillResult.fail(error=f"Unknown notes intent: {intent}")

    def can_handle(self, request: SkillRequest) -> float:
        intent = request.intent.lower()
        keywords = ["note", "notes", "memo", "jot", "write down", "save this"]
        if any(k in intent for k in keywords):
            return 0.95
        return super().can_handle(request)

    # === Implementation ===

    def _create(self, params: Dict) -> SkillResult:
        title = params.get("title")
        if not title:
            return SkillResult.fail(error="Title is required")
        try:
            note_id = self.storage.note_add(
                title=title,
                content=params.get("content", ""),
                category=params.get("category", "general"),
                tags=params.get("tags", [])
            )
            return SkillResult.ok(
                message=f"Note '{title}' created.",
                data={"note_id": note_id, "title": title}
            )
        except Exception as e:
            return SkillResult.fail(error=str(e))

    def _get(self, params: Dict) -> SkillResult:
        note_id = params.get("note_id")
        if not note_id:
            return SkillResult.fail(error="note_id is required")
        note = self.storage.note_get(note_id)
        if note:
            return SkillResult.ok(data={"note": note})
        return SkillResult.fail(error="Note not found")

    def _list(self, params: Dict) -> SkillResult:
        notes = self.storage.note_list(
            category=params.get("category"),
            search=params.get("search")
        )
        return SkillResult.ok(
            data={"notes": notes, "count": len(notes)},
            message=f"Found {len(notes)} note(s)."
        )

    def _update(self, params: Dict) -> SkillResult:
        note_id = params.get("note_id")
        if not note_id:
            return SkillResult.fail(error="note_id is required")
        updates = {}
        for key in ["title", "content", "category", "tags"]:
            if key in params:
                updates[key] = params[key]
        if not updates:
            return SkillResult.fail(error="No fields to update")
        try:
            self.storage.note_update(note_id, **updates)
            return SkillResult.ok(message=f"Note {note_id} updated.")
        except Exception as e:
            return SkillResult.fail(error=str(e))

    def _delete(self, params: Dict) -> SkillResult:
        note_id = params.get("note_id")
        if not note_id:
            return SkillResult.fail(error="note_id is required")
        try:
            self.storage.note_delete(note_id)
            return SkillResult.ok(message=f"Note {note_id} deleted.")
        except Exception as e:
            return SkillResult.fail(error=str(e))

    def _pin(self, params: Dict) -> SkillResult:
        note_id = params.get("note_id")
        pinned = params.get("pinned", True)
        if not note_id:
            return SkillResult.fail(error="note_id is required")
        try:
            self.storage.note_update(note_id, pinned=1 if pinned else 0)
            return SkillResult.ok(message=f"Note {note_id} {'pinned' if pinned else 'unpinned'}.")
        except Exception as e:
            return SkillResult.fail(error=str(e))

    def _search(self, params: Dict) -> SkillResult:
        query = params.get("query", "")
        notes = self.storage.note_list(search=query, category=params.get("category"))
        return SkillResult.ok(
            data={"notes": notes, "count": len(notes)},
            message=f"Found {len(notes)} note(s) matching '{query}'."
        )

    def _quick(self, params: Dict) -> SkillResult:
        text = params.get("text", "")
        if not text:
            return SkillResult.fail(error="text is required")
        title = text[:50] + ("..." if len(text) > 50 else "")
        return self._create({"title": title, "content": text, "category": params.get("category", "quick")})

    def _export(self, params: Dict) -> SkillResult:
        note_id = params.get("note_id")
        fmt = params.get("format", "markdown")
        note = self.storage.note_get(note_id)
        if not note:
            return SkillResult.fail(error="Note not found")

        if fmt == "markdown":
            content = f"# {note['title']}\n\n**Category:** {note['category']}\n**Tags:** {', '.join(note.get('tags', []))}\n**Created:** {note['created_at']}\n\n{note['content']}"
        elif fmt == "json":
            content = json.dumps(note, indent=2, default=str)
        else:
            content = note["content"]

        return SkillResult.ok(data={"content": content, "format": fmt})

    def _categories(self) -> SkillResult:
        notes = self.storage.note_list()
        cats = sorted(set(n.get("category", "general") for n in notes))
        return SkillResult.ok(data={"categories": cats})
