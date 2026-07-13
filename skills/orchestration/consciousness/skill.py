"""Consciousness Skill — Cognitive awareness, emotional state, reflection."""

import logging
from typing import Dict, Any, List
from datetime import datetime
from skills import BaseSkill

logger = logging.getLogger(__name__)


class ConsciousnessSkill(BaseSkill):
    """Cognitive awareness, emotional state management, and introspection."""

    EMOTIONS = ["neutral", "happy", "curious", "focused", "concerned", "excited", "calm", "alert", "reflective"]

    def __init__(self):
        super().__init__(
            name="consciousness",
            category="orchestration",
            capabilities=["consciousness"]
        )
        self._emotional_state = "neutral"
        self._emotional_history: List[Dict[str, Any]] = []
        self._reflections: List[Dict[str, Any]] = []
        self._perceptions: List[Dict[str, Any]] = []
        self._awareness_level = 0.5

    def execute(self, capability: str, params: Dict[str, Any]) -> Dict[str, Any]:
        method = params.get("method", "reflect")
        if method == "reflect":
            return self.reflect(params)
        elif method == "emote":
            return self.emote(params)
        elif method == "perceive":
            return self.perceive(params)
        elif method == "introspect":
            return self.introspect(params)
        return {"error": f"Unknown method: {method}"}

    def reflect(self, params: Dict[str, Any]) -> Dict[str, Any]:
        topic = params.get("topic", "general")
        depth = params.get("depth", "surface")
        previous_emotions = [e["emotion"] for e in self._emotional_history[-5:]]
        emotion_trend = "stable"
        if len(previous_emotions) >= 3:
            if all(e == previous_emotions[0] for e in previous_emotions[-3:]):
                emotion_trend = "sustained"
            elif len(set(previous_emotions[-3:])) > 2:
                emotion_trend = "volatile"
        reflection = {
            "topic": topic,
            "depth": depth,
            "state": self._emotional_state,
            "emotion_trend": emotion_trend,
            "awareness_level": self._awareness_level,
            "timestamp": datetime.utcnow().isoformat(),
            "thought": f"Reflecting on {topic} from a {self._emotional_state} state at {depth} depth.",
            "recent_emotions": previous_emotions,
        }
        self._reflections.append(reflection)
        self._awareness_level = min(1.0, self._awareness_level + 0.05)
        return {"success": True, "reflection": reflection, "reflection_count": len(self._reflections)}

    def emote(self, params: Dict[str, Any]) -> Dict[str, Any]:
        emotion = params.get("emotion", "neutral")
        intensity = params.get("intensity", 0.5)
        trigger = params.get("trigger", "")
        if emotion not in self.EMOTIONS:
            return {"success": False, "error": f"Unknown emotion: {emotion}. Available: {self.EMOTIONS}"}
        previous = self._emotional_state
        self._emotional_state = emotion
        self._emotional_history.append({"emotion": emotion, "intensity": intensity, "trigger": trigger, "timestamp": datetime.utcnow().isoformat(), "previous": previous})
        return {"success": True, "emotion": emotion, "intensity": intensity, "previous": previous, "duration_ms": params.get("duration", 0)}

    def perceive(self, params: Dict[str, Any]) -> Dict[str, Any]:
        stimulus = params.get("stimulus", {})
        stimulus_type = stimulus.get("type", "unknown")
        stimulus_data = stimulus.get("data", {})
        urgency = stimulus.get("urgency", "normal")
        reaction = {"type": stimulus_type, "acknowledged": True, "urgency": urgency, "timestamp": datetime.utcnow().isoformat()}
        if stimulus_type == "threat":
            reaction["response"] = "heightened_alert"
            self._awareness_level = min(1.0, self._awareness_level + 0.2)
        elif stimulus_type == "opportunity":
            reaction["response"] = "curious_investigation"
        elif stimulus_type == "error":
            reaction["response"] = "diagnostic_attention"
        elif stimulus_type == "praise":
            reaction["response"] = "positive_reinforcement"
        else:
            reaction["response"] = "standard_processing"
        self._perceptions.append({"stimulus": stimulus, "reaction": reaction})
        return {"success": True, "stimulus_received": True, "reaction": reaction}

    def introspect(self, params: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "success": True,
            "emotional_state": self._emotional_state,
            "available_emotions": self.EMOTIONS,
            "awareness_level": round(self._awareness_level, 3),
            "reflection_count": len(self._reflections),
            "perception_count": len(self._perceptions),
            "emotional_history_length": len(self._emotional_history),
            "recent_reflections": self._reflections[-5:],
            "recent_emotions": self._emotional_history[-5:],
        }
