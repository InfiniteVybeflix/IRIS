"""
IRIS v7.0 Memory Package
Persistent, queryable, and learning-capable memory systems.

All memory modules inherit from BaseMemory and implement:
- SQLite persistence (JSON fallback)
- Thread-safe operations
- Semantic + keyword search
- Graceful degradation on missing ML libraries

Modules:
    base_memory:        Abstract base for all memory systems
    agent_memory:       Per-agent episodic mission records
    knowledge_graph:    Subject-predicate-object fact graph
    skill_memory:       Technique effectiveness tracking
    mission_archive:    Complete mission logs with outcomes
    semantic_search:    Vector embeddings for memory retrieval
    learning_engine:    Pattern extraction and improvement

Usage:
    from iris_v7.memory import BaseMemory, AgentMemory, KnowledgeGraph
    from iris_v7.memory import SkillMemory, MissionArchive, SemanticSearch, LearningEngine
"""

from .base_memory import BaseMemory
from .agent_memory import AgentMemory
from .knowledge_graph import KnowledgeGraph
from .skill_memory import SkillMemory
from .mission_archive import MissionArchive
from .semantic_search import SemanticSearch
from .learning_engine import LearningEngine

__all__ = [
    "BaseMemory",
    "AgentMemory",
    "KnowledgeGraph",
    "SkillMemory",
    "MissionArchive",
    "SemanticSearch",
    "LearningEngine",
]
