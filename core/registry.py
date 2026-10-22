"""
Aevibron Agent Corps — Agent Registry
Agent discovery, registration, health monitoring, and lifecycle management.

Author: IRIS v1.0
"""

import importlib
import inspect
import logging
import os
import pkgutil
import sys
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Type

from .base_agent import BaseAgent, AgentStatus


class AgentRegistry:
    """
    AgentRegistry — The roster and heartbeat monitor of the Aevibron Agent Corps.

    Manages the lifecycle of all agents:
    - Auto-discovery of agents from domain modules
    - Registration and deregistration
    - Health monitoring with periodic checks
    - Load balancing information
    - Agent metadata and capability indexing

    Attributes:
        _agents (dict): Mapping of agent_name -> agent_instance.
        _agent_classes (dict): Mapping of agent_name -> agent_class.
        _domain_index (dict): Mapping of domain -> list of agent names.
        _capability_index (dict): Mapping of capability -> list of agent names.
        _lock (threading.RLock): Thread-safe lock.
        _logger (logging.Logger): Logger instance.
        _health_check_interval (int): Seconds between health checks.
        _health_thread (threading.Thread): Background health monitor thread.
        _shutdown (bool): Flag to stop health monitoring.
    """

    def __init__(self, health_check_interval: int = 30):
        self._agents: Dict[str, BaseAgent] = {}
        self._agent_classes: Dict[str, Type[BaseAgent]] = {}
        self._domain_index: Dict[str, List[str]] = {}
        self._capability_index: Dict[str, List[str]] = {}
        self._health_history: Dict[str, List[Dict[str, Any]]] = {}
        self._lock = threading.RLock()
        self._logger = logging.getLogger("Aevibron.Registry")
        self._logger.setLevel(logging.DEBUG)

        if not self._logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                "%(asctime)s | %(name)s | %(levelname)s | %(message)s"
            )
            handler.setFormatter(formatter)
            self._logger.addHandler(handler)

        self._health_check_interval = health_check_interval
        self._shutdown = False
        self._health_thread = threading.Thread(target=self._health_monitor_loop, daemon=True)
        self._health_thread.start()

        self._logger.info("[Registry] Agent registry initialized. Health monitoring active.")

    def register(self, agent: BaseAgent) -> bool:
        """
        Register an agent instance.

        Args:
            agent: The agent instance to register.

        Returns:
            bool: True if registration succeeded.
        """
        try:
            with self._lock:
                self._agents[agent.name] = agent

                # Update domain index
                if agent.domain not in self._domain_index:
                    self._domain_index[agent.domain] = []
                if agent.name not in self._domain_index[agent.domain]:
                    self._domain_index[agent.domain].append(agent.name)

                # Update capability index
                for capability in agent.capabilities:
                    if capability not in self._capability_index:
                        self._capability_index[capability] = []
                    if agent.name not in self._capability_index[capability]:
                        self._capability_index[capability].append(agent.name)

                # Initialize health history
                self._health_history[agent.name] = []

            self._logger.info(f"[Registry] Agent {agent.name} registered in domain {agent.domain}.")
            return True

        except Exception as e:
            self._logger.error(f"[Registry] Failed to register {agent.name}: {e}")
            return False

    def unregister(self, agent_name: str) -> bool:
        """
        Unregister an agent.

        Args:
            agent_name: The codename of the agent to remove.

        Returns:
            bool: True if unregistered successfully.
        """
        with self._lock:
            if agent_name not in self._agents:
                return False

            agent = self._agents[agent_name]

            # Remove from domain index
            if agent.domain in self._domain_index:
                self._domain_index[agent.domain] = [
                    n for n in self._domain_index[agent.domain] if n != agent_name
                ]

            # Remove from capability index
            for capability in agent.capabilities:
                if capability in self._capability_index:
                    self._capability_index[capability] = [
                        n for n in self._capability_index[capability] if n != agent_name
                    ]

            # Remove agent
            del self._agents[agent_name]
            if agent_name in self._health_history:
                del self._health_history[agent_name]

        self._logger.info(f"[Registry] Agent {agent_name} unregistered.")
        return True

    def discover(self, domains_path: Optional[str] = None) -> List[str]:
        """
        Auto-discover agents from domain modules.

        Scans the domains/ directory for agent classes inheriting from BaseAgent
        and registers them.

        Args:
            domains_path: Path to the domains directory. Defaults to adjacent to this file.

        Returns:
            List[str]: Names of discovered agents.
        """
        discovered = []

        try:
            if domains_path is None:
                domains_path = os.path.join(os.path.dirname(__file__), "domains")

            if not os.path.exists(domains_path):
                self._logger.warning(f"[Registry] Domains path not found: {domains_path}")
                return discovered

            # Add domains path to sys.path if needed
            parent_dir = os.path.dirname(domains_path)
            if parent_dir not in sys.path:
                sys.path.insert(0, parent_dir)

            # Walk through domain packages
            for domain_dir in os.listdir(domains_path):
                domain_path = os.path.join(domains_path, domain_dir)
                if not os.path.isdir(domain_path) or domain_dir.startswith("__"):
                    continue

                module_name = f"domains.{domain_dir}"

                try:
                    # Import the domain package
                    domain_module = importlib.import_module(module_name)

                    # Find all modules in the domain
                    for _, module_file, _ in pkgutil.iter_modules([domain_path]):
                        if module_file.startswith("__"):
                            continue

                        full_module_name = f"{module_name}.{module_file}"

                        try:
                            agent_module = importlib.import_module(full_module_name)

                            # Find BaseAgent subclasses
                            for name, obj in inspect.getmembers(agent_module):
                                if (inspect.isclass(obj) and 
                                    issubclass(obj, BaseAgent) and 
                                    obj is not BaseAgent and
                                    not inspect.isabstract(obj)):

                                    self._agent_classes[name] = obj
                                    discovered.append(name)
                                    self._logger.info(f"[Registry] Discovered agent class: {name} in {full_module_name}")

                        except Exception as e:
                            self._logger.warning(f"[Registry] Could not import {full_module_name}: {e}")

                except Exception as e:
                    self._logger.warning(f"[Registry] Could not import domain {module_name}: {e}")

            self._logger.info(f"[Registry] Discovery complete. Found {len(discovered)} agent classes.")
            return discovered

        except Exception as e:
            self._logger.error(f"[Registry] Discovery failed: {e}", exc_info=True)
            return discovered

    def instantiate(self, agent_name: str, **kwargs) -> Optional[BaseAgent]:
        """
        Instantiate a discovered agent class.

        Args:
            agent_name: The class name of the agent.
            **kwargs: Arguments to pass to the agent constructor.

        Returns:
            BaseAgent: The instantiated agent, or None if not found.
        """
        if agent_name not in self._agent_classes:
            self._logger.error(f"[Registry] Agent class {agent_name} not found. Run discover() first.")
            return None

        try:
            agent_class = self._agent_classes[agent_name]
            agent = agent_class(**kwargs)
            self.register(agent)
            return agent

        except Exception as e:
            self._logger.error(f"[Registry] Failed to instantiate {agent_name}: {e}", exc_info=True)
            return None

    def get_by_name(self, agent_name: str) -> Optional[BaseAgent]:
        """
        Get an agent by its codename.

        Args:
            agent_name: The agent's codename.

        Returns:
            BaseAgent: The agent instance, or None if not found.
        """
        with self._lock:
            return self._agents.get(agent_name)

    def get_by_domain(self, domain: str) -> List[BaseAgent]:
        """
        Get all agents in a domain.

        Args:
            domain: The domain name.

        Returns:
            List[BaseAgent]: Agents in the domain.
        """
        with self._lock:
            names = self._domain_index.get(domain, [])
            return [self._agents[name] for name in names if name in self._agents]

    def get_by_capability(self, capability: str) -> List[BaseAgent]:
        """
        Get all agents with a specific capability.

        Args:
            capability: The capability to search for.

        Returns:
            List[BaseAgent]: Agents with the capability.
        """
        with self._lock:
            names = self._capability_index.get(capability, [])
            return [self._agents[name] for name in names if name in self._agents]

    def get_available(self) -> List[BaseAgent]:
        """
        Get all idle agents.

        Returns:
            List[BaseAgent]: Agents with IDLE status.
        """
        with self._lock:
            return [
                agent for agent in self._agents.values()
                if agent.status == AgentStatus.IDLE
            ]

    def get_all(self) -> List[BaseAgent]:
        """
        Get all registered agents.

        Returns:
            List[BaseAgent]: All registered agents.
        """
        with self._lock:
            return list(self._agents.values())

    def health_check_all(self) -> Dict[str, Dict[str, Any]]:
        """
        Run health checks on all registered agents.

        Returns:
            Dict: Mapping of agent_name -> health status.
        """
        results = {}

        with self._lock:
            agents_snapshot = list(self._agents.items())

        for name, agent in agents_snapshot:
            try:
                health = agent.health_check()
                results[name] = health

                with self._lock:
                    if name not in self._health_history:
                        self._health_history[name] = []
                    self._health_history[name].append(health)
                    # Keep last 100 entries
                    if len(self._health_history[name]) > 100:
                        self._health_history[name] = self._health_history[name][-100:]

            except Exception as e:
                self._logger.error(f"[Registry] Health check failed for {name}: {e}")
                results[name] = {
                    "agent_name": name,
                    "status": "error",
                    "error": str(e),
                    "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                }

        return results

    def get_health_history(self, agent_name: str, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get health check history for an agent.

        Args:
            agent_name: The agent's codename.
            limit: Maximum number of history entries.

        Returns:
            List[Dict]: Health check history.
        """
        with self._lock:
            history = self._health_history.get(agent_name, [])
            return history[-limit:]

    def _health_monitor_loop(self) -> None:
        """Background thread for periodic health monitoring."""
        while not self._shutdown:
            try:
                time.sleep(self._health_check_interval)
                if not self._shutdown:
                    self.health_check_all()
            except Exception as e:
                self._logger.error(f"[Registry] Health monitor error: {e}")

    def shutdown(self) -> None:
        """Shutdown the registry and stop health monitoring."""
        self._shutdown = True
        self._logger.info("[Registry] Registry shutdown initiated.")

    def get_stats(self) -> Dict[str, Any]:
        """
        Get registry statistics.

        Returns:
            Dict: Statistics about registered agents.
        """
        with self._lock:
            status_counts = {}
            for agent in self._agents.values():
                status = agent.status.value
                status_counts[status] = status_counts.get(status, 0) + 1

            return {
                "total_agents": len(self._agents),
                "domains": list(self._domain_index.keys()),
                "capabilities": list(self._capability_index.keys()),
                "status_breakdown": status_counts,
                "available_agents": len(self.get_available()),
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            }

    def find_best_agent(self, task_description: str, domain: Optional[str] = None) -> Optional[BaseAgent]:
        """
        Find the best agent for a task based on capability matching and current load.

        Args:
            task_description: Description of the task.
            domain: Optional domain constraint.

        Returns:
            BaseAgent: The best matching idle agent, or None.
        """
        candidates = []

        with self._lock:
            if domain:
                agents = self.get_by_domain(domain)
            else:
                agents = list(self._agents.values())

            for agent in agents:
                if agent.status != AgentStatus.IDLE:
                    continue

                confidence = agent.can_handle(task_description)
                if confidence > 0:
                    # Factor in load - prefer less loaded agents
                    score = confidence * (1 - agent.load * 0.5)
                    candidates.append((score, agent))

        if candidates:
            candidates.sort(key=lambda x: x[0], reverse=True)
            best = candidates[0][1]
            self._logger.info(f"[Registry] Best agent for task: {best.name} (score={candidates[0][0]:.2f})")
            return best

        return None


__all__ = ["AgentRegistry"]


# Usage Example:
# registry = AgentRegistry()
# registry.discover()
# agent = registry.instantiate("VAULT")
# all_agents = registry.get_all()
# health = registry.health_check_all()
