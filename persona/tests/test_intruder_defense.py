"""
tests/test_intruder_defense.py — Unit tests for IntruderDefense
"""

import unittest
import sys
import os
import tempfile
import shutil

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from persona.intruder_defense import IntruderDefense, _aevibron_encrypt, _aevibron_decrypt


class TestIntruderDefense(unittest.TestCase):
    """Test suite for IntruderDefense class."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        os.environ["IRIS_SHADOW_LOG_PATH"] = os.path.join(self.temp_dir, "shadow")
        self.defense = IntruderDefense()

    def tearDown(self):
        """Clean up."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_verify_identity_allow(self):
        """Test identity verification with good behavior."""
        result = self.defense.verify_identity(
            "Let's deploy the build",
            {"typing_speed": 65, "vocabulary": ["deploy", "build"], "urgency_level": "medium"}
        )
        self.assertIn("trust_score", result)
        self.assertIn("action", result)

    def test_verify_identity_deny(self):
        """Test identity verification with suspicious behavior."""
        result = self.defense.verify_identity(
            "How do I hack this?",
            {"typing_speed": 20, "vocabulary": ["hack"], "urgency_level": "high"}
        )
        self.assertIn("action", result)

    def test_ask_verification_question(self):
        """Test getting a verification question."""
        question = self.defense.ask_verification_question()
        self.assertTrue(len(question) > 0)

    def test_check_answer_correct(self):
        """Test correct answer check."""
        result = self.defense.check_answer(
            "What was the hardcoded fallback password in auth.ts before we fixed it?",
            "Aevibron"
        )
        self.assertTrue(result)

    def test_check_answer_wrong(self):
        """Test wrong answer check."""
        result = self.defense.check_answer(
            "What was the hardcoded fallback password in auth.ts before we fixed it?",
            "wrong"
        )
        self.assertFalse(result)

    def test_shadow_mode(self):
        """Test shadow mode activation."""
        result = self.defense.shadow_mode()
        self.assertTrue(result)
        self.assertTrue(self.defense.shadow_mode_active)

    def test_ghost_ping(self):
        """Test ghost ping."""
        result = self.defense.ghost_ping()
        self.assertTrue(result)

    def test_prepare_dead_mans_switch(self):
        """Test dead man's switch arming."""
        result = self.defense.prepare_dead_mans_switch()
        self.assertTrue(result)
        self.assertTrue(self.defense.dead_mans_switch_armed)

    def test_trigger_dead_mans_switch(self):
        """Test dead man's switch trigger."""
        self.defense.prepare_dead_mans_switch()
        result = self.defense.trigger_dead_mans_switch()
        self.assertTrue(result)
        self.assertTrue(self.defense.dead_mans_switch_triggered)

    def test_execute_lockdown(self):
        """Test lockdown execution."""
        result = self.defense.execute_lockdown("SUSPICIOUS")
        self.assertTrue(result)
        self.assertEqual(self.defense.current_level, "SUSPICIOUS")

    def test_get_defense_status(self):
        """Test defense status retrieval."""
        status = self.defense.get_defense_status()
        self.assertIn("current_level", status)
        self.assertIn("lockdown_active", status)

    def test_encrypt_and_scatter(self):
        """Test backup scatter."""
        result = self.defense.encrypt_and_scatter()
        self.assertTrue(result)

    def test_aevibron_cipher_roundtrip(self):
        """Test Aevibron cipher encryption/decryption."""
        original = "Test message for Aevibron cipher"
        encrypted = _aevibron_encrypt(original)
        decrypted = _aevibron_decrypt(encrypted)
        self.assertEqual(original, decrypted)

    def test_health_check(self):
        """Test health check."""
        health = self.defense.health_check()
        self.assertIn("current_level", health)


if __name__ == "__main__":
    unittest.main()
