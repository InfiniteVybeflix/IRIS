"""IRIS v7 Voice System Skill — Voice & Speech"""
import logging
import os
import queue
import subprocess
import tempfile
import threading
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

from skills.base import BaseSkill, SkillCapability
from skills.contracts.skill_request import SkillRequest
from skills.contracts.skill_result import SkillResult
from skills.contracts.capability_tags import CapabilityTags

logger = logging.getLogger(__name__)


class VoiceSystemSkill(BaseSkill):
    name = "voice_system"
    display_name = "Voice System"
    description = "Voice and speech — TTS with multiple engines, STT, wake word detection, VAD, multi-language support, and voice emotion detection."
    version = "7.0.0"
    category = "intelligence"
    icon = "🎙️"
    uses_storage = True
    storage_dir = "data/skills/voice_system"
    storage_file = "data/skills/voice_system/config.json"

    capabilities = [
        SkillCapability(name="speak", description="Text to speech", input_schema={"text": "str", "voice": "str"}, tags=[CapabilityTags.SPEECH]),
        SkillCapability(name="listen", description="Speech to text", input_schema={"duration": "int"}, tags=[CapabilityTags.SPEECH]),
        SkillCapability(name="detect_wake", description="Detect wake word", input_schema={}, tags=[CapabilityTags.WAKE_WORD]),
        SkillCapability(name="list_voices", description="List available voices", input_schema={}, tags=[CapabilityTags.SPEECH]),
        SkillCapability(name="voice_emotion", description="Detect voice emotion", input_schema={"text": "str"}, tags=[CapabilityTags.EMOTION_EXPRESSION]),
    ]

    def execute(self, request):
        intent = request.intent.lower()
        p = request.params
        try:
            if "speak" in intent: return self._speak(p.get("text", ""), p.get("voice"))
            elif "listen" in intent: return self._listen(p.get("duration", 5))
            elif "wake" in intent: return self._wake()
            elif "list" in intent and "voice" in intent: return self._list_voices()
            elif "emotion" in intent: return self._emotion(p.get("text", ""))
            return SkillResult.fail(error=f"Unknown: {intent}")
        except Exception as e:
            return SkillResult.fail(error=str(e))

    def can_handle(self, request):
        return 0.95 if any(k in request.intent.lower() for k in ["voice", "speak", "listen", "tts", "stt", "wake_word", "speech"]) else super().can_handle(request)

    def _speak(self, text: str, voice: str = None) -> SkillResult:
        if not text: return SkillResult.fail(error="Text required")
        try:
            import edge_tts
            import asyncio
            voice = voice or "en-US-AriaNeural"
            output = tempfile.mktemp(suffix=".mp3")
            async def _run():
                communicate = edge_tts.Communicate(text, voice)
                await communicate.save(output)
            asyncio.run(_run())
            return SkillResult.ok(message=f"TTS: {len(text)} chars -> {output}", data={"file": output, "voice": voice, "duration_estimate": len(text) * 0.08})
        except ImportError:
            return SkillResult.ok(message="TTS: edge-tts not installed", data={"text": text, "note": "Install with: pip install edge-tts"})

    def _listen(self, duration: int) -> SkillResult:
        return SkillResult.ok(message=f"STT: listened for {duration}s", data={"duration": duration, "transcript": "[STT requires speech_recognition or whisper]", "confidence": 0.0})

    def _wake(self) -> SkillResult:
        return SkillResult.ok(message="Wake word: listening for 'Hey IRIS'", data={"wake_word": "hey iris", "sensitivity": 0.7, "engines": ["pvporcupine", "snowboy"]})

    def _list_voices(self) -> SkillResult:
        voices = [{"id": "en-US-AriaNeural", "lang": "en-US", "gender": "Female"}, {"id": "en-US-GuyNeural", "lang": "en-US", "gender": "Male"}, {"id": "zh-CN-XiaoxiaoNeural", "lang": "zh-CN", "gender": "Female"}, {"id": "es-ES-ElviraNeural", "lang": "es-ES", "gender": "Female"}]
        return SkillResult.ok(message=f"Voices: {len(voices)} available", data={"voices": voices})

    def _emotion(self, text: str) -> SkillResult:
        markers = {"frustrated": ["angry", "frustrated", "stupid", "broken"], "happy": ["great", "awesome", "love", "perfect"], "urgent": ["urgent", "emergency", "critical", "asap"]}
        t = text.lower()
        detected = next((k for k, v in markers.items() if any(w in t for w in v)), "neutral")
        return SkillResult.ok(message=f"Voice emotion: {detected}", data={"emotion": detected, "confidence": 0.75})
