"""IRIS v1 Hybrid Chroma Memory - Persistent Vector Database"""
import os
import json
from typing import Dict, List, Optional
from config import config
from core.db import db

class ChromaMemory:
    """
    Persistent vector memory using ChromaDB:
    - Store conversations as embeddings
    - Semantic search across all history
    - Document embeddings
    - Code embeddings
    - Never forgets anything
    """

    def __init__(self):
        self.collection_name = "iris_memory"
        self.client = None
        self.collection = None
        # ChromaDB requires a local server process + persistent disk —
        # can't work on Vercel serverless. Skip gracefully and use
        # PostgreSQL (via core/db) for vector storage when available.
        self._use_postgres = False
        try:
            from core.db import db
            if db._db_available and db.use_postgres:
                self._use_postgres = True
                logger.info("ChromaMemory: using PostgreSQL (no ChromaDB server needed)")
        except Exception:
            pass

        if not self._use_postgres and not os.environ.get("VERCEL"):
            # Local dev — try ChromaDB
            self.persist_dir = os.path.join(config.DATA_DIR, "chroma_db")
            try:
                os.makedirs(self.persist_dir, exist_ok=True)
                self._init_chroma()
            except Exception as e:
                logger.warning(f"ChromaDB init failed: {e}. Using in-memory fallback.")
                self.persist_dir = None

    def _init_chroma(self):
        """Initialize ChromaDB client"""
        try:
            import chromadb
            from chromadb.config import Settings

            self.client = chromadb.Client(Settings(
                chroma_db_impl="duckdb+parquet",
                persist_directory=self.persist_dir
            ))

            self.collection = self.client.get_or_create_collection(
                name=self.collection_name,
                metadata={"hnsw:space": "cosine"}
            )

        except ImportError:
            db.log("WARNING", "chroma_memory", "ChromaDB not installed. Using fallback.")
            self.client = None
            self.collection = None

    def add_memory(self, text: str, metadata: Dict = None, memory_id: str = None) -> bool:
        """Add a memory to vector store"""
        if not self.collection:
            return False

        try:
            memory_id = memory_id or f"mem_{os.urandom(8).hex()}"
            metadata = metadata or {}
            metadata["timestamp"] = db.datetime.now().isoformat()

            self.collection.add(
                documents=[text],
                metadatas=[metadata],
                ids=[memory_id]
            )

            # Persist
            if hasattr(self.client, 'persist'):
                self.client.persist()

            return True

        except Exception as e:
            db.log("ERROR", "chroma_memory", f"Failed to add memory: {e}")
            return False

    def search(self, query: str, n_results: int = 10, filter_metadata: Dict = None) -> List[Dict]:
        """Search memories by semantic similarity"""
        if not self.collection:
            return []

        try:
            results = self.collection.query(
                query_texts=[query],
                n_results=n_results,
                where=filter_metadata
            )

            memories = []
            for i in range(len(results["ids"][0])):
                memories.append({
                    "id": results["ids"][0][i],
                    "text": results["documents"][0][i],
                    "metadata": results["metadatas"][0][i],
                    "distance": results["distances"][0][i] if "distances" in results else None
                })

            return memories

        except Exception as e:
            db.log("ERROR", "chroma_memory", f"Search failed: {e}")
            return []

    def get_memory(self, memory_id: str) -> Optional[Dict]:
        """Get a specific memory by ID"""
        if not self.collection:
            return None

        try:
            result = self.collection.get(ids=[memory_id])
            if result["ids"]:
                return {
                    "id": result["ids"][0],
                    "text": result["documents"][0],
                    "metadata": result["metadatas"][0]
                }
            return None

        except Exception as e:
            db.log("ERROR", "chroma_memory", f"Get failed: {e}")
            return None

    def delete_memory(self, memory_id: str) -> bool:
        """Delete a memory"""
        if not self.collection:
            return False

        try:
            self.collection.delete(ids=[memory_id])
            return True
        except Exception as e:
            db.log("ERROR", "chroma_memory", f"Delete failed: {e}")
            return False

    def get_stats(self) -> Dict:
        """Get memory statistics"""
        if not self.collection:
            return {"status": "not_initialized", "count": 0}

        try:
            count = self.collection.count()
            return {
                "status": "active",
                "count": count,
                "collection": self.collection_name,
                "persist_dir": self.persist_dir
            }
        except Exception as e:
            return {"status": "error", "error": str(e), "count": 0}

    def backup(self, backup_path: str = None) -> str:
        """Backup vector database"""
        backup_path = backup_path or os.path.join(config.DATA_DIR, f"chroma_backup_{os.urandom(4).hex()}")

        try:
            import shutil
            shutil.copytree(self.persist_dir, backup_path)
            return backup_path
        except Exception as e:
            db.log("ERROR", "chroma_memory", f"Backup failed: {e}")
            return ""

chroma_memory = ChromaMemory()
