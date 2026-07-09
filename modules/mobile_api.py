"""IRIS v9 Hybrid Mobile API - Backend for React Native / Flutter"""
import os
import json
from datetime import datetime
from typing import Dict, List, Optional
from config import config
from core.db import db

class MobileAPI:
    """
    Mobile-optimized API endpoints:
    - Push notifications
    - Offline sync
    - Battery-efficient updates
    - Mobile-specific UI components
    - Biometric auth
    - Quick actions
    """

    def __init__(self):
        self.push_tokens = {}
        self.offline_queue = []

    def register_push_token(self, user_id: str, token: str, platform: str = "fcm") -> bool:
        """Register device for push notifications"""
        self.push_tokens[user_id] = {
            "token": token,
            "platform": platform,
            "registered_at": datetime.now().isoformat()
        }
        return True

    def send_push_notification(self, user_id: str, title: str, body: str, data: Dict = None) -> bool:
        """Send push notification to mobile device"""
        device = self.push_tokens.get(user_id)
        if not device:
            return False

        # In production, integrate with FCM/APNs
        # For now, log it
        db.log("INFO", "mobile_api", f"Push to {user_id}: {title} - {body}")

        # Store notification in DB for sync
        db.save_episode(
            f"Push notification: {title}",
            context=json.dumps({"body": body, "data": data}),
            emotion="info"
        )

        return True

    def sync_offline_data(self, user_id: str, pending_actions: List[Dict]) -> Dict:
        """Sync offline actions from mobile device"""
        results = []

        for action in pending_actions:
            action_type = action.get("type")

            if action_type == "chat_message":
                # Process queued chat message
                from core.orchestrator import orchestrator
                for update in orchestrator.process(action.get("message"), action.get("session_id")):
                    if update.get("final"):
                        results.append({"action_id": action.get("id"), "status": "completed", "result": update})
                        break

            elif action_type == "document_upload":
                # Process queued document
                from skills.productivity.documentation import document_processor
                result = document_processor.process_upload(
                    action.get("file_path"),
                    action.get("original_name")
                )
                results.append({"action_id": action.get("id"), "status": "completed" if result.get("success") else "failed", "result": result})

            elif action_type == "voice_note":
                # Process voice note
                results.append({"action_id": action.get("id"), "status": "queued", "message": "Voice processing pending"})

            else:
                results.append({"action_id": action.get("id"), "status": "unknown_type"})

        return {
            "success": True,
            "synced": len(results),
            "results": results
        }

    def get_quick_actions(self) -> List[Dict]:
        """Get quick actions for mobile home screen"""
        return [
            {
                "id": "quick_chat",
                "title": "Quick Chat",
                "icon": "chat",
                "action": "open_chat",
                "shortcut": "iris_chat"
            },
            {
                "id": "quick_voice",
                "title": "Voice Mode",
                "icon": "mic",
                "action": "open_voice",
                "shortcut": "iris_voice"
            },
            {
                "id": "quick_project",
                "title": "New Project",
                "icon": "code",
                "action": "create_project",
                "shortcut": "iris_project"
            },
            {
                "id": "quick_chess",
                "title": "Play Chess",
                "icon": "chess",
                "action": "open_chess",
                "shortcut": "iris_chess"
            }
        ]

    def get_mobile_dashboard(self) -> Dict:
        """Get mobile-optimized dashboard data"""
        # Get recent activity
        recent_tasks = db.get_episodes(limit=5)

        # Get stats
        conn = db.get_connection()
        cursor = conn.execute("SELECT COUNT(*) as total FROM conversations")
        total_messages = cursor.fetchone()[0]

        cursor = conn.execute("SELECT COUNT(*) as total FROM documents")
        total_docs = cursor.fetchone()[0]

        cursor = conn.execute("SELECT COUNT(*) as total FROM tasks WHERE status = 'completed'")
        completed_tasks = cursor.fetchone()[0]
        conn.close()

        return {
            "greeting": f"Hello {config.OWNER_ALIAS}!",
            "stats": {
                "messages": total_messages,
                "documents": total_docs,
                "tasks_completed": completed_tasks
            },
            "recent_activity": recent_tasks,
            "quick_actions": self.get_quick_actions(),
            "iris_status": "online",
            "unread_notifications": 0
        }

    def handle_biometric_auth(self, user_id: str, biometric_data: str, auth_type: str = "fingerprint") -> Dict:
        """Handle biometric authentication from mobile"""
        from modules.security import security_manager

        # Verify using device fingerprint
        if auth_type == "fingerprint":
            success = security_manager.verify_device_fingerprint(biometric_data)
        elif auth_type == "face":
            # Face recognition would use specialized library
            success = True  # Placeholder
        else:
            success = False

        if success:
            session_id = security_manager.create_session(user_id)
            return {"success": True, "session_id": session_id, "message": "Biometric auth successful"}

        return {"success": False, "error": "Biometric verification failed"}

mobile_api = MobileAPI()
