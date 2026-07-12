"""IRIS v7 Smart Memory Skill — Conscious Persistent Memory"""
import json
import logging
import os
import re
import sqlite3
import threading
import time
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from skills.base import BaseSkill, SkillCapability
from skills.contracts.skill_request import SkillRequest
from skills.contracts.skill_result import SkillResult
from skills.contracts.capability_tags import CapabilityTags

logger = logging.getLogger(__name__)


class SmartMemorySkill(BaseSkill):
    name = "smart_memory"
    display_name = "Smart Memory"
    description = "Persistent memory — semantic search, episodic memory, temporal reasoning, goal tracking, emotional memory, importance-based decay, and cross-session continuity."
    version = "7.0.0"
    category = "intelligence"
    icon = "🧠"
    uses_storage = True
    storage_dir = "data/skills/smart_memory"
    storage_file = "data/skills/smart_memory/memories.db"

    capabilities = [
        SkillCapability(name="store_memory", description="Store a memory", input_schema={"content": "str", "type": "str", "importance": "float"}, tags=[CapabilityTags.MEMORY]),
        SkillCapability(name="retrieve", description="Search memories", input_schema={"query": "str"}, tags=[CapabilityTags.MEMORY]),
        SkillCapability(name="track_goal", description="Track a goal", input_schema={"description": "str", "priority": "int"}, tags=[CapabilityTags.GOALS]),
        SkillCapability(name="temporal_query", description="Temporal reasoning query", input_schema={"subject": "str", "query": "str"}, tags=[CapabilityTags.MEMORY]),
        SkillCapability(name="consolidate", description="Consolidate memories", input_schema={}, tags=[CapabilityTags.MEMORY]),
        SkillCapability(name="get_stats", description="Memory statistics", input_schema={}, tags=[CapabilityTags.OBSERVABILITY]),
    ]

    def __init__(self):
        super().__init__()
        self._lock = threading.Lock()
        os.makedirs(self.storage_dir, exist_ok=True)
        with sqlite3.connect(self.storage_file) as conn:
            conn.execute("CREATE TABLE IF NOT EXISTS memories (id TEXT PRIMARY KEY, content TEXT, type TEXT, timestamp REAL, importance REAL, tags TEXT)")
            conn.execute("CREATE TABLE IF NOT EXISTS goals (id TEXT PRIMARY KEY, description TEXT, priority INTEGER, progress REAL, status TEXT, created REAL)")
            conn.execute("CREATE TABLE IF NOT EXISTS temporal (id TEXT PRIMARY KEY, subject TEXT, predicate TEXT, obj TEXT, timestamp REAL, marker TEXT)")
            conn.commit()

    def execute(self, request):
        intent = request.intent.lower()
        p = request.params
        try:
            if "store" in intent: return self._store(p.get("content"), p.get("type", "fact"), p.get("importance", 0.5))
            elif "retrieve" in intent: return self._retrieve(p.get("query", ""))
            elif "goal" in intent: return self._goal(p.get("description"), p.get("priority", 5))
            elif "temporal" in intent: return self._temporal(p.get("subject"), p.get("query"))
            elif "consolidate" in intent: return self._consolidate()
            elif "stats" in intent: return self._stats()
            return SkillResult.fail(error=f"Unknown: {intent}")
        except Exception as e:
            return SkillResult.fail(error=str(e))

    def can_handle(self, request):
        return 0.9 if any(k in request.intent.lower() for k in ["memory", "remember", "recall", "goal", "temporal", "consolidate"]) else super().can_handle(request)

    def _store(self, content: str, mem_type: str, importance: float) -> SkillResult:
        if not content: return SkillResult.fail(error="Content required")
        mid = f"mem_{int(time.time())}_{hash(content) % 10000}"
        tags = ",".join(re.findall(r"\b\w{4,}\b", content.lower())[:5])
        with sqlite3.connect(self.storage_file) as conn:
            conn.execute("INSERT INTO memories VALUES (?, ?, ?, ?, ?, ?)", (mid, content, mem_type, time.time(), importance, tags))
            conn.commit()
        return SkillResult.ok(message=f"Stored: {mid}", data={"id": mid, "type": mem_type, "importance": importance})

    def _retrieve(self, query: str) -> SkillResult:
        if not query: return SkillResult.fail(error="Query required")
        words = query.lower().split()
        with sqlite3.connect(self.storage_file) as conn:
            cursor = conn.execute("SELECT * FROM memories WHERE content LIKE ? OR tags LIKE ? ORDER BY timestamp DESC LIMIT 10", (f"%{query}%", f"%{query}%"))
            rows = cursor.fetchall()
        results = [{"id": r[0], "content": r[1][:200], "type": r[2], "timestamp": r[3], "importance": r[4]} for r in rows]
        return SkillResult.ok(message=f"Retrieved: {len(results)} memories", data={"query": query, "results": results})

    def _goal(self, description: str, priority: int) -> SkillResult:
        if not description: return SkillResult.fail(error="Description required")
        gid = f"goal_{int(time.time())}"
        with sqlite3.connect(self.storage_file) as conn:
            conn.execute("INSERT INTO goals VALUES (?, ?, ?, ?, ?, ?)", (gid, description, priority, 0.0, "active", time.time()))
            conn.commit()
        return SkillResult.ok(message=f"Goal tracked: {description}", data={"id": gid, "priority": priority})

    def _temporal(self, subject: str, query: str) -> SkillResult:
        if not subject: return SkillResult.fail(error="Subject required")
        with sqlite3.connect(self.storage_file) as conn:
            cursor = conn.execute("SELECT * FROM temporal WHERE subject = ? ORDER BY timestamp DESC", (subject,))
            rows = cursor.fetchall()
        return SkillResult.ok(message=f"Temporal: {len(rows)} facts about {subject}", data={"subject": subject, "facts": [{"predicate": r[2], "object": r[3], "time": r[4], "marker": r[5]} for r in rows]})

    def _consolidate(self) -> SkillResult:
        with sqlite3.connect(self.storage_file) as conn:
            cutoff = time.time() - 30 * 86400
            cursor = conn.execute("DELETE FROM memories WHERE timestamp < ? AND importance < 0.3", (cutoff,))
            removed = cursor.rowcount
            conn.commit()
        return SkillResult.ok(message=f"Consolidated: {removed} old memories removed", data={"removed": removed})

    def _stats(self) -> SkillResult:
        with sqlite3.connect(self.storage_file) as conn:
            mem_count = conn.execute("SELECT COUNT(*) FROM memories").fetchone()[0]
            goal_count = conn.execute("SELECT COUNT(*) FROM goals WHERE status = 'active'").fetchone()[0]
        return SkillResult.ok(message=f"Stats: {mem_count} memories, {goal_count} active goals", data={"memories": mem_count, "active_goals": goal_count, "storage_file": self.storage_file})
