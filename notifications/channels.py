"""Notification channels — abstract base + implementations."""
from __future__ import annotations
import json
import urllib.request
from abc import ABC, abstractmethod
from typing import Dict, Optional

from core.logging_config import get_logger

logger = get_logger("notifications.channels")


class NotificationChannel(ABC):
    """Base class for notification delivery channels."""

    name: str = "base"

    @abstractmethod
    def send(self, title: str, message: str, priority: str = "info") -> bool:
        ...


class ConsoleChannel(NotificationChannel):
    name = "console"

    def send(self, title: str, message: str, priority: str = "info") -> bool:
        print(f"[{priority.upper()}] {title}\n{message}\n")
        return True


class TelegramChannel(NotificationChannel):
    """Deliver via Telegram bot API."""

    name = "telegram"

    def __init__(self, bot_token: str, chat_id: str):
        self.bot_token = bot_token
        self.chat_id = chat_id

    def send(self, title: str, message: str, priority: str = "info") -> bool:
        if not self.bot_token or not self.chat_id:
            return False
        url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        payload = json.dumps({
            "chat_id": self.chat_id,
            "text": f"<b>{title}</b>\n\n{message}",
            "parse_mode": "HTML",
        }).encode("utf-8")
        try:
            req = urllib.request.Request(url, data=payload,
                                         headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=15) as resp:
                return json.loads(resp.read().decode()).get("ok", False)
        except Exception as exc:  # noqa: BLE001
            logger.error("Telegram notification failed: %s", exc)
            return False


class WebhookChannel(NotificationChannel):
    """Deliver via generic HTTP webhook (e.g., Discord, Slack, custom)."""

    name = "webhook"

    def __init__(self, webhook_url: str, format_type: str = "json"):
        self.webhook_url = webhook_url
        self.format_type = format_type

    def send(self, title: str, message: str, priority: str = "info") -> bool:
        if not self.webhook_url:
            return False
        if self.format_type == "discord":
            payload = json.dumps({"content": f"**{title}**\n{message}",
                                  "username": "XAUUSD Bot"}).encode("utf-8")
        elif self.format_type == "slack":
            payload = json.dumps({"text": f"*{title}*\n{message}"}).encode("utf-8")
        else:
            payload = json.dumps({"title": title, "message": message,
                                  "priority": priority}).encode("utf-8")
        try:
            req = urllib.request.Request(self.webhook_url, data=payload,
                                         headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=15) as resp:
                return resp.status in (200, 204)
        except Exception as exc:  # noqa: BLE001
            logger.error("Webhook notification failed: %s", exc)
            return False
