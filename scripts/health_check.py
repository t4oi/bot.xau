#!/usr/bin/env python3
"""Health check script — verifies data source + Telegram connectivity."""
import sys
sys.path.insert(0, ".")
from config.settings import get_settings
from data.feed import FeedManager
from telegram_bot.client import TelegramClient


def main():
    settings = get_settings()
    feed = FeedManager()
    health = feed.health()
    print(f"[1/3] Data source ({health['source']}): {'OK' if health['healthy'] else 'FAIL'}")

    tick = feed.tick()
    if tick:
        print(f"[2/3] XAUUSD price: {tick.mid:.2f} (spread {tick.spread:.2f})")
    else:
        print("[2/3] Price fetch: FAIL")

    tg = TelegramClient(token=settings.telegram_bot_token, default_chat_id=settings.telegram_chat_id)
    me = tg.get_me()
    if me:
        print(f"[3/3] Telegram bot @{me.get('username')}: OK")
    else:
        print("[3/3] Telegram bot: FAIL")

    ok = health["healthy"] and tick and me
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
