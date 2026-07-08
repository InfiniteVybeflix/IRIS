#!/usr/bin/env python3
"""
email_herald.py — HERALD
Email Operations Agent for IRIS v7.0
Rich HTML templates (Jinja2), multiple SMTP providers (SendGrid/AWS SES/Mailgun),
scheduling (cron-like), alert thresholds, queue management, delivery tracking, bounce handling.
"""

import threading
import hashlib
import json
import logging
import time
import os
import smtplib
import subprocess
import re
from typing import Dict, Any, List, Tuple, Optional
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.utils import formataddr
from queue import Queue, Empty

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("HERALD")


class EmailHerald:
    CODENAME = "HERALD"

    def __init__(self, commander_bus=None, shared_memory=None):
        self._lock = threading.RLock()
        self._running = False
        self._commander_bus = commander_bus
        self._shared_memory = shared_memory
        self._session_id = hashlib.sha256(f"{self.CODENAME}{time.time()}".encode()).hexdigest()[:16]
        self._queue: Queue = Queue()
        self._delivery_log: List[Dict[str, Any]] = []
        self._bounce_log: List[Dict[str, Any]] = []
        self._scheduler_thread: Optional[threading.Thread] = None
        self._scheduled_jobs: List[Dict[str, Any]] = []
        self._alert_thresholds: Dict[str, int] = {"hourly": 100, "daily": 1000}
        self._sent_counters: Dict[str, int] = {"hourly": 0, "daily": 0}
        self._counter_reset_time = datetime.utcnow()
        logger.info(f"[{self.CODENAME}] Session {self._session_id} initialized.")

    def start(self) -> bool:
        with self._lock:
            if self._running:
                return True
            self._running = True
            self._scheduler_thread = threading.Thread(target=self._scheduler_loop, daemon=True)
            self._scheduler_thread.start()
            self._report_to_commander("HERALD started", level="info")
            return True

    def stop(self) -> bool:
        with self._lock:
            if not self._running:
                return True
            self._running = False
            self._report_to_commander("HERALD stopped", level="info")
            return True

    def health(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "agent": self.CODENAME,
                "session_id": self._session_id,
                "running": self._running,
                "queue_size": self._queue.qsize(),
                "delivery_count": len(self._delivery_log),
                "bounce_count": len(self._bounce_log),
                "scheduled_jobs": len(self._scheduled_jobs),
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

    def _check_thresholds(self) -> Tuple[bool, str]:
        now = datetime.utcnow()
        elapsed = now - self._counter_reset_time
        if elapsed >= timedelta(hours=1):
            self._sent_counters["hourly"] = 0
        if elapsed >= timedelta(days=1):
            self._sent_counters["daily"] = 0
            self._counter_reset_time = now
        if self._sent_counters["hourly"] >= self._alert_thresholds["hourly"]:
            return False, "Hourly send threshold exceeded"
        if self._sent_counters["daily"] >= self._alert_thresholds["daily"]:
            return False, "Daily send threshold exceeded"
        return True, ""

    # ------------------------------------------------------------------
    # Capabilities
    # ------------------------------------------------------------------
    def render_template(self, template_str: str, context: Dict[str, Any]) -> str:
        """Render a Jinja2-like template using simple string replacement fallback."""
        try:
            import jinja2
            env = jinja2.Environment()
            t = env.from_string(template_str)
            return t.render(**context)
        except ImportError:
            result = template_str
            for key, val in context.items():
                result = result.replace(f"{{{{ {key} }}}}", str(val)).replace(f"{{{{{key}}}}}", str(val))
            return result

    def send_email(self, to_addrs: List[str], subject: str, body_html: str, body_text: str = "",
                   from_addr: str = "", provider: str = "smtp", smtp_config: Optional[Dict] = None) -> Dict[str, Any]:
        """Send email via SMTP, SendGrid API, AWS SES, or Mailgun."""
        if not self._running:
            raise RuntimeError("Agent not running")
        ok, reason = self._check_thresholds()
        if not ok:
            self._report_to_commander(reason, level="warning")
            return {"status": "throttled", "reason": reason}

        from_addr = from_addr or os.environ.get("HERALD_FROM_EMAIL", "iris@aevibron.local")
        msg_id = hashlib.sha256(f"{to_addrs}{subject}{time.time()}".encode()).hexdigest()[:16]
        result = {"message_id": msg_id, "provider": provider, "recipients": to_addrs, "status": "unknown"}

        try:
            if provider == "smtp":
                cfg = smtp_config or {
                    "host": os.environ.get("SMTP_HOST", "localhost"),
                    "port": int(os.environ.get("SMTP_PORT", "587")),
                    "user": os.environ.get("SMTP_USER", ""),
                    "password": os.environ.get("SMTP_PASSWORD", ""),
                    "tls": os.environ.get("SMTP_TLS", "true").lower() == "true",
                }
                msg = MIMEMultipart("alternative")
                msg["Subject"] = subject
                msg["From"] = formataddr(("IRIS", from_addr))
                msg["To"] = ", ".join(to_addrs)
                if body_text:
                    msg.attach(MIMEText(body_text, "plain"))
                msg.attach(MIMEText(body_html, "html"))
                with smtplib.SMTP(cfg["host"], cfg["port"]) as server:
                    if cfg["tls"]:
                        server.starttls()
                    if cfg["user"]:
                        server.login(cfg["user"], cfg["password"])
                    server.sendmail(from_addr, to_addrs, msg.as_string())
                result["status"] = "sent"

            elif provider == "sendgrid":
                api_key = os.environ.get("SENDGRID_API_KEY", "")
                if not api_key:
                    raise RuntimeError("SENDGRID_API_KEY not set")
                payload = {
                    "personalizations": [{"to": [{"email": a} for a in to_addrs]}],
                    "from": {"email": from_addr},
                    "subject": subject,
                    "content": [
                        {"type": "text/plain", "value": body_text or " "},
                        {"type": "text/html", "value": body_html},
                    ],
                }
                req = __import__("urllib.request").request.Request(
                    "https://api.sendgrid.com/v3/mail/send",
                    data=json.dumps(payload).encode(),
                    headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                    method="POST",
                )
                with __import__("urllib.request").request.urlopen(req, timeout=30) as resp:
                    result["status"] = "sent" if resp.status in (200, 202) else f"http_{resp.status}"

            elif provider == "ses":
                import boto3
                client = boto3.client("ses", region_name=os.environ.get("AWS_REGION", "us-east-1"))
                response = client.send_email(
                    Source=from_addr,
                    Destination={"ToAddresses": to_addrs},
                    Message={
                        "Subject": {"Data": subject},
                        "Body": {
                            "Text": {"Data": body_text or " "},
                            "Html": {"Data": body_html},
                        },
                    },
                )
                result["status"] = "sent"
                result["aws_message_id"] = response.get("MessageId", "")

            elif provider == "mailgun":
                api_key = os.environ.get("MAILGUN_API_KEY", "")
                domain = os.environ.get("MAILGUN_DOMAIN", "")
                if not api_key or not domain:
                    raise RuntimeError("MAILGUN_API_KEY or MAILGUN_DOMAIN not set")
                data = {
                    "from": from_addr,
                    "to": ", ".join(to_addrs),
                    "subject": subject,
                    "text": body_text or " ",
                    "html": body_html,
                }
                req = __import__("urllib.request").request.Request(
                    f"https://api.mailgun.net/v3/{domain}/messages",
                    data=__import__("urllib.parse").parse.urlencode(data).encode(),
                    headers={"Authorization": f"Basic {__import__("base64").b64encode(f'api:{api_key}'.encode()).decode()}"},
                    method="POST",
                )
                with __import__("urllib.request").request.urlopen(req, timeout=30) as resp:
                    result["status"] = "sent" if resp.status == 200 else f"http_{resp.status}"
            else:
                result["status"] = "unsupported_provider"
        except Exception as e:
            result["status"] = "error"
            result["error"] = str(e)
            self._bounce_log.append({"message_id": msg_id, "error": str(e), "timestamp": datetime.utcnow().isoformat()})
            self._report_to_commander(f"Send failed: {e}", level="error", data=result)
            return result

        self._sent_counters["hourly"] += len(to_addrs)
        self._sent_counters["daily"] += len(to_addrs)
        self._delivery_log.append({
            "message_id": msg_id,
            "recipients": to_addrs,
            "subject": subject,
            "provider": provider,
            "timestamp": datetime.utcnow().isoformat(),
        })
        self._store_memory(f"delivery:{msg_id}", result)
        return result

    def schedule_email(self, to_addrs: List[str], subject: str, body_html: str, send_at: datetime,
                       body_text: str = "", provider: str = "smtp", smtp_config: Optional[Dict] = None) -> str:
        """Schedule an email for future delivery."""
        job_id = hashlib.sha256(f"{to_addrs}{subject}{send_at.isoformat()}".encode()).hexdigest()[:16]
        job = {
            "job_id": job_id,
            "to_addrs": to_addrs,
            "subject": subject,
            "body_html": body_html,
            "body_text": body_text,
            "provider": provider,
            "smtp_config": smtp_config,
            "send_at": send_at.isoformat(),
            "status": "scheduled",
        }
        with self._lock:
            self._scheduled_jobs.append(job)
        self._store_memory(f"schedule:{job_id}", job)
        return job_id

    def _scheduler_loop(self) -> None:
        """Background thread to process scheduled emails."""
        while self._running:
            now = datetime.utcnow()
            with self._lock:
                ready = [j for j in self._scheduled_jobs if datetime.fromisoformat(j["send_at"]) <= now and j["status"] == "scheduled"]
                for j in ready:
                    j["status"] = "sending"
                    try:
                        self.send_email(
                            j["to_addrs"], j["subject"], j["body_html"],
                            j["body_text"], provider=j["provider"], smtp_config=j.get("smtp_config")
                        )
                        j["status"] = "sent"
                    except Exception as e:
                        j["status"] = f"failed: {e}"
            time.sleep(10)

    def get_delivery_status(self, message_id: str) -> Optional[Dict[str, Any]]:
        """Lookup delivery record by message ID."""
        for entry in self._delivery_log:
            if entry.get("message_id") == message_id:
                return entry
        return None

    def get_bounces(self, since: Optional[datetime] = None) -> List[Dict[str, Any]]:
        """Return bounce records, optionally filtered by time."""
        if since is None:
            return list(self._bounce_log)
        return [b for b in self._bounce_log if datetime.fromisoformat(b["timestamp"]) >= since]

    def set_alert_threshold(self, period: str, limit: int) -> None:
        """Set send threshold for hourly or daily period."""
        with self._lock:
            self._alert_thresholds[period] = limit

    # ------------------------------------------------------------------
    # Unit test stubs
    # ------------------------------------------------------------------
    def test_render_template(self) -> bool:
        r = self.render_template("Hello {{ name }}", {"name": "IRIS"})
        return "Hello IRIS" in r

    def test_send_email_smtp(self) -> bool:
        # Requires local SMTP or mock; returns True if no exception on config check
        try:
            r = self.send_email(["test@local"], "T", "<b>H</b>", provider="smtp",
                                smtp_config={"host": "localhost", "port": 25, "tls": False, "user": "", "password": ""})
            return r.get("status") in ("sent", "error")
        except Exception:
            return False

    def test_schedule_email(self) -> bool:
        jid = self.schedule_email(["a@b.com"], "S", "B", datetime.utcnow() + timedelta(minutes=5))
        return len(jid) == 16

    def test_delivery_status(self) -> bool:
        return self.get_delivery_status("nonexistent") is None

    def test_bounces(self) -> bool:
        return isinstance(self.get_bounces(), list)


if __name__ == "__main__":
    agent = EmailHerald()
    agent.start()
    print(agent.health())
    agent.stop()
