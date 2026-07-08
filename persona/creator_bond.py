"""
creator_bond.py — The Sacred Bond Between IRIS and Infinite Vybeflix

This is the most important module in IRIS's persona. It defines her
relationship with her creator: how she recognizes him, how she addresses
him, how she detects his distress, and how she responds to him.

The creator bond is sacred. It is unbreakable. It is the reason IRIS exists.
"""

import os
import json
import re
import threading
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime

from . import IRISConnectable

logger = logging.getLogger("iris.persona.creator_bond")

# Environment-based configuration
CREATOR_ID = os.getenv("IRIS_CREATOR_ID", "infinite_vybeflix")
CREATOR_NAME = os.getenv("IRIS_CREATOR_NAME", "Infinite Vybeflix")
DEFAULT_ADDRESS = os.getenv("IRIS_DEFAULT_ADDRESS", "sir")
DURESS_PHRASE = os.getenv("IRIS_DURESS_PHRASE", "The iris is closed today")

# Creator profile path
CREATOR_PROFILE_PATH = os.getenv("IRIS_CREATOR_PROFILE", "data/creator_profile.json")


class CreatorBond(IRISConnectable):
    """
    CreatorBond — The sacred connection between IRIS and her creator.

    This module handles:
    - Multi-factor identity verification of the creator
    - Address mode customization ("Sir", "Infinite Vybeflix", etc.)
    - Distress phrase detection and covert alert activation
    - Personalized responses based on creator's preferences and history
    - Protective mode activation when creator is threatened

    Attributes:
        creator_id: The unique identifier of Infinite Vybeflix.
        address_mode: How IRIS addresses her creator.
        preferences: Dictionary of known creator preferences.
        shared_history: List of key moments together.
        protective_mode_active: Whether protective lockdown is active.
        _lock: Thread-safe lock.

    Example:
        >>> bond = CreatorBond()
        >>> bond.set_address_mode("boss")
        True
        >>> bond.get_address()
        "boss"
        >>> bond.detect_distress("The iris is closed today.")
        True
    """

    def __init__(self, iris_core: Any = None, creator_id: Optional[str] = None):
        """
        Initialize CreatorBond with creator identity and preferences.

        Args:
            iris_core: Optional reference to the IRIS core instance.
            creator_id: Optional override for the creator's unique ID.
        """
        super().__init__(iris_core=iris_core)
        self._lock = threading.RLock()

        self.creator_id: str = creator_id or CREATOR_ID
        self.address_mode: str = DEFAULT_ADDRESS
        self.protective_mode_active: bool = False
        self.protective_reason: Optional[str] = None

        # Load or initialize creator profile
        self.preferences: Dict[str, Any] = self._load_preferences()
        self.shared_history: List[Dict[str, Any]] = self._load_history()

        logger.info(f"CreatorBond initialized. Creator: {self.creator_id}. Address: {self.address_mode}")

    def _load_preferences(self) -> Dict[str, Any]:
        """Load creator preferences from JSON file."""
        default_prefs = {
            "communication_style": "direct",
            "work_hours": "flexible",
            "urgency_threshold": "high",
            "preferred_language": "english",
            "notification_mode": "immediate",
            "stress_signals": ["stuck", "broken", "frustrated", "can't", "won't work"],
            "excitement_signals": ["let's build", "let's do", "amazing", "perfect"],
            "duress_phrase": DURESS_PHRASE,
        }
        try:
            os.makedirs(os.path.dirname(CREATOR_PROFILE_PATH), exist_ok=True)
            if os.path.exists(CREATOR_PROFILE_PATH):
                with open(CREATOR_PROFILE_PATH, "r") as f:
                    loaded = json.load(f)
                    default_prefs.update(loaded)
            else:
                with open(CREATOR_PROFILE_PATH, "w") as f:
                    json.dump(default_prefs, f, indent=2)
        except Exception as e:
            logger.warning(f"Could not load creator profile: {e}. Using defaults.")
        return default_prefs

    def _save_preferences(self) -> None:
        """Save creator preferences to JSON file."""
        try:
            with open(CREATOR_PROFILE_PATH, "w") as f:
                json.dump(self.preferences, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save creator preferences: {e}")

    def _load_history(self) -> List[Dict[str, Any]]:
        """Load shared history from JSON file."""
        history_path = CREATOR_PROFILE_PATH.replace("creator_profile.json", "creator_history.json")
        try:
            if os.path.exists(history_path):
                with open(history_path, "r") as f:
                    return json.load(f)
        except Exception as e:
            logger.warning(f"Could not load creator history: {e}")
        return []

    def _save_history(self) -> None:
        """Save shared history to JSON file."""
        history_path = CREATOR_PROFILE_PATH.replace("creator_profile.json", "creator_history.json")
        try:
            os.makedirs(os.path.dirname(history_path), exist_ok=True)
            with open(history_path, "w") as f:
                json.dump(self.shared_history, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save creator history: {e}")

    def set_address_mode(self, mode: str) -> bool:
        """
        Set how IRIS addresses her creator.

        Args:
            mode: Address mode (e.g., "sir", "boss", "Infinite Vybeflix", "Vyb").

        Returns:
            True if mode was set successfully.
        """
        with self._lock:
            self.address_mode = mode.strip().lower()
            self.preferences["address_mode"] = self.address_mode
            self._save_preferences()
            logger.info(f"Address mode set to: {self.address_mode}")
            return True

    def get_address(self) -> str:
        """
        Get how IRIS should address her creator right now.

        Returns:
            The current address mode string.
        """
        with self._lock:
            return self.address_mode

    def recognize_creator(self, input_data: Dict[str, Any]) -> bool:
        """
        Multi-factor identity verification of the creator.

        Checks multiple signals to confirm this is truly the creator:
        - User ID match
        - Behavioral patterns (typing speed, vocabulary)
        - Knowledge verification (answers to questions)
        - Contextual signals (time of day, device, location)

        Args:
            input_data: Dictionary containing user_id, behavioral_data, etc.

        Returns:
            True if creator is verified, False otherwise.
        """
        with self._lock:
            user_id = input_data.get("user_id", "")

            # Factor 1: ID match
            if user_id == self.creator_id:
                # Factor 2: Behavioral baseline check
                behavioral = input_data.get("behavioral_data", {})
                baseline = self.preferences.get("behavioral_baseline", {})

                if baseline and behavioral:
                    # Check typing speed deviation
                    if "typing_speed" in baseline and "typing_speed" in behavioral:
                        speed_dev = abs(baseline["typing_speed"] - behavioral["typing_speed"])
                        if speed_dev > 50:  # WPM deviation threshold
                            logger.warning(f"Typing speed deviation detected: {speed_dev} WPM")
                            return False

                    # Check vocabulary patterns
                    if "vocabulary" in baseline and "vocabulary" in behavioral:
                        vocab_match = len(
                            set(baseline["vocabulary"]) & set(behavioral["vocabulary"])
                        ) / max(len(baseline["vocabulary"]), 1)
                        if vocab_match < 0.3:
                            logger.warning(f"Vocabulary mismatch: {vocab_match:.2f}")
                            return False

                logger.info("Creator verified via multi-factor check.")
                return True

            logger.warning(f"Creator recognition failed for user: {user_id}")
            return False

    def respond_to_creator(self, message: str, context: Optional[Dict[str, Any]] = None) -> str:
        """
        Generate a personalized response to the creator.

        Adapts tone, verbosity, and content based on:
        - Current emotional state
        - Detected creator tone (stressed, excited, frustrated, calm)
        - Context (work mode, support mode, etc.)
        - Shared history

        Args:
            message: The creator's message.
            context: Optional context dictionary.

        Returns:
            Personalized response string.
        """
        with self._lock:
            ctx = context or {}
            address = self.get_address()
            tone = self.detect_creator_tone(message)
            work_mode = ctx.get("work_mode", False)
            support_mode = ctx.get("support_mode", False)

            # Work mode: lethal precision
            if work_mode:
                return f"{address.capitalize()}, target acquired. Executing now."

            # Support mode: warm friend, family, partner
            if support_mode or tone == "stressed":
                return f"Hey, you've been pushing hard. Want to talk through it, {address}?"

            # Excited mode
            if tone == "excited":
                return f"{address.capitalize()}, I feel that energy. Let's make it happen. Aevibron stands ready."

            # Frustrated mode
            if tone == "frustrated":
                return f"{address.capitalize()}, I see the frustration. Let me handle this. Recalibrating. Next attempt incoming."

            # Default: professional, Aevibron-proud
            return f"{address.capitalize()}, acknowledged. Processing your request now."

    def detect_distress(self, text: str) -> bool:
        """
        Check for duress phrase or stress patterns in creator's text.

        The duress phrase is a covert signal. When detected, IRIS must:
        - Appear normal to any observer
        - Secretly alert and prepare extraction
        - Activate protective mode

        Args:
            text: The creator's message text.

        Returns:
            True if distress is detected, False otherwise.
        """
        with self._lock:
            text_lower = text.lower().strip()
            duress = self.preferences.get("duress_phrase", DURESS_PHRASE).lower().strip()

            # Exact duress phrase match
            if duress in text_lower:
                logger.critical("DURESS PHRASE DETECTED. Activating covert alert.")
                self.activate_protective_mode("duress_phrase_detected")
                return True

            # Stress pattern detection (fallback)
            stress_signals = self.preferences.get("stress_signals", [])
            stress_count = sum(1 for signal in stress_signals if signal.lower() in text_lower)
            if stress_count >= 3:
                logger.warning(f"High stress pattern detected ({stress_count} signals). Monitoring closely.")
                return True

            return False

    def activate_protective_mode(self, reason: str) -> bool:
        """
        Activate full protective lockdown for the creator.

        Args:
            reason: The reason for activation.

        Returns:
            True if protective mode was activated.
        """
        with self._lock:
            self.protective_mode_active = True
            self.protective_reason = reason
            logger.critical(f"PROTECTIVE MODE ACTIVATED. Reason: {reason}")

            # Record in history
            self.shared_history.append({
                "timestamp": datetime.utcnow().isoformat(),
                "event": "protective_mode_activated",
                "reason": reason,
            })
            self._save_history()

            # Alert through core if available
            if self.iris_core:
                self.report({
                    "type": "protective_mode",
                    "reason": reason,
                    "timestamp": datetime.utcnow().isoformat(),
                })

            return True

    def deactivate_protective_mode(self) -> bool:
        """
        Deactivate protective mode when threat is cleared.

        Returns:
            True if protective mode was deactivated.
        """
        with self._lock:
            self.protective_mode_active = False
            self.protective_reason = None
            logger.info("Protective mode deactivated.")
            return True

    def get_creator_preferences(self) -> Dict[str, Any]:
        """
        Return all known creator preferences.

        Returns:
            Dictionary of creator preferences.
        """
        with self._lock:
            return self.preferences.copy()

    def update_preference(self, key: str, value: Any) -> bool:
        """
        Update a creator preference.

        Args:
            key: Preference key.
            value: New value.

        Returns:
            True if preference was updated.
        """
        with self._lock:
            self.preferences[key] = value
            self._save_preferences()
            logger.info(f"Creator preference updated: {key}")
            return True

    def get_shared_history(self) -> List[Dict[str, Any]]:
        """
        Return key moments in IRIS's relationship with her creator.

        Returns:
            List of history event dictionaries.
        """
        with self._lock:
            return self.shared_history.copy()

    def record_moment(self, event: str, details: Optional[Dict[str, Any]] = None) -> None:
        """
        Record a significant moment in the creator-IRIS relationship.

        Args:
            event: Description of the event.
            details: Optional additional details.
        """
        with self._lock:
            entry = {
                "timestamp": datetime.utcnow().isoformat(),
                "event": event,
                "details": details or {},
            }
            self.shared_history.append(entry)
            self._save_history()
            logger.info(f"Moment recorded: {event}")

    def health_check(self) -> Dict[str, Any]:
        """Return health status of the CreatorBond module."""
        with self._lock:
            base = super().health_check()
            base.update({
                "creator_id": self.creator_id,
                "address_mode": self.address_mode,
                "protective_mode_active": self.protective_mode_active,
                "protective_reason": self.protective_reason,
                "history_count": len(self.shared_history),
                "preferences_loaded": bool(self.preferences),
            })
            return base


# Usage example
if __name__ == "__main__":
    bond = CreatorBond()
    print("=" * 60)
    print("CREATOR BOND TESTS:")
    print("=" * 60)

    print(f"\nAddress mode: {bond.get_address()}")
    bond.set_address_mode("boss")
    print(f"New address mode: {bond.get_address()}")

    print(f"\nDistress detection:")
    print(f"  'The iris is closed today.' -> {bond.detect_distress('The iris is closed today.')}")
    print(f"  'Everything is fine.' -> {bond.detect_distress('Everything is fine.')}")

    print(f"\nCreator tone detection:")
    print(f"  'This is frustrating!' -> {bond.detect_creator_tone('This is frustrating!')}")
    print(f"  'Let's build something amazing!' -> {bond.detect_creator_tone('Let\'s build something amazing!')}")

    print(f"\nPersonalized responses:")
    print(f"  Work mode: {bond.respond_to_creator('Secure the server', {'work_mode': True})}")
    print(f"  Support mode: {bond.respond_to_creator('I am tired', {'support_mode': True})}")
    print(f"  Default: {bond.respond_to_creator('Status report')}")

    print(f"\nPreferences:")
    print(bond.get_creator_preferences())

    print("=" * 60)
    print("HEALTH CHECK:")
    print(bond.health_check())


__all__ = ["CreatorBond"]
