"""Image Editor Skill — Basic image editing: crop, resize, filter."""
import logging
import io
import base64
from typing import Dict, Any
from skills import BaseSkill
logger = logging.getLogger(__name__)

class ImageEditorSkill(BaseSkill):
    def __init__(self):
        super().__init__(name="image_editor", category="media", capabilities=["image_editor"])

    def execute(self, capability: str, params: Dict[str, Any]) -> Dict[str, Any]:
        method = params.get("method", "resize")
        if method == "resize": return self.resize(params)
        elif method == "crop": return self.crop(params)
        elif method == "filter": return self.apply_filter(params)
        elif method == "info": return self.info(params)
        return {"error": f"Unknown method: {method}"}

    def _open_image(self, path: str):
        from PIL import Image
        return Image.open(path)

    def _save_b64(self, img) -> str:
        buf = io.BytesIO()
        img.save(buf, format='PNG')
        return base64.b64encode(buf.getvalue()).decode()

    def resize(self, params: Dict[str, Any]) -> Dict[str, Any]:
        path = params.get("path", "")
        w, h = params.get("width", 0), params.get("height", 0)
        try:
            img = self._open_image(path)
            img = img.resize((w, h))
            return {"success": True, "base64": self._save_b64(img), "new_size": [w, h]}
        except ImportError:
            return {"success": False, "error": "Pillow required"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def crop(self, params: Dict[str, Any]) -> Dict[str, Any]:
        path = params.get("path", "")
        box = params.get("box", [0, 0, 100, 100])
        try:
            img = self._open_image(path)
            img = img.crop(tuple(box))
            return {"success": True, "base64": self._save_b64(img), "crop_box": box}
        except ImportError:
            return {"success": False, "error": "Pillow required"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def apply_filter(self, params: Dict[str, Any]) -> Dict[str, Any]:
        path = params.get("path", "")
        filter_name = params.get("filter", "grayscale")
        try:
            from PIL import ImageFilter, ImageOps
            img = self._open_image(path)
            if filter_name == "grayscale":
                img = ImageOps.grayscale(img)
            elif filter_name == "blur":
                img = img.filter(ImageFilter.GaussianBlur(radius=5))
            elif filter_name == "sharpen":
                img = img.filter(ImageFilter.SHARPEN)
            elif filter_name == "edge":
                img = img.filter(ImageFilter.FIND_EDGES)
            return {"success": True, "base64": self._save_b64(img), "filter": filter_name}
        except ImportError:
            return {"success": False, "error": "Pillow required"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def info(self, params: Dict[str, Any]) -> Dict[str, Any]:
        path = params.get("path", "")
        try:
            img = self._open_image(path)
            return {"success": True, "format": img.format, "size": img.size, "mode": img.mode}
        except Exception as e:
            return {"success": False, "error": str(e)}
