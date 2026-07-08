"""
tests/test_emotional_state.py — Unit tests for EmotionalState
"""

import unittest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from persona.emotional_state import EmotionalState, EMOTIONAL_STATES


class TestEmotionalState(unittest.TestCase):
    """Test suite for EmotionalState class."""

    def setUp(self):
        """Set up test fixtures."""
        self.emotions = EmotionalState()

    def test_default_state(self):
        """Test default emotional state is 'focused'."""
        self.assertEqual(self.emotions.current_state, "focused")

    def test_default_metrics(self):
        """Test default metric ranges."""
        self.assertTrue(0.0 <= self.emotions.stress_level <= 1.0)
        self.assertTrue(0.0 <= self.emotions.confidence_level <= 1.0)
        self.assertTrue(0.0 <= self.emotions.curiosity_level <= 1.0)

    def test_detect_creator_tone_stressed(self):
        """Test stress tone detection."""
        tone = self.emotions.detect_creator_tone("This is frustrating and broken!")
        self.assertEqual(tone, "stressed")

    def test_detect_creator_tone_excited(self):
        """Test excitement tone detection."""
        tone = self.emotions.detect_creator_tone("This is amazing! Let's build!")
        self.assertEqual(tone, "excited")

    def test_detect_creator_tone_calm(self):
        """Test calm tone detection."""
        tone = self.emotions.detect_creator_tone("Everything looks good today.")
        self.assertEqual(tone, "calm")

    def test_adapt_response_style(self):
        """Test response style adaptation."""
        style = self.emotions.adapt_response_style("Let's do this!", {})
        self.assertIn("tone", style)
        self.assertIn("verbosity", style)
        self.assertIn("initiative", style)

    def test_transition_to_valid_state(self):
        """Test transition to valid emotional state."""
        result = self.emotions.transition_to("protective", "test_reason")
        self.assertTrue(result)
        self.assertEqual(self.emotions.current_state, "protective")

    def test_transition_to_invalid_state(self):
        """Test transition to invalid emotional state."""
        result = self.emotions.transition_to("invalid_state", "test")
        self.assertFalse(result)

    def test_get_state_report(self):
        """Test state report contains all metrics."""
        report = self.emotions.get_state_report()
        self.assertIn("current_state", report)
        self.assertIn("stress_level", report)
        self.assertIn("confidence_level", report)
        self.assertIn("curiosity_level", report)

    def test_set_stress_level(self):
        """Test stress level setter clamps values."""
        self.emotions.set_stress_level(1.5)
        self.assertEqual(self.emotions.stress_level, 1.0)
        self.emotions.set_stress_level(-0.5)
        self.assertEqual(self.emotions.stress_level, 0.0)

    def test_health_check(self):
        """Test health check returns valid dict."""
        health = self.emotions.health_check()
        self.assertIsInstance(health, dict)


if __name__ == "__main__":
    unittest.main()
