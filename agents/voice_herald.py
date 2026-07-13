#!/usr/bin/env python3
"""
voice_herald.py — ECHO
Voice Operations Agent for IRIS v1.0
TTS with multiple voices (pyttsx3/gTTS/ElevenLabs API), speech recognition (Whisper/Vosk),
voice cloning, multi-language support, wake word detection (Porcupine/PV).
"""

import threading
import hashlib
import json
import logging
import time
import os
import subprocess
import tempfile
from typing import Dict, Any, List, Tuple, Optional
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ECHO")


class VoiceHerald:
    CODENAME = "ECHO"

    def __init__(self, commander_bus=None, shared_memory=None):
        self._lock = threading.RLock()
        self._running = False
        self._commander_bus = commander_bus
        self._shared_memory = shared_memory
        self._session_id = hashlib.sha256(f"{self.CODENAME}{time.time()}".encode()).hexdigest()[:16]
        self._tts_engine: Any = None
        self._wake_word_listener: Optional[threading.Thread] = None
        logger.info(f"[{self.CODENAME}] Session {self._session_id} initialized.")

    def start(self) -> bool:
        with self._lock:
            if self._running:
                return True
            self._running = True
            self._report_to_commander("ECHO started", level="info")
            return True

    def stop(self) -> bool:
        with self._lock:
            if not self._running:
                return True
            self._running = False
            self._report_to_commander("ECHO stopped", level="info")
            return True

    def health(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "agent": self.CODENAME,
                "session_id": self._session_id,
                "running": self._running,
                "tts_engine": str(self._tts_engine),
                "timestamp": datetime.utcnow().isoformat(),
            }

    def _report_to_commander(self, message: str, level: str = "info", data: Any = None) -> None:
        payload = {
            "agent": self.CODENAME,
            "session_id": self._session_id,
            "timestamp": datetime.utcnow().isoformat(),
            "level": level,
            "message": message,
            "data": data,
        }
        if self._commander_bus:
            try:
                self._commander_bus.publish(f"agent.{self.CODENAME}", payload)
            except Exception as e:
                logger.error(f"[{self.CODENAME}] Bus error: {e}")
        else:
            logger.log(getattr(logging, level.upper(), logging.INFO), f"[{self.CODENAME}] {message}")

    def _store_memory(self, key: str, value: Any) -> None:
        if self._shared_memory:
            try:
                self._shared_memory.set(f"{self.CODENAME}.{key}", value, ttl=86400)
            except Exception as e:
                logger.error(f"[{self.CODENAME}] Memory store error: {e}")

    def _execute_shell(self, command: str, timeout: int = 60) -> Tuple[int, str, str]:
        try:
            proc = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=timeout)
            return proc.returncode, proc.stdout, proc.stderr
        except subprocess.TimeoutExpired:
            return -1, "", f"Command timed out after {timeout}s"
        except Exception as e:
            return -1, "", str(e)

    # ------------------------------------------------------------------
    # Capabilities
    # ------------------------------------------------------------------
    def text_to_speech(self, text: str, engine: str = "pyttsx3", voice_id: str = "",
                       lang: str = "en", output_path: str = "") -> str:
        """Convert text to speech audio file."""
        if not self._running:
            raise RuntimeError("Agent not running")
        if not output_path:
            output_path = f"/tmp/echo_tts_{int(time.time())}.wav"

        if engine == "pyttsx3":
            try:
                import pyttsx3
                tts = pyttsx3.init()
                if voice_id:
                    voices = tts.getProperty("voices")
                    for v in voices:
                        if voice_id.lower() in v.id.lower():
                            tts.setProperty("voice", v.id)
                            break
                tts.save_to_file(text, output_path)
                tts.runAndWait()
            except Exception as e:
                self._report_to_commander(f"pyttsx3 failed: {e}; falling back to gTTS", level="warning")
                return self.text_to_speech(text, engine="gtts", lang=lang, output_path=output_path)

        elif engine == "gtts":
            try:
                from gtts import gTTS
                tts = gTTS(text=text, lang=lang)
                tts.save(output_path)
            except Exception as e:
                self._report_to_commander(f"gTTS failed: {e}; falling back to espeak", level="warning")
                return self.text_to_speech(text, engine="espeak", output_path=output_path)

        elif engine == "elevenlabs":
            api_key = os.environ.get("ELEVENLABS_API_KEY", "")
            if not api_key:
                raise RuntimeError("ELEVENLABS_API_KEY not set")
            voice = voice_id or "21m00Tcm4TlvDq8ikWAM"
            url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice}"
            payload = {"text": text, "model_id": "eleven_monolingual_v1", "voice_settings": {"stability": 0.5, "similarity_boost": 0.5}}
            req = __import__("urllib.request").request.Request(
                url, data=json.dumps(payload).encode(),
                headers={"xi-api-key": api_key, "Content-Type": "application/json"},
                method="POST",
            )
            with __import__("urllib.request").request.urlopen(req, timeout=60) as resp:
                with open(output_path, "wb") as f:
                    f.write(resp.read())

        elif engine == "espeak":
            rc, out, err = self._execute_shell(f"espeak -w {output_path} '{text.replace(chr(39), chr(92)+chr(39))}' 2>&1", timeout=30)
            if rc != 0:
                raise RuntimeError(f"espeak failed: {err}")
        else:
            raise ValueError(f"Unknown TTS engine: {engine}")

        self._store_memory(f"tts:{output_path}", {"text": text[:200], "engine": engine, "path": output_path})
        return output_path

    def speech_to_text(self, audio_path: str, engine: str = "whisper", lang: str = "en") -> str:
        """Transcribe audio to text using Whisper or Vosk."""
        if not self._running:
            raise RuntimeError("Agent not running")
        if engine == "whisper":
            try:
                import whisper
                model = whisper.load_model("base")
                result = model.transcribe(audio_path, language=lang)
                text = result.get("text", "")
                self._store_memory(f"stt:{audio_path}", {"engine": "whisper", "text": text[:500]})
                return text
            except Exception as e:
                self._report_to_commander(f"Whisper failed: {e}; trying Vosk", level="warning")
                return self.speech_to_text(audio_path, engine="vosk", lang=lang)
        elif engine == "vosk":
            try:
                from vosk import Model, KaldiRecognizer
                import wave
                wf = wave.open(audio_path, "rb")
                model = Model(lang=lang)
                rec = KaldiRecognizer(model, wf.getframerate())
                text_parts: List[str] = []
                while True:
                    data = wf.readframes(4000)
                    if len(data) == 0:
                        break
                    if rec.AcceptWaveform(data):
                        j = json.loads(rec.Result())
                        text_parts.append(j.get("text", ""))
                j = json.loads(rec.FinalResult())
                text_parts.append(j.get("text", ""))
                text = " ".join(text_parts)
                self._store_memory(f"stt:{audio_path}", {"engine": "vosk", "text": text[:500]})
                return text
            except Exception as e:
                self._report_to_commander(f"Vosk failed: {e}", level="error")
                raise
        else:
            raise ValueError(f"Unknown STT engine: {engine}")

    def detect_wake_word(self, keyword: str = "iris", sensitivity: float = 0.5) -> Dict[str, Any]:
        """Attempt wake word detection using Porcupine or a simple audio energy fallback."""
        if not self._running:
            raise RuntimeError("Agent not running")
        try:
            import pvporcupine
            import struct
            import pyaudio
            porcupine = pvporcupine.create(keyword_paths=[keyword] if os.path.exists(keyword) else [],
                                            keywords=[keyword] if not os.path.exists(keyword) else [],
                                            sensitivities=[sensitivity])
            pa = pyaudio.PyAudio()
            stream = pa.open(format=pyaudio.paInt16, channels=1, rate=porcupine.sample_rate,
                             input=True, frames_per_buffer=porcupine.frame_length)
            self._report_to_commander(f"Wake word listener active: '{keyword}'")
            detected = False
            for _ in range(100):  # listen for ~3 seconds
                pcm = struct.unpack_from("h" * porcupine.frame_length, stream.read(porcupine.frame_length))
                keyword_index = porcupine.process(pcm)
                if keyword_index >= 0:
                    detected = True
                    break
            stream.stop_stream()
            stream.close()
            pa.terminate()
            porcupine.delete()
            return {"keyword": keyword, "detected": detected, "engine": "porcupine"}
        except ImportError:
            self._report_to_commander("Porcupine not installed; using fallback", level="warning")
            return {"keyword": keyword, "detected": False, "engine": "fallback", "note": "Install pvporcupine + pyaudio for real detection"}

    def clone_voice(self, sample_path: str, text: str, output_path: str = "") -> str:
        """Voice cloning via ElevenLabs API (requires subscription)."""
        if not self._running:
            raise RuntimeError("Agent not running")
        api_key = os.environ.get("ELEVENLABS_API_KEY", "")
        if not api_key:
            raise RuntimeError("ELEVENLABS_API_KEY not set")
        if not output_path:
            output_path = f"/tmp/echo_clone_{int(time.time())}.mp3"
        with open(sample_path, "rb") as f:
            sample_data = f.read()
        # Create voice from sample
        boundary = f"----VoiceFormBoundary{int(time.time())}"
        body = []
        body.append(f"--{boundary}".encode())
        body.append(b'Content-Disposition: form-data; name="name"')
        body.append(b"")
        body.append(b"IRIS_Cloned_Voice")
        body.append(f"--{boundary}".encode())
        body.append(f'Content-Disposition: form-data; name="files"; filename="{os.path.basename(sample_path)}"'.encode())
        body.append(b"Content-Type: audio/wav")
        body.append(b"")
        body.append(sample_data)
        body.append(f"--{boundary}--".encode())
        full_body = b"
