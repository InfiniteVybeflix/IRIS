"""OCR Skill — Extract text from images using pytesseract."""
import logging
from typing import Dict, Any
from skills import BaseSkill
logger = logging.getLogger(__name__)

class OcrSkill(BaseSkill):
    def __init__(self):
        super().__init__(name="ocr", category="utilities", capabilities=["ocr"])

    def execute(self, capability: str, params: Dict[str, Any]) -> Dict[str, Any]:
        method = params.get("method", "extract")
        if method == "extract": return self.extract(params)
        return {"error": f"Unknown method: {method}"}

    def extract(self, params: Dict[str, Any]) -> Dict[str, Any]:
        image_path = params.get("image_path", "")
        if not image_path: return {"success": False, "error": "No image path provided"}
        try:
            import pytesseract
            from PIL import Image
            img = Image.open(image_path)
            text = pytesseract.image_to_string(img)
            return {"success": True, "text": text, "word_count": len(text.split()), "image_path": image_path}
        except ImportError:
            return {"success": False, "error": "pytesseract and Pillow required. Install: pip install pytesseract Pillow"}
        except Exception as e:
            return {"success": False, "error": str(e)}
