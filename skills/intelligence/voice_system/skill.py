"""Voice System Skill — Text-to-speech and speech-to-text."""

import logging
import os
import tempfile
from typing import Dict, Any, List
from skills import BaseSkill

logger = logging.getLogger(__name__)


class VoiceSystemSkill(BaseSkill):
    """Voice synthesis and recognition capabilities."""

    def __init__(self):
        super().__init__(
            name="voice_system",
            category="intelligence",
            capabilities=["voice_synthesis", "voice_recognition"]
        )
        self._voices = {
            "default": {"lang": "en", "gender": "neutral", "speed": 1.0},
            "en_female": {"lang": "en", "gender": "female", "speed": 1.0},
            "en_male": {"lang": "en", "gender": "male", "speed": 1.0},
            "en_gb": {"lang": "en-GB", "gender": "female", "speed": 1.0},
            "en_au": {"lang": "en-AU", "gender": "female", "speed": 1.0},
            "es": {"lang": "es", "gender": "female", "speed": 1.0},
            "fr": {"lang": "fr", "gender": "female", "speed": 1.0},
            "de": {"lang": "de", "gender": "male", "speed": 1.0},
            "ja": {"lang": "ja", "gender": "female", "speed": 1.0},
            "zh": {"lang": "zh-CN", "gender": "female", "speed": 1.0},
        }

    def execute(self, capability: str, params: Dict[str, Any]) -> Dict[str, Any]:
        if capability == "voice_synthesis":
            return self.synthesize(params)
        elif capability == "voice_recognition":
            return self.transcribe(params)
        return {"error": f"Unknown capability: {capability}"}

    def synthesize(self, params: Dict[str, Any]) -> Dict[str, Any]:
        text = params.get("text", "")
        voice_id = params.get("voice_id", "default")
        output_format = params.get("format", "mp3")
        speed = params.get("speed", self._voices.get(voice_id, {}).get("speed", 1.0))
        if not text:
            return {"success": False, "error": "No text provided"}
        voice_cfg = self._voices.get(voice_id, self._voices["default"])
        # Use pyttsx3 for local TTS
        try:
            import pyttsx3
            engine = pyttsx3.init()
            engine.setProperty("rate", int(200 * speed))
            voices = engine.getProperty("voices")
            if voices and len(voices) > 1:
                if voice_cfg.get("gender") == "male" and len(voices) > 0:
                    engine.setProperty("voice", voices[0].id)
                elif voice_cfg.get("gender") == "female" and len(voices) > 1:
                    engine.setProperty("voice", voices[1].id)
            output_path = params.get("output_path", os.path.join(tempfile.gettempdir(), f"iris_tts_{os.urandom(4).hex()}.{output_format}"))
            engine.save_to_file(text, output_path)
            engine.runAndWait()
            return {"success": True, "text": text, "voice_id": voice_id, "output_path": output_path, "format": output_format, "voice_config": voice_cfg}
        except ImportError:
            return {"success": False, "error": "pyttsx3 not installed. Install with: pip install pyttsx3", "text": text, "voice_id": voice_id}
        except Exception as e:
            logger.error(f"TTS error: {e}")
            return {"success": False, "error": str(e), "text": text}

    def transcribe(self, params: Dict[str, Any]) -> Dict[str, Any]:
        audio_source = params.get("audio", "")
        audio_path = params.get("audio_path", "")
        language = params.get("language", "en-US")
        try:
            import speech_recognition as sr
            recognizer = sr.Recognizer()
            if audio_path:
                with sr.AudioFile(audio_path) as source:
                    audio_data = recognizer.record(source)
            elif isinstance(audio_source, sr.AudioData):
                audio_data = audio_source
            else:
                return {"success": False, "error": "Provide audio_path or AudioData object"}
            transcript = recognizer.recognize_google(audio_data, language=language)
            return {"success": True, "transcript": transcript, "language": language, "confidence": 0.9}
        except ImportError:
            return {"success": False, "error": "speech_recognition not installed. Install with: pip install SpeechRecognition"}
        except Exception as e:
            logger.error(f"STT error: {e}")
            return {"success": False, "error": str(e)}

    def list_voices(self, params: Dict[str, Any] = None) -> Dict[str, Any]:
        return {"success": True, "voices": self._voices, "count": len(self._voices)}
