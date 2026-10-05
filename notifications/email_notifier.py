"""Email notifier — SMTP-based email alerts."""
from __future__ import annotations
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import List, Optional

from ..core.logging_config import get_logger
from .channels import NotificationChannel

logger = get_logger("notifications.email")


class EmailNotifier(NotificationChannel):
    """Send email alerts via SMTP."""

    name = "email"

    def __init__(self, smtp_host: str, smtp_port: int, username: str, password: str,
                 recipients: List[str], use_tls: bool = True):
        self.smtp_host = smtp_host
        self.smtp_port = smtp_port
        self.username = username
        self.password = password
        self.recipients = recipients
        self.use_tls = use_tls

    def send(self, title: str, message: str, priority: str = "info") -> bool:
        if not self.recipients:
            return False
        try:
            msg = MIMEMultipart()
            msg["From"] = self.username
            msg["To"] = ", ".join(self.recipients)
            msg["Subject"] = f"[XAUUSD Bot] {title}"
            msg.attach(MIMEText(message, "plain"))
            with smtplib.SMTP(self.smtp_host, self.smtp_port, timeout=20) as server:
                if self.use_tls:
                    server.starttls()
                server.login(self.username, self.password)
                server.send_message(msg)
            return True
        except Exception as exc:  # noqa: BLE001
            logger.error("Email send failed: %s", exc)
            return False
