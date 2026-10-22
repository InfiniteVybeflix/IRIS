"""
IRIS v1.0 — SemanticSearch
Vector embeddings for memory retrieval.

Generates dense vector embeddings for text documents, enabling
semantic similarity search. Falls back to TF-IDF + keyword search
if sentence-transformers is unavailable.

Features:
- Embed text into dense vectors (sentence-transformers or TF-IDF fallback)
- Index documents with metadata
- Semantic similarity search
- Hybrid search (semantic + keyword)
- Reindex all documents
- Find similar documents by ID

Storage:
    SQLite table `embeddings` (JSON fallback with vector cache).

Usage:
    ss = SemanticSearch()
    ss.index_document("doc-1", "IRIS is an autonomous AI system.", {"type": "description"})
    results = ss.search("autonomous intelligence", top_k=5)
    similar = ss.get_similar("doc-1", top_k=3)

Author: IRIS Core Team
"""

from __future__ import annotations

import json
import logging
import math
import os
import sqlite3
import threading
import time
from collections import Counter
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from .base_memory import BaseMemory

logger = logging.getLogger("iris.memory.semantic_search")


class SemanticSearch(BaseMemory):
    """
    Vector-based semantic search with graceful degradation.

    Uses sentence-transformers when available, falls back to
    TF-IDF + cosine similarity for keyword-based semantic search.
    """

    def __init__(
        self,
        db_path: Optional[str] = None,
        model_name: Optional[str] = None,
        iris_core: Optional[Any] = None,
    ) -> None:
        """
        Initialize SemanticSearch.

        Args:
            db_path: Path to SQLite database. Defaults to env var
                     IRIS_SEMANTIC_DB or "iris_semantic_search.db".
            model_name: Sentence-transformers model name. Defaults to
                        env var IRIS_EMBEDDING_MODEL or "all-MiniLM-L6-v2".
            iris_core: Reference to IRIS core.
        """
        super().__init__(
            db_path=db_path or os.getenv("IRIS_SEMANTIC_DB", "iris_semantic_search.db"),
            iris_core=iris_core,
        )
        self.model_name = model_name or os.getenv("IRIS_EMBEDDING_MODEL", "all-MiniLM-L6-v2")
        self._model: Optional[Any] = None
        self._tfidf: Optional[Dict[str, Any]] = None
        self._use_transformers: bool = False
        self._init_model()
        self._create_semantic_tables()

    def _init_model(self) -> None:
        """Initialize embedding model or TF-IDF fallback."""
        try:
            from sentence_transformers import SentenceTransformer
            self._model = SentenceTransformer(self.model_name)
            self._use_transformers = True
            logger.info(f"SemanticSearch using model: {self.model_name}")
        except ImportError:
            logger.warning("sentence-transformers not available. Using TF-IDF fallback.")
            self._use_transformers = False
            self._tfidf = {"documents": {}, "idf": {}, "doc_count": 0}

    def _create_semantic_tables(self) -> None:
        """Create semantic search tables."""
        with self._lock:
                self._execute_sql(
                    """
                    CREATE TABLE IF NOT EXISTS embeddings (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        doc_id TEXT NOT NULL UNIQUE,
                        text TEXT NOT NULL,
                        vector TEXT,
                        metadata TEXT,
                        created_at TEXT DEFAULT CURRENT_TIMESTAMP
                    )
                    """
                )
                self._execute_sql(
                    "CREATE INDEX IF NOT EXISTS idx_doc_id ON embeddings(doc_id)"
                )
                
    # ------------------------------------------------------------------
    # Core interface
    # ------------------------------------------------------------------
    def store(self, key: str, value: Any, metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Store a document. Value should be text string."""
        if not isinstance(value, str):
            return self._result(False, "store", errors=["Value must be text string"])
        return self.index_document(key, value, metadata)

    def retrieve(self, key: str) -> Dict[str, Any]:
        """Retrieve a document by doc_id."""
        start = time.perf_counter()
        try:
            if self._use_postgres or self.use_sqlite:
                row = self._sql_execute_one("SELECT * FROM embeddings WHERE doc_id = ?", (key,))
                if row:
                    data = {
                        "id": row[0], "doc_id": row[1], "text": row[2],
                        "vector": json.loads(row[3]) if row[3] else None,
                        "metadata": json.loads(row[4]) if row[4] else {},
                        "created_at": row[5],
                    }
                    return self._result(True, "retrieve", data, duration_ms=int((time.perf_counter()-start)*1000))
            else:
                data = self._json_read(key)
                if data:
                    return self._result(True, "retrieve", data, duration_ms=int((time.perf_counter()-start)*1000))
            return self._result(False, "retrieve", errors=[f"Document {key} not found"])
        except Exception as exc:
            return self._result(False, "retrieve", errors=[str(exc)])

    def search(self, query: str, limit: int = 10) -> Dict[str, Any]:
        """Semantic search for documents matching query."""
        return self.search(query, top_k=limit)

    def update(self, key: str, value: Any) -> Dict[str, Any]:
        """Update document text by doc_id."""
        start = time.perf_counter()
        try:
            if not isinstance(value, str):
                return self._result(False, "update", errors=["Value must be text string"])
            vector = json.dumps(self.embed(value)) if self._use_transformers else None
            if self._use_postgres or self.use_sqlite:
                self._sql_execute(
                    "UPDATE embeddings SET text = ?, vector = ? WHERE doc_id = ?",
                    (value, vector, key),
                )
            else:
                data = self._json_read(key)
                if data:
                    data["value"] = value
                    data["updated_at"] = datetime.now(timezone.utc).isoformat()
                    self._json_write(key, data["value"], data.get("metadata"))
            duration_ms = int((time.perf_counter() - start) * 1000)
            return self._result(True, "update", duration_ms=duration_ms)
        except Exception as exc:
            return self._result(False, "update", errors=[str(exc)])

    def delete(self, key: str) -> Dict[str, Any]:
        """Delete a document by doc_id."""
        start = time.perf_counter()
        try:
            if self._use_postgres or self.use_sqlite:
                self._sql_execute("DELETE FROM embeddings WHERE doc_id = ?", (key,))
            else:
                self._json_delete(key)
            if not self._use_transformers and self._tfidf:
                if key in self._tfidf["documents"]:
                    del self._tfidf["documents"][key]
            duration_ms = int((time.perf_counter() - start) * 1000)
            return self._result(True, "delete", duration_ms=duration_ms)
        except Exception as exc:
            return self._result(False, "delete", errors=[str(exc)])

    def list_all(self, filter_: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """List all indexed documents."""
        start = time.perf_counter()
        try:
            results = []
            if self._use_postgres or self.use_sqlite:
                sql = "SELECT * FROM embeddings"
                params = []
                if filter_:
                    conditions = []
                    for k, v in filter_.items():
                        conditions.append(f"metadata LIKE ?")
                        params.append(f'%"{k}": "{v}"%')
                    if conditions:
                        sql += " WHERE " + " AND ".join(conditions)
                sql += " ORDER BY created_at DESC"
                rows = self._sql_execute(sql, tuple(params))
                for row in rows:
                    results.append({
                        "id": row[0], "doc_id": row[1], "text": row[2],
                        "vector": json.loads(row[3]) if row[3] else None,
                        "metadata": json.loads(row[4]) if row[4] else {},
                        "created_at": row[5],
                    })
            else:
                for item in self._json_list():
                    results.append(item)
            duration_ms = int((time.perf_counter() - start) * 1000)
            return self._result(True, "list_all", results, duration_ms=duration_ms)
        except Exception as exc:
            return self._result(False, "list_all", errors=[str(exc)])

    # ------------------------------------------------------------------
    # Semantic search methods
    # ------------------------------------------------------------------
    def embed(self, text: str) -> List[float]:
        """
        Generate embedding vector for text.

        Uses sentence-transformers if available, otherwise returns
        TF-IDF vector (sparse representation as dense list).

        Args:
            text: Input text to embed.

        Returns:
            List of floats representing the embedding.
        """
        if self._use_transformers and self._model:
            return self._model.encode(text).tolist()
        else:
            # TF-IDF fallback: return normalized term frequency vector
            return self._tfidf_embed(text)

    def _tfidf_embed(self, text: str) -> List[float]:
        """Generate a simple TF-IDF-like embedding as fallback."""
        tokens = self._tokenize(text)
        tf = Counter(tokens)
        total = len(tokens) if tokens else 1
        # Use a fixed vocabulary hash for consistency
        vocab_size = 384  # Match MiniLM dimension
        vec = [0.0] * vocab_size
        for token, count in tf.items():
            idx = hash(token) % vocab_size
            vec[idx] += count / total
        # Normalize
        norm = math.sqrt(sum(v * v for v in vec))
        if norm > 0:
            vec = [v / norm for v in vec]
        return vec

    def _tokenize(self, text: str) -> List[str]:
        """Simple tokenization for TF-IDF fallback."""
        return text.lower().split()

    def _cosine_similarity(self, a: List[float], b: List[float]) -> float:
        """Compute cosine similarity between two vectors."""
        dot = sum(x * y for x, y in zip(a, b))
        norm_a = math.sqrt(sum(x * x for x in a))
        norm_b = math.sqrt(sum(x * x for x in b))
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot / (norm_a * norm_b)

    def index_document(
        self,
        doc_id: str,
        text: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Add a document to the semantic index.

        Args:
            doc_id: Unique document identifier.
            text: Document content.
            metadata: Optional metadata dict.

        Returns:
            Standard result envelope.
        """
        start = time.perf_counter()
        try:
            vector = self.embed(text)
            vector_json = json.dumps(vector)
            metadata_json = json.dumps(metadata or {}, default=str)

            if self._use_postgres or self.use_sqlite:
                self._sql_execute(
                    """
                    INSERT OR REPLACE INTO embeddings
                    (doc_id, text, vector, metadata)
                    VALUES (?, ?, ?, ?)
                    """,
                    (doc_id, text, vector_json, metadata_json),
                )
            else:
                self._json_write(
                    doc_id,
                    {"doc_id": doc_id, "text": text, "vector": vector, "metadata": metadata or {}},
                )

            if not self._use_transformers and self._tfidf:
                self._tfidf["documents"][doc_id] = {"text": text, "vector": vector}

            duration_ms = int((time.perf_counter() - start) * 1000)
            self.report({"action": "index_document", "doc_id": doc_id})
            return self._result(True, "index_document", {"doc_id": doc_id}, duration_ms=duration_ms)
        except Exception as exc:
            return self._result(False, "index_document", errors=[str(exc)])

    def search(self, query: str, top_k: int = 10) -> Dict[str, Any]:
        """
        Semantic similarity search.

        Args:
            query: Search query text.
            top_k: Number of top results to return.

        Returns:
            Standard result with list of matching documents and scores.
        """
        start = time.perf_counter()
        try:
            query_vec = self.embed(query)
            results = []

            if self._use_postgres or self.use_sqlite:
                rows = self._sql_execute("SELECT doc_id, text, vector, metadata FROM embeddings", ())
                for row in rows:
                    doc_vec = json.loads(row[2]) if row[2] else []
                    score = self._cosine_similarity(query_vec, doc_vec)
                    results.append({
                        "doc_id": row[0],
                        "text": row[1],
                        "score": round(score, 4),
                        "metadata": json.loads(row[3]) if row[3] else {},
                    })
            else:
                for item in self._json_list():
                    doc_vec = item.get("vector", [])
                    score = self._cosine_similarity(query_vec, doc_vec)
                    results.append({
                        "doc_id": item.get("doc_id"),
                        "text": item.get("text", ""),
                        "score": round(score, 4),
                        "metadata": item.get("metadata", {}),
                    })

            results.sort(key=lambda x: x["score"], reverse=True)
            results = results[:top_k]
            duration_ms = int((time.perf_counter() - start) * 1000)
            return self._result(True, "search", results, duration_ms=duration_ms)
        except Exception as exc:
            return self._result(False, "search", errors=[str(exc)])

    def hybrid_search(self, query: str, top_k: int = 10) -> Dict[str, Any]:
        """
        Combine semantic similarity with keyword matching.

        Scores are blended: 0.7 * semantic + 0.3 * keyword.

        Args:
            query: Search query text.
            top_k: Number of top results.

        Returns:
            Standard result with blended scores.
        """
        start = time.perf_counter()
        try:
            query_lower = query.lower()
            query_tokens = set(self._tokenize(query))
            query_vec = self.embed(query)
            results = []

            if self._use_postgres or self.use_sqlite:
                rows = self._sql_execute("SELECT doc_id, text, vector, metadata FROM embeddings", ())
                for row in rows:
                    text = row[1]
                    doc_vec = json.loads(row[2]) if row[2] else []
                    semantic_score = self._cosine_similarity(query_vec, doc_vec)
                    # Keyword score: Jaccard similarity of token sets
                    doc_tokens = set(self._tokenize(text))
                    intersection = len(query_tokens & doc_tokens)
                    union = len(query_tokens | doc_tokens)
                    keyword_score = intersection / union if union > 0 else 0.0
                    blended = 0.7 * semantic_score + 0.3 * keyword_score
                    results.append({
                        "doc_id": row[0],
                        "text": text,
                        "semantic_score": round(semantic_score, 4),
                        "keyword_score": round(keyword_score, 4),
                        "blended_score": round(blended, 4),
                        "metadata": json.loads(row[3]) if row[3] else {},
                    })
            else:
                for item in self._json_list():
                    text = item.get("text", "")
                    doc_vec = item.get("vector", [])
                    semantic_score = self._cosine_similarity(query_vec, doc_vec)
                    doc_tokens = set(self._tokenize(text))
                    intersection = len(query_tokens & doc_tokens)
                    union = len(query_tokens | doc_tokens)
                    keyword_score = intersection / union if union > 0 else 0.0
                    blended = 0.7 * semantic_score + 0.3 * keyword_score
                    results.append({
                        "doc_id": item.get("doc_id"),
                        "text": text,
                        "semantic_score": round(semantic_score, 4),
                        "keyword_score": round(keyword_score, 4),
                        "blended_score": round(blended, 4),
                        "metadata": item.get("metadata", {}),
                    })

            results.sort(key=lambda x: x["blended_score"], reverse=True)
            results = results[:top_k]
            duration_ms = int((time.perf_counter() - start) * 1000)
            return self._result(True, "hybrid_search", results, duration_ms=duration_ms)
        except Exception as exc:
            return self._result(False, "hybrid_search", errors=[str(exc)])

    def reindex(self) -> Dict[str, Any]:
        """
        Rebuild all embeddings from stored text.

        Returns:
            Standard result with count of reindexed documents.
        """
        start = time.perf_counter()
        try:
            docs = self.list_all().get("data", [])
            count = 0
            for doc in docs:
                doc_id = doc.get("doc_id")
                text = doc.get("text", "")
                metadata = doc.get("metadata", {})
                vector = self.embed(text)
                vector_json = json.dumps(vector)
                if self._use_postgres or self.use_sqlite:
                    self._sql_execute(
                        "UPDATE embeddings SET vector = ? WHERE doc_id = ?",
                        (vector_json, doc_id),
                    )
                count += 1
            duration_ms = int((time.perf_counter() - start) * 1000)
            return self._result(True, "reindex", {"reindexed": count}, duration_ms=duration_ms)
        except Exception as exc:
            return self._result(False, "reindex", errors=[str(exc)])

    def get_similar(self, doc_id: str, top_k: int = 5) -> Dict[str, Any]:
        """
        Find documents similar to a given document.

        Args:
            doc_id: Reference document ID.
            top_k: Number of similar documents.

        Returns:
            Standard result with similar documents.
        """
        start = time.perf_counter()
        try:
            doc = self.retrieve(doc_id).get("data", {})
            if not doc:
                return self._result(False, "get_similar", errors=[f"Document {doc_id} not found"])
            text = doc.get("text", "")
            results = self.search(text, top_k=top_k + 1).get("data", [])
            # Exclude the query document itself
            results = [r for r in results if r.get("doc_id") != doc_id][:top_k]
            duration_ms = int((time.perf_counter() - start) * 1000)
            return self._result(True, "get_similar", results, duration_ms=duration_ms)
        except Exception as exc:
            return self._result(False, "get_similar", errors=[str(exc)])


# ------------------------------------------------------------------
# Usage example
# ------------------------------------------------------------------
if __name__ == "__main__":
    ss = SemanticSearch()
    ss.index_document("doc-1", "IRIS is an autonomous AI system with reasoning capabilities.")
    ss.index_document("doc-2", "Machine learning models process data to make predictions.")
    ss.index_document("doc-3", "Neural networks are inspired by biological brains.")
    print(ss.search("autonomous intelligence"))
    print(ss.hybrid_search("AI reasoning"))
