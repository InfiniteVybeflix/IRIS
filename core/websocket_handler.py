"""IRIS v9 Hybrid WebSocket Handler - Real-Time Voice & Face Streaming"""
import asyncio
import json
import base64
import websockets
from datetime import datetime
from typing import Dict, Set
from config import config
from core.db import db

class WebSocketHandler:
    """
    Real-time WebSocket connections for:
    - Live voice streaming (bidirectional)
    - Face emotion updates
    - Real-time chat
    - Status updates
    """

    def __init__(self):
        self.clients: Set[websockets.WebSocketServerProtocol] = set()
        self.authenticated_clients: Dict[str, websockets.WebSocketServerProtocol] = {}

    async def register(self, websocket: websockets.WebSocketServerProtocol):
        """Register new client connection"""
        self.clients.add(websocket)
        db.log("INFO", "websocket", f"Client connected: {websocket.remote_address}")

    async def unregister(self, websocket: websockets.WebSocketServerProtocol):
        """Unregister client"""
        self.clients.discard(websocket)
        # Remove from authenticated
        for sid, ws in list(self.authenticated_clients.items()):
            if ws == websocket:
                del self.authenticated_clients[sid]
        db.log("INFO", "websocket", f"Client disconnected: {websocket.remote_address}")

    async def handle_client(self, websocket: websockets.WebSocketServerProtocol, path: str):
        """Handle client connection lifecycle"""
        await self.register(websocket)
        try:
            async for message in websocket:
                await self.process_message(websocket, message)
        except websockets.exceptions.ConnectionClosed:
            pass
        finally:
            await self.unregister(websocket)

    async def process_message(self, websocket: websockets.WebSocketServerProtocol, message: str):
        """Process incoming WebSocket message"""
        try:
            data = json.loads(message)
            msg_type = data.get("type")

            if msg_type == "auth":
                await self.handle_auth(websocket, data)

            elif msg_type == "chat":
                await self.handle_chat(websocket, data)

            elif msg_type == "voice_start":
                await self.handle_voice_start(websocket, data)

            elif msg_type == "voice_data":
                await self.handle_voice_data(websocket, data)

            elif msg_type == "emotion_request":
                await self.handle_emotion_request(websocket, data)

            elif msg_type == "ping":
                await websocket.send(json.dumps({"type": "pong", "timestamp": datetime.now().isoformat()}))

        except json.JSONDecodeError:
            await websocket.send(json.dumps({"type": "error", "message": "Invalid JSON"}))
        except Exception as e:
            db.log("ERROR", "websocket", f"Message processing error: {e}")

    async def handle_auth(self, websocket: websockets.WebSocketServerProtocol, data: Dict):
        """Authenticate WebSocket connection"""
        session_id = data.get("session_id")
        from modules.security import security_manager

        if security_manager.validate_session(session_id):
            self.authenticated_clients[session_id] = websocket
            await websocket.send(json.dumps({"type": "auth_success", "message": "Authenticated"}))

            # Send initial emotion
            from modules.consciousness import consciousness
            emotion = consciousness.get_emotional_state()
            await websocket.send(json.dumps({"type": "emotion", "data": emotion}))
        else:
            await websocket.send(json.dumps({"type": "auth_failed", "message": "Invalid session"}))

    async def handle_chat(self, websocket: websockets.WebSocketServerProtocol, data: Dict):
        """Handle real-time chat via WebSocket"""
        message = data.get("message", "")
        session_id = data.get("session_id")

        # Send thinking status
        await websocket.send(json.dumps({
            "type": "status",
            "phase": "thinking",
            "message": "IRIS is thinking...",
            "progress": 10
        }))

        # Process through orchestrator
        from core.orchestrator import orchestrator
        for update in orchestrator.process(message, session_id):
            await websocket.send(json.dumps({
                "type": "update",
                "data": update
            }))

        # Update emotion based on result
        from modules.consciousness import consciousness
        consciousness.on_event("user_message", {"message": message})
        emotion = consciousness.get_emotional_state()
        await websocket.send(json.dumps({"type": "emotion", "data": emotion}))

    async def handle_voice_start(self, websocket: websockets.WebSocketServerProtocol, data: Dict):
        """Start voice streaming session"""
        await websocket.send(json.dumps({
            "type": "voice_status",
            "status": "ready",
            "message": "Voice streaming ready. Send audio data."
        }))

    async def handle_voice_data(self, websocket: websockets.WebSocketServerProtocol, data: Dict):
        """Process voice audio data"""
        audio_data = data.get("audio", "")
        # Decode base64 audio
        try:
            audio_bytes = base64.b64decode(audio_data)
            # Process with speech-to-text (placeholder for now)
            # In production, use Whisper or similar

            await websocket.send(json.dumps({
                "type": "voice_transcription",
                "text": "[Voice processing not yet implemented - use text chat]"
            }))
        except Exception as e:
            await websocket.send(json.dumps({"type": "error", "message": f"Voice processing error: {e}"}))

    async def handle_emotion_request(self, websocket: websockets.WebSocketServerProtocol, data: Dict):
        """Send current emotion state to client"""
        from modules.consciousness import consciousness
        emotion = consciousness.get_emotional_state()
        await websocket.send(json.dumps({"type": "emotion", "data": emotion}))

    async def broadcast(self, message: Dict):
        """Broadcast message to all authenticated clients"""
        if self.authenticated_clients:
            message_json = json.dumps(message)
            await asyncio.gather(
                *[client.send(message_json) for client in self.authenticated_clients.values()],
                return_exceptions=True
            )

    async def send_to_session(self, session_id: str, message: Dict):
        """Send message to specific session"""
        websocket = self.authenticated_clients.get(session_id)
        if websocket:
            await websocket.send(json.dumps(message))

    def start_server(self, host: str = "0.0.0.0", port: int = 8765):
        """Start WebSocket server"""
        start_server = websockets.serve(self.handle_client, host, port)
        asyncio.get_event_loop().run_until_complete(start_server)
        db.log("INFO", "websocket", f"WebSocket server started on ws://{host}:{port}")

websocket_handler = WebSocketHandler()
