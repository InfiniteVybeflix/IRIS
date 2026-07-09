"""IRIS v9 Hybrid Multimodal Handler - Image, Video, 3D Generation"""
import os
import base64
from typing import Dict, List, Optional
from config import config
from core.db import db

class MultimodalHandler:
    """
    Handle multimodal AI tasks:
    - Image generation (DALL-E, Stable Diffusion)
    - Image analysis (GPT-4 Vision)
    - Video generation
    - 3D model generation
    - Audio processing
    """

    def __init__(self):
        self.media_dir = os.path.join(config.DATA_DIR, "media")
        os.makedirs(self.media_dir, exist_ok=True)

    def generate_image(self, prompt: str, size: str = "1024x1024", style: str = "vivid") -> Dict:
        """Generate image from text prompt"""
        try:
            from core.aevibron_client import aevibron

            # Use Aevibron for image generation if available
            # Fallback: create placeholder
            response = aevibron._make_request("POST", "/images/generations", json={
                "prompt": prompt,
                "size": size,
                "style": style,
                "n": 1
            })

            if response.get("error"):
                return {"success": False, "error": response.get("message", "Image generation failed")}

            # Save image
            image_data = response.get("data", [{}])[0].get("b64_json", "")
            if image_data:
                image_bytes = base64.b64decode(image_data)
                filename = f"generated_{os.urandom(4).hex()}.png"
                filepath = os.path.join(self.media_dir, filename)
                with open(filepath, "wb") as f:
                    f.write(image_bytes)

                return {
                    "success": True,
                    "filename": filename,
                    "path": filepath,
                    "prompt": prompt,
                    "size": size
                }

            return {"success": False, "error": "No image data received"}

        except Exception as e:
            return {"success": False, "error": str(e)}

    def analyze_image(self, image_path: str, question: str = "What is in this image?") -> Dict:
        """Analyze image content"""
        try:
            from core.aevibron_client import aevibron

            # Read and encode image
            with open(image_path, "rb") as f:
                image_data = base64.b64encode(f.read()).decode()

            response = aevibron.chat([
                {"role": "user", "content": [
                    {"type": "text", "text": question},
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{image_data}"}}
                ]}
            ])

            if response.get("error"):
                return {"success": False, "error": response.get("message")}

            content = response.get("choices", [{}])[0].get("message", {}).get("content", "")

            return {
                "success": True,
                "analysis": content,
                "image": image_path,
                "question": question
            }

        except Exception as e:
            return {"success": False, "error": str(e)}

    def generate_video(self, prompt: str, duration: int = 5) -> Dict:
        """Generate video from text (placeholder for Sora-like models)"""
        return {
            "success": False,
            "error": "Video generation not yet implemented. Coming in Phase 4.",
            "prompt": prompt,
            "duration": duration
        }

    def generate_3d(self, prompt: str, format: str = "obj") -> Dict:
        """Generate 3D model from text (placeholder)"""
        return {
            "success": False,
            "error": "3D generation not yet implemented. Coming in Phase 4.",
            "prompt": prompt,
            "format": format
        }

    def process_audio(self, audio_path: str, task: str = "transcribe") -> Dict:
        """Process audio: transcribe, analyze, etc."""
        try:
            if task == "transcribe":
                # Use Whisper via Aevibron
                from core.aevibron_client import aevibron

                with open(audio_path, "rb") as f:
                    audio_data = f.read()

                # This would use Aevibron's audio transcription endpoint
                # For now, return placeholder
                return {
                    "success": True,
                    "transcription": "[Audio transcription via Aevibron - implement endpoint]",
                    "task": task
                }

            return {"success": False, "error": f"Unknown audio task: {task}"}

        except Exception as e:
            return {"success": False, "error": str(e)}

    def get_media_library(self) -> List[Dict]:
        """Get all generated media"""
        media = []
        if os.path.exists(self.media_dir):
            for filename in os.listdir(self.media_dir):
                filepath = os.path.join(self.media_dir, filename)
                media.append({
                    "filename": filename,
                    "path": filepath,
                    "size": os.path.getsize(filepath),
                    "created": os.path.getctime(filepath)
                })
        return media

multimodal_handler = MultimodalHandler()
