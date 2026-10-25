"""IRIS v1 Vision Stream — Screen & Camera Capture for Real-time Analysis"""
import os
import base64
import threading
import time
from typing import Callable, Optional, Dict
from config import config

# Guard heavy imports — these require system libs (OpenCV needs libGL,
# pyautogui needs a display). On serverless (Vercel), these aren't available.
# The module still loads; methods that need cv2/pyautogui return clear errors.
try:
    import cv2
    HAS_CV2 = True
except ImportError:
    cv2 = None
    HAS_CV2 = False

try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    np = None
    HAS_NUMPY = False

class VisionStream:
    """
    Capture screen or camera feed for IRIS to analyze in real-time:
    - Screenshot capture
    - Camera feed (webcam / phone camera)
    - Screen recording
    - Real-time frame streaming to IRIS
    """

    def __init__(self):
        self.is_streaming = False
        self.stream_thread = None
        self.frame_callback: Optional[Callable] = None
        self.last_frame = None
        self.capture_source = "screen"  # "screen" or "camera"
        self.frame_interval = 2.0  # seconds between captures

    def set_frame_callback(self, callback: Callable):
        """Set callback for each captured frame."""
        self.frame_callback = callback

    def capture_screen(self) -> Optional[str]:
        """Capture screen and return base64 encoded image."""
        if not HAS_CV2 or not HAS_NUMPY:
            return None  # cv2/numpy not available (serverless)
        try:
            import pyautogui
            screenshot = pyautogui.screenshot()
            img_array = np.array(screenshot)
            img_rgb = cv2.cvtColor(img_array, cv2.COLOR_RGB2BGR)
            _, buffer = cv2.imencode('.jpg', img_rgb, [cv2.IMWRITE_JPEG_QUALITY, 70])
            return base64.b64encode(buffer).decode('utf-8')
        except ImportError:
            # Fallback: use PIL
            try:
                from PIL import ImageGrab
                screenshot = ImageGrab.grab()
                img_array = np.array(screenshot)
                img_rgb = cv2.cvtColor(img_array, cv2.COLOR_RGB2BGR)
                _, buffer = cv2.imencode('.jpg', img_rgb, [cv2.IMWRITE_JPEG_QUALITY, 70])
                return base64.b64encode(buffer).decode('utf-8')
            except Exception as e:
                print(f"Screen capture failed: {e}")
                return None

    def capture_camera(self, camera_id: int = 0) -> Optional[str]:
        """Capture from webcam and return base64 encoded image."""
        if not HAS_CV2:
            return None  # cv2 not available (serverless)
        try:
            cap = cv2.VideoCapture(camera_id)
            ret, frame = cap.read()
            cap.release()
            if ret:
                _, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 70])
                return base64.b64encode(buffer).decode('utf-8')
            return None
        except Exception as e:
            print(f"Camera capture failed: {e}")
            return None

    def start_stream(self, source: str = "screen", interval: float = 2.0):
        """Start continuous frame capture in background."""
        if self.is_streaming:
            return
        self.capture_source = source
        self.frame_interval = interval
        self.is_streaming = True
        self.stream_thread = threading.Thread(target=self._stream_loop, daemon=True)
        self.stream_thread.start()
        print(f"📹 Vision stream started: {source} every {interval}s")

    def stop_stream(self):
        """Stop continuous capture."""
        self.is_streaming = False
        if self.stream_thread:
            self.stream_thread.join(timeout=1)
        print("📹 Vision stream stopped")

    def _stream_loop(self):
        """Background loop for frame capture."""
        while self.is_streaming:
            try:
                if self.capture_source == "screen":
                    frame = self.capture_screen()
                else:
                    frame = self.capture_camera()

                if frame:
                    self.last_frame = frame
                    if self.frame_callback:
                        self.frame_callback(frame)

                time.sleep(self.frame_interval)
            except Exception as e:
                print(f"Stream error: {e}")
                time.sleep(1)

    def analyze_current_view(self, question: str = "What do you see?",
                             frame_b64: str = None,
                             transcript: str = "") -> Dict:
        """Send a frame to the configured vision model for analysis.

        frame_b64: base64 JPEG (with or without the data: URI prefix) captured
        by the browser from the live screen/camera stream. When omitted, the
        last server-side frame is used (only meaningful when self-hosted).
        transcript: optional live speech transcript to give the model context.
        """
        frame = frame_b64 or self.last_frame
        if not frame:
            return {"success": False,
                    "error": ("No frame available. Start the screen/camera stream first so a frame "
                              "can be captured, then analyze.")}

        # Accept full data URIs from the browser and strip the prefix.
        if frame.startswith("data:"):
            idx = frame.find("base64,")
            frame = frame[idx + 7:] if idx != -1 else frame

        try:
            from core.llm_router import llm_router, extract_content

            user_parts = [{"type": "text", "text": question}]
            if transcript:
                user_parts.append({"type": "text",
                                   "text": f"Live audio transcript for context:\n{transcript[-2000:]}"})
            user_parts.append({"type": "image_url",
                               "image_url": {"url": f"data:image/jpeg;base64,{frame}"}})
            messages = [
                {"role": "system", "content":
                    "You are IRIS, analyzing a live frame from the user's screen or camera. "
                    "Be concrete and specific about what is actually visible. If the frame is "
                    "unreadable, say exactly that."},
                {"role": "user", "content": user_parts},
            ]

            # Vision model name only applies to the Aevibron gateway; other
            # providers fall back to their own configured default model.
            model = None
            try:
                backend = llm_router.get_backend(None)
                if getattr(backend, "name", "") == "aevibron":
                    model = config.VISION_MODEL
            except Exception:
                model = config.VISION_MODEL

            response = llm_router.chat(messages, model=model)
            content = getattr(response, "content", "") or ""
            if content.startswith("[aevibron error") or content.startswith("[error") \
                    or "error HTTP" in content[:40]:
                return {"success": False, "error": content}
            if not content:
                return {"success": False, "error": "The vision model returned an empty answer."}
            return {"success": True, "analysis": content}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def get_last_frame_base64(self) -> Optional[str]:
        """Get the last captured frame as base64."""
        return self.last_frame

# Singleton
vision_stream = VisionStream()
