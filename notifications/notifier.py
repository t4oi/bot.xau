"""Notifier — aggregates multiple channels and routes alerts."""
from __future__ import annotations
from typing import Dict, List, Optional

from core.logging_config import get_logger
from .channels import NotificationChannel

logger = get_logger("notifications.manager")


class Notifier:
    """Multi-channel notification manager with priority routing."""

    PRIORITY_LEVELS = ["debug", "info", "warning", "critical"]

    def __init__(self, min_priority: str = "info"):
        self.channels: List[NotificationChannel] = []
        self.min_priority_idx = self.PRIORITY_LEVELS.index(min_priority)
        self._history: List[Dict] = []

    def add_channel(self, channel: NotificationChannel) -> None:
        self.channels.append(channel)
        logger.info("Added notification channel: %s", channel.name)

    def _should_send(self, priority: str) -> bool:
        idx = self.PRIORITY_LEVELS.index(priority) if priority in self.PRIORITY_LEVELS else 1
        return idx >= self.min_priority_idx

    def notify(self, title: str, message: str, priority: str = "info") -> Dict:
        """Send to all registered channels. Returns per-channel results."""
        if not self._should_send(priority):
            return {"delivered": 0, "skipped": "below priority threshold"}
        results = {}
        delivered = 0
        for ch in self.channels:
            try:
                ok = ch.send(title, message, priority)
                results[ch.name] = ok
                if ok:
                    delivered += 1
            except Exception as exc:  # noqa: BLE001
                results[ch.name] = f"error: {exc}"
                logger.error("Channel %s failed: %s", ch.name, exc)
        self._history.append({"title": title, "priority": priority, "delivered": delivered})
        return {"delivered": delivered, "total_channels": len(self.channels), "results": results}

    def alert_signal(self, signal_summary: str) -> Dict:
        return self.notify("📊 New Trading Signal", signal_summary, priority="info")

    def alert_risk(self, message: str) -> Dict:
        return self.notify("⚠️ RISK ALERT", message, priority="warning")

    def alert_critical(self, message: str) -> Dict:
        return self.notify("🚨 CRITICAL", message, priority="critical")

    def history(self, limit: int = 50) -> List[Dict]:
        return self._history[-limit:]
