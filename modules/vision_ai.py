"""IRIS v1 Vision AI — Multi-Modal Image/Video Understanding
Analyzes images, screenshots, and video frames with detailed descriptions.
"""
import base64
import logging
from typing import Dict, List, Optional
from core.aevibron_client import aevibron
from config import config

logger = logging.getLogger(__name__)

class VisionAI:
    """
    Advanced vision capabilities:
    - Image description and analysis
    - Screenshot understanding (UI elements, errors, etc.)
    - Video frame analysis
    - OCR (text extraction from images)
    - Object detection description
    - Code extraction from screenshots
    """

    def __init__(self):
        self.supported_formats = ["png", "jpg", "jpeg", "gif", "webp", "bmp"]

    def analyze_image(self, image_path: str = None, image_base64: str = None, 
                      question: str = "What do you see?", detail: str = "high") -> Dict:
        """
        Analyze an image with a specific question.

        Args:
            image_path: Path to local image file
            image_base64: Base64-encoded image string
            question: What to ask about the image
            detail: "low", "high", or "auto"
        """
        try:
            # Get image data
            if image_path:
                with open(image_path, "rb") as f:
                    image_data = base64.b64encode(f.read()).decode("utf-8")
            elif image_base64:
                image_data = image_base64
            else:
                return {"success": False, "error": "No image provided"}

            # Build message with image
            messages = [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": question},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/png;base64,{image_data}",
                                "detail": detail
                            }
                        }
                    ]
                }
            ]

            response = aevibron.chat(
                messages=messages,
                model=config.VISION_MODEL,
                temperature=0.5,
                max_tokens=2000
            )

            if response.get("error"):
                return {"success": False, "error": response.get("message", "Vision API error")}

            content = response.get("choices", [{}])[0].get("message", {}).get("content", "")

            return {
                "success": True,
                "analysis": content,
                "question": question,
                "detail_level": detail
            }
        except Exception as e:
            logger.error(f"Image analysis failed: {e}")
            return {"success": False, "error": str(e)}

    def describe_screenshot(self, image_path: str = None, image_base64: str = None) -> Dict:
        """Specialized screenshot analysis for UI debugging."""
        question = """Analyze this screenshot in detail:
1. What application/website is shown?
2. What UI elements are visible? (buttons, forms, menus, etc.)
3. Are there any error messages or warnings?
4. What is the current state of the interface?
5. Are there any visual bugs or issues?
6. What action should the user take next?"""

        return self.analyze_image(image_path, image_base64, question, detail="high")

    def extract_code_from_image(self, image_path: str = None, image_base64: str = None) -> Dict:
        """Extract and format code from a screenshot."""
        question = """Extract all code visible in this image. Format it properly with correct indentation and syntax. If it's a specific programming language, identify it."""

        result = self.analyze_image(image_path, image_base64, question, detail="high")
        if result.get("success"):
            # Try to extract code blocks
            import re
            code_blocks = re.findall(r"```(?:\w+)?\n(.*?)```", result["analysis"], re.DOTALL)
            result["code_blocks"] = code_blocks
            result["code_count"] = len(code_blocks)
        return result

    def analyze_video_frame(self, frame_base64: str, timestamp: float = 0, 
                           context: str = "") -> Dict:
        """Analyze a single video frame."""
        question = f"""Analyze this video frame at timestamp {timestamp}s.
Context: {context if context else "No additional context"}

Describe:
1. What is happening in this frame?
2. Key objects and people
3. Text visible in the frame
4. Any notable events or actions"""

        return self.analyze_image(image_base64=frame_base64, question=question)

    def compare_images(self, image1_base64: str, image2_base64: str) -> Dict:
        """Compare two images and describe differences."""
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "Compare these two images. Describe all differences, changes, or similarities."},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/png;base64,{image1_base64}", "detail": "high"}
                    },
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/png;base64,{image2_base64}", "detail": "high"}
                    }
                ]
            }
        ]

        try:
            response = aevibron.chat(
                messages=messages,
                model=config.VISION_MODEL,
                temperature=0.3,
                max_tokens=2000
            )

            content = response.get("choices", [{}])[0].get("message", {}).get("content", "")
            return {"success": True, "comparison": content}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def generate_image_description(self, image_path: str = None, image_base64: str = None,
                                   style: str = "detailed") -> Dict:
        """Generate various styles of image descriptions."""
        styles = {
            "detailed": "Describe this image in rich detail including colors, composition, mood, and subject matter.",
            "technical": "Provide a technical analysis of this image including resolution assessment, color palette, composition rules, and photographic quality.",
            "creative": "Write a creative, evocative description of this image as if for a novel or art gallery.",
            "social": "Write a catchy social media caption for this image with relevant hashtags.",
            "alt_text": "Write concise, accessible alt text for this image (under 125 characters if possible)."
        }

        question = styles.get(style, styles["detailed"])
        return self.analyze_image(image_path, image_base64, question)

    def detect_ui_issues(self, screenshot_path: str = None, screenshot_base64: str = None) -> Dict:
        """Detect UI/UX issues in a screenshot."""
        question = """Analyze this UI screenshot for potential issues:
1. Accessibility problems (contrast, font size, missing labels)
2. Layout issues (alignment, spacing, responsiveness)
3. Usability concerns (confusing navigation, unclear CTAs)
4. Performance indicators (loading states, empty states)
5. Security concerns (sensitive data exposure)
6. Recommendations for improvement"""

        return self.analyze_image(screenshot_path, screenshot_base64, question, detail="high")


# Singleton
vision_ai = VisionAI()
