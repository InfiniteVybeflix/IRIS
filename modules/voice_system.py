"""IRIS v1 Hybrid Voice System — Live Mode with 3D Face"""
import os
import asyncio
import tempfile
from pathlib import Path
from typing import Optional, Dict
from config import config
from core.db import db

try:
    import edge_tts
except ImportError:
    edge_tts = None

class VoiceSystem:
    """
    Text-to-speech with Edge-TTS.
    Live mode: WebSocket streaming for real-time conversation.
    3D Face: Animated face with expressions.
    """

    def __init__(self):
        self.voice = config.EDGE_TTS_VOICE
        self.temp_dir = os.path.join(config.DATA_DIR, "voice_temp")
        os.makedirs(self.temp_dir, exist_ok=True)
        self.current_emotion = "neutral"

    async def speak(self, text: str, emotion: str = "neutral") -> Dict:
        """Convert text to speech and return audio file path"""
        try:
            self.current_emotion = emotion

            # Adjust voice based on emotion
            voice = self._select_voice(emotion)

            # Generate audio
            communicate = edge_tts.Communicate(text, voice)

            # Save to temp file
            temp_file = os.path.join(self.temp_dir, f"iris_{hash(text)}.mp3")
            await communicate.save(temp_file)

            return {
                "success": True,
                "audio_path": temp_file,
                "text": text,
                "emotion": emotion,
                "voice": voice
            }
        except Exception as e:
            db.log("ERROR", "voice_system", f"TTS failed: {e}")
            return {"success": False, "error": str(e)}

    def _select_voice(self, emotion: str) -> str:
        """Select voice based on emotion"""
        voices = {
            "neutral": config.EDGE_TTS_VOICE,
            "happy": "en-US-JennyNeural",
            "sad": "en-US-BrandonNeural",
            "excited": "en-US-AriaNeural",
            "thinking": "en-US-GuyNeural",
            "concerned": "en-US-SoniaNeural",
            "celebrating": "en-US-JennyNeural"
        }
        return voices.get(emotion, config.EDGE_TTS_VOICE)

    async def speak_stream(self, text_stream):
        """Stream text-to-speech for real-time conversation"""
        # For WebSocket live mode
        buffer = ""
        for chunk in text_stream:
            buffer += chunk
            # When we hit a sentence boundary, speak it
            if any(buffer.endswith(end) for end in ['.', '!', '?', '\n']):
                if buffer.strip():
                    result = await self.speak(buffer.strip())
                    yield result
                buffer = ""

        # Speak remaining buffer
        if buffer.strip():
            result = await self.speak(buffer.strip())
            yield result

    def get_face_html(self) -> str:
        """Get the 3D face HTML for live mode"""
        return self._generate_face_html()

    def _generate_face_html(self) -> str:
        """Generate Three.js 3D face HTML"""
        return '''<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>IRIS Face</title>
    <style>
        body { margin: 0; overflow: hidden; background: #0a0a1a; }
        #canvas-container { width: 100vw; height: 100vh; }
        .status { position: absolute; bottom: 20px; left: 50%; transform: translateX(-50%);
                  color: #00ff88; font-family: monospace; font-size: 14px; }
    </style>
</head>
<body>
    <div id="canvas-container"></div>
    <div class="status" id="status">IRIS is online</div>

    <script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"></script>
    <script>
        // IRIS 3D Face
        const scene = new THREE.Scene();
        const camera = new THREE.PerspectiveCamera(75, window.innerWidth / window.innerHeight, 0.1, 1000);
        const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
        renderer.setSize(window.innerWidth, window.innerHeight);
        renderer.setClearColor(0x0a0a1a, 1);
        document.getElementById('canvas-container').appendChild(renderer.domElement);

        // Lighting
        const ambientLight = new THREE.AmbientLight(0x404040, 0.5);
        scene.add(ambientLight);

        const pointLight = new THREE.PointLight(0x00ff88, 1, 100);
        pointLight.position.set(5, 5, 5);
        scene.add(pointLight);

        const backLight = new THREE.PointLight(0x0088ff, 0.5, 100);
        backLight.position.set(-5, 5, -5);
        scene.add(backLight);

        // Face Group
        const faceGroup = new THREE.Group();
        scene.add(faceGroup);

        // Head (sphere)
        const headGeometry = new THREE.SphereGeometry(2, 32, 32);
        const headMaterial = new THREE.MeshPhongMaterial({ 
            color: 0x1a1a3a, 
            emissive: 0x0a0a2a,
            shininess: 100,
            transparent: true,
            opacity: 0.9
        });
        const head = new THREE.Mesh(headGeometry, headMaterial);
        faceGroup.add(head);

        // Eyes
        const eyeGeometry = new THREE.SphereGeometry(0.3, 16, 16);
        const eyeMaterial = new THREE.MeshPhongMaterial({ 
            color: 0x00ff88, 
            emissive: 0x00ff88,
            emissiveIntensity: 0.5
        });

        const leftEye = new THREE.Mesh(eyeGeometry, eyeMaterial);
        leftEye.position.set(-0.8, 0.3, 1.7);
        faceGroup.add(leftEye);

        const rightEye = new THREE.Mesh(eyeGeometry, eyeMaterial);
        rightEye.position.set(0.8, 0.3, 1.7);
        faceGroup.add(rightEye);

        // Eye pupils
        const pupilGeometry = new THREE.SphereGeometry(0.15, 16, 16);
        const pupilMaterial = new THREE.MeshBasicMaterial({ color: 0x000000 });

        const leftPupil = new THREE.Mesh(pupilGeometry, pupilMaterial);
        leftPupil.position.set(-0.8, 0.3, 1.9);
        faceGroup.add(leftPupil);

        const rightPupil = new THREE.Mesh(pupilGeometry, pupilMaterial);
        rightPupil.position.set(0.8, 0.3, 1.9);
        faceGroup.add(rightPupil);

        // Mouth
        const mouthGeometry = new THREE.TorusGeometry(0.5, 0.1, 8, 16, Math.PI);
        const mouthMaterial = new THREE.MeshPhongMaterial({ 
            color: 0x00ff88, 
            emissive: 0x00ff88,
            emissiveIntensity: 0.3
        });
        const mouth = new THREE.Mesh(mouthGeometry, mouthMaterial);
        mouth.position.set(0, -0.8, 1.7);
        mouth.rotation.x = Math.PI;
        faceGroup.add(mouth);

        // Energy rings
        const ringGeometry = new THREE.TorusGeometry(3, 0.05, 8, 64);
        const ringMaterial = new THREE.MeshBasicMaterial({ 
            color: 0x00ff88, 
            transparent: true, 
            opacity: 0.3 
        });
        const ring1 = new THREE.Mesh(ringGeometry, ringMaterial);
        faceGroup.add(ring1);

        const ring2 = new THREE.Mesh(ringGeometry, ringMaterial.clone());
        ring2.rotation.x = Math.PI / 2;
        faceGroup.add(ring2);

        // Particles
        const particlesGeometry = new THREE.BufferGeometry();
        const particlesCount = 500;
        const posArray = new Float32Array(particlesCount * 3);

        for(let i = 0; i < particlesCount * 3; i++) {
            posArray[i] = (Math.random() - 0.5) * 20;
        }

        particlesGeometry.setAttribute('position', new THREE.BufferAttribute(posArray, 3));
        const particlesMaterial = new THREE.PointsMaterial({
            size: 0.05,
            color: 0x00ff88,
            transparent: true,
            opacity: 0.6
        });
        const particles = new THREE.Points(particlesGeometry, particlesMaterial);
        scene.add(particles);

        camera.position.z = 6;

        // Emotion states
        let currentEmotion = 'neutral';
        let blinkTimer = 0;
        let isBlinking = false;

        function setEmotion(emotion) {
            currentEmotion = emotion;
            const status = document.getElementById('status');

            switch(emotion) {
                case 'thinking':
                    eyeMaterial.emissive.setHex(0x0088ff);
                    eyeMaterial.color.setHex(0x0088ff);
                    status.textContent = 'IRIS is thinking...';
                    status.style.color = '#0088ff';
                    break;
                case 'happy':
                    eyeMaterial.emissive.setHex(0x00ff00);
                    eyeMaterial.color.setHex(0x00ff00);
                    mouth.scale.y = 1.5;
                    status.textContent = 'IRIS is happy!';
                    status.style.color = '#00ff00';
                    break;
                case 'concerned':
                    eyeMaterial.emissive.setHex(0xff8800);
                    eyeMaterial.color.setHex(0xff8800);
                    status.textContent = 'IRIS is concerned...';
                    status.style.color = '#ff8800';
                    break;
                case 'celebrating':
                    eyeMaterial.emissive.setHex(0xff00ff);
                    eyeMaterial.color.setHex(0xff00ff);
                    status.textContent = 'IRIS is celebrating!';
                    status.style.color = '#ff00ff';
                    break;
                default: // neutral
                    eyeMaterial.emissive.setHex(0x00ff88);
                    eyeMaterial.color.setHex(0x00ff88);
                    mouth.scale.y = 1;
                    status.textContent = 'IRIS is online';
                    status.style.color = '#00ff88';
            }
        }

        // Listen for emotion changes from parent
        window.addEventListener('message', (e) => {
            if (e.data && e.data.emotion) {
                setEmotion(e.data.emotion);
            }
        });

        // Animation loop
        function animate() {
            requestAnimationFrame(animate);

            const time = Date.now() * 0.001;

            // Gentle head movement
            faceGroup.rotation.y = Math.sin(time * 0.5) * 0.1;
            faceGroup.rotation.x = Math.sin(time * 0.3) * 0.05;

            // Ring animation
            ring1.rotation.z += 0.01;
            ring2.rotation.y += 0.01;

            // Particle animation
            particles.rotation.y = time * 0.05;

            // Blinking
            blinkTimer += 0.016;
            if (blinkTimer > 3 + Math.random() * 2) {
                isBlinking = true;
                blinkTimer = 0;
            }

            if (isBlinking) {
                leftEye.scale.y = Math.max(0.1, leftEye.scale.y - 0.1);
                rightEye.scale.y = Math.max(0.1, rightEye.scale.y - 0.1);
                if (leftEye.scale.y <= 0.1) {
                    isBlinking = false;
                }
            } else {
                leftEye.scale.y = Math.min(1, leftEye.scale.y + 0.1);
                rightEye.scale.y = Math.min(1, rightEye.scale.y + 0.1);
            }

            // Thinking animation
            if (currentEmotion === 'thinking') {
                headMaterial.emissiveIntensity = 0.3 + Math.sin(time * 3) * 0.2;
            }

            renderer.render(scene, camera);
        }

        animate();

        // Resize handler
        window.addEventListener('resize', () => {
            camera.aspect = window.innerWidth / window.innerHeight;
            camera.updateProjectionMatrix();
            renderer.setSize(window.innerWidth, window.innerHeight);
        });
    </script>
</body>
</html>'''

    def get_emotion_for_state(self, state: str) -> str:
        """Map agent state to emotion"""
        states = {
            "observing": "thinking",
            "thinking": "thinking",
            "planning": "thinking",
            "working": "neutral",
            "verifying": "thinking",
            "reflecting": "thinking",
            "complete": "happy",
            "error": "concerned",
            "recovering": "concerned"
        }
        return states.get(state, "neutral")

# Singleton
voice_system = VoiceSystem()
