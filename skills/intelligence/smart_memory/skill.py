"""Smart Memory Skill — Semantic storage, retrieval, search, consolidation."""

import json
import hashlib
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from skills import BaseSkill

logger = logging.getLogger(__name__)


class SmartMemorySkill(BaseSkill):
    """Semantic memory with storage, retrieval, search, and auto-consolidation."""

    def __init__(self):
        super().__init__(
            name="smart_memory",
            category="intelligence",
            capabilities=["smart_memory"]
        )
        self._memories: Dict[str, Dict[str, Any]] = {}
        self._tag_index: Dict[str, List[str]] = {}
        self._category_index: Dict[str, List[str]] = {}
        self._access_log: List[Dict[str, Any]] = []

    def execute(self, capability: str, params: Dict[str, Any]) -> Dict[str, Any]:
        method = params.get("method", "store")
        if method == "store":
            return self.store(params)
        elif method == "retrieve":
            return self.retrieve(params)
        elif method == "search":
            return self.search(params)
        elif method == "consolidate":
            return self.consolidate(params)
        elif method == "forget":
            return self.forget(params)
        return {"error": f"Unknown method: {method}"}

    def store(self, params: Dict[str, Any]) -> Dict[str, Any]:
        content = params.get("content", "")
        key = params.get("key", hashlib.sha256(str(content).encode()).hexdigest()[:16])
        memory = {
            "id": key,
            "content": content,
            "tags": params.get("tags", []),
            "category": params.get("category", "general"),
            "importance": params.get("importance", 5),
            "created_at": datetime.utcnow().isoformat(),
            "last_accessed": datetime.utcnow().isoformat(),
            "access_count": 0,
            "metadata": params.get("metadata", {}),
        }
        self._memories[key] = memory
        for tag in memory["tags"]:
            self._tag_index.setdefault(tag, []).append(key)
        cat = memory["category"]
        self._category_index.setdefault(cat, []).append(key)
        logger.info(f"Memory stored: {key} (category: {cat}, tags: {memory['tags']})")
        return {"success": True, "id": key, "stored": True, "memory": memory}

    def retrieve(self, params: Dict[str, Any]) -> Dict[str, Any]:
        key = params.get("key", "")
        memory = self._memories.get(key)
        if memory:
            memory["access_count"] += 1
            memory["last_accessed"] = datetime.utcnow().isoformat()
            self._access_log.append({"key": key, "action": "retrieve", "timestamp": datetime.utcnow().isoformat()})
            return {"success": True, "found": True, "memory": memory}
        return {"success": True, "found": False, "memory": None}

    def search(self, params: Dict[str, Any]) -> Dict[str, Any]:
        query = params.get("query", "").lower()
        tag = params.get("tag", "")
        category = params.get("category", "")
        limit = params.get("limit", 10)
        min_importance = params.get("min_importance", 0)
        candidates = []
        if tag:
            candidates = [self._memories[k] for k in self._tag_index.get(tag, []) if k in self._memories]
        elif category:
            candidates = [self._memories[k] for k in self._category_index.get(category, []) if k in self._memories]
        else:
            candidates = list(self._memories.values())
        results = []
        for m in candidates:
            if m.get("importance", 0) < min_importance:
                continue
            if not query or query in str(m.get("content", "")).lower() or query in str(m.get("tags", [])).lower():
                results.append(m)
        results.sort(key=lambda x: (x.get("importance", 0), x.get("access_count", 0)), reverse=True)
        return {"success": True, "query": query, "results_count": len(results), "results": results[:limit]}

    def consolidate(self, params: Dict[str, Any]) -> Dict[str, Any]:
        category = params.get("category", "")
        threshold = params.get("similarity_threshold", 0.9)
        memories_list = [m for m in self._memories.values() if not category or m.get("category") == category]
        merged = 0
        to_remove = []
        content_hashes = {}
        for key, memory in self._memories.items():
            if category and memory.get("category") != category:
                continue
            content_str = str(memory.get("content", ""))
            h = hashlib.md5(content_str.encode()).hexdigest()
            if h in content_hashes:
                to_remove.append(key)
                merged += 1
            else:
                content_hashes[h] = key
        for key in to_remove:
            if key in self._memories:
                del self._memories[key]
        for key in to_remove:
            for tag_list in self._tag_index.values():
                if key in tag_list:
                    tag_list.remove(key)
            for cat_list in self._category_index.values():
                if key in cat_list:
                    cat_list.remove(key)
        return {"success": True, "merged_duplicates": merged, "remaining": len(self._memories)}

    def forget(self, params: Dict[str, Any]) -> Dict[str, Any]:
        key = params.get("key", "")
        if key in self._memories:
            memory = self._memories.pop(key)
            for tag_list in self._tag_index.values():
                if key in tag_list:
                    tag_list.remove(key)
            for cat_list in self._category_index.values():
                if key in cat_list:
                    cat_list.remove(key)
            return {"success": True, "forgotten": True, "memory_id": key}
        return {"success": False, "error": "Memory not found", "memory_id": key}
