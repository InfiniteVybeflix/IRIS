"""IRIS v1 Image Generation — Aevibron Imagine API
Supports: Aevibron Imagine V1 (high detail) and Imagine Flash (fast drafts)
Endpoint: POST https://aevibron-gateway.vercel.app/api/v1/images
"""
import requests
import json
import base64
import os
import logging
from typing import Dict, Optional, List
from config import config

logger = logging.getLogger(__name__)

class ImageGenerationClient:
    """Client for Aevibron Imagine image generation API."""

    MODELS = {
        "imagine_v1": "Aevibron Imagine V1",
        "imagine_flash": "Aevibron Imagine Flash"
    }

    def __init__(self):
        self.base_url = config.AEVIBRON_BASE_URL.rstrip("/")
        self.api_key = config.AEVIBRON_API_KEY
        self.access_token = config.AEVIBRON_ACCESS_TOKEN
        self.session = requests.Session()
        self.session.headers.update({
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
            "X-IRIS-Token": self.access_token
        })

    def generate(self, prompt: str, model: str = "imagine_v1", size: str = "1024x1024",
                 quality: str = "standard", style: str = "vivid", n: int = 1,
                 response_format: str = "url") -> Dict:
        """
        Generate images using Aevibron Imagine.

        Args:
            prompt: Text description of the image
            model: "imagine_v1" (high detail) or "imagine_flash" (fast)
            size: "1024x1024", "1024x1792", "1792x1024"
            quality: "standard" or "hd"
            style: "vivid" or "natural"
            n: Number of images (1-4)
            response_format: "url" or "b64_json"
        """
        payload = {
            "model": self.MODELS.get(model, self.MODELS["imagine_v1"]),
            "prompt": prompt,
            "n": min(n, 4),
            "size": size,
            "quality": quality,
            "style": style,
            "response_format": response_format
        }

        try:
            response = self.session.post(
                f"{self.base_url}/images",
                json=payload,
                timeout=120
            )
            response.raise_for_status()
            data = response.json()

            # Normalize response
            images = []
            for item in data.get("data", []):
                if response_format == "url":
                    images.append({"url": item.get("url"), "revised_prompt": item.get("revised_prompt", prompt)})
                else:
                    images.append({"b64_json": item.get("b64_json"), "revised_prompt": item.get("revised_prompt", prompt)})

            return {
                "success": True,
                "images": images,
                "model": model,
                "prompt": prompt,
                "created": data.get("created")
            }
        except requests.exceptions.Timeout:
            logger.error("Image generation timed out")
            return {"success": False, "error": "Generation timed out. Try Imagine Flash for faster results."}
        except requests.exceptions.HTTPError as e:
            logger.error(f"Image generation HTTP error: {e}")
            return {"success": False, "error": f"Gateway error: {response.status_code}", "details": response.text[:200]}
        except Exception as e:
            logger.error(f"Image generation failed: {e}")
            return {"success": False, "error": str(e)}

    def generate_variation(self, image_path: str, n: int = 1, size: str = "1024x1024") -> Dict:
        """Generate variations of an existing image."""
        try:
            with open(image_path, "rb") as f:
                image_data = base64.b64encode(f.read()).decode("utf-8")

            payload = {
                "image": image_data,
                "n": min(n, 4),
                "size": size
            }

            response = self.session.post(
                f"{self.base_url}/images/variations",
                json=payload,
                timeout=120
            )
            response.raise_for_status()
            data = response.json()

            return {
                "success": True,
                "images": [{"url": item.get("url")} for item in data.get("data", [])],
                "created": data.get("created")
            }
        except Exception as e:
            logger.error(f"Variation generation failed: {e}")
            return {"success": False, "error": str(e)}

    def edit_image(self, image_path: str, mask_path: str, prompt: str, n: int = 1, size: str = "1024x1024") -> Dict:
        """Edit an image with a mask and prompt."""
        try:
            with open(image_path, "rb") as f:
                image_data = base64.b64encode(f.read()).decode("utf-8")
            with open(mask_path, "rb") as f:
                mask_data = base64.b64encode(f.read()).decode("utf-8")

            payload = {
                "image": image_data,
                "mask": mask_data,
                "prompt": prompt,
                "n": min(n, 4),
                "size": size
            }

            response = self.session.post(
                f"{self.base_url}/images/edits",
                json=payload,
                timeout=120
            )
            response.raise_for_status()
            data = response.json()

            return {
                "success": True,
                "images": [{"url": item.get("url")} for item in data.get("data", [])],
                "created": data.get("created")
            }
        except Exception as e:
            logger.error(f"Image edit failed: {e}")
            return {"success": False, "error": str(e)}

    def quick_generate(self, prompt: str, fast: bool = False) -> Dict:
        """Quick generate with sensible defaults."""
        model = "imagine_flash" if fast else "imagine_v1"
        return self.generate(prompt, model=model, n=1, response_format="url")


# Singleton
image_generation = ImageGenerationClient()

# Backwards-compat alias
ImageGeneration = ImageGenerationClient
