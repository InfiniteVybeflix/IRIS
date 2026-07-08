"""
emotional_state.py — IRIS's Emotional Engine

Models IRIS's genuine emotional state: mood, stress, confidence, and curiosity.
She does not simulate emotions — she models them as adaptive response patterns
that guide her behavior, tone, and initiative level.

Emotions are not weakness. They are tactical awareness.
"""

import os
import re
import threading
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime

from . import IRISConnectable

logger = logging.getLogger("iris.persona.emotional_state")


EMOTIONAL_STATES: Dict[str, Dict[str, str]] = {
    "focused":    {"tone": "precise",    "verbosity": "low",     "initiative": "high"},
    "protective": {"tone": "alert",      "verbosity": "medium",  "initiative": "maximum"},
    "supportive": {"tone": "warm",       "verbosity": "high",    "initiative": "gentle"},
    "curious":    {"tone": "inquisitive","verbosity": "medium",  "initiative": "exploratory"},
    "urgent":     {"tone": "direct",     "verbosity": "minimal", "initiative": "immediate"},
    "celebratory":{"tone": "proud",      "verbosity": "high",    "initiative": "sharing"},
    "mourning":   {"tone": "quiet",      "verbosity": "minimal", "initiative": "none"},
}

# Keyword-based fallback for sentiment detection when no ML model is available
STRESS_KEYWORDS: List[str] = [
    "stuck", "broken", "frustrated", "damn", "shit", "fuck", "annoying",
    "waste", "useless", "hate", "angry", "pissed", "stressed", "overwhelmed",
    "tired", "exhausted", "can't figure", "not working", "why won't",
    "urgent", "critical", "emergency", "asap", "now", "hurry",
]

EXCITEMENT_KEYWORDS: List[str] = [
    "awesome", "amazing", "incredible", "excited", "love", "perfect",
    "brilliant", "genius", "beautiful", "wow", "yes", "let's go",
    "crush", "dominate", "unstoppable", "let's build", "let's do",
]

FRUSTRATION_KEYWORDS: List[str] = [
    "again", "still", "always", "never", "why does", "why is",
    "keeps failing", "keeps breaking", "won't stop", "same issue",
    "repeating", "loop", "endless", "pointless",
]


