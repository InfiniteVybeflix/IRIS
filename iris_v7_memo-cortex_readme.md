# IRIS v7.0 — Memory & Cortex System (Complete Package)

> This file combines all documentation, code, and requirements for the IRIS v7.0 cognitive layer.
> Generated from: README_memo-cortex.md, __init__.py, iris_core.py, requirements.txt

---

# TABLE OF CONTENTS

1. [System Overview](#1-system-overview)
2. [Installation & Setup](#2-installation--setup)
3. [Environment Variables](#3-environment-variables)
4. [Module Reference](#4-module-reference)
5. [Architecture](#5-architecture)
6. [Package __init__.py](#6-package-initpy)
7. [IRISCore (Central Brain)](#7-iriscore-central-brain)
8. [Requirements](#8-requirements)
9. [Graceful Degradation](#9-graceful-degradation)
10. [Testing](#10-testing)

---

# 1. SYSTEM OVERVIEW

This is the **cognitive layer** of IRIS v7.0 — her memory and reasoning engine. Every memory persists. Every reasoning chain produces real decisions. IRIS learns, plans, and adapts.

This package contains two subsystems:
- **`memory/`** — Persistent, queryable, learning-capable memory systems
- **`cortex/`** — Planning, strategy, risk assessment, and self-improvement engines

---

# 2. INSTALLATION & SETUP

### 2.1 Directory Structure

```
your_project/
├── iris_v7/
│   ├── __init__.py
│   ├── iris_core.py
│   ├── memory/
│   │   ├── __init__.py
│   │   ├── base_memory.py
│   │   ├── agent_memory.py
│   │   ├── knowledge_graph.py
│   │   ├── skill_memory.py
│   │   ├── mission_archive.py
│   │   ├── semantic_search.py
│   │   └── learning_engine.py
│   └── cortex/
│       ├── __init__.py
│       ├── base_cortex.py
│       ├── planner.py
│       ├── strategist.py
│       ├── risk_assessor.py
│       ├── resource_optimizer.py
│       ├── hypothesis_tester.py
│       └── meta_learner.py
├── main.py
└── requirements.txt
```

### 2.2 Install Dependencies

```bash
pip install -r requirements.txt
```

### 2.3 Quick Start

```python
from iris_v7.memory import (
    BaseMemory, AgentMemory, KnowledgeGraph,
    SkillMemory, MissionArchive, SemanticSearch, LearningEngine,
)
from iris_v7.cortex import (
    BaseCortex, Planner, Strategist, RiskAssessor,
    ResourceOptimizer, HypothesisTester, MetaLearner,
)
from iris_v7.iris_core import IRISCore

# Full integration
iris = IRISCore()
iris.boot()

# Plan and execute a mission
result = iris.execute_mission("Secure website", context={"target": "example.com"})

# Query memory
history = iris.memory.agent_memory.get_agent_history("Alpha")

# Add knowledge
iris.add_knowledge("IRIS", "is_a", "AI_system", 1.0)

# Semantic search
results = iris.search_memory("network security", top_k=5)

# Shutdown cleanly
iris.shutdown()
```

---

# 3. ENVIRONMENT VARIABLES

All configuration is environment-driven. No hardcoded secrets.

| Variable | Default | Description |
|----------|---------|-------------|
| `IRIS_MEMORY_DB` | `iris_memory.db` | Base memory SQLite path |
| `IRIS_AGENT_MEMORY_DB` | `iris_agent_memory.db` | Agent memory SQLite path |
| `IRIS_KG_DB` | `iris_knowledge_graph.db` | Knowledge graph SQLite path |
| `IRIS_SKILL_MEMORY_DB` | `iris_skill_memory.db` | Skill memory SQLite path |
| `IRIS_MISSION_ARCHIVE_DB` | `iris_mission_archive.db` | Mission archive SQLite path |
| `IRIS_SEMANTIC_DB` | `iris_semantic_search.db` | Semantic search SQLite path |
| `IRIS_LEARNING_DB` | `iris_learning.db` | Learning engine SQLite path |
| `IRIS_CORTEX_DB` | `iris_cortex.db` | Cortex base SQLite path |
| `IRIS_PLANNER_DB` | `iris_planner.db` | Planner SQLite path |
| `IRIS_STRATEGIST_DB` | `iris_strategist.db` | Strategist SQLite path |
| `IRIS_RISK_DB` | `iris_risk_assessor.db` | Risk assessor SQLite path |
| `IRIS_RESOURCE_DB` | `iris_resource_optimizer.db` | Resource optimizer SQLite path |
| `IRIS_HYPOTHESIS_DB` | `iris_hypothesis_tester.db` | Hypothesis tester SQLite path |
| `IRIS_META_LEARNER_DB` | `iris_meta_learner.db` | Meta learner SQLite path |
| `IRIS_EMBEDDING_MODEL` | `all-MiniLM-L6-v2` | Sentence-transformers model name |

---

# 4. MODULE REFERENCE

### 4.1 Memory Systems

| Module | Purpose |
|--------|---------|
| `BaseMemory` | Abstract base — SQLite/JSON persistence, thread-safe, standard result format |
| `AgentMemory` | Per-agent episodic memory, performance tracking, agent comparison |
| `KnowledgeGraph` | S-P-O fact graph, path finding, inference, RDF/Turtle export |
| `SkillMemory` | Technique effectiveness, best technique recommendation, emerging/deprecated detection |
| `MissionArchive` | Complete mission logs, timeline, statistics, comparison, lesson extraction |
| `SemanticSearch` | Vector embeddings (sentence-transformers or TF-IDF fallback), hybrid search |
| `LearningEngine` | Pattern extraction, success prediction, skill gap detection, Bayesian belief updates |

### 4.2 Reasoning Modules

| Module | Purpose |
|--------|---------|
| `BaseCortex` | Abstract base — reasoning logs, evaluation, explanation, confidence |
| `Planner` | Goal decomposition, sequencing, estimation, optimization, validation |
| `Strategist` | Approach selection, trade-off analysis, dynamic adaptation |
| `RiskAssessor` | Multi-dimensional risk (operational, legal, reputational, technical), mitigations |
| `ResourceOptimizer` | Cost estimation, budget optimization, scheduling, caching, load balancing |
| `HypothesisTester` | Hypothesis generation, testing, simulation, scenario comparison, falsification |
| `MetaLearner` | Outcome recording, bias detection, reasoning improvements, accuracy tracking |

---

# 5. ARCHITECTURE

```
┌─────────────────────────────────────────┐
│              IRIS Core                  │
│         (your main application)          │
└─────────────────────────────────────────┘
                    │
    ┌───────────────┼───────────────┐
    ▼               ▼               ▼
┌─────────┐   ┌─────────┐   ┌─────────┐
│ Memory  │   │ Cortex  │   │ Reports │
│ Systems │   │ Modules │   │  Back   │
└─────────┘   └─────────┘   └─────────┘
    │               │
    ▼               ▼
┌─────────┐   ┌─────────┐
│ SQLite  │   │ SQLite  │
│ (WAL)   │   │ (WAL)   │
└─────────┘   └─────────┘
    │               │
    ▼               ▼
┌─────────┐   ┌─────────┐
│  JSON   │   │  JSON   │
│Fallback │   │Fallback │
└─────────┘   └─────────┘
```

Every module:
- Inherits from `IRISConnectable` (health checks, status reports, findings)
- Is thread-safe (`threading.RLock()`)
- Uses SQLite with WAL mode (falls back to JSON files)
- Returns standard result envelopes
- Has comprehensive logging
- Includes type hints and docstrings

---

# 6. PACKAGE __init__.py

```python
"""
IRIS v7.0 Memory & Cortex System — Core Package
The cognitive layer of the most powerful autonomous intelligence.

This package contains all memory and reasoning modules that form
IRIS's cognitive architecture. Every module is production-ready,
thread-safe, and implements graceful degradation.

Modules:
    memory: Persistent knowledge, episodic records, semantic search,
            skill tracking, mission archives, and learning engines.
    cortex: Planning, strategy, risk assessment, resource optimization,
            hypothesis testing, and meta-learning.

Usage:
    from iris_v7.memory import BaseMemory, AgentMemory, KnowledgeGraph
    from iris_v7.cortex import BaseCortex, Planner, Strategist

Author: IRIS Core Team
Version: 7.0.0
"""

import logging
import sys

# Configure root logger for IRIS
logger = logging.getLogger("iris")
logger.setLevel(logging.DEBUG)

if not logger.handlers:
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(logging.DEBUG)
    formatter = logging.Formatter(
        "%(asctime)s | %(name)s | %(levelname)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)

__version__ = "7.0.0"
__author__ = "IRIS Core Team"

__all__ = ["memory", "cortex", "logger"]

```

---

# 7. IRISCORE (CENTRAL BRAIN)

```python

"""
"""
IRIS v7.0 — IRISCore
The central brain that wires all memory and cortex modules together.

This is the integration layer that connects every memory system and
reasoning module into a unified cognitive architecture. It handles:
- Module discovery and lifecycle management
- Cross-module communication
- Finding aggregation and routing
- Health monitoring across all subsystems
- Mission execution orchestration

Usage:
    from iris_v7.iris_core import IRISCore

    iris = IRISCore()
    iris.boot()

    # Plan and execute a mission
    result = iris.execute_mission("Secure website", context={"target": "example.com"})

    # Query memory
    history = iris.memory.agent_memory.get_agent_history("Alpha")

    # Shutdown cleanly
    iris.shutdown()

Author: IRIS Core Team
Version: 7.0.0
"""

from __future__ import annotations

import json
import logging
import os
import threading
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from .memory import (
    AgentMemory,
    KnowledgeGraph,
    LearningEngine,
    MissionArchive,
    SemanticSearch,
    SkillMemory,
)
from .cortex import (
    HypothesisTester,
    MetaLearner,
    Planner,
    ResourceOptimizer,
    RiskAssessor,
    Strategist,
)

logger = logging.getLogger("iris.core")


class IRISCore:
    """
    Central orchestrator for IRIS v7.0 cognitive architecture.

    Manages all memory and cortex modules, handles cross-module
    communication, and provides high-level mission execution.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None) -> None:
        """
        Initialize IRIS Core with all subsystems.

        Args:
            config: Optional configuration dict with db_paths, model_name, etc.
        """
        self.config = config or {}
        self.status = "initializing"
        self._lock = threading.RLock()
        self._findings: List[Dict[str, Any]] = []
        self._findings_lock = threading.Lock()

        # Memory subsystems
        self.memory = self._init_memory()
        # Cortex subsystems
        self.cortex = self._init_cortex()
        # Connect learning engine to memory systems
        self.memory.learning_engine = LearningEngine(
            agent_memory=self.memory.agent_memory,
            mission_archive=self.memory.mission_archive,
            skill_memory=self.memory.skill_memory,
            iris_core=self,
        )

        self.status = "ready"
        logger.info("IRIS Core v7.0 initialized successfully")

    def _init_memory(self) -> "MemoryHub":
        """Initialize all memory subsystems."""
        return MemoryHub(
            agent_memory=AgentMemory(iris_core=self),
            knowledge_graph=KnowledgeGraph(iris_core=self),
            skill_memory=SkillMemory(iris_core=self),
            mission_archive=MissionArchive(iris_core=self),
            semantic_search=SemanticSearch(iris_core=self),
            learning_engine=None,  # Set after init
        )

    def _init_cortex(self) -> "CortexHub":
        """Initialize all cortex reasoning modules."""
        return CortexHub(
            planner=Planner(iris_core=self),
            strategist=Strategist(iris_core=self),
            risk_assessor=RiskAssessor(iris_core=self),
            resource_optimizer=ResourceOptimizer(iris_core=self),
            hypothesis_tester=HypothesisTester(iris_core=self),
            meta_learner=MetaLearner(iris_core=self),
        )

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------
    def boot(self) -> Dict[str, Any]:
        """
        Boot IRIS Core and all subsystems.

        Returns:
            Boot status dict.
        """
        start = time.perf_counter()
        with self._lock:
            health = self.health_check()
            all_ready = all(m["available"] for m in health["modules"].values())
            self.status = "online" if all_ready else "degraded"
            duration_ms = int((time.perf_counter() - start) * 1000)
            return {
                "status": self.status,
                "modules": health["modules"],
                "boot_time_ms": duration_ms,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

    def shutdown(self) -> None:
        """Gracefully shut down all subsystems."""
        with self._lock:
            self.status = "shutting_down"
            # Close all memory connections
            for name, module in vars(self.memory).items():
                if module and hasattr(module, "close"):
                    try:
                        module.close()
                        logger.info(f"Closed memory module: {name}")
                    except Exception as exc:
                        logger.warning(f"Error closing {name}: {exc}")
            # Close all cortex connections
            for name, module in vars(self.cortex).items():
                if module and hasattr(module, "close"):
                    try:
                        module.close()
                        logger.info(f"Closed cortex module: {name}")
                    except Exception as exc:
                        logger.warning(f"Error closing {name}: {exc}")
            self.status = "offline"
            logger.info("IRIS Core shutdown complete")

    # ------------------------------------------------------------------
    # Health & Status
    # ------------------------------------------------------------------
    def health_check(self) -> Dict[str, Any]:
        """
        Check health of all subsystems.

        Returns:
            Health status dict with per-module status.
        """
        modules = {}
        for name, module in vars(self.memory).items():
            if module and hasattr(module, "health_check"):
                modules[f"memory.{name}"] = module.health_check()
        for name, module in vars(self.cortex).items():
            if module and hasattr(module, "health_check"):
                modules[f"cortex.{name}"] = module.health_check()

        any_error = any(not m["available"] for m in modules.values())
        return {
            "core_status": self.status,
            "overall": "healthy" if not any_error else "degraded",
            "modules": modules,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    def status_report(self) -> Dict[str, Any]:
        """
        Full operational status report.

        Returns:
            Status report dict.
        """
        return {
            "core_status": self.status,
            "memory_modules": [k for k in vars(self.memory).keys() if not k.startswith("_")],
            "cortex_modules": [k for k in vars(self.cortex).keys() if not k.startswith("_")],
            "pending_findings": len(self._findings),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    # ------------------------------------------------------------------
    # Finding system
    # ------------------------------------------------------------------
    def receive_finding(self, finding: Dict[str, Any]) -> None:
        """
        Receive a finding from any module.

        Args:
            finding: Dict with finding data.
        """
        with self._findings_lock:
            finding["received_at"] = datetime.now(timezone.utc).isoformat()
            self._findings.append(finding)
            logger.info(f"Finding received: {finding.get('action', 'unknown')}")

    def get_findings(self, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Retrieve recent findings.

        Args:
            limit: Maximum findings to return.

        Returns:
            List of finding dicts.
        """
        with self._findings_lock:
            return self._findings[-limit:]

    def clear_findings(self) -> None:
        """Clear all pending findings."""
        with self._findings_lock:
            self._findings.clear()

    # ------------------------------------------------------------------
    # High-level operations
    # ------------------------------------------------------------------
    def execute_mission(
        self,
        goal: str,
        agent_name: str = "default",
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Execute a complete mission from planning to archival.

        This is the primary high-level API for mission execution.

        Args:
            goal: Mission goal string.
            agent_name: Agent to assign.
            context: Optional mission context.

        Returns:
            Complete mission result dict.
        """
        start = time.perf_counter()
        mission_id = f"mission_{int(time.time() * 1000)}"
        ctx = context or {}

        logger.info(f"Executing mission {mission_id}: {goal}")

        # 1. Create plan
        plan_result = self.cortex.planner.create_plan(goal, ctx)
        if not plan_result["success"]:
            return self._mission_result(mission_id, False, "planning_failed", plan_result, start)
        plan = plan_result["data"]

        # 2. Select strategy
        task = {"type": plan["tasks"][0]["type"] if plan["tasks"] else "general", "description": goal}
        strategy = self.cortex.strategist.select_approach(
            task, [agent_name], ctx
        )

        # 3. Assess risks for each task
        risks = []
        for task in plan["tasks"]:
            risk = self.cortex.risk_assessor.assess_action(
                task.get("type", "unknown"),
                ctx.get("target", "unknown"),
                ctx,
            )
            risks.append(risk)
            if risk["data"]["risk_score"] > 0.7:
                task["requires_approval"] = True
                task["mitigations"] = risk["data"]["mitigations"]

        # 4. Optimize resources
        optimized = self.cortex.resource_optimizer.optimize_for_budget(
            plan, ctx.get("budget", {})
        )

        # 5. Predict success
        prediction = self.memory.learning_engine.predict_success_probability(plan)

        # 6. Simulate execution (placeholder for actual execution)
        execution_result = self._simulate_execution(plan, ctx)

        # 7. Record outcomes
        self.cortex.meta_learner.record_outcome(plan, execution_result)
        self.memory.mission_archive.archive_mission({
            "id": mission_id,
            "agent_name": agent_name,
            "mission_type": plan["tasks"][0]["type"] if plan["tasks"] else "general",
            "description": goal,
            "tasks": plan["tasks"],
            "outcomes": execution_result,
            "timeline": [
                {"timestamp": datetime.now(timezone.utc).isoformat(), "event": "mission_completed"}
            ],
            "metadata": {
                "strategy": strategy.get("data", {}),
                "risks": [r.get("data", {}) for r in risks],
                "prediction": prediction.get("data", 0.5),
            },
        })
        self.memory.agent_memory.record_mission(
            agent_name, mission_id, plan["tasks"], execution_result,
            execution_result.get("duration_ms", 0),
        )

        # 8. Update beliefs
        self.memory.learning_engine.update_beliefs({
            f"mission_{mission_id}_success": 1.0 if execution_result["success"] else 0.0,
        })

        duration_ms = int((time.perf_counter() - start) * 1000)
        return self._mission_result(
            mission_id, execution_result["success"], "completed",
            {
                "plan": plan,
                "strategy": strategy.get("data", {}),
                "risks": [r.get("data", {}) for r in risks],
                "prediction": prediction.get("data", 0.5),
                "execution": execution_result,
            },
            start,
        )

    def _simulate_execution(
        self,
        plan: Dict[str, Any],
        context: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Simulate mission execution (replace with real execution)."""
        total_duration = sum(t.get("estimated_ms", 0) for t in plan.get("tasks", []))
        # Simulate some failures based on risk
        import random
        success = random.random() > 0.1  # 90% success rate for simulation
        return {
            "success": success,
            "duration_ms": total_duration,
            "errors": [] if success else ["simulated_failure"],
            "warnings": [],
            "outputs": {},
        }

    def _mission_result(
        self,
        mission_id: str,
        success: bool,
        status: str,
        data: Any,
        start_time: float,
    ) -> Dict[str, Any]:
        """Build standardized mission result."""
        return {
            "success": success,
            "mission_id": mission_id,
            "status": status,
            "data": data,
            "duration_ms": int((time.perf_counter() - start_time) * 1000),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    def query_knowledge(self, subject: Optional[str] = None, predicate: Optional[str] = None) -> Dict[str, Any]:
        """
        Query the knowledge graph.

        Args:
            subject: Filter by subject.
            predicate: Filter by predicate.

        Returns:
            Query results.
        """
        return self.memory.knowledge_graph.query(subject=subject, predicate=predicate)

    def add_knowledge(self, subject: str, predicate: str, object: str, confidence: float = 1.0) -> Dict[str, Any]:
        """
        Add a fact to the knowledge graph.

        Args:
            subject: Subject entity.
            predicate: Relationship.
            object: Object entity.
            confidence: Confidence 0.0-1.0.

        Returns:
            Result with fact_id.
        """
        return self.memory.knowledge_graph.add_fact(subject, predicate, object, confidence)

    def search_memory(self, query: str, top_k: int = 10) -> Dict[str, Any]:
        """
        Semantic search across all indexed memory.

        Args:
            query: Search query.
            top_k: Number of results.

        Returns:
            Search results.
        """
        return self.memory.semantic_search.search(query, top_k=top_k)

    def get_agent_performance(self, agent_name: str) -> Dict[str, Any]:
        """
        Get performance metrics for an agent.

        Args:
            agent_name: Agent name.

        Returns:
            Performance dict.
        """
        return self.memory.agent_memory.get_agent_performance(agent_name)

    def suggest_improvements(self) -> Dict[str, Any]:
        """
        Get reasoning improvement suggestions.

        Returns:
            Improvement suggestions.
        """
        return self.cortex.meta_learner.suggest_reasoning_improvements()


class MemoryHub:
    """Container for all memory subsystems."""

    def __init__(
        self,
        agent_memory: AgentMemory,
        knowledge_graph: KnowledgeGraph,
        skill_memory: SkillMemory,
        mission_archive: MissionArchive,
        semantic_search: SemanticSearch,
        learning_engine: Optional[LearningEngine] = None,
    ) -> None:
        self.agent_memory = agent_memory
        self.knowledge_graph = knowledge_graph
        self.skill_memory = skill_memory
        self.mission_archive = mission_archive
        self.semantic_search = semantic_search
        self.learning_engine = learning_engine


class CortexHub:
    """Container for all cortex reasoning modules."""

    def __init__(
        self,
        planner: Planner,
        strategist: Strategist,
        risk_assessor: RiskAssessor,
        resource_optimizer: ResourceOptimizer,
        hypothesis_tester: HypothesisTester,
        meta_learner: MetaLearner,
    ) -> None:
        self.planner = planner
        self.strategist = strategist
        self.risk_assessor = risk_assessor
        self.resource_optimizer = resource_optimizer
        self.hypothesis_tester = hypothesis_tester
        self.meta_learner = meta_learner


# ------------------------------------------------------------------
# Usage example
# ------------------------------------------------------------------
if __name__ == "__main__":
    iris = IRISCore()
    boot = iris.boot()
    print(json.dumps(boot, indent=2))

    # Add some knowledge
    iris.add_knowledge("IRIS", "is_a", "AI_system", 1.0)
    iris.add_knowledge("IRIS", "has_capability", "reasoning", 0.95)

    # Execute a mission
    result = iris.execute_mission("Scan network perimeter", agent_name="Alpha")
    print(json.dumps(result, indent=2))

    # Check health
    print(json.dumps(iris.health_check(), indent=2))

    iris.shutdown()

```

---

# 8. REQUIREMENTS

```
# IRIS v7.0 — Memory & Cortex System Dependencies
# Core (always required)
numpy>=1.24.0

# Semantic search embeddings (optional — falls back to TF-IDF if unavailable)
sentence-transformers>=2.2.0

# For production deployments
# uvloop>=0.17.0  # Faster event loop (optional)
# aiosqlite>=0.19.0  # Async SQLite (optional)

```

---

# 9. GRACEFUL DEGRADATION

| If this fails... | System falls back to... |
|-------------------|------------------------|
| `sentence-transformers` not installed | TF-IDF + cosine similarity for embeddings |
| SQLite unavailable | JSON file storage per module |
| Model download fails | Pre-computed hash-based vectors |
| Disk full | In-memory operation (data lost on restart) |

---

# 10. TESTING

Each module includes a `__main__` block with usage examples. Run individually:

```bash
python -m iris_v7.memory.agent_memory
python -m iris_v7.cortex.planner
```

For unit tests, stub each module's dependencies and verify:
1. Standard result envelope format
2. SQLite persistence (or JSON fallback)
3. Thread safety
4. Graceful degradation paths

---

# VERSION

**IRIS v7.0.0** — Cognitive Layer

Built for the most powerful autonomous intelligence in history.

IRIS must remember. IRIS must think. IRIS must learn.
IRIS must be unstoppable.
