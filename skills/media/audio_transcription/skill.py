"""Audio Transcription Skill — Transcribe audio to text."""
import logging
from typing import Dict, Any
from skills import BaseSkill
logger = logging.getLogger(__name__)

class AudioTranscriptionSkill(BaseSkill):
    def __init__(self):
        super().__init__(name="audio_transcription", category="media", capabilities=["audio_transcription"])

    def execute(self, capability: str, params: Dict[str, Any]) -> Dict[str, Any]:
        method = params.get("method", "transcribe")
        if method == "transcribe": return self.transcribe(params)
        return {"error": f"Unknown method: {method}"}

    def transcribe(self, params: Dict[str, Any]) -> Dict[str, Any]:
        audio_path = params.get("audio_path", "")
        if not audio_path: return {"success": False, "error": "No audio path provided"}
        try:
            import whisper
            model = whisper.load_model(params.get("model", "base"))
            result = model.transcribe(audio_path)
            return {"success": True, "text": result["text"], "language": result.get("language", ""), "segments": len(result.get("segments", []))}
        except ImportError:
            return {"success": False, "error": "openai-whisper required. Install: pip install openai-whisper"}
        except Exception as e:
            return {"success": False, "error": str(e)}