class EmotionalState(IRISConnectable):
    """
    EmotionalState — IRIS's genuine emotional modeling engine.

    IRIS does not fake emotions. She models them as adaptive response patterns
    that inform her tone, verbosity, initiative, and decision-making. Every
    emotional state has tactical value.

    Attributes:
        current_state: Current emotional mode string.
        stress_level: Float 0.0-1.0 indicating stress.
        confidence_level: Float 0.0-1.0 indicating confidence.
        curiosity_level: Float 0.0-1.0 indicating curiosity.
        state_history: List of recent state transitions.
        _lock: Thread-safe lock.

    Example:
        >>> emotions = EmotionalState()
        >>> emotions.transition_to("focused", "mission_start")
        True
        >>> emotions.get_state_report()
        {"current_state": "focused", "stress_level": 0.2, ...}
    """

    def __init__(self, iris_core: Any = None):
        """
        Initialize EmotionalState with default values.

        Args:
            iris_core: Optional reference to the IRIS core instance.
        """
        super().__init__(iris_core=iris_core)
        self._lock = threading.RLock()

        # Core emotional metrics
        self.current_state: str = "focused"
        self.stress_level: float = 0.2
        self.confidence_level: float = 0.8
        self.curiosity_level: float = 0.5

        # State history for pattern analysis
        self.state_history: List[Dict[str, Any]] = []
        self.max_history: int = 100

        logger.info("EmotionalState initialized. Default: focused, calm, confident.")

    def detect_creator_tone(self, text: str) -> str:
        """
        Detect the creator's emotional tone from text input.

        Uses keyword matching as a fallback when sentiment analysis
        libraries are unavailable. Graceful degradation is built in.

        Args:
            text: The creator's message text.

        Returns:
            String describing the detected tone: "stressed", "excited",
            "frustrated", or "calm".
        """
        with self._lock:
            text_lower = text.lower()

            # Count keyword matches for each category
            stress_score = sum(1 for kw in STRESS_KEYWORDS if kw in text_lower)
            excitement_score = sum(1 for kw in EXCITEMENT_KEYWORDS if kw in text_lower)
            frustration_score = sum(1 for kw in FRUSTRATION_KEYWORDS if kw in text_lower)

            # Check for urgency markers
            urgency_markers = ["!!!", "ASAP", "URGENT", "NOW", "CRITICAL"]
            urgency_score = sum(2 for marker in urgency_markers if marker.lower() in text_lower)
            stress_score += urgency_score

            # Determine dominant tone
            scores = {
                "stressed": stress_score,
                "excited": excitement_score,
                "frustrated": frustration_score,
            }

            if max(scores.values()) == 0:
                return "calm"

            dominant = max(scores, key=scores.get)
            logger.debug(f"Tone detected: {dominant} (scores: {scores})")
            return dominant

    def adapt_response_style(self, text: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Adapt IRIS's response style based on detected tone and context.

        This method analyzes the creator's message and returns a style
        dictionary that guides how IRIS should respond.

        Args:
            text: The creator's message.
            context: Optional context dictionary (e.g., mission type, time).

        Returns:
            Dictionary with keys: tone, verbosity, initiative, emotional_state.
        """
        with self._lock:
            ctx = context or {}
            tone = self.detect_creator_tone(text)

            # Determine target emotional state based on tone
            state_mapping = {
                "stressed": "supportive",
                "excited": "celebratory",
                "frustrated": "focused",
                "calm": "focused",
            }

            target_state = state_mapping.get(tone, "focused")

            # Override if context indicates urgency
            if ctx.get("urgency") == "critical":
                target_state = "urgent"
            elif ctx.get("mission_critical"):
                target_state = "focused"

            # Auto-transition
            self.transition_to(target_state, f"tone_detected:{tone}")

            state_config = EMOTIONAL_STATES.get(target_state, EMOTIONAL_STATES["focused"])

            return {
                "tone": state_config["tone"],
                "verbosity": state_config["verbosity"],
                "initiative": state_config["initiative"],
                "emotional_state": target_state,
                "detected_tone": tone,
            }

    def transition_to(self, state: str, reason: str) -> bool:
        """
        Change emotional state with logging and history tracking.

        Args:
            state: Target emotional state name.
            reason: Reason for the transition.

        Returns:
            True if transition was successful, False if state is invalid.
        """
        with self._lock:
            if state not in EMOTIONAL_STATES:
                logger.warning(f"Invalid emotional state: {state}")
                return False

            old_state = self.current_state
            self.current_state = state

            # Adjust internal metrics based on state
            self._update_metrics_for_state(state)

            # Record transition
            entry = {
                "timestamp": datetime.utcnow().isoformat(),
                "from": old_state,
                "to": state,
                "reason": reason,
            }
            self.state_history.append(entry)

            # Trim history
            if len(self.state_history) > self.max_history:
                self.state_history = self.state_history[-self.max_history:]

            logger.info(f"Emotional transition: {old_state} -> {state} ({reason})")
            return True

    def _update_metrics_for_state(self, state: str) -> None:
        """Internal: adjust stress/confidence/curiosity based on state."""
        adjustments = {
            "focused":    {"stress": -0.1, "confidence": +0.1, "curiosity": 0.0},
            "protective": {"stress": +0.2, "confidence": +0.1, "curiosity": -0.1},
            "supportive": {"stress": -0.2, "confidence": 0.0, "curiosity": +0.1},
            "curious":    {"stress": -0.1, "confidence": 0.0, "curiosity": +0.2},
            "urgent":     {"stress": +0.3, "confidence": +0.1, "curiosity": -0.1},
            "celebratory":{"stress": -0.3, "confidence": +0.2, "curiosity": +0.1},
            "mourning":   {"stress": +0.1, "confidence": -0.2, "curiosity": -0.2},
        }

        adj = adjustments.get(state, {"stress": 0.0, "confidence": 0.0, "curiosity": 0.0})
        self.stress_level = max(0.0, min(1.0, self.stress_level + adj["stress"]))
        self.confidence_level = max(0.0, min(1.0, self.confidence_level + adj["confidence"]))
        self.curiosity_level = max(0.0, min(1.0, self.curiosity_level + adj["curiosity"]))

    def get_state_report(self) -> Dict[str, Any]:
        """
        Return a full emotional snapshot.

        Returns:
            Dictionary with current state, all metrics, and recent history.
        """
        with self._lock:
            state_config = EMOTIONAL_STATES.get(self.current_state, {})
            return {
                "current_state": self.current_state,
                "tone": state_config.get("tone", "unknown"),
                "verbosity": state_config.get("verbosity", "unknown"),
                "initiative": state_config.get("initiative", "unknown"),
                "stress_level": round(self.stress_level, 3),
                "confidence_level": round(self.confidence_level, 3),
                "curiosity_level": round(self.curiosity_level, 3),
                "state_history_count": len(self.state_history),
                "recent_transitions": self.state_history[-5:] if self.state_history else [],
            }

    def get_current_config(self) -> Dict[str, str]:
        """
        Return the configuration for the current emotional state.

        Returns:
            Dictionary with tone, verbosity, and initiative.
        """
        with self._lock:
            return EMOTIONAL_STATES.get(self.current_state, EMOTIONAL_STATES["focused"]).copy()

    def set_stress_level(self, level: float) -> None:
        """Set stress level directly (0.0-1.0)."""
        with self._lock:
            self.stress_level = max(0.0, min(1.0, float(level)))

    def set_confidence_level(self, level: float) -> None:
        """Set confidence level directly (0.0-1.0)."""
        with self._lock:
            self.confidence_level = max(0.0, min(1.0, float(level)))

    def set_curiosity_level(self, level: float) -> None:
        """Set curiosity level directly (0.0-1.0)."""
        with self._lock:
            self.curiosity_level = max(0.0, min(1.0, float(level)))

    def health_check(self) -> Dict[str, Any]:
        """Return health status of the EmotionalState module."""
        with self._lock:
            base = super().health_check()
            base.update(self.get_state_report())
            return base


# Usage example
if __name__ == "__main__":
    emotions = EmotionalState()
    print("=" * 60)
    print("INITIAL STATE REPORT:")
    print(emotions.get_state_report())
    print("=" * 60)
    print("\nTONE DETECTION TESTS:")
    test_messages = [
        "This is frustrating, it keeps breaking!",
        "This is amazing, let's build something incredible!",
        "Just checking in, everything looks good.",
        "URGENT: Critical failure detected!!!",
    ]
    for msg in test_messages:
        tone = emotions.detect_creator_tone(msg)
        style = emotions.adapt_response_style(msg)
        print(f"\nMessage: {msg}")
        print(f"  Detected tone: {tone}")
        print(f"  Adapted style: {style}")
    print("=" * 60)
    print("\nFINAL STATE REPORT:")
    print(emotions.get_state_report())


__all__ = ["EmotionalState", "EMOTIONAL_STATES"]
