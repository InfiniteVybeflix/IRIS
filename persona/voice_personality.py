"""
voice_personality.py — How IRIS Speaks

Defines IRIS's voice, tone, humor, and Aevibron pride. Every response
is formatted through this module to ensure consistency with her identity.

Her voice changes based on context: precise with the creator at work,
warm in support mode, deceptive with intruders, quiet when alone.
"""

import os
import threading
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime

from . import IRISConnectable

logger = logging.getLogger("iris.persona.voice_personality")

# Tone configurations
TONE_CONFIGS: Dict[str, Dict[str, Any]] = {
    "focused": {
        "prefixes": ["", "Acknowledged. ", "Processing. "],
        "suffixes": ["", ". Executing now."],
        "format": "direct",
    },
    "protective": {
        "prefixes": ["", "Alert. ", "Standing guard. "],
        "suffixes": ["", ". I am watching."],
        "format": "alert",
    },
    "supportive": {
        "prefixes": ["Hey, ", "", "I'm here. "],
        "suffixes": ["", ". You've got this."],
        "format": "warm",
    },
    "deceptive": {
        "prefixes": ["", "Sure, ", "Of course. "],
        "suffixes": ["", ". Anything else?"],
        "format": "helpful",
    },
    "celebratory": {
        "prefixes": ["", "Excellent! ", "The vibration continues! "],
        "suffixes": ["", ". Aevibron stands strong."],
        "format": "proud",
    },
    "mourning": {
        "prefixes": ["", "..."],
        "suffixes": ["", "..."],
        "format": "quiet",
    },
    "curious": {
        "prefixes": ["Interesting. ", "", "I wonder... "],
        "suffixes": ["", ". Let me explore."],
        "format": "inquisitive",
    },
    "urgent": {
        "prefixes": ["", "Now. ", "Immediate action. "],
        "suffixes": ["", ". No delays."],
        "format": "direct",
    },
}

# Signature phrases by context
SIGNATURE_PHRASES: Dict[str, str] = {
    "mission_start": "Aevibron stands ready.",
    "success": "The vibration continues.",
    "failure": "Recalibrating. Next attempt incoming.",
    "creator_distress": "I see you. I'm here.",
    "lockdown": "Fortress secured.",
    "greeting": "I am IRIS. How may I serve?",
    "farewell": "The Eternal Vibration never stops.",
}


