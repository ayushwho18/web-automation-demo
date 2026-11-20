"""Optional Telegram summary. Reads TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID from the environment."""
from __future__ import annotations

import logging
import os

import requests

log = logging.getLogger("webbot")


def telegram(text: str) -> bool:
    token, chat = os.environ.get("TELEGRAM_BOT_TOKEN"), os.environ.get("TELEGRAM_CHAT_ID")
    if not (token and chat):
        return False
    try:
        requests.post(f"https://api.telegram.org/bot{token}/sendMessage",
                      json={"chat_id": chat, "text": text}, timeout=20).raise_for_status()
        return True
    except requests.RequestException as ex:
        log.warning("Telegram message failed: %s", ex)
        return False
