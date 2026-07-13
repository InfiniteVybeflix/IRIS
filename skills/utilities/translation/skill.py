"""Translation Skill — Text translation between languages."""
import logging
import urllib.request
import urllib.parse
import json
from typing import Dict, Any
from skills import BaseSkill
logger = logging.getLogger(__name__)

class TranslationSkill(BaseSkill):
    def __init__(self):
        super().__init__(name="translation", category="utilities", capabilities=["translation"])
        self._languages = {"en": "English", "es": "Spanish", "fr": "French", "de": "German", "it": "Italian", "pt": "Portuguese", "ru": "Russian", "zh": "Chinese", "ja": "Japanese", "ko": "Korean", "ar": "Arabic", "hi": "Hindi", "sw": "Swahili", "nl": "Dutch", "pl": "Polish", "tr": "Turkish", "vi": "Vietnamese"}

    def execute(self, capability: str, params: Dict[str, Any]) -> Dict[str, Any]:
        method = params.get("method", "translate")
        if method == "translate": return self.translate(params)
        elif method == "detect": return self.detect(params)
        elif method == "list_languages": return self.list_languages(params)
        return {"error": f"Unknown method: {method}"}

    def translate(self, params: Dict[str, Any]) -> Dict[str, Any]:
        text = params.get("text", "")
        target = params.get("to", "en")
        source = params.get("from", "auto")
        if not text: return {"success": False, "error": "No text provided"}
        try:
            encoded = urllib.parse.quote(text)
            url = f"https://api.mymemory.translated.net/get?q={encoded}&langpair={source}|{target}"
            req = urllib.request.Request(url, headers={"User-Agent": "IRIS-OMNIS/1.0"})
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode())
            return {"success": True, "original": text, "translated": data.get("responseData", {}).get("translatedText", ""), "from": data.get("responseData", {}).get("detectedLang", source), "to": target}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def detect(self, params: Dict[str, Any]) -> Dict[str, Any]:
        text = params.get("text", "")
        if not text: return {"success": False, "error": "No text provided"}
        return {"success": True, "text": text[:100], "detected": "unknown", "confidence": 0.0}

    def list_languages(self, params: Dict[str, Any]) -> Dict[str, Any]:
        return {"success": True, "languages": self._languages, "count": len(self._languages)}
