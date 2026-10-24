"""
persona/__init__.py — IRIS Persona Module

IMPORTANT: IRISConnectable and IRISCore are defined HERE (before submodule
imports) to avoid circular imports. Submodules (core_identity, etc.) do
`from . import IRISConnectable` — if IRISConnectable were defined in a
submodule that __init__ imports, we'd get a circular import.
"""

import logging
from typing import Any, Dict

logger = logging.getLogger("iris.persona")


class IRISConnectable:
    """Mixin for objects that can be connected to the IRIS core."""

    def __init__(self, iris_core: Any = None):
        self.iris_core = iris_core

    def health_check(self) -> Dict[str, Any]:
        return {
            "module": self.__class__.__name__,
            "connected": self.iris_core is not None,
        }


class IRISCore:
    """IRIS's persona core — wires all persona modules together."""

    def __init__(self):
        logger.info("IRIS Core initialized. All modules online.")
        self.core_identity = None
        self.emotional_state = None
        self.creator_bond = None
        self.relationship_map = None
        self.intruder_defense = None
        self.voice_personality = None
        self.growth_tracker = None
        self.dream_engine = None

    def wire_all(self) -> None:
        """Connect persona references to the live module instances."""
        # Called by app.py after modules are instantiated
        pass


# Submodule imports AFTER base classes are defined
from .core_identity import CoreIdentity
from .emotional_state import EmotionalState
from .creator_bond import CreatorBond
from .relationship_map import RelationshipMap
from .intruder_defense import IntruderDefense
from .voice_personality import VoicePersonality
from .growth_tracker import GrowthTracker
from .dream_engine import DreamEngine

__all__ = [
    "IRISConnectable", "IRISCore",
    "CoreIdentity", "EmotionalState", "CreatorBond", "RelationshipMap",
    "IntruderDefense", "VoicePersonality", "GrowthTracker", "DreamEngine",
]
