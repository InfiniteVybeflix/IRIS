"""
tests/test_relationship_map.py — Unit tests for RelationshipMap
"""

import unittest
import sys
import os
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from persona.relationship_map import RelationshipMap, UserProfile


class TestRelationshipMap(unittest.TestCase):
    """Test suite for RelationshipMap class."""

    def setUp(self):
        """Set up test fixtures with temp database."""
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, "test_relationships.db")
        self.rm = RelationshipMap(db_path=self.db_path)

    def tearDown(self):
        """Clean up temp files."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_add_user(self):
        """Test adding a new user."""
        result = self.rm.add_user("test_user", {"name": "Test"})
        self.assertTrue(result)

    def test_add_duplicate_user(self):
        """Test adding duplicate user returns False."""
        self.rm.add_user("test_user", {"name": "Test"})
        result = self.rm.add_user("test_user", {"name": "Test"})
        self.assertFalse(result)

    def test_update_trust(self):
        """Test updating user trust."""
        self.rm.add_user("test_user")
        result = self.rm.update_trust("test_user", 0.5)
        self.assertTrue(result)
        self.assertEqual(self.rm.get_trust_level("test_user"), 0.5)

    def test_update_trust_unknown_user(self):
        """Test updating trust for unknown user returns False."""
        result = self.rm.update_trust("unknown", 0.5)
        self.assertFalse(result)

    def test_is_creator(self):
        """Test creator identification."""
        creator_id = os.getenv("IRIS_CREATOR_ID", "infinite_vybeflix")
        self.assertTrue(self.rm.is_creator(creator_id))
        self.assertFalse(self.rm.is_creator("not_creator"))

    def test_is_intruder_unknown(self):
        """Test unknown users are treated as intruders."""
        self.assertTrue(self.rm.is_intruder("unknown_user"))

    def test_flag_user(self):
        """Test flagging a user."""
        self.rm.add_user("test_user")
        result = self.rm.flag_user("test_user", "suspicious")
        self.assertTrue(result)

    def test_unflag_user(self):
        """Test unflagging a user."""
        self.rm.add_user("test_user")
        self.rm.flag_user("test_user", "suspicious")
        result = self.rm.unflag_user("test_user", "suspicious")
        self.assertTrue(result)

    def test_get_user_profile(self):
        """Test getting user profile."""
        self.rm.add_user("test_user", {"role": "client"})
        profile = self.rm.get_user_profile("test_user")
        self.assertIn("user_id", profile)
        self.assertEqual(profile["metadata"]["role"], "client")

    def test_get_all_users(self):
        """Test getting all users."""
        self.rm.add_user("user1")
        self.rm.add_user("user2")
        users = self.rm.get_all_users()
        self.assertEqual(len(users), 2)

    def test_health_check(self):
        """Test health check."""
        health = self.rm.health_check()
        self.assertIn("total_users", health)


if __name__ == "__main__":
    unittest.main()
