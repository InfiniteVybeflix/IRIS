"""Email Reporter Skill — Send formatted emails, reports, and alerts."""

import logging
import smtplib
import json
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from typing import Dict, Any, List
from datetime import datetime
from skills import BaseSkill

logger = logging.getLogger(__name__)


class EmailReporterSkill(BaseSkill):
    """Email sending, report generation, and alerting via SMTP."""

    def __init__(self):
        super().__init__(name="email_reporter", category="productivity", capabilities=["email_report"])
        self._smtp_host = ""
        self._smtp_port = 587
        self._smtp_user = ""
        self._smtp_pass = ""
        self._sent_count = 0

    def execute(self, capability: str, params: Dict[str, Any]) -> Dict[str, Any]:
        method = params.get("method", "send_email")
        if method == "send_email":
            return self.send_email(params)
        elif method == "send_digest":
            return self.send_digest(params)
        elif method == "send_alert":
            return self.send_alert(params)
        return {"error": f"Unknown method: {method}"}

    def send_email(self, params: Dict[str, Any]) -> Dict[str, Any]:
        to = params.get("to", "")
        subject = params.get("subject", "IRIS Notification")
        body = params.get("body", "")
        body_html = params.get("body_html", "")
        cc = params.get("cc", [])
        bcc = params.get("bcc", [])
        attachments = params.get("attachments", [])
        smtp_host = params.get("smtp_host", self._smtp_host)
        smtp_port = params.get("smtp_port", self._smtp_port)
        smtp_user = params.get("smtp_user", self._smtp_user)
        smtp_pass = params.get("smtp_pass", self._smtp_pass)
        if not to:
            return {"success": False, "error": "No recipient provided"}
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = smtp_user or "iris@aevibron.com"
        msg["To"] = to if isinstance(to, str) else ", ".join(to)
        if cc:
            msg["Cc"] = cc if isinstance(cc, str) else ", ".join(cc)
        if body:
            msg.attach(MIMEText(body, "plain"))
        if body_html:
            msg.attach(MIMEText(body_html, "html"))
        for att in attachments:
            part = MIMEBase("application", "octet-stream")
            if isinstance(att, dict):
                part.set_payload(att.get("content", b""))
                encoders.encode_base64(part)
                part.add_header("Content-Disposition", f'attachment; filename="{att.get("filename", "file")}"')
            msg.attach(part)
        try:
            with smtplib.SMTP(smtp_host, smtp_port, timeout=30) as server:
                if smtp_user and smtp_pass:
                    server.starttls()
                    server.login(smtp_user, smtp_pass)
                recipients = ([to] if isinstance(to, str) else to) + ([cc] if isinstance(cc, str) else cc) + ([bcc] if isinstance(bcc, str) else bcc)
                server.sendmail(msg["From"], recipients, msg.as_string())
            self._sent_count += 1
            return {"success": True, "to": to, "subject": subject, "sent": True, "timestamp": datetime.utcnow().isoformat()}
        except Exception as e:
            return {"success": False, "error": str(e), "to": to, "subject": subject}

    def send_digest(self, params: Dict[str, Any]) -> Dict[str, Any]:
        items = params.get("items", [])
        to = params.get("to", "")
        title = params.get("title", "Daily Digest")
        body_lines = [f"# {title}\n", f"Generated: {datetime.utcnow().isoformat()}\n", f"Total items: {len(items)}\n\n---\n"]
        for i, item in enumerate(items, 1):
            body_lines.append(f"\n{i}. {item.get('title', 'Untitled')}\n{item.get('summary', '')}\n")
        body = "\n".join(body_lines)
        return self.send_email({"to": to, "subject": title, "body": body, **{k: v for k, v in params.items() if k not in ("items", "title")}})

    def send_alert(self, params: Dict[str, Any]) -> Dict[str, Any]:
        severity = params.get("severity", "info")
        message = params.get("message", "")
        component = params.get("component", "IRIS")
        emoji = {"critical": "[CRITICAL]", "high": "[HIGH]", "warning": "[WARN]", "info": "[INFO]"}.get(severity, "[INFO]")
        subject = f"{emoji} {component} Alert: {message[:50]}"
        body = f"Severity: {severity.upper()}\nComponent: {component}\nMessage: {message}\nTime: {datetime.utcnow().isoformat()}"
        return self.send_email({"to": params.get("to", ""), "subject": subject, "body": body, **{k: v for k, v in params.items() if k not in ("severity", "message", "component")}})