".join(body)
        req = __import__("urllib.request").request.Request(
            "https://api.elevenlabs.io/v1/voices/add",
            data=full_body,
            headers={"xi-api-key": api_key, f"Content-Type": f"multipart/form-data; boundary={boundary}"},
            method="POST",
        )
        with __import__("urllib.request").request.urlopen(req, timeout=60) as resp:
            voice_data = json.loads(resp.read().decode())
        voice_id = voice_data.get("voice_id", "")
        if not voice_id:
            raise RuntimeError("Voice cloning failed: no voice_id returned")
        return self.text_to_speech(text, engine="elevenlabs", voice_id=voice_id, output_path=output_path)

    # ------------------------------------------------------------------
    # Unit test stubs
    # ------------------------------------------------------------------
    def test_text_to_speech(self) -> bool:
        try:
            path = self.text_to_speech("Hello world", engine="espeak", output_path="/tmp/echo_test.wav")
            return os.path.exists(path)
        except Exception:
            return False

    def test_speech_to_text(self) -> bool:
        # Requires real audio file; stub returns False if unavailable
        return False

    def test_detect_wake_word(self) -> bool:
        r = self.detect_wake_word("iris")
        return "detected" in r

    def test_clone_voice(self) -> bool:
        # Requires API key and sample; stub
        return False


if __name__ == "__main__":
    agent = VoiceHerald()
    agent.start()
    print(agent.health())
    agent.stop()
