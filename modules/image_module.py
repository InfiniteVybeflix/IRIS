"""IRIS v1 Image Module — Background removal, processing, generation"""
import os
import requests
import base64
from io import BytesIO
from typing import Dict, Optional
from PIL import Image

class ImageModule:
    """
    IRIS image capabilities:
    - Remove backgrounds (remove.bg API)
    - Image enhancement
    - Format conversion
    - Resize/crop
    - Base64 encoding for AI analysis
    """

    def __init__(self):
        self.remove_bg_key = os.getenv("IRIS_REMOVEBG_API_KEY", "")

    def remove_background(self, image_path: str, output_path: str = None) -> Dict:
        """Remove background from image using remove.bg API."""
        if not self.remove_bg_key:
            return {"success": False, "error": "Remove.bg API key not configured in .env"}

        if not os.path.exists(image_path):
            return {"success": False, "error": "Image file not found"}

        try:
            with open(image_path, 'rb') as f:
                response = requests.post(
                    "https://api.remove.bg/v1.0/removebg",
                    files={"image_file": f},
                    data={"size": "auto"},
                    headers={"X-Api-Key": self.remove_bg_key},
                    timeout=30
                )

            if response.status_code == 200:
                if not output_path:
                    output_path = image_path.replace(".", "_nobg.")
                with open(output_path, 'wb') as f:
                    f.write(response.content)
                return {"success": True, "output_path": output_path, "message": "Background removed"}

            error_data = response.json()
            return {"success": False, "error": error_data.get("errors", [{}])[0].get("title", "Unknown error")}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def remove_background_base64(self, base64_image: str) -> Dict:
        """Remove background from base64 image."""
        if not self.remove_bg_key:
            return {"success": False, "error": "Remove.bg API key not configured"}

        try:
            image_data = base64.b64decode(base64_image)
            response = requests.post(
                "https://api.remove.bg/v1.0/removebg",
                files={"image_file": ("image.png", BytesIO(image_data), "image/png")},
                data={"size": "auto"},
                headers={"X-Api-Key": self.remove_bg_key},
                timeout=30
            )

            if response.status_code == 200:
                result_base64 = base64.b64encode(response.content).decode('utf-8')
                return {"success": True, "image_base64": result_base64}
            return {"success": False, "error": "Background removal failed"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def resize_image(self, image_path: str, width: int, height: int, output_path: str = None) -> Dict:
        """Resize image."""
        try:
            with Image.open(image_path) as img:
                resized = img.resize((width, height), Image.LANCZOS)
                if not output_path:
                    output_path = image_path
                resized.save(output_path)
                return {"success": True, "output_path": output_path, "size": (width, height)}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def convert_format(self, image_path: str, target_format: str = "png", output_path: str = None) -> Dict:
        """Convert image format."""
        try:
            with Image.open(image_path) as img:
                if not output_path:
                    base = os.path.splitext(image_path)[0]
                    output_path = f"{base}.{target_format.lower()}"
                img.save(output_path, format=target_format.upper())
                return {"success": True, "output_path": output_path, "format": target_format}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def image_to_base64(self, image_path: str) -> str:
        """Convert image to base64 string."""
        with open(image_path, "rb") as f:
            return base64.b64encode(f.read()).decode('utf-8')

    def base64_to_image(self, base64_string: str, output_path: str) -> Dict:
        """Save base64 string to image file."""
        try:
            image_data = base64.b64decode(base64_string)
            with open(output_path, "wb") as f:
                f.write(image_data)
            return {"success": True, "output_path": output_path}
        except Exception as e:
            return {"success": False, "error": str(e)}

# Singleton
image_module = ImageModule()
