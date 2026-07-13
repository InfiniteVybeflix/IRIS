"""IRIS v1 Email Module — Secure email sending with Gmail/Resend"""
import os
import smtplib
import requests
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from datetime import datetime
from typing import Dict, List, Optional
from config import config

class EmailModule:
    """
    IRIS email capabilities:
    - Send emails via Gmail SMTP or Resend API
    - Log reports to admin email
    - Send attachments
    - HTML formatting
    """

    def __init__(self):
        self.sender = os.getenv("IRIS_EMAIL_SENDER", "")
        self.app_password = os.getenv("IRIS_EMAIL_APP_PASSWORD", "")
        self.recipient = os.getenv("IRIS_EMAIL_RECIPIENT", "")
        self.resend_key = os.getenv("IRIS_RESEND_API_KEY", "")

    def send_gmail(self, to: str, subject: str, body: str, html: bool = False, 
                   attachments: List[str] = None) -> Dict:
        """Send email via Gmail SMTP."""
        if not self.sender or not self.app_password:
            return {"success": False, "error": "Email credentials not configured in .env"}

        try:
            msg = MIMEMultipart()
            msg['From'] = self.sender
            msg['To'] = to
            msg['Subject'] = subject

            content_type = 'html' if html else 'plain'
            msg.attach(MIMEText(body, content_type))

            # Attach files
            if attachments:
                for filepath in attachments:
                    if os.path.exists(filepath):
                        with open(filepath, 'rb') as f:
                            part = MIMEBase('application', 'octet-stream')
                            part.set_payload(f.read())
                        encoders.encode_base64(part)
                        part.add_header('Content-Disposition', f'attachment; filename={os.path.basename(filepath)}')
                        msg.attach(part)

            server = smtplib.SMTP('smtp.gmail.com', 587)
            server.starttls()
            server.login(self.sender, self.app_password)
            server.send_message(msg)
            server.quit()

            return {"success": True, "message": f"Email sent to {to}", "timestamp": datetime.now().isoformat()}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def send_resend(self, to: str, subject: str, body: str, html: bool = False) -> Dict:
        """Send email via Resend API."""
        if not self.resend_key:
            return {"success": False, "error": "Resend API key not configured in .env"}

        try:
            headers = {"Authorization": f"Bearer {self.resend_key}", "Content-Type": "application/json"}
            payload = {
                "from": self.sender or "iris@aevibron.com",
                "to": [to],
                "subject": subject,
                "html" if html else "text": body
            }
            response = requests.post("https://api.resend.com/emails", json=payload, headers=headers, timeout=30)
            data = response.json()
            if response.status_code == 200:
                return {"success": True, "message": "Email sent via Resend", "id": data.get("id")}
            return {"success": False, "error": data.get("message", "Unknown error")}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def send_log_report(self, log_content: str, title: str = "IRIS Log Report") -> Dict:
        """Send log report to admin email."""
        if not self.recipient:
            return {"success": False, "error": "Recipient not configured"}

        html_body = f"""
        <h2>{title}</h2>
        <p><strong>Time:</strong> {datetime.now().isoformat()}</p>
        <p><strong>Status:</strong> IRIS v1 Active</p>
        <hr>
        <pre style="background:#f5f5f5;padding:15px;border-radius:8px;">{log_content}</pre>
        """

        # Try Resend first, fallback to Gmail
        if self.resend_key:
            return self.send_resend(self.recipient, title, html_body, html=True)
        return self.send_gmail(self.recipient, title, html_body, html=True)

    def send_alert(self, alert_type: str, message: str, priority: str = "normal") -> Dict:
        """Send priority alert."""
        subject = f"[{priority.upper()}] IRIS Alert: {alert_type}"
        body = f"""
Alert Type: {alert_type}
Priority: {priority}
Time: {datetime.now().isoformat()}

{message}
        """
        if self.resend_key:
            return self.send_resend(self.recipient, subject, body)
        return self.send_gmail(self.recipient, subject, body)

# Singleton
email_module = EmailModule()
