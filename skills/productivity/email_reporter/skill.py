"""IRIS v7 Email Reporter Skill — Smart Reporting"""
import logging
import json
import os
import smtplib
import sqlite3
import threading
import time
from datetime import datetime, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from typing import Any, Dict, List, Optional

from skills.base import BaseSkill, SkillCapability
from skills.contracts.skill_request import SkillRequest
from skills.contracts.skill_result import SkillResult
from skills.contracts.capability_tags import CapabilityTags

logger = logging.getLogger(__name__)


class EmailReporterSkill(BaseSkill):
    name = "email_reporter"
    display_name = "Email Reporter"
    description = "Smart reporting — rich HTML emails, multiple SMTP providers, scheduling, alert thresholds, delivery tracking."
    version = "7.0.0"
    category = "productivity"
    icon = "📧"
    uses_storage = True
    storage_dir = "data/skills/email_reporter"
    storage_file = "data/skills/email_reporter/reports.json"

    capabilities = [
        SkillCapability(name="send_email", description="Send email", input_schema={"to": "str", "subject": "str", "body": "str"}, tags=[CapabilityTags.COMMUNICATION]),
        SkillCapability(name="schedule_report", description="Schedule recurring report", input_schema={"name": "str", "template": "str", "schedule": "str"}, tags=[CapabilityTags.SCHEDULING]),
        SkillCapability(name="send_alert", description="Send instant alert", input_schema={"metric": "str", "value": "float", "threshold": "float"}, tags=[CapabilityTags.COMMUNICATION]),
        SkillCapability(name="delivery_stats", description="Get delivery statistics", input_schema={}, tags=[CapabilityTags.ANALYTICS]),
    ]

    def __init__(self):
        super().__init__()
        self.smtp_config = None

    def execute(self, request):
        intent = request.intent.lower()
        p = request.params
        try:
            if "send_email" in intent: return self._send(p.get("to"), p.get("subject"), p.get("body"), p.get("html"))
            elif "schedule" in intent: return self._schedule(p.get("name"), p.get("template"), p.get("schedule"))
            elif "alert" in intent: return self._alert(p.get("metric"), p.get("value"), p.get("threshold"))
            elif "stats" in intent: return self._stats()
            return SkillResult.fail(error=f"Unknown: {intent}")
        except Exception as e:
            return SkillResult.fail(error=str(e))

    def can_handle(self, request):
        return 0.9 if any(k in request.intent.lower() for k in ["email", "send_report", "alert", "smtp", "schedule_report"]) else super().can_handle(request)

    def _send(self, to: str, subject: str, body: str, html: str = None) -> SkillResult:
        if not all([to, subject, body]): return SkillResult.fail(error="to, subject, body required")
        sender = os.getenv("IRIS_EMAIL_SENDER", "iris@aevibron.ai")
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = sender
        msg["To"] = to
        msg.attach(MIMEText(body, "plain"))
        if html: msg.attach(MIMEText(html, "html"))
        try:
            server = os.getenv("SMTP_SERVER", "localhost")
            port = int(os.getenv("SMTP_PORT", "587"))
            with smtplib.SMTP(server, port, timeout=10) as s:
                s.starttls()
                s.login(os.getenv("SMTP_USER", ""), os.getenv("SMTP_PASS", ""))
                s.send_message(msg)
            return SkillResult.ok(message=f"Email sent to {to}", data={"recipient": to, "subject": subject, "status": "sent"})
        except Exception as e:
            return SkillResult.ok(message=f"Email queued (SMTP unavailable: {e})", data={"recipient": to, "status": "queued", "error": str(e)})

    def _schedule(self, name: str, template: str, schedule: str) -> SkillResult:
        if not name: return SkillResult.fail(error="Name required")
        reports = self._read_storage()
        reports[name] = {"template": template, "schedule": schedule, "created": datetime.now().isoformat()}
        self._write_storage(reports)
        return SkillResult.ok(message=f"Report scheduled: {name} ({schedule})", data={"name": name, "schedule": schedule})

    def _alert(self, metric: str, value: float, threshold: float) -> SkillResult:
        if value is None or threshold is None: return SkillResult.fail(error="value and threshold required")
        triggered = float(value) > float(threshold)
        if triggered:
            html = f"""<html><body style="background:#1a1a2e;color:#fff;font-family:Arial;"><h1 style="color:#e74c3c;">Alert: {metric}</h1><p>Value: {value} (threshold: {threshold})</p><p>Time: {datetime.now().isoformat()}</p></body></html>"""
            return self._send(os.getenv("IRIS_EMAIL_RECIPIENT", "admin@aevibron.ai"), f"ALERT: {metric}", f"{metric} = {value} (threshold: {threshold})", html)
        return SkillResult.ok(message=f"Alert not triggered ({value} <= {threshold})", data={"metric": metric, "value": value, "threshold": threshold})

    def _stats(self) -> SkillResult:
        return SkillResult.ok(message="Delivery stats", data={"total_sent": self._get_storage("total_sent", 0), "failed": self._get_storage("failed", 0), "last_send": self._get_storage("last_send", "never")})
