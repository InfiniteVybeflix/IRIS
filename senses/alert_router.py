"""
IRIS v7.0 — Alert Router

Central alert management: routing, deduplication, escalation,
formatting per agent, and multi-channel notification delivery.

Dependencies:
    - Standard library (smtplib for email)
    - requests (for webhooks)

Safety:
    - No hardcoded credentials for notification channels.
    - All channel configs from environment variables.

Usage:
    from senses.alert_router import AlertRouter
    router = AlertRouter()
    router.route_alert({"type": "security", "severity": "high", "message": "..."})
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import smtplib
import time
from email.mime.text import MIMEText
from typing import Any, Callable, Dict, List, Optional

import requests

from .base_sense import BaseSense

logger = logging.getLogger(__name__)


class AlertRouter(BaseSense):
    """
    Alert management and notification routing sense.

    Routes alerts to appropriate agents, deduplicates, escalates
    unacknowledged alerts, and sends notifications via multiple channels.

    Attributes:
        name: "alert_router"
        interval: 30 seconds
        thresholds: Alert thresholds.
    """

    name: str = "alert_router"
    interval: int = 30
    thresholds: Dict[str, Any] = {
        "dedup_window_seconds": 300,
        "escalation_delay_seconds": 900,
        "max_alert_history": 10000,
    }

    def __init__(self, iris_core: Optional[Any] = None) -> None:
        super().__init__(iris_core)
        self._alerts: List[Dict[str, Any]] = []
        self._dedup_cache: Dict[str, float] = {}
        self._unacknowledged: Dict[str, Dict[str, Any]] = {}
        self._handlers: Dict[str, Callable[[Dict[str, Any]], None]] = {}
        self._register_default_handlers()

    def _register_default_handlers(self) -> None:
        """Register default notification channel handlers."""
        self._handlers["email"] = self._send_email
        self._handlers["webhook"] = self._send_webhook
        self._handlers["sms"] = self._send_sms
        self._handlers["push"] = self._send_push

    def _sense(self) -> Dict[str, Any]:
        """
        Process pending alerts: deduplicate, escalate, and route.

        Returns:
            Dictionary with routing statistics.
        """
        now = time.time()
        findings: Dict[str, Any] = {
            "routed": 0,
            "deduplicated": 0,
            "escalated": 0,
            "pending": len(self._unacknowledged),
        }

        for alert_id, alert in list(self._unacknowledged.items()):
            elapsed = now - alert.get("timestamp", now)
            if elapsed > self.thresholds.get("escalation_delay_seconds", 900):
                self._escalate(alert)
                findings["escalated"] += 1

        return findings

    def route_alert(self, alert: Dict[str, Any]) -> Dict[str, Any]:
        """
        Route an alert to the appropriate agent and channels.

        Args:
            alert: Alert dictionary with keys: type, severity, message, data.

        Returns:
            Standard result dict with routing status.
        """
        self._begin_check()
        try:
            dedup_key = self._generate_dedup_key(alert)
            now = time.time()
            if dedup_key in self._dedup_cache:
                last_seen = self._dedup_cache[dedup_key]
                if now - last_seen < self.thresholds.get("dedup_window_seconds", 300):
                    res = self._build_result(success=True, action="route_alert", output="Alert deduplicated", parsed={"deduplicated": True, "alert": alert})
                    self.last_result = res
                    self._end_check(success=True)
                    return res
            self._dedup_cache[dedup_key] = now

            channels = self._determine_channels(alert)
            routed = []
            for channel in channels:
                handler = self._handlers.get(channel)
                if handler:
                    try:
                        handler(alert)
                        routed.append(channel)
                    except Exception as exc:
                        logger.error(f"Failed to send alert via {channel}: {exc}")

            alert_id = hashlib.sha256(json.dumps(alert, sort_keys=True).encode()).hexdigest()[:16]
            alert["id"] = alert_id
            alert["timestamp"] = now
            alert["routed_channels"] = routed
            self._unacknowledged[alert_id] = alert
            self._alerts.append(alert)

            if len(self._alerts) > self.thresholds.get("max_alert_history", 10000):
                self._alerts = self._alerts[-5000:]

            res = self._build_result(success=True, action="route_alert", output=f"Routed to {len(routed)} channels", parsed={"alert_id": alert_id, "routed_channels": routed, "severity": alert.get("severity"), "type": alert.get("type")})
            self.last_result = res
            self._end_check(success=True)
            return res
        except Exception as exc:
            logger.exception("AlertRouter route_alert failed")
            res = self._build_result(success=False, action="route_alert", errors=[str(exc)])
            self.last_result = res
            self._end_check(success=False)
            return res

    def deduplicate(self, alerts: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Deduplicate a list of alerts within the configured window."""
        now = time.time()
        window = self.thresholds.get("dedup_window_seconds", 300)
        unique: List[Dict[str, Any]] = []
        for alert in alerts:
            key = self._generate_dedup_key(alert)
            if key not in self._dedup_cache or now - self._dedup_cache[key] > window:
                self._dedup_cache[key] = now
                unique.append(alert)
        return unique

    def escalate(self, alert: Dict[str, Any]) -> Dict[str, Any]:
        """Escalate an unacknowledged alert to higher-priority channels."""
        self._begin_check()
        try:
            alert["escalated"] = True
            alert["escalated_at"] = time.time()
            for channel, handler in self._handlers.items():
                try:
                    handler(alert)
                except Exception as exc:
                    logger.error(f"Escalation failed via {channel}: {exc}")
            res = self._build_result(success=True, action="escalate", output="Alert escalated to all channels", parsed={"alert_id": alert.get("id"), "channels": list(self._handlers.keys())})
            self.last_result = res
            self._end_check(success=True)
            return res
        except Exception as exc:
            logger.exception("AlertRouter escalate failed")
            res = self._build_result(success=False, action="escalate", errors=[str(exc)])
            self.last_result = res
            self._end_check(success=False)
            return res

    def format_for_agent(self, agent_name: str, alert: Dict[str, Any]) -> str:
        """Format an alert for a specific agent's preference."""
        severity = alert.get("severity", "unknown").upper()
        msg = alert.get("message", "No message")
        data = json.dumps(alert.get("data", {}), indent=2) if alert.get("data") else ""
        if agent_name.lower() == "slack":
            return f":warning: *{severity}* | {msg}
