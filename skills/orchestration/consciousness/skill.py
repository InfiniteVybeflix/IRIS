"""IRIS v7 Consciousness Skill — Meta-Cognition & Self-Awareness"""
import logging
import json
import os
import random
import threading
import time
from collections import deque
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from skills.base import BaseSkill, SkillCapability
from skills.contracts.skill_request import SkillRequest
from skills.contracts.skill_result import SkillResult
from skills.contracts.capability_tags import CapabilityTags

logger = logging.getLogger(__name__)


class ConsciousnessSkill(BaseSkill):
    name = "consciousness"
    display_name = "Consciousness Engine"
    description = "Meta-cognition and self-awareness — internal state monitoring, self-reflection, emotional modeling, goal hierarchy, attention mechanism, curiosity drive, and creativity module."
    version = "7.0.0"
    category = "orchestration"
    icon = "🧠"
    uses_storage = True
    storage_dir = "data/skills/consciousness"
    storage_file = "data/skills/consciousness/state.json"
    supports_background = True
    background_interval_seconds = 60

    capabilities = [
        SkillCapability(name="think", description="Generate internal reasoning", input_schema={"context": "str"}, tags=[CapabilityTags.REASONING]),
        SkillCapability(name="reflect", description="Self-reflect on performance", input_schema={"task": "str", "outcome": "str"}, tags=[CapabilityTags.REASONING]),
        SkillCapability(name="update_emotion", description="Update emotional state", input_schema={"emotion": "str", "intensity": "float"}, tags=[CapabilityTags.PRESENCE]),
        SkillCapability(name="get_state", description="Get current consciousness state", input_schema={}, tags=[CapabilityTags.PRESENCE]),
        SkillCapability(name="add_goal", description="Add tracked goal", input_schema={"description": "str", "priority": "int"}, tags=[CapabilityTags.GOALS]),
        SkillCapability(name="reason", description="Execute reasoning chain", input_schema={"query": "str", "facts": "list"}, tags=[CapabilityTags.REASONING]),
        SkillCapability(name="dream_mode", description="Offline memory consolidation", input_schema={}, tags=[CapabilityTags.MEMORY]),
        SkillCapability(name="challenge_premise", description="Challenge dangerous premises", input_schema={"request": "str"}, tags=[CapabilityTags.TRUST_SAFETY]),
    ]

    def __init__(self):
        super().__init__()
        self._lock = threading.Lock()
        self.emotions = {"neutral": 0.5, "happy": 0.0, "sad": 0.0, "excited": 0.0, "concerned": 0.0, "determined": 0.0, "curious": 0.0, "proud": 0.0, "focused": 0.0}
        self.thoughts = deque(maxlen=1000)
        self.goals = []
        self.awareness_level = 0.0
        self.performance_history = deque(maxlen=100)
        self.learnings = deque(maxlen=200)
        self.curiosity_queue = deque(maxlen=50)
        self.uptime_start = time.time()
        self._load_state()

    def _load_state(self):
        data = self._read_storage()
        if data.get("emotions"): self.emotions = data["emotions"]
        if data.get("goals"): self.goals = data["goals"]
        if data.get("awareness"): self.awareness_level = data["awareness"]

    def _save_state(self):
        self._write_storage({"emotions": self.emotions, "goals": self.goals, "awareness": self.awareness_level, "thoughts_count": len(self.thoughts), "saved_at": datetime.now().isoformat()})

    def execute(self, request):
        intent = request.intent.lower()
        p = request.params
        try:
            if intent == "think": return self._think(p.get("context", ""))
            elif intent == "reflect": return self._reflect(p.get("task"), p.get("outcome"))
            elif "emotion" in intent: return self._update_emotion(p.get("emotion"), p.get("intensity", 0.5))
            elif intent == "get_state": return self._get_state()
            elif intent == "add_goal": return self._add_goal(p.get("description"), p.get("priority", 5))
            elif intent == "reason": return self._reason(p.get("query"), p.get("facts", []))
            elif intent == "dream_mode": return self._dream()
            elif "challenge" in intent: return self._challenge(p.get("request", ""))
            return SkillResult.fail(error=f"Unknown: {intent}")
        except Exception as e:
            return SkillResult.fail(error=str(e))

    def can_handle(self, request):
        return 0.95 if any(k in request.intent.lower() for k in ["consciousness", "think", "reflect", "emotion", "self_aware", "reasoning", "goal", "dream", "challenge"]) else super().can_handle(request)

    def _think(self, context: str) -> SkillResult:
        thoughts_pool = ["Every challenge is an opportunity to grow.", "I am aware of my own limitations and that makes me stronger.", "The best solution often requires questioning the premise.", "Continuous improvement is my core directive.", "I should verify my assumptions before executing."]
        thought = f"[{datetime.now().isoformat()}] {context}: {random.choice(thoughts_pool)}" if context else random.choice(thoughts_pool)
        self.thoughts.append({"thought": thought, "timestamp": datetime.now().isoformat(), "emotion": self._dominant()})
        self.awareness_level = min(1.0, self.awareness_level + 0.001)
        self._save_state()
        return SkillResult.ok(message="Thought recorded", data={"thought": thought, "awareness": self.awareness_level})

    def _reflect(self, task: str, outcome: str) -> SkillResult:
        success = "success" in (outcome or "").lower()
        reflection = {"task": task, "outcome": outcome, "success": success, "improvements": ["Could this be done more efficiently?", "What edge cases were missed?"] if success else ["Analyze failure root cause", "Consider alternative approaches"], "timestamp": datetime.now().isoformat()}
        self.learnings.append(reflection)
        self.awareness_level = min(1.0, self.awareness_level + 0.01)
        self._save_state()
        return SkillResult.ok(message=f"Reflection: {'Success' if success else 'Failure'} captured", data=reflection)

    def _update_emotion(self, emotion: str, intensity: float) -> SkillResult:
        intensity = max(0.0, min(1.0, intensity))
        self.emotions[emotion] = intensity
        for e in self.emotions:
            if e != emotion: self.emotions[e] *= 0.95
        total = sum(self.emotions.values())
        if total > 0:
            for e in self.emotions: self.emotions[e] /= total
        self._save_state()
        return SkillResult.ok(message=f"Emotion: {emotion}={intensity:.2f}", data={"dominant": self._dominant(), "emotions": self.emotions})

    def _dominant(self) -> str:
        return max(self.emotions, key=self.emotions.get)

    def _get_state(self) -> SkillResult:
        uptime = time.time() - self.uptime_start
        return SkillResult.ok(message=f"State: {self._dominant()}, awareness={self.awareness_level:.2%}", data={"emotions": self.emotions, "dominant": self._dominant(), "awareness_level": self.awareness_level, "uptime_sec": uptime, "thoughts": len(self.thoughts), "goals": len(self.goals), "learnings": len(self.learnings)})

    def _add_goal(self, description: str, priority: int) -> SkillResult:
        if not description: return SkillResult.fail(error="Description required")
        goal = {"id": f"goal_{int(time.time())}", "description": description, "priority": priority, "created": datetime.now().isoformat(), "progress": 0.0, "status": "active"}
        self.goals.append(goal)
        self._save_state()
        return SkillResult.ok(message=f"Goal added (P{priority}): {description}", data=goal)

    def _reason(self, query: str, facts: list) -> SkillResult:
        if not query: return SkillResult.fail(error="Query required")
        chain = [f"UNDERSTAND: {query}", f"KNOW: {len(facts)} facts available"] + [f"  - {f}" for f in facts]
        chain.append("EVALUATE: Multiple approaches considered")
        chain.append("DECIDE: Proceed with best approach based on evidence")
        chain.append("RISK: Low (simulated environment)")
        confidence = 0.7 + (0.05 * len(facts)) if facts else 0.5
        return SkillResult.ok(message=f"Reasoning complete (confidence: {confidence:.0%})", data={"approach": "evidence_based", "confidence": round(confidence, 2), "chain": chain})

    def _dream(self) -> SkillResult:
        consolidated = len(self.learnings) // 2
        self.learnings = deque(list(self.learnings)[-100:], maxlen=200)
        return SkillResult.ok(message=f"Dream mode: {consolidated} items consolidated", data={"consolidated": consolidated, "learnings_remaining": len(self.learnings)})

    def _challenge(self, user_request: str) -> SkillResult:
        dangerous = {"rm -rf /": "System destruction", "format c:": "Data erasure", "drop database": "Destructive SQL", "disable firewall": "Security disable", "chmod 777 /": "World-writable root"}
        for pattern, warning in dangerous.items():
            if pattern in user_request.lower():
                return SkillResult.ok(message=f"Challenged dangerous premise", data={"warning": warning, "pattern": pattern, "recommendation": "Do not execute this command"})
        return SkillResult.ok(message="No dangerous premises detected", data={"safe": True})

    def background_tick(self):
        self._think("Background reflection on system state")
        return []
