"""IRIS v1 VoiceRSS Module — Alternative TTS with more voice options"""
import os
import requests
from typing import Dict, Optional

class VoiceRSSModule:
    """
    IRIS VoiceRSS TTS capabilities:
    - Multiple voice options (male, female, accents)
    - Language selection
    - Speed control
    - Fallback when Edge TTS unavailable
    """

    def __init__(self):
        self.api_key = os.getenv("IRIS_VOICERSS_API_KEY", "")
        self.base_url = "http://api.voicerss.org/"

    def speak(self, text: str, language: str = "en-us", voice: str = "Linda",
              speed: int = 0, output_path: str = None) -> Dict:
        """Generate speech using VoiceRSS API."""
        if not self.api_key:
            return {"success": False, "error": "VoiceRSS API key not configured in .env"}

        if not output_path:
            from config import config
            output_path = os.path.join(config.DATA_DIR, "audio", f"iris_voicerss_{int(__import__('time').time())}.mp3")
            os.makedirs(os.path.dirname(output_path), exist_ok=True)

        try:
            params = {
                "key": self.api_key,
                "src": text,
                "hl": language,
                "v": voice,
                "r": str(speed),
                "c": "MP3",
                "f": "44khz_16bit_stereo"
            }

            response = requests.get(self.base_url, params=params, timeout=30)

            if response.status_code == 200 and len(response.content) > 1000:
                with open(output_path, "wb") as f:
                    f.write(response.content)
                return {
                    "success": True,
                    "audio_path": output_path,
                    "text": text,
                    "voice": voice,
                    "language": language
                }

            # Check for error in response
            if response.headers.get('Content-Type', '').startswith('text'):
                return {"success": False, "error": response.text[:200]}
            return {"success": False, "error": "VoiceRSS returned invalid audio"}

        except Exception as e:
            return {"success": False, "error": str(e)}

    def get_voices(self, language: str = "en-us") -> Dict:
        """Get available voices for a language."""
        voices = {
            "en-us": ["Linda", "Amy", "Mary", "John", "Mike", "David", "Anna"],
            "en-gb": ["Alice", "Emma", "Brian", "Arthur"],
            "en-au": ["Zoe", "Isla", "William", "Jack"],
            "en-in": ["Eka", "Jai", "Ajit", "Prashant"],
            "fr-fr": ["Bette", "Iva", "Zola", "Axel"],
            "es-es": ["Camila", "Sofia", "Diego", "Luis"],
            "de-de": ["Hanna", "Lina", "Jonas", "Tim"],
            "it-it": ["Bianca", "mia", "Vincenzo", "Lorenzo"],
            "pt-br": ["Camila", "Felipe", "Fernanda", "Rodrigo"],
            "ja-jp": ["Hikari", "Haruka", "Takeru", "Ryo"],
            "ko-kr": ["Yuna", "Nari", "Junwoo", "Sanghoon"],
            "zh-cn": ["Luli", "Wang", "Xiaomei", "Zhiyu"],
            "ar-eg": ["Oda", "Salim", "Laila", "Tarik"],
            "hi-in": ["Puja", "Kabir", "Farhan", "Babitha"],
            "sw-ke": ["Elimu", "Baraka", "Hekima", "Imani"],
        }
        return {"success": True, "voices": voices.get(language, voices["en-us"]), "language": language}

    def speak_with_emotion(self, text: str, emotion: str = "neutral") -> Dict:
        """Speak with emotion-mapped voice."""
        emotion_map = {
            "neutral": {"voice": "Linda", "speed": 0},
            "happy": {"voice": "Amy", "speed": 2},
            "excited": {"voice": "Mary", "speed": 3},
            "sad": {"voice": "John", "speed": -2},
            "determined": {"voice": "Mike", "speed": 1},
            "concerned": {"voice": "David", "speed": -1},
            "proud": {"voice": "Anna", "speed": 1},
            "curious": {"voice": "Alice", "speed": 1},
        }

        config = emotion_map.get(emotion, emotion_map["neutral"])
        return self.speak(text, voice=config["voice"], speed=config["speed"])

# Singleton
voicerss_module = VoiceRSSModule()
