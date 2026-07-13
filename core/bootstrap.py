#!/usr/bin/env python3
"""
core/bootstrap.py — IRIS v1.0 Bootstrap
Registers all 29 agents into the AgentRegistry, wires MessageBus,
SharedMemory, and TaskQueue. Provides a single entry point to bring
the entire Aevibron Agent Corps online.
"""

import sys
import os

# Ensure paths
_BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _BASE)
sys.path.insert(0, os.path.join(_BASE, "agents"))
sys.path.insert(0, os.path.join(_BASE, "core"))

from typing import Dict, List, Any, Optional
import logging

# Core infrastructure
from base_agent import BaseAgent, Task, TaskResult, AgentStatus, TaskPriority
from registry import AgentRegistry
from communication import MessageBus
from shared_memory import SharedMemory
from task_queue import TaskQueue
from commander import Commander

# Agent wrappers
from agent_wrappers import (
    VAULT, SCRIPT, PROBE, PIPE,
    SHADOW, SCAR, CRIMSON, AEGIS, SCALE, TRACE, OMEN,
    NEBULA, SHELL, WEB, CORE,
    CRUCIBLE, SAGE, QUILL, HERALD, CANVAS, ECHO, GEAR,
    PORTAL, ARCHIVE, GUARD, CHAIN, QBIT, TENSOR, PIXEL,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
)
logger = logging.getLogger("IRIS.Bootstrap")


# Mapping of codename -> wrapper class
AGENT_REGISTRY_MAP: Dict[str, type] = {
    "VAULT": VAULT,
    "SCRIPT": SCRIPT,
    "PROBE": PROBE,
    "PIPE": PIPE,
    "SHADOW": SHADOW,
    "SCAR": SCAR,
    "CRIMSON": CRIMSON,
    "AEGIS": AEGIS,
    "SCALE": SCALE,
    "TRACE": TRACE,
    "OMEN": OMEN,
    "NEBULA": NEBULA,
    "SHELL": SHELL,
    "WEB": WEB,
    "CORE": CORE,
    "CRUCIBLE": CRUCIBLE,
    "SAGE": SAGE,
    "QUILL": QUILL,
    "HERALD": HERALD,
    "CANVAS": CANVAS,
    "ECHO": ECHO,
    "GEAR": GEAR,
    "PORTAL": PORTAL,
    "ARCHIVE": ARCHIVE,
    "GUARD": GUARD,
    "CHAIN": CHAIN,
    "QBIT": QBIT,
    "TENSOR": TENSOR,
    "PIXEL": PIXEL,
}


def create_infrastructure(
    data_dir: str = "/mnt/agents/output/iris_v7/data",
) -> tuple:
    """Create and return all core infrastructure components."""
    os.makedirs(data_dir, exist_ok=True)

    message_bus = MessageBus(persistence_path=os.path.join(data_dir, "message_bus.json"))
    shared_memory = SharedMemory(persistence_path=os.path.join(data_dir, "shared_memory.json"))
    task_queue = TaskQueue(persistence_path=os.path.join(data_dir, "task_queue.json"))
    registry = AgentRegistry(health_check_interval=30)

    # Try to load persisted state
    message_bus.load()
    shared_memory.load()
    task_queue.load()

    return registry, message_bus, shared_memory, task_queue


def register_agents(
    registry: AgentRegistry,
    message_bus: MessageBus,
    shared_memory: SharedMemory,
    commander: Optional[Any] = None,
) -> Dict[str, BaseAgent]:
    """Instantiate and register all 29 agents into the registry."""
    agents: Dict[str, BaseAgent] = {}

    for codename, agent_class in AGENT_REGISTRY_MAP.items():
        try:
            agent = agent_class()

            # Wire infrastructure
            agent.set_message_bus(message_bus)
            if commander:
                agent.set_commander(commander)

            # Wire native agent's bus/memory references
            if hasattr(agent, "_native"):
                agent._native._commander_bus = message_bus
                agent._native._shared_memory = shared_memory

            registry.register(agent)
            agents[codename] = agent
            logger.info(f"[Bootstrap] Registered {codename} ({agent.domain})")

        except Exception as e:
            logger.error(f"[Bootstrap] Failed to register {codename}: {e}", exc_info=True)

    logger.info(f"[Bootstrap] Total agents registered: {len(agents)}/29")
    return agents


def bootstrap_all(
    data_dir: str = "/mnt/agents/output/iris_v7/data",
    max_workers: int = 10,
) -> Commander:
    """
    Full bootstrap: create infrastructure, register all agents, return Commander.

    Usage:
        commander = bootstrap_all()
        report = commander.execute_mission("Scan example.com for vulnerabilities")
        print(report)
    """
    logger.info("=" * 60)
    logger.info("  AEVIBRON AGENT CORPS — IRIS v1.0 BOOTSTRAP")
    logger.info("=" * 60)

    registry, message_bus, shared_memory, task_queue = create_infrastructure(data_dir)

    # Create Commander (agents will be wired after Commander exists)
    commander = Commander(
        registry=registry,
        message_bus=message_bus,
        shared_memory=shared_memory,
        task_queue=task_queue,
        max_workers=max_workers,
    )

    # Register all agents with Commander reference
    agents = register_agents(registry, message_bus, shared_memory, commander)

    # Subscribe all agents to the message bus for inter-agent comms
    for codename, agent in agents.items():
        def make_handler(a):
            def handler(msg):
                a._logger.debug(f"[{a.name}] Received bus message: {msg.get('type', 'unknown')}")
            return handler
        message_bus.subscribe(codename, make_handler(agent))

    # Store agent roster in shared memory
    roster = {
        "agents": [
            {"name": a.name, "domain": a.domain, "status": a.status.value, "capabilities": a.capabilities}
            for a in agents.values()
        ],
        "total": len(agents),
        "bootstrapped_at": __import__("time").strftime("%Y-%m-%dT%H:%M:%SZ", __import__("time").gmtime()),
    }
    shared_memory.store("_roster", roster, mission_id="global", agent_name="IRIS", tags=["bootstrap", "meta"])

    logger.info("=" * 60)
    logger.info(f"  ALL SYSTEMS ONLINE — {len(agents)} AGENTS DEPLOYED")
    logger.info("=" * 60)

    return commander


def shutdown(commander: Commander) -> None:
    """Graceful shutdown of the entire system."""
    logger.info("[Bootstrap] Initiating system shutdown...")
    commander.shutdown()
    logger.info("[Bootstrap] Aevibron Agent Corps offline.")


if __name__ == "__main__":
    commander = bootstrap_all()
    print("\n--- Agent Registry Status ---")
    print(commander.registry.get_stats())
    print("\n--- Shared Memory Stats ---")
    print(commander.shared_memory.get_stats())
    print("\n--- Message Bus Stats ---")
    print(commander.message_bus.get_stats())
    print("\n--- Task Queue Stats ---")
    print(commander.task_queue.get_stats())
    print("\nIRIS v1.0 is online. Ready for missions.")