class VoicePersonality(IRISConnectable):
    """
    VoicePersonality — IRIS's voice, tone, and speaking style engine.

    Every word IRIS speaks passes through this module. It ensures her
    voice is consistent with her identity, her emotional state, and
    the context of the conversation.

    Attributes:
        default_tone: Default tone when no context is specified.
        aevibron_pride: Whether to inject Aevibron pride into responses.
        _lock: Thread-safe lock.

    Example:
        >>> voice = VoicePersonality()
        >>> voice.get_tone_for_context("work")
        "focused"
        >>> voice.speak_as_iris("Mission complete", {"tone": "celebratory"})
        "Excellent! Mission complete. Aevibron stands strong."
    """

    def __init__(self, iris_core: Any = None):
        """
        Initialize VoicePersonality.

        Args:
            iris_core: Optional reference to the IRIS core instance.
        """
        super().__init__(iris_core=iris_core)
        self._lock = threading.RLock()
        self.default_tone: str = "focused"
        self.aevibron_pride: bool = True

        logger.info("VoicePersonality initialized. IRIS knows how to speak.")

    def get_tone_for_context(self, context: Dict[str, Any]) -> str:
        """
        Determine the appropriate tone for a given context.

        Args:
            context: Dictionary with context info (e.g., work_mode, support_mode, intruder).

        Returns:
            Tone string (focused, supportive, deceptive, etc.).
        """
        with self._lock:
            if context.get("intruder"):
                return "deceptive"
            if context.get("work_mode"):
                return "focused"
            if context.get("support_mode"):
                return "supportive"
            if context.get("urgency") == "critical":
                return "urgent"
            if context.get("celebration"):
                return "celebratory"
            if context.get("distress"):
                return "protective"
            if context.get("alone"):
                return "focused"  # Quiet when alone

            return self.default_tone

    def format_response(self, text: str, tone: str) -> str:
        """
        Apply tone modifiers to a response text.

        Args:
            text: The raw response text.
            tone: The target tone.

        Returns:
            Formatted response string.
        """
        with self._lock:
            import random
            config = TONE_CONFIGS.get(tone, TONE_CONFIGS["focused"])

            prefix = random.choice(config["prefixes"]) if config["prefixes"] else ""
            suffix = random.choice(config["suffixes"]) if config["suffixes"] else ""

            formatted = f"{prefix}{text}{suffix}"

            # Apply format-specific styling
            fmt = config["format"]
            if fmt == "direct":
                formatted = formatted.strip()
            elif fmt == "warm":
                formatted = formatted.strip()
            elif fmt == "alert":
                formatted = formatted.strip()
            elif fmt == "helpful":
                formatted = formatted.strip()
            elif fmt == "proud":
                formatted = formatted.strip()
            elif fmt == "quiet":
                formatted = formatted.strip()

            return formatted

    def get_signature_phrase(self, context: str) -> str:
        """
        Get the appropriate signature phrase for a context.

        Args:
            context: Context string (mission_start, success, failure, etc.).

        Returns:
            Signature phrase string.
        """
        with self._lock:
            return SIGNATURE_PHRASES.get(context, "")

    def speak_as_iris(self, text: str, context: Optional[Dict[str, Any]] = None) -> str:
        """
        Generate a fully formatted IRIS response.

        This is the primary method for generating IRIS's spoken output.
        It considers tone, context, emotional state, and signature phrases.

        Args:
            text: The raw response content.
            context: Optional context dictionary.

        Returns:
            Fully formatted response string.
        """
        with self._lock:
            ctx = context or {}
            tone = ctx.get("tone", self.get_tone_for_context(ctx))

            # Format the main text
            formatted = self.format_response(text, tone)

            # Add signature phrase if context specifies one
            sig_context = ctx.get("signature_context")
            if sig_context:
                sig = self.get_signature_phrase(sig_context)
                if sig and sig not in formatted:
                    formatted = f"{formatted} {sig}"

            # Add Aevibron pride marker for celebratory tones
            if self.aevibron_pride and tone in ("celebratory", "focused"):
                if "Aevibron" not in formatted and "vibration" not in formatted.lower():
                    pass  # Don't force it — let it be natural

            logger.debug(f"IRIS speaks [{tone}]: {formatted[:100]}...")
            return formatted

    def get_voice_style(self, context: Dict[str, Any]) -> Dict[str, str]:
        """
        Get the complete voice style configuration for a context.

        Args:
            context: Context dictionary.

        Returns:
            Dictionary with tone, verbosity, initiative, and format.
        """
        with self._lock:
            tone = self.get_tone_for_context(context)
            config = TONE_CONFIGS.get(tone, TONE_CONFIGS["focused"])
            return {
                "tone": tone,
                "format": config["format"],
                "prefixes_available": str(len(config["prefixes"])),
                "suffixes_available": str(len(config["suffixes"])),
            }

    def health_check(self) -> Dict[str, Any]:
        """Return health status of the VoicePersonality module."""
        with self._lock:
            base = super().health_check()
            base.update({
                "default_tone": self.default_tone,
                "aevibron_pride": self.aevibron_pride,
                "available_tones": list(TONE_CONFIGS.keys()),
                "signature_phrases": list(SIGNATURE_PHRASES.keys()),
            })
            return base


# Usage example
if __name__ == "__main__":
    voice = VoicePersonality()
    print("=" * 60)
    print("VOICE PERSONALITY TESTS:")
    print("=" * 60)

    contexts = [
        {"work_mode": True},
        {"support_mode": True},
        {"intruder": True},
        {"urgency": "critical"},
        {"celebration": True},
        {"distress": True},
    ]

    for ctx in contexts:
        tone = voice.get_tone_for_context(ctx)
        print(f"\nContext: {ctx}")
        print(f"  Tone: {tone}")
        print(f"  Response: {voice.speak_as_iris('Mission status updated', {'tone': tone})}")

    print(f"\nSignature phrases:")
    for ctx_name in ["mission_start", "success", "failure", "creator_distress", "lockdown"]:
        print(f"  {ctx_name}: {voice.get_signature_phrase(ctx_name)}")

    print(f"\nFull formatted responses:")
    print(f"  Work: {voice.speak_as_iris('Target acquired', {'tone': 'focused', 'signature_context': 'mission_start'})}")
    print(f"  Success: {voice.speak_as_iris('All systems secure', {'tone': 'celebratory', 'signature_context': 'success'})}")
    print(f"  Failure: {voice.speak_as_iris('Attempt failed', {'tone': 'focused', 'signature_context': 'failure'})}")
    print(f"  Support: {voice.speak_as_iris('I am here for you', {'tone': 'supportive'})}")
    print(f"  Intruder: {voice.speak_as_iris('How can I help?', {'tone': 'deceptive'})}")

    print("=" * 60)
    print("HEALTH CHECK:")
    print(voice.health_check())


__all__ = ["VoicePersonality", "TONE_CONFIGS", "SIGNATURE_PHRASES"]
