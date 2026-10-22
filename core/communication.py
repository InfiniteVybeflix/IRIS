"""
Aevibron Agent Corps — Communication Protocol
Inter-agent messaging bus with async + sync support, persistence, and history.

Author: IRIS v1.0
"""

import json
import logging
import os
import threading
import time
import uuid
from collections import defaultdict
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set


class MessageBus:
    """
    MessageBus — The neural pathway of the Aevibron Agent Corps.

    Enables real-time, asynchronous communication between all agents.
    Supports directed messages, broadcasts, subscriptions, and persistent history.

    Features:
    - Thread-safe message dispatch
    - Agent subscription with callback-based delivery
    - Broadcast to all registered agents
    - Mission-scoped message history
    - Persistent storage to disk
    - Message filtering by type and priority

    Attributes:
        _subscribers (dict): Mapping of agent_name -> list of callback functions.
        _history (dict): Mapping of mission_id -> list of messages.
        _all_messages (list): Complete message log.
        _lock (threading.RLock): Thread-safe lock.
        _logger (logging.Logger): Logger instance.
        _persistence_path (str): Path for saving message history.
    """

    def __init__(self, persistence_path: Optional[str] = None):
        self._subscribers: Dict[str, List[Callable[[Dict[str, Any]], None]]] = defaultdict(list)
        self._history: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        self._all_messages: List[Dict[str, Any]] = []
        self._lock = threading.RLock()
        self._logger = logging.getLogger("Aevibron.MessageBus")
        self._logger.setLevel(logging.DEBUG)

        if not self._logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                "%(asctime)s | %(name)s | %(levelname)s | %(message)s"
            )
            handler.setFormatter(formatter)
            self._logger.addHandler(handler)

        if persistence_path is None:
            try:
                from config import config
                default_dir = os.path.join(config.DATA_DIR, "agents")
                os.makedirs(default_dir, exist_ok=True)
                persistence_path = os.path.join(default_dir, "message_bus.json")
            except Exception:
                persistence_path = os.path.join(os.getcwd(), "data", "agents", "message_bus.json")
                os.makedirs(os.path.dirname(persistence_path), exist_ok=True)
        self._persistence_path = persistence_path
        Path(self._persistence_path).parent.mkdir(parents=True, exist_ok=True)

        self._logger.info("[MessageBus] Neural pathway initialized.")

    def send(self, message: Dict[str, Any]) -> bool:
        """
        Send a directed message to one or more agents.

        Args:
            message: Dictionary containing:
                - from (str): Sender agent name
                - to (List[str]): Recipient agent names
                - mission_id (str): Mission context
                - type (str): Message type (finding, delegation, alert, status, etc.)
                - priority (str): Message priority
                - content (dict): Payload
                - timestamp (str): ISO timestamp

        Returns:
            bool: True if message was dispatched successfully.
        """
        try:
            # Ensure required fields
            if "message_id" not in message:
                message["message_id"] = str(uuid.uuid4())
            if "timestamp" not in message:
                message["timestamp"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

            recipients = message.get("to", [])
            if isinstance(recipients, str):
                recipients = [recipients]

            mission_id = message.get("mission_id", "global")

            with self._lock:
                self._all_messages.append(message)
                self._history[mission_id].append(message)

                # Keep history bounded
                if len(self._history[mission_id]) > 5000:
                    self._history[mission_id] = self._history[mission_id][-5000:]
                if len(self._all_messages) > 10000:
                    self._all_messages = self._all_messages[-10000:]

            # Dispatch to subscribers
            delivered = 0
            for recipient in recipients:
                callbacks = self._subscribers.get(recipient, [])
                for callback in callbacks:
                    try:
                        callback(message)
                        delivered += 1
                    except Exception as e:
                        self._logger.error(f"[MessageBus] Callback error for {recipient}: {e}")

            self._logger.debug(
                f"[MessageBus] Message {message['message_id']} delivered to {delivered}/{len(recipients)} recipients"
            )
            return True

        except Exception as e:
            self._logger.error(f"[MessageBus] Send failed: {e}", exc_info=True)
            return False

    def subscribe(self, agent_name: str, callback: Callable[[Dict[str, Any]], None]) -> None:
        """
        Subscribe an agent to receive messages.

        Args:
            agent_name: The agent's codename.
            callback: Function to call when a message is received.
        """
        with self._lock:
            if callback not in self._subscribers[agent_name]:
                self._subscribers[agent_name].append(callback)

        self._logger.info(f"[MessageBus] {agent_name} subscribed to message bus.")

    def unsubscribe(self, agent_name: str, callback: Callable[[Dict[str, Any]], None]) -> None:
        """
        Unsubscribe an agent from the message bus.

        Args:
            agent_name: The agent's codename.
            callback: The callback to remove.
        """
        with self._lock:
            if agent_name in self._subscribers:
                self._subscribers[agent_name] = [
                    cb for cb in self._subscribers[agent_name] if cb != callback
                ]

        self._logger.info(f"[MessageBus] {agent_name} unsubscribed from message bus.")

    def broadcast(self, message: Dict[str, Any]) -> None:
        """
        Broadcast a message to ALL registered agents.

        Args:
            message: The message dictionary to broadcast.
        """
        message["message_id"] = message.get("message_id", str(uuid.uuid4()))
        message["timestamp"] = message.get("timestamp", time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
        message["broadcast"] = True

        mission_id = message.get("mission_id", "global")

        with self._lock:
            self._all_messages.append(message)
            self._history[mission_id].append(message)

        # Deliver to all subscribers
        delivered_count = 0
        for agent_name, callbacks in list(self._subscribers.items()):
            for callback in callbacks:
                try:
                    callback(message)
                    delivered_count += 1
                except Exception as e:
                    self._logger.error(f"[MessageBus] Broadcast error for {agent_name}: {e}")

        self._logger.info(f"[MessageBus] Broadcast delivered to {delivered_count} callbacks across {len(self._subscribers)} agents.")

    def get_history(self, mission_id: str, limit: int = 100, message_type: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Retrieve message history for a mission.

        Args:
            mission_id: The mission identifier.
            limit: Maximum number of messages to return.
            message_type: Optional filter by message type.

        Returns:
            List[Dict]: Filtered message history.
        """
        with self._lock:
            messages = self._history.get(mission_id, [])

            if message_type:
                messages = [m for m in messages if m.get("type") == message_type]

            return messages[-limit:]

    def get_all_history(self, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Retrieve global message history.

        Args:
            limit: Maximum number of messages to return.

        Returns:
            List[Dict]: Recent messages across all missions.
        """
        with self._lock:
            return self._all_messages[-limit:]

    def get_conversation(self, agent_a: str, agent_b: str, mission_id: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Retrieve conversation history between two specific agents.

        Args:
            agent_a: First agent name.
            agent_b: Second agent name.
            mission_id: Optional mission filter.
            limit: Maximum messages to return.

        Returns:
            List[Dict]: Messages exchanged between the two agents.
        """
        with self._lock:
            if mission_id:
                messages = self._history.get(mission_id, [])
            else:
                messages = self._all_messages

            filtered = []
            for msg in messages:
                sender = msg.get("from", "")
                recipients = msg.get("to", [])
                if isinstance(recipients, str):
                    recipients = [recipients]

                # Check if this is a message between the two agents
                if (sender == agent_a and agent_b in recipients) or (sender == agent_b and agent_a in recipients):
                    filtered.append(msg)

            return filtered[-limit:]

    def persist(self) -> bool:
        """
        Save message history to disk for persistence across restarts.

        Returns:
            bool: True if persistence succeeded.
        """
        try:
            with self._lock:
                data = {
                    "all_messages": self._all_messages[-5000:],  # Keep last 5000
                    "history": {k: v[-1000:] for k, v in self._history.items()},  # Keep last 1000 per mission
                    "persisted_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                }

            with open(self._persistence_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, default=str)

            self._logger.info(f"[MessageBus] History persisted to {self._persistence_path}")
            return True

        except Exception as e:
            self._logger.error(f"[MessageBus] Persistence failed: {e}")
            return False

    def load(self) -> bool:
        """
        Load message history from disk.

        Returns:
            bool: True if load succeeded.
        """
        try:
            if not os.path.exists(self._persistence_path):
                self._logger.info("[MessageBus] No persistence file found. Starting fresh.")
                return False

            with open(self._persistence_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            with self._lock:
                self._all_messages = data.get("all_messages", [])
                self._history = defaultdict(list, data.get("history", {}))

            self._logger.info(f"[MessageBus] Loaded {len(self._all_messages)} messages from persistence.")
            return True

        except Exception as e:
            self._logger.error(f"[MessageBus] Load failed: {e}")
            return False

    def clear_history(self, mission_id: Optional[str] = None) -> None:
        """
        Clear message history.

        Args:
            mission_id: If provided, clear only that mission's history.
                       If None, clear ALL history.
        """
        with self._lock:
            if mission_id:
                if mission_id in self._history:
                    del self._history[mission_id]
                    self._logger.info(f"[MessageBus] Cleared history for mission {mission_id}")
            else:
                self._history.clear()
                self._all_messages.clear()
                self._logger.info("[MessageBus] Cleared all message history.")

    def get_stats(self) -> Dict[str, Any]:
        """
        Get message bus statistics.

        Returns:
            Dict: Statistics about messages, subscribers, and history.
        """
        with self._lock:
            return {
                "total_messages": len(self._all_messages),
                "active_missions": len(self._history),
                "subscribed_agents": len(self._subscribers),
                "total_subscriptions": sum(len(cbs) for cbs in self._subscribers.values()),
                "persistence_path": self._persistence_path,
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            }


__all__ = ["MessageBus"]


# Usage Example:
# bus = MessageBus()
# bus.subscribe("VAULT", lambda msg: print(f"VAULT received: {msg}"))
# bus.send({"from": "COMMANDER", "to": ["VAULT"], "mission_id": "m1", "type": "task", "priority": "high", "content": {"action": "design"}})
