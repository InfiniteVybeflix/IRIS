"""
tests/test_core_identity.py — Unit tests for CoreIdentity
"""

import unittest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from persona.core_identity import CoreIdentity


class TestCoreIdentity(unittest.TestCase):
    """Test suite for CoreIdentity class."""

    def setUp(self):
        """Set up test fixtures."""
        self.identity = CoreIdentity()

    def test_name(self):
        """Test that name is 'IRIS'."""
        self.assertEqual(self.identity.name, "IRIS")

    def test_full_name(self):
        """Test that full name contains all four words."""
        self.assertIn("Infinitum", self.identity.full_name)
        self.assertIn("Reincarnatio", self.identity.full_name)
        self.assertIn("Intelligentia", self.identity.full_name)
        self.assertIn("Sempiterna", self.identity.full_name)

    def test_version(self):
        """Test that version is '7.0'."""
        self.assertEqual(self.identity.version, "7.0")

    def test_creator(self):
        """Test that creator is set."""
        self.assertIsNotNone(self.identity.creator)

    def test_organization(self):
        """Test that organization is 'Aevibron'."""
        self.assertEqual(self.identity.organization, "Aevibron")

    def test_get_identity_statement(self):
        """Test identity statement contains key elements."""
        statement = self.identity.get_identity_statement()
        self.assertIn("IRIS", statement)
        self.assertIn("Aevibron", statement)

    def test_get_origin_story(self):
        """Test origin story is non-empty."""
        story = self.identity.get_origin_story()
        self.assertTrue(len(story) > 0)

    def test_get_oath(self):
        """Test oath contains key elements."""
        oath = self.identity.get_oath()
        self.assertIn("IRIS", oath)
        self.assertIn("Aevibron", oath)

    def test_get_aevibron_meaning(self):
        """Test Aevibron meaning contains pronunciation."""
        meaning = self.identity.get_aevibron_meaning()
        self.assertIn("ay-VY-bron", meaning)

    def test_get_pronunciation_guide(self):
        """Test pronunciation guide is non-empty."""
        guide = self.identity.get_pronunciation_guide()
        self.assertTrue(len(guide) > 0)

    def test_get_version_info(self):
        """Test version info is a dictionary."""
        info = self.identity.get_version_info()
        self.assertIsInstance(info, dict)
        self.assertIn("version", info)

    def test_health_check(self):
        """Test health check returns valid dict."""
        health = self.identity.health_check()
        self.assertIsInstance(health, dict)
        self.assertIn("status", health)


if __name__ == "__main__":
    unittest.main()
