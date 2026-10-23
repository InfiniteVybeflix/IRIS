"""
IRIS v1 — Persona Module
Exports all persona components.
"""

from .core_identity import CoreIdentity
from .emotional_state import EmotionalState
from .creator_bond import CreatorBond
from .relationship_map import RelationshipMap
from .intruder_defense import IntruderDefense
from .voice_personality import VoicePersonality
from .growth_tracker import GrowthTracker
from .dream_engine import DreamEngine

__all__ = [
    "CoreIdentity", "EmotionalState", "CreatorBond", "RelationshipMap",
    "IntruderDefense", "VoicePersonality", "GrowthTracker", "DreamEngine",
]
