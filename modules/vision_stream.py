"""IRIS v1 Vision Stream — Screen & Camera Capture for Real-time Analysis"""
import os
import cv2
import numpy as np
import base64
import threading
import time
from typing import Callable, Optional, Dict
from config import config

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

    def analyze_current_view(self, question: str = "What do you see?") -> Dict:
        """Send current frame to IRIS for analysis."""
        if not self.last_frame:
            return {"success": False, "error": "No frame captured yet"}

        try:
            from core.aevibron_client import aevibron
            messages = [
                {"role": "system", "content": "You are IRIS analyzing a live image. Describe what you see in detail."},
                {"role": "user", "content": [
                    {"type": "text", "text": question},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{self.last_frame}"}}
                ]}
            ]
            response = aevibron.chat(messages, model=config.VISION_MODEL)
            if response.get("error"):
                return {"success": False, "error": response.get("message")}
            content = response.get("choices", [{}])[0].get("message", {}).get("content", "")
            return {"success": True, "analysis": content}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def get_last_frame_base64(self) -> Optional[str]:
        """Get the last captured frame as base64."""
        return self.last_frame

# Singleton
vision_stream = VisionStream()
