"""
tests/test_voice_personality.py — Unit tests for VoicePersonality
"""

import unittest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from persona.voice_personality import VoicePersonality, TONE_CONFIGS, SIGNATURE_PHRASES


class TestVoicePersonality(unittest.TestCase):
    """Test suite for VoicePersonality class."""

    def setUp(self):
        """Set up test fixtures."""
        self.voice = VoicePersonality()

    def test_get_tone_for_context_work(self):
        """Test work mode tone."""
        tone = self.voice.get_tone_for_context({"work_mode": True})
        self.assertEqual(tone, "focused")

    def test_get_tone_for_context_intruder(self):
        """Test intruder tone."""
        tone = self.voice.get_tone_for_context({"intruder": True})
        self.assertEqual(tone, "deceptive")

    def test_get_tone_for_context_support(self):
        """Test support mode tone."""
        tone = self.voice.get_tone_for_context({"support_mode": True})
        self.assertEqual(tone, "supportive")

    def test_format_response(self):
        """Test response formatting."""
        formatted = self.voice.format_response("Test message", "focused")
        self.assertTrue(len(formatted) > 0)

    def test_get_signature_phrase(self):
        """Test signature phrase retrieval."""
        phrase = self.voice.get_signature_phrase("mission_start")
        self.assertTrue(len(phrase) > 0)

    def test_speak_as_iris(self):
        """Test full IRIS response generation."""
        response = self.voice.speak_as_iris("Mission complete", {"tone": "celebratory"})
        self.assertTrue(len(response) > 0)

    def test_get_voice_style(self):
        """Test voice style retrieval."""
        style = self.voice.get_voice_style({"work_mode": True})
        self.assertIn("tone", style)
        self.assertIn("format", style)

    def test_health_check(self):
        """Test health check."""
        health = self.voice.health_check()
        self.assertIn("default_tone", health)


if __name__ == "__main__":
    unittest.main()
