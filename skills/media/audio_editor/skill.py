"""Audio Editor Skill — Trim, merge, convert audio."""
import logging
from typing import Dict, Any
from skills import BaseSkill
logger = logging.getLogger(__name__)

class AudioEditorSkill(BaseSkill):
    def __init__(self):
        super().__init__(name="audio_editor", category="media", capabilities=["audio_editor"])

    def execute(self, capability: str, params: Dict[str, Any]) -> Dict[str, Any]:
        method = params.get("method", "trim")
        if method == "trim": return self.trim(params)
        elif method == "merge": return self.merge(params)
        elif method == "convert": return self.convert(params)
        return {"error": f"Unknown method: {method}"}

    def trim(self, params: Dict[str, Any]) -> Dict[str, Any]:
        path = params.get("path", "")
        start_ms = params.get("start_ms", 0)
        end_ms = params.get("end_ms", 0)
        try:
            from pydub import AudioSegment
            audio = AudioSegment.from_file(path)
            trimmed = audio[start_ms:end_ms]
            output = params.get("output", path.replace(".", "_trimmed."))
            trimmed.export(output, format=output.split(".")[-1])
            return {"success": True, "output": output, "duration_ms": len(trimmed)}
        except ImportError:
            return {"success": False, "error": "pydub required. Install: pip install pydub"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def merge(self, params: Dict[str, Any]) -> Dict[str, Any]:
        paths = params.get("paths", [])
        try:
            from pydub import AudioSegment
            combined = AudioSegment.empty()
            for p in paths:
                combined += AudioSegment.from_file(p)
            output = params.get("output", "merged.mp3")
            combined.export(output, format=output.split(".")[-1])
            return {"success": True, "output": output, "duration_ms": len(combined)}
        except ImportError:
            return {"success": False, "error": "pydub required"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def convert(self, params: Dict[str, Any]) -> Dict[str, Any]:
        path = params.get("path", "")
        fmt = params.get("format", "mp3")
        try:
            from pydub import AudioSegment
            audio = AudioSegment.from_file(path)
            output = path.rsplit(".", 1)[0] + "." + fmt
            audio.export(output, format=fmt)
            return {"success": True, "output": output, "format": fmt}
        except ImportError:
            return {"success": False, "error": "pydub required"}
        except Exception as e:
            return {"success": False, "error": str(e)}
