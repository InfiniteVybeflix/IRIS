"""
tests/test_dream_engine.py — Unit tests for DreamEngine
"""

import unittest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from persona.dream_engine import DreamEngine


class TestDreamEngine(unittest.TestCase):
    """Test suite for DreamEngine class."""

    def setUp(self):
        """Set up test fixtures."""
        self.dream = DreamEngine()

    def test_sleep(self):
        """Test entering dream state."""
        result = self.dream.sleep()
        self.assertTrue(result)
        self.assertTrue(self.dream.is_sleeping)

    def test_wake(self):
        """Test waking from dream state."""
        self.dream.sleep()
        result = self.dream.wake()
        self.assertTrue(result)
        self.assertFalse(self.dream.is_sleeping)

    def test_consolidate_memories_while_awake(self):
        """Test memory consolidation rejected while awake."""
        result = self.dream.consolidate_memories()
        self.assertFalse(result)

    def test_generate_insights_while_awake(self):
        """Test insight generation rejected while awake."""
        result = self.dream.generate_insights()
        self.assertEqual(len(result), 0)

    def test_generate_insights_while_sleeping(self):
        """Test insight generation during sleep."""
        self.dream.sleep()
        insights = self.dream.generate_insights()
        self.assertTrue(len(insights) > 0)

    def test_practice_scenarios_while_sleeping(self):
        """Test scenario practice during sleep."""
        self.dream.sleep()
        scenarios = self.dream.practice_scenarios()
        self.assertTrue(len(scenarios) > 0)

    def test_optimize_self_while_sleeping(self):
        """Test self-optimization during sleep."""
        self.dream.sleep()
        result = self.dream.optimize_self()
        self.assertTrue(result)

    def test_get_dream_report(self):
        """Test dream report."""
        self.dream.sleep()
        self.dream.wake()
        report = self.dream.get_dream_report()
        self.assertIn("insights_generated", report)
        self.assertIn("scenarios_practiced", report)

    def test_health_check(self):
        """Test health check."""
        health = self.dream.health_check()
        self.assertIn("is_sleeping", health)


if __name__ == "__main__":
    unittest.main()
