"""Telegram API client — thin wrapper over HTTP with retry + rate limiting."""
from __future__ import annotations
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, List, Optional

from config.constants import TG_PARSE_MODE, TG_MAX_MESSAGE_LEN
from core.exceptions import TelegramError
from core.logging_config import get_logger

logger = get_logger("telegram.client")


class TelegramClient:
    """Minimal Telegram Bot API client using urllib (no extra deps)."""

    BASE = "https://api.telegram.org/bot{token}/{method}"

    def __init__(self, token: str, default_chat_id: str = "", timeout: int = 45):
        self.token = token
        self.default_chat_id = default_chat_id
        self.timeout = timeout
        self._last_send = 0.0
        self._min_interval = 0.05  # ~20 msg/s global limit

    def _throttle(self) -> None:
        elapsed = time.time() - self._last_send
        if elapsed < self._min_interval:
            time.sleep(self._min_interval - elapsed)
        self._last_send = time.time()

    def _api(self, method: str, payload: Optional[Dict[str, Any]] = None) -> Optional[Dict]:
        if not self.token:
            raise TelegramError("BOT_TOKEN not configured")
        url = self.BASE.format(token=self.token, method=method)
        data = json.dumps(payload or {}).encode("utf-8")
        req = urllib.request.Request(
            url, data=data,
            headers={"Content-Type": "application/json", "Accept": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                body = json.loads(resp.read().decode("utf-8"))
                if not body.get("ok"):
                    logger.error("Telegram API error %s: %s", method, body)
                return body
        except urllib.error.HTTPError as exc:
            if exc.code == 429:
                retry_after = int(exc.headers.get("Retry-After", 5))
                logger.warning("Telegram rate limited, sleeping %ds", retry_after)
                time.sleep(retry_after)
                return self._api(method, payload)
            logger.error("Telegram HTTP %s on %s", exc.code, method)
            raise TelegramError(f"HTTP {exc.code}") from exc
        except Exception as exc:  # noqa: BLE001
            msg = str(exc)
            if "timed out" in msg.lower() or "timeout" in msg.lower():
                logger.warning("Telegram request timed out (will retry): %s", exc)
            else:
                logger.error("Telegram request failed: %s", exc)
            raise TelegramError(str(exc)) from exc

    def send_message(self, text: str, chat_id: Optional[str] = None,
                     reply_markup: Optional[Dict] = None,
                     parse_mode: str = TG_PARSE_MODE,
                     disable_preview: bool = True) -> bool:
        cid = chat_id or self.default_chat_id
        if not cid:
            logger.warning("No chat_id configured")
            return False
        self._throttle()
        # Split long messages
        chunks = [text[i:i + TG_MAX_MESSAGE_LEN - 100]
                  for i in range(0, len(text), TG_MAX_MESSAGE_LEN - 100)]
        ok = True
        for idx, chunk in enumerate(chunks):
            payload = {
                "chat_id": cid, "text": chunk, "parse_mode": parse_mode,
                "disable_web_page_preview": disable_preview,
            }
            if idx == len(chunks) - 1 and reply_markup:
                payload["reply_markup"] = reply_markup
            try:
                result = self._api("sendMessage", payload)
                ok = ok and bool(result and result.get("ok"))
            except TelegramError:
                ok = False
        return ok

    def send_photo(self, photo_url_or_file_id: str, caption: str = "",
                   chat_id: Optional[str] = None) -> bool:
        cid = chat_id or self.default_chat_id
        self._throttle()
        try:
            result = self._api("sendPhoto", {
                "chat_id": cid, "photo": photo_url_or_file_id,
                "caption": caption[:1024], "parse_mode": TG_PARSE_MODE,
            })
            return bool(result and result.get("ok"))
        except TelegramError:
            return False

    def get_updates(self, offset: int = 0, timeout: int = 25) -> List[Dict]:
        # Long-poll timeout must be shorter than the socket read timeout (self.timeout)
        # otherwise urllib raises "read operation timed out" on every idle poll.
        long_poll = min(timeout, max(5, self.timeout - 15))
        try:
            result = self._api("getUpdates", {"offset": offset, "timeout": long_poll})
            if result and result.get("ok"):
                return result.get("result", [])
        except TelegramError as exc:
            # A read timeout during long-polling is normal (no updates) — don't spam
            if "timed out" not in str(exc).lower():
                logger.error("getUpdates failed: %s", exc)
        except Exception as exc:  # noqa: BLE001
            if "timed out" not in str(exc).lower():
                logger.error("getUpdates error: %s", exc)
        return []

    def delete_webhook(self) -> bool:
        try:
            result = self._api("deleteWebhook", {})
            return bool(result and result.get("ok"))
        except TelegramError:
            return False

    def get_me(self) -> Optional[Dict]:
        try:
            result = self._api("getMe", {})
            return result.get("result") if result and result.get("ok") else None
        except TelegramError:
            return None
