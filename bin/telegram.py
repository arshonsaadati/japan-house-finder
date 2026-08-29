#!/usr/bin/env python3
"""Minimal Telegram sender — stdlib only, no extra deps.

Reads TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID from the environment or from a
sibling `.env.telegram` file (gitignored). Plain-text messages so listing
titles/URLs never need escaping; Telegram auto-links bare URLs.

CLI:  python3 bin/telegram.py "your message"   (or pipe text on stdin)
"""

from __future__ import annotations

import json
import os
import sys
import urllib.parse
import urllib.request
from pathlib import Path

ENV_FILE = Path(__file__).resolve().parent.parent / ".env.telegram"


def _load_env() -> None:
    if ENV_FILE.exists():
        for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())


def _api(method: str, params: dict) -> dict:
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        raise SystemExit("TELEGRAM_BOT_TOKEN not set (check .env.telegram)")
    url = f"https://api.telegram.org/bot{token}/{method}"
    data = urllib.parse.urlencode(params).encode()
    req = urllib.request.Request(url, data=data)
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def send_message(text: str, chat_id: str | None = None, preview: bool = True) -> dict:
    _load_env()
    chat_id = chat_id or os.environ.get("TELEGRAM_CHAT_ID")
    if not chat_id:
        raise SystemExit("TELEGRAM_CHAT_ID not set (check .env.telegram)")
    return _api("sendMessage", {
        "chat_id": chat_id,
        "text": text[:4096],
        "disable_web_page_preview": "false" if preview else "true",
    })


def send_photo(photo: str, caption: str = "", chat_id: str | None = None) -> dict:
    _load_env()
    chat_id = chat_id or os.environ.get("TELEGRAM_CHAT_ID")
    return _api("sendPhoto", {"chat_id": chat_id, "photo": photo, "caption": caption[:1024]})


if __name__ == "__main__":
    _load_env()
    msg = " ".join(sys.argv[1:]).strip() or sys.stdin.read().strip()
    if not msg:
        raise SystemExit("usage: telegram.py <message>")
    res = send_message(msg)
    print("sent" if res.get("ok") else json.dumps(res))
