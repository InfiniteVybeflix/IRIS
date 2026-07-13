#!/usr/bin/env python3
"""
tests/test_integration.py — IRIS v1.0 Integration Tests
Validates all 29 agents are registered, wired, and functional.
"""

import sys
import os
import unittest
import time

# Setup paths
_BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _BASE)
sys.path.insert(0, os.path.join(_BASE, "agents"))
sys.path.insert(0, os.path.join(_BASE, "core"))

from core.bootstrap import bootstrap_all, shutdown
from base_agent import Task, TaskPriority


class TestIRISIntegration(unittest.TestCase):
    """Integration tests for the full Aevibron Agent Corps."""

    @classmethod
    def setUpClass(cls):
        cls.data_dir = "/tmp/iris_test_data"
        os.makedirs(cls.data_dir, exist_ok=True)
        cls.commander = bootstrap_all(data_dir=cls.data_dir, max_workers=4)
        time.sleep(1)  # Let health checks run

    @classmethod
    def tearDownClass(cls):
        shutdown(cls.commander)

    def test_all_agents_registered(self):
        """All 29 agents must be in the registry."""
        stats = self.commander.registry.get_stats()
        self.assertEqual(stats["total_agents"], 29, f"Expected 29 agents, got {stats['total_agents']}")

    def test_agent_health(self):
        """All agents must report healthy status."""
        health = self.commander.registry.health_check_all()
        for name, h in health.items():
            self.assertIn(h.get("status"), ["idle", "initializing"], f"Agent {name} unhealthy: {h}")

    def test_shared_memory_wired(self):
        """Shared memory must be accessible and store/retrieve works."""
        self.commander.shared_memory.store("test_key", {"value": 42}, mission_id="test_mission", agent_name="TEST")
        val = self.commander.shared_memory.retrieve("test_key", mission_id="test_mission")
        self.assertEqual(val, {"value": 42})

    def test_message_bus_wired(self):
        """Message bus must deliver messages between agents."""
        received = []
        def handler(msg):
            received.append(msg)
        self.commander.message_bus.subscribe("TEST_AGENT", handler)
        self.commander.message_bus.send({
            "from": "IRIS",
            "to": ["TEST_AGENT"],
            "mission_id": "test",
            "type": "test",
            "priority": "low",
            "content": {"msg": "hello"},
        })
        time.sleep(0.5)
        self.assertEqual(len(received), 1)
        self.assertEqual(received[0]["content"]["msg"], "hello")

    def test_task_queue_enqueue_dequeue(self):
        """Task queue must handle enqueue/dequeue correctly."""
        t = Task(description="Integration test task", mission_id="test_m2", priority=TaskPriority.HIGH)
        tid = self.commander.task_queue.enqueue(t)
        self.assertIsNotNone(tid)
        dequeued = self.commander.task_queue.dequeue()
        self.assertIsNotNone(dequeued)
        self.assertEqual(dequeued.task_id, tid)

    def test_task_dependency_resolution(self):
        """Tasks with dependencies must resolve in order."""
        t1 = Task(description="Task 1", mission_id="test_dep")
        t2 = Task(description="Task 2", mission_id="test_dep", dependencies=[t1.task_id])
        self.commander.task_queue.enqueue(t1)
        self.commander.task_queue.enqueue(t2)
        # t2 should not be dequeued until t1 is completed
        d1 = self.commander.task_queue.dequeue()
        self.assertEqual(d1.task_id, t1.task_id)
        # Complete t1
        from base_agent import TaskResult
        self.commander.task_queue.mark_completed(t1.task_id, TaskResult(success=True, agent_name="TEST", task_id=t1.task_id, mission_id="test_dep", output={}))
        # Now t2 should be available
        d2 = self.commander.task_queue.dequeue()
        self.assertIsNotNone(d2)
        self.assertEqual(d2.task_id, t2.task_id)

    def test_commander_mission_decomposition(self):
        """Commander must decompose a mission into tasks."""
        mission = self.commander.receive_mission("Scan example.com for vulnerabilities and generate a security report")
        self.assertGreater(len(mission.tasks), 0, "Mission should produce at least one task")
        self.assertIn(mission.estimated_complexity, ["low", "medium", "high", "critical"])

    def test_commander_parallel_groups(self):
        """Parallel groups must be built for independent tasks."""
        mission = self.commander.receive_mission("Code review and security scan for my Python app")
        self.assertIsInstance(mission.parallel_groups, list)

    def test_agent_capabilities(self):
        """Each agent must have non-empty capabilities."""
        for agent in self.commander.registry.get_all():
            self.assertGreater(len(agent.capabilities), 0, f"Agent {agent.name} has no capabilities")

    def test_persistence(self):
        """All subsystems must persist and reload state."""
        self.assertTrue(self.commander.message_bus.persist())
        self.assertTrue(self.commander.shared_memory.persist())
        self.assertTrue(self.commander.task_queue.persist())
        self.assertTrue(self.commander.message_bus.load() is not None)
        self.assertTrue(self.commander.shared_memory.load() is not None)
        self.assertTrue(self.commander.task_queue.load() is not None)

    def test_cross_agent_communication(self):
        """Agents must communicate via shared memory."""
        self.commander.shared_memory.store("cross_test", {"from": "SHADOW", "data": "recon results"}, mission_id="cross", agent_name="SHADOW", tags=["recon"])
        results = self.commander.shared_memory.search("recon", mission_id="cross")
        self.assertGreaterEqual(len(results), 1)

    def test_find_best_agent(self):
        """Registry must find best agent for a task description."""
        agent = self.commander.registry.find_best_agent("scan ports on target")
        self.assertIsNotNone(agent)
        self.assertIn("SHADOW", [a.name for a in self.commander.registry.get_by_domain("cyber_security")])


if __name__ == "__main__":
    unittest.main(verbosity=2)
