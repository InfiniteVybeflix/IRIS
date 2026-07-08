"""
tests/test_growth_tracker.py — Unit tests for GrowthTracker
"""

import unittest
import sys
import os
import tempfile
import shutil

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from persona.growth_tracker import GrowthTracker


class TestGrowthTracker(unittest.TestCase):
    """Test suite for GrowthTracker class."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, "test_growth.db")
        self.growth = GrowthTracker(db_path=self.db_path)

    def tearDown(self):
        """Clean up."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_record_mission_success(self):
        """Test recording successful mission."""
        result = self.growth.record_mission_outcome("test_mission", True)
        self.assertTrue(result)
        self.assertEqual(self.growth.missions_completed, 1)

    def test_record_mission_failure(self):
        """Test recording failed mission."""
        result = self.growth.record_mission_outcome("test_mission", False)
        self.assertTrue(result)
        self.assertEqual(self.growth.missions_failed, 1)

    def test_learn_skill(self):
        """Test learning a new skill."""
        result = self.growth.learn_skill("Python", "test")
        self.assertTrue(result)
        self.assertIn("Python", self.growth.skills_learned)

    def test_learn_duplicate_skill(self):
        """Test learning duplicate skill returns False."""
        self.growth.learn_skill("Python", "test")
        result = self.growth.learn_skill("Python", "test")
        self.assertFalse(result)

    def test_record_lesson(self):
        """Test recording a lesson."""
        result = self.growth.record_lesson("Always test first", "test_mission")
        self.assertTrue(result)
        self.assertEqual(len(self.growth.lessons_learned), 1)

    def test_record_duplicate_lesson(self):
        """Test duplicate lesson is skipped."""
        self.growth.record_lesson("Always test first", "test")
        result = self.growth.record_lesson("Always test first", "test")
        self.assertFalse(result)

    def test_get_growth_report(self):
        """Test growth report."""
        self.growth.record_mission_outcome("m1", True)
        report = self.growth.get_growth_report()
        self.assertIn("missions_completed", report)
        self.assertIn("success_rate", report)

    def test_get_milestone_status(self):
        """Test milestone status."""
        status = self.growth.get_milestone_status()
        self.assertIn("missions", status)
        self.assertIn("skills", status)
        self.assertIn("lessons", status)

    def test_set_milestone(self):
        """Test setting milestone."""
        result = self.growth.set_milestone("missions", 50)
        self.assertTrue(result)

    def test_get_skills(self):
        """Test getting skills."""
        self.growth.learn_skill("Test Skill", "test")
        skills = self.growth.get_skills()
        self.assertIn("Test Skill", skills)

    def test_get_lessons(self):
        """Test getting lessons."""
        self.growth.record_lesson("Test Lesson", "test")
        lessons = self.growth.get_lessons()
        self.assertEqual(len(lessons), 1)

    def test_health_check(self):
        """Test health check."""
        health = self.growth.health_check()
        self.assertIn("missions_completed", health)


if __name__ == "__main__":
    unittest.main()
