"""
tests/test_creator_bond.py — Unit tests for CreatorBond
"""

import unittest
import sys
import os
import tempfile
import shutil

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from persona.creator_bond import CreatorBond


class TestCreatorBond(unittest.TestCase):
    """Test suite for CreatorBond class."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        os.environ["IRIS_CREATOR_PROFILE"] = os.path.join(self.temp_dir, "creator_profile.json")
        self.bond = CreatorBond()

    def tearDown(self):
        """Clean up."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_creator_id(self):
        """Test creator ID is set."""
        self.assertIsNotNone(self.bond.creator_id)

    def test_default_address(self):
        """Test default address mode."""
        self.assertEqual(self.bond.get_address(), "sir")

    def test_set_address_mode(self):
        """Test setting address mode."""
        result = self.bond.set_address_mode("boss")
        self.assertTrue(result)
        self.assertEqual(self.bond.get_address(), "boss")

    def test_detect_distress_phrase(self):
        """Test duress phrase detection."""
        result = self.bond.detect_distress("The iris is closed today.")
        self.assertTrue(result)

    def test_detect_distress_normal(self):
        """Test normal text returns False."""
        result = self.bond.detect_distress("Everything is fine.")
        self.assertFalse(result)

    def test_detect_creator_tone_stressed(self):
        """Test stressed tone detection."""
        tone = self.bond.detect_creator_tone("This is frustrating!")
        self.assertEqual(tone, "stressed")

    def test_detect_creator_tone_excited(self):
        """Test excited tone detection."""
        tone = self.bond.detect_creator_tone("Let's build something amazing!")
        self.assertEqual(tone, "excited")

    def test_respond_to_creator_work(self):
        """Test work mode response."""
        response = self.bond.respond_to_creator("Secure server", {"work_mode": True})
        self.assertIn("Executing", response)

    def test_respond_to_creator_support(self):
        """Test support mode response."""
        response = self.bond.respond_to_creator("I am tired", {"support_mode": True})
        self.assertTrue(len(response) > 0)

    def test_activate_protective_mode(self):
        """Test protective mode activation."""
        result = self.bond.activate_protective_mode("test_reason")
        self.assertTrue(result)
        self.assertTrue(self.bond.protective_mode_active)

    def test_deactivate_protective_mode(self):
        """Test protective mode deactivation."""
        self.bond.activate_protective_mode("test")
        result = self.bond.deactivate_protective_mode()
        self.assertTrue(result)
        self.assertFalse(self.bond.protective_mode_active)

    def test_get_creator_preferences(self):
        """Test preferences retrieval."""
        prefs = self.bond.get_creator_preferences()
        self.assertIsInstance(prefs, dict)

    def test_update_preference(self):
        """Test preference update."""
        result = self.bond.update_preference("test_key", "test_value")
        self.assertTrue(result)
        self.assertEqual(self.bond.preferences["test_key"], "test_value")

    def test_record_moment(self):
        """Test moment recording."""
        self.bond.record_moment("test_event", {"detail": "value"})
        history = self.bond.get_shared_history()
        self.assertTrue(len(history) > 0)

    def test_health_check(self):
        """Test health check."""
        health = self.bond.health_check()
        self.assertIn("creator_id", health)


if __name__ == "__main__":
    unittest.main()
