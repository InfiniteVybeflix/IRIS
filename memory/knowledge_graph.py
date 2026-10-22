"""
IRIS v1.0 — KnowledgeGraph
Connected facts graph (subject-predicate-object).

Stores and queries a semantic graph of facts with confidence scores.
Supports graph traversal, path finding between entities, inference,
visualization, deduplication, and RDF/Turtle export.

Features:
- Add facts with confidence and source attribution
- Query by subject, predicate, or object
- Find shortest paths between entities
- Infer missing facts from graph patterns
- Export to Graphviz DOT, Mermaid, or RDF/Turtle
- Merge duplicate facts

Storage:
    SQLite tables `facts` and `fact_sources` (JSON fallback).

Usage:
    kg = KnowledgeGraph()
    fid = kg.add_fact("IRIS", "is_a", "AI_system", confidence=1.0, source="design_doc")
    kg.query(subject="IRIS")
    kg.find_path("IRIS", "humanity")
    kg.visualize(format="dot")

Author: IRIS Core Team
"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
import time
from collections import deque
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from .base_memory import BaseMemory

logger = logging.getLogger("iris.memory.knowledge_graph")


class KnowledgeGraph(BaseMemory):
    """
    Semantic knowledge graph with inference and visualization.

    Stores facts as (subject, predicate, object) triples with
    confidence scores and source attribution.
    """

    def __init__(
        self,
        db_path: Optional[str] = None,
        iris_core: Optional[Any] = None,
    ) -> None:
        """
        Initialize KnowledgeGraph.

        Args:
            db_path: Path to SQLite database. Defaults to env var
                     IRIS_KG_DB or "iris_knowledge_graph.db".
            iris_core: Reference to IRIS core.
        """
        super().__init__(
            db_path=db_path or os.getenv("IRIS_KG_DB", "iris_knowledge_graph.db"),
            iris_core=iris_core,
        )
        self._create_kg_tables()

    def _create_kg_tables(self) -> None:
        """Create knowledge graph tables."""
        with self._lock:
                self._execute_sql(
                    """
                    CREATE TABLE IF NOT EXISTS facts (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        fact_id TEXT NOT NULL UNIQUE,
                        subject TEXT NOT NULL,
                        predicate TEXT NOT NULL,
                        object TEXT NOT NULL,
                        confidence REAL DEFAULT 1.0,
                        source TEXT,
                        created_at TEXT DEFAULT CURRENT_TIMESTAMP
                    )
                    """
                )
                self._execute_sql(
                    "CREATE INDEX IF NOT EXISTS idx_spo ON facts(subject, predicate, object)"
                )
                self._execute_sql(
                    "CREATE INDEX IF NOT EXISTS idx_subject ON facts(subject)"
                )
                self._execute_sql(
                    "CREATE INDEX IF NOT EXISTS idx_object ON facts(object)"
                )
                
    # ------------------------------------------------------------------
    # Core interface
    # ------------------------------------------------------------------
    def store(self, key: str, value: Any, metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Store a fact. Value must be dict with subject, predicate, object keys."""
        if not isinstance(value, dict):
            return self._result(False, "store", errors=["Value must be dict with subject, predicate, object"])
        return self.add_fact(
            value.get("subject", key),
            value.get("predicate", "related_to"),
            value.get("object", ""),
            confidence=value.get("confidence", 1.0),
            source=value.get("source"),
        )

    def retrieve(self, key: str) -> Dict[str, Any]:
        """Retrieve a fact by fact_id."""
        start = time.perf_counter()
        try:
            if self._use_postgres or self.use_sqlite:
                row = self._sql_execute_one("SELECT * FROM facts WHERE fact_id = ?", (key,))
                if row:
                    data = {
                        "id": row[0], "fact_id": row[1], "subject": row[2],
                        "predicate": row[3], "object": row[4],
                        "confidence": row[5], "source": row[6], "created_at": row[7],
                    }
                    return self._result(True, "retrieve", data, duration_ms=int((time.perf_counter()-start)*1000))
            else:
                data = self._json_read(key)
                if data:
                    return self._result(True, "retrieve", data, duration_ms=int((time.perf_counter()-start)*1000))
            return self._result(False, "retrieve", errors=[f"Fact {key} not found"])
        except Exception as exc:
            return self._result(False, "retrieve", errors=[str(exc)])

    def search(self, query: str, limit: int = 10) -> Dict[str, Any]:
        """Search facts by subject, predicate, or object."""
        start = time.perf_counter()
        try:
            results = []
            if self._use_postgres or self.use_sqlite:
                rows = self._sql_execute(
                    """
                    SELECT * FROM facts
                    WHERE subject LIKE ? OR predicate LIKE ? OR object LIKE ?
                    ORDER BY confidence DESC
                    LIMIT ?
                    """,
                    (f"%{query}%", f"%{query}%", f"%{query}%", limit),
                )
                for row in rows:
                    results.append({
                        "id": row[0], "fact_id": row[1], "subject": row[2],
                        "predicate": row[3], "object": row[4],
                        "confidence": row[5], "source": row[6], "created_at": row[7],
                    })
            else:
                for item in self._json_list():
                    if any(query.lower() in str(v).lower() for v in item.values()):
                        results.append(item)
                    if len(results) >= limit:
                        break
            duration_ms = int((time.perf_counter() - start) * 1000)
            return self._result(True, "search", results, duration_ms=duration_ms)
        except Exception as exc:
            return self._result(False, "search", errors=[str(exc)])

    def update(self, key: str, value: Any) -> Dict[str, Any]:
        """Update fact confidence by fact_id."""
        start = time.perf_counter()
        try:
            if isinstance(value, dict):
                confidence = value.get("confidence", 1.0)
                if self._use_postgres or self.use_sqlite:
                    self._sql_execute(
                        "UPDATE facts SET confidence = ? WHERE fact_id = ?",
                        (confidence, key),
                    )
                else:
                    data = self._json_read(key)
                    if data:
                        data["value"]["confidence"] = confidence
                        data["updated_at"] = datetime.now(timezone.utc).isoformat()
                        self._json_write(key, data["value"], data.get("metadata"))
            duration_ms = int((time.perf_counter() - start) * 1000)
            return self._result(True, "update", duration_ms=duration_ms)
        except Exception as exc:
            return self._result(False, "update", errors=[str(exc)])

    def delete(self, key: str) -> Dict[str, Any]:
        """Delete a fact by fact_id."""
        start = time.perf_counter()
        try:
            if self._use_postgres or self.use_sqlite:
                self._sql_execute("DELETE FROM facts WHERE fact_id = ?", (key,))
            else:
                self._json_delete(key)
            duration_ms = int((time.perf_counter() - start) * 1000)
            return self._result(True, "delete", duration_ms=duration_ms)
        except Exception as exc:
            return self._result(False, "delete", errors=[str(exc)])

    def list_all(self, filter_: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """List all facts with optional filter."""
        start = time.perf_counter()
        try:
            results = []
            if self._use_postgres or self.use_sqlite:
                sql = "SELECT * FROM facts"
                params = []
                conditions = []
                if filter_:
                    for k, v in filter_.items():
                        if k in ("subject", "predicate", "object", "source"):
                            conditions.append(f"{k} = ?")
                            params.append(v)
                if conditions:
                    sql += " WHERE " + " AND ".join(conditions)
                sql += " ORDER BY confidence DESC"
                rows = self._sql_execute(sql, tuple(params))
                for row in rows:
                    results.append({
                        "id": row[0], "fact_id": row[1], "subject": row[2],
                        "predicate": row[3], "object": row[4],
                        "confidence": row[5], "source": row[6], "created_at": row[7],
                    })
            else:
                for item in self._json_list():
                    if filter_:
                        match = True
                        for k, v in filter_.items():
                            if item.get(k) != v:
                                match = False
                                break
                        if not match:
                            continue
                    results.append(item)
            duration_ms = int((time.perf_counter() - start) * 1000)
            return self._result(True, "list_all", results, duration_ms=duration_ms)
        except Exception as exc:
            return self._result(False, "list_all", errors=[str(exc)])

    # ------------------------------------------------------------------
    # Graph-specific methods
    # ------------------------------------------------------------------
    def add_fact(
        self,
        subject: str,
        predicate: str,
        object: str,
        confidence: float = 1.0,
        source: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Add a fact triple to the knowledge graph.

        Args:
            subject: Entity being described.
            predicate: Relationship type.
            object: Related entity or value.
            confidence: 0.0-1.0 confidence in this fact.
            source: Attribution for this fact.

        Returns:
            Standard result with generated fact_id.
        """
        start = time.perf_counter()
        try:
            fact_id = f"fact_{subject}_{predicate}_{object}_{int(time.time() * 1000)}"
            if self._use_postgres or self.use_sqlite:
                self._sql_execute(
                    """
                    INSERT OR REPLACE INTO facts
                    (fact_id, subject, predicate, object, confidence, source)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (fact_id, subject, predicate, object, confidence, source),
                )
            else:
                self._json_write(
                    fact_id,
                    {
                        "fact_id": fact_id,
                        "subject": subject,
                        "predicate": predicate,
                        "object": object,
                        "confidence": confidence,
                        "source": source,
                    },
                )
            duration_ms = int((time.perf_counter() - start) * 1000)
            self.report({"action": "add_fact", "fact_id": fact_id})
            return self._result(True, "add_fact", {"fact_id": fact_id}, duration_ms=duration_ms)
        except Exception as exc:
            return self._result(False, "add_fact", errors=[str(exc)])

    def query(
        self,
        subject: Optional[str] = None,
        predicate: Optional[str] = None,
        object: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Query facts by any combination of subject, predicate, object.

        Args:
            subject: Filter by subject entity.
            predicate: Filter by relationship.
            object: Filter by object entity.

        Returns:
            Standard result with matching facts.
        """
        start = time.perf_counter()
        try:
            results = []
            if self._use_postgres or self.use_sqlite:
                conditions = []
                params = []
                if subject:
                    conditions.append("subject = ?")
                    params.append(subject)
                if predicate:
                    conditions.append("predicate = ?")
                    params.append(predicate)
                if object:
                    conditions.append("object = ?")
                    params.append(object)
                sql = "SELECT * FROM facts"
                if conditions:
                    sql += " WHERE " + " AND ".join(conditions)
                sql += " ORDER BY confidence DESC"
                rows = self._sql_execute(sql, tuple(params))
                for row in rows:
                    results.append({
                        "id": row[0], "fact_id": row[1], "subject": row[2],
                        "predicate": row[3], "object": row[4],
                        "confidence": row[5], "source": row[6], "created_at": row[7],
                    })
            else:
                for item in self._json_list():
                    match = True
                    if subject and item.get("subject") != subject:
                        match = False
                    if predicate and item.get("predicate") != predicate:
                        match = False
                    if object and item.get("object") != object:
                        match = False
                    if match:
                        results.append(item)
            duration_ms = int((time.perf_counter() - start) * 1000)
            return self._result(True, "query", results, duration_ms=duration_ms)
        except Exception as exc:
            return self._result(False, "query", errors=[str(exc)])

    def find_path(
        self,
        subject: str,
        object: str,
        max_depth: int = 5,
    ) -> Dict[str, Any]:
        """
        Find shortest path between two entities in the graph.

        Uses BFS traversal. Returns list of fact dicts forming the path.

        Args:
            subject: Starting entity.
            object: Target entity.
            max_depth: Maximum hops to search.

        Returns:
            Standard result with path as list of facts, or empty if no path.
        """
        start = time.perf_counter()
        try:
            # Build adjacency list from all facts
            all_facts = self.list_all().get("data", [])
            adj = {}
            fact_map = {}
            for f in all_facts:
                s = f["subject"]
                o = f["object"]
                fid = f["fact_id"]
                if s not in adj:
                    adj[s] = []
                adj[s].append(o)
                fact_map[(s, o)] = f

            # BFS
            queue = deque([(subject, [subject])])
            visited = {subject}
            while queue:
                current, path = queue.popleft()
                if current == object:
                    # Reconstruct fact path
                    fact_path = []
                    for i in range(len(path) - 1):
                        fact_path.append(fact_map.get((path[i], path[i + 1]), {}))
                    duration_ms = int((time.perf_counter() - start) * 1000)
                    return self._result(True, "find_path", fact_path, duration_ms=duration_ms)
                if len(path) > max_depth:
                    continue
                for neighbor in adj.get(current, []):
                    if neighbor not in visited:
                        visited.add(neighbor)
                        queue.append((neighbor, path + [neighbor]))

            duration_ms = int((time.perf_counter() - start) * 1000)
            return self._result(True, "find_path", [], duration_ms=duration_ms)
        except Exception as exc:
            return self._result(False, "find_path", errors=[str(exc)])

    def get_related(self, entity: str, depth: int = 2) -> Dict[str, Any]:
        """
        Get neighborhood of an entity up to a given depth.

        Args:
            entity: Center entity.
            depth: How many hops to traverse.

        Returns:
            Standard result with list of related facts.
        """
        start = time.perf_counter()
        try:
            all_facts = self.list_all().get("data", [])
            related = set()
            current_level = {entity}
            for _ in range(depth):
                next_level = set()
                for f in all_facts:
                    if f["subject"] in current_level:
                        related.add(f["object"])
                        next_level.add(f["object"])
                    if f["object"] in current_level:
                        related.add(f["subject"])
                        next_level.add(f["subject"])
                current_level = next_level

            results = [f for f in all_facts if f["subject"] in related or f["object"] in related]
            duration_ms = int((time.perf_counter() - start) * 1000)
            return self._result(True, "get_related", results, duration_ms=duration_ms)
        except Exception as exc:
            return self._result(False, "get_related", errors=[str(exc)])

    def infer(self, subject: str, predicate: str) -> Dict[str, Any]:
        """
        Infer missing facts from graph patterns.

        Simple transitive inference: if A->B and B->C, then A->C.

        Args:
            subject: Starting entity.
            predicate: Relationship to infer.

        Returns:
            Standard result with inferred facts.
        """
        start = time.perf_counter()
        try:
            # Get all facts with this predicate
            facts = self.query(predicate=predicate).get("data", [])
            # Build transitive closure
            closure = {}
            for f in facts:
                s = f["subject"]
                o = f["object"]
                if s not in closure:
                    closure[s] = set()
                closure[s].add(o)

            # Simple one-hop transitive inference
            inferred = []
            for s, objs in closure.items():
                for o in objs:
                    if o in closure:
                        for o2 in closure[o]:
                            if o2 not in objs:
                                inferred.append({
                                    "subject": s,
                                    "predicate": predicate,
                                    "object": o2,
                                    "inferred": True,
                                    "confidence": 0.7,
                                    "source": "inference",
                                })

            duration_ms = int((time.perf_counter() - start) * 1000)
            return self._result(True, "infer", inferred, duration_ms=duration_ms)
        except Exception as exc:
            return self._result(False, "infer", errors=[str(exc)])

    def visualize(self, format_: str = "dot") -> str:
        """
        Export graph to visualization format.

        Args:
            format_: "dot" (Graphviz) or "mermaid".

        Returns:
            String in the requested format.
        """
        try:
            facts = self.list_all().get("data", [])
            if format_ == "dot":
                lines = ["digraph KnowledgeGraph {"]
                for f in facts:
                    s = f["subject"].replace('"', '\"')
                    p = f["predicate"].replace('"', '\"')
                    o = f["object"].replace('"', '\"')
                    lines.append(f'    "{s}" -> "{o}" [label="{p}"];')
                lines.append("}")
                return "\n".join(lines)
            elif format_ == "mermaid":
                lines = ["graph TD;"]
                for f in facts:
                    s = f["subject"].replace('"', '\"')
                    p = f["predicate"].replace('"', '\"')
                    o = f["object"].replace('"', '\"')
                    lines.append(f'    {s}-->|{p}|{o};')
                return "\n".join(lines)
            else:
                return json.dumps(facts, indent=2, default=str)
        except Exception as exc:
            logger.error(f"Visualization failed: {exc}")
            return f"# Error: {exc}"

    def merge_duplicates(self) -> Dict[str, Any]:
        """
        Remove duplicate facts (same subject, predicate, object).

        Returns:
            Standard result with count of duplicates removed.
        """
        start = time.perf_counter()
        try:
            if self._use_postgres or self.use_sqlite:
                rows = self._sql_execute(
                    """
                    SELECT subject, predicate, object, COUNT(*) as cnt
                    FROM facts
                    GROUP BY subject, predicate, object
                    HAVING cnt > 1
                    """
                )
                removed = 0
                for row in rows:
                    s, p, o, cnt = row
                    # Keep the highest confidence one, delete others
                    to_delete = self._sql_execute(
                        """
                        SELECT fact_id FROM facts
                        WHERE subject = ? AND predicate = ? AND object = ?
                        ORDER BY confidence DESC
                        """,
                        (s, p, o),
                    )
                    for del_row in to_delete[1:]:
                        self._sql_execute("DELETE FROM facts WHERE fact_id = ?", (del_row[0],))
                        removed += 1
            else:
                items = self._json_list()
                seen = {}
                removed = 0
                for item in items:
                    key = (item.get("subject"), item.get("predicate"), item.get("object"))
                    if key in seen:
                        self._json_delete(item.get("fact_id", ""))
                        removed += 1
                    else:
                        seen[key] = item
            duration_ms = int((time.perf_counter() - start) * 1000)
            return self._result(True, "merge_duplicates", {"removed": removed}, duration_ms=duration_ms)
        except Exception as exc:
            return self._result(False, "merge_duplicates", errors=[str(exc)])

    def export_turtle(self) -> str:
        """
        Export graph as RDF/Turtle format.

        Returns:
            Turtle-formatted string.
        """
        try:
            facts = self.list_all().get("data", [])
            lines = [
                "@prefix iris: <http://iris.aevibron.org/kg#> .",
                "@prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .",
                "",
            ]
            for f in facts:
                s = f["subject"].replace(" ", "_")
                p = f["predicate"].replace(" ", "_")
                o = f["object"].replace(" ", "_")
                lines.append(f'iris:{s} iris:{p} iris:{o} .')
            return "\n".join(lines)
        except Exception as exc:
            logger.error(f"Turtle export failed: {exc}")
            return f"# Error: {exc}"


# ------------------------------------------------------------------
# Usage example
# ------------------------------------------------------------------
if __name__ == "__main__":
    kg = KnowledgeGraph()
    kg.add_fact("IRIS", "is_a", "AI_system", confidence=1.0, source="design")
    kg.add_fact("IRIS", "has_capability", "reasoning", confidence=0.95)
    kg.add_fact("reasoning", "enables", "planning", confidence=0.9)
    print(kg.query(subject="IRIS"))
    print(kg.find_path("IRIS", "planning"))
    print(kg.visualize("mermaid"))