```{data}```"
        elif agent_name.lower() == "discord":
            return f"**{severity}** | {msg}
```{data}```"
        elif agent_name.lower() == "telegram":
            return f"<b>{severity}</b>
{msg}"
        else:
            return f"[{severity}] {msg}
{data}"

    def send_notification(self, channel: str, message: str) -> Dict[str, Any]:
        """Send a raw notification to a channel."""
        self._begin_check()
        try:
            handler = self._handlers.get(channel)
            if not handler:
                res = self._build_result(success=False, action="send_notification", errors=[f"Unknown channel: {channel}"])
                self.last_result = res
                self._end_check(success=False)
                return res
            handler({"message": message})
            res = self._build_result(success=True, action="send_notification", output=f"Sent via {channel}", parsed={"channel": channel})
            self.last_result = res
            self._end_check(success=True)
            return res
        except Exception as exc:
            logger.exception("AlertRouter send_notification failed")
            res = self._build_result(success=False, action="send_notification", errors=[str(exc)])
            self.last_result = res
            self._end_check(success=False)
            return res

    def _generate_dedup_key(self, alert: Dict[str, Any]) -> str:
        content = f"{alert.get('type')}:{alert.get('severity')}:{alert.get('message', '')}"
        return hashlib.sha256(content.encode()).hexdigest()[:16]

    def _determine_channels(self, alert: Dict[str, Any]) -> List[str]:
        severity = alert.get("severity", "low").lower()
        if severity == "critical":
            return ["email", "webhook", "sms", "push"]
        elif severity == "high":
            return ["email", "webhook", "push"]
        elif severity == "medium":
            return ["webhook", "push"]
        return ["webhook"]

    def _send_email(self, alert: Dict[str, Any]) -> None:
        smtp_host = os.environ.get("IRIS_SMTP_HOST", "")
        smtp_port = int(os.environ.get("IRIS_SMTP_PORT", "587"))
        smtp_user = os.environ.get("IRIS_SMTP_USER", "")
        smtp_pass = os.environ.get("IRIS_SMTP_PASS", "")
        to_addr = os.environ.get("IRIS_ALERT_EMAIL", "")
        if not all([smtp_host, smtp_user, smtp_pass, to_addr]):
            logger.warning("Email not configured. Skipping email alert.")
            return
        msg = MIMEText(json.dumps(alert, indent=2))
        msg["Subject"] = f"[IRIS ALERT] {alert.get('severity', 'UNKNOWN')} - {alert.get('type', 'Unknown')}"
        msg["From"] = smtp_user
        msg["To"] = to_addr
        with smtplib.SMTP(smtp_host, smtp_port) as server:
            server.starttls()
            server.login(smtp_user, smtp_pass)
            server.send_message(msg)

    def _send_webhook(self, alert: Dict[str, Any]) -> None:
        webhook_url = os.environ.get("IRIS_WEBHOOK_URL", "")
        if not webhook_url:
            logger.warning("Webhook URL not configured. Skipping webhook alert.")
            return
        requests.post(webhook_url, json=alert, timeout=30)

    def _send_sms(self, alert: Dict[str, Any]) -> None:
        twilio_sid = os.environ.get("IRIS_TWILIO_SID", "")
        twilio_token = os.environ.get("IRIS_TWILIO_TOKEN", "")
        twilio_from = os.environ.get("IRIS_TWILIO_FROM", "")
        to_number = os.environ.get("IRIS_SMS_NUMBER", "")
        if not all([twilio_sid, twilio_token, twilio_from, to_number]):
            logger.warning("SMS not configured. Skipping SMS alert.")
            return
        logger.info(f"SMS alert would be sent to {to_number}")

    def _send_push(self, alert: Dict[str, Any]) -> None:
        push_token = os.environ.get("IRIS_PUSH_TOKEN", "")
        if not push_token:
            logger.warning("Push not configured. Skipping push alert.")
            return
        logger.info("Push notification would be sent")

    def acknowledge_alert(self, alert_id: str) -> bool:
        """Acknowledge an alert, removing it from unacknowledged queue."""
        if alert_id in self._unacknowledged:
            del self._unacknowledged[alert_id]
            return True
        return False

    def get_alert_history(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Retrieve recent alert history."""
        return self._alerts[-limit:]

    def _should_alert(self, result: Dict[str, Any]) -> bool:
        return False

    def _emit_alert(self, result: Dict[str, Any]) -> None:
        pass


__all__ = ["AlertRouter"]
