#!/usr/bin/env python3
"""Telegram ↔ Claude bridge for the akiya project. Stdlib only.

Long-polls the bot's getUpdates, and for each message from the OWNER's chat
(TELEGRAM_CHAT_ID) pipes the text to headless `claude -p` running in the repo,
then sends Claude's reply back to the chat. Anyone else who messages the bot is
ignored (and logged) — the bot token is a doorbell, the chat filter is the lock.

Claude runs with a restricted tool allowlist: it can read the repo and run the
`akiya` CLI, nothing else. Conversation continuity via `--continue` (the repo
dir scopes the session); text "/new" starts a fresh conversation.

Run under systemd (akiya-bridge.service) or tmux:
  .venv/bin/python bin/telegram_claude_bridge.py
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
CLAUDE = Path.home() / ".local" / "bin" / "claude"
OFFSET_FILE = Path.home() / ".akiya-bridge-offset"
CLAUDE_TIMEOUT_S = 420

sys.path.insert(0, str(REPO / "bin"))
import telegram  # noqa: E402  (our sender module; also loads .env.telegram)

ALLOWED_TOOLS = [
    "Read", "Grep", "Glob",
    f"Bash({REPO}/.venv/bin/akiya *)",
    "Bash(.venv/bin/akiya *)",
]

SYSTEM_HINT = (
    "You are the Hokkaido akiya house-hunt assistant, chatting via Telegram. "
    "Working directory is the japan-house-finder repo: data/listings.json holds "
    "all scraped listings; HANDOFF.md has strategy/legal context; the `akiya` "
    "CLI (at .venv/bin/akiya) offers: list --verdict pass|stretch|flagged "
    "[--town X] [--max-price N], leads, underwrite --price N [--reno-mult X "
    "--winter-nights N --adr N]. Answer conversationally and CONCISELY (this "
    "is a phone chat): plain text only, no markdown tables or headers, keep "
    "replies under ~1500 characters, include listing URLs when discussing "
    "specific houses."
)


def _api(method: str, params: dict, timeout: int = 60) -> dict:
    token = os.environ["TELEGRAM_BOT_TOKEN"]
    data = urllib.parse.urlencode(params).encode()
    req = urllib.request.Request(f"https://api.telegram.org/bot{token}/{method}", data=data)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)


def _load_offset() -> int:
    try:
        return int(OFFSET_FILE.read_text().strip())
    except Exception:
        return 0


def _save_offset(v: int) -> None:
    OFFSET_FILE.write_text(str(v))


def _ask_claude(text: str, fresh: bool) -> str:
    cmd = [str(CLAUDE), "-p", f"{SYSTEM_HINT}\n\nUser (via Telegram): {text}"]
    for t in ALLOWED_TOOLS:
        cmd += ["--allowedTools", t]
    if not fresh:
        cmd.append("--continue")
    try:
        r = subprocess.run(cmd, capture_output=True, text=True,
                           timeout=CLAUDE_TIMEOUT_S, cwd=str(REPO))
        if r.returncode != 0 and not fresh:
            # No prior conversation to continue — start a new one.
            return _ask_claude(text, fresh=True)
        out = (r.stdout or "").strip()
        return out or f"(claude returned nothing; rc={r.returncode})"
    except subprocess.TimeoutExpired:
        return "(claude timed out — try a simpler question or /new)"
    except Exception as e:
        return f"(bridge error: {e})"


def main() -> None:
    telegram._load_env()
    owner = os.environ["TELEGRAM_CHAT_ID"]
    offset = _load_offset()
    print(f"bridge up; owner chat {owner}; offset {offset}", flush=True)
    while True:
        try:
            resp = _api("getUpdates", {"timeout": 50, "offset": offset + 1}, timeout=70)
        except Exception as e:
            print(f"getUpdates error: {e}; sleeping 15s", flush=True)
            time.sleep(15)
            continue
        for upd in resp.get("result", []):
            offset = max(offset, upd["update_id"])
            _save_offset(offset)
            msg = upd.get("message") or {}
            chat_id = str(msg.get("chat", {}).get("id", ""))
            text = (msg.get("text") or "").strip()
            if not text:
                continue
            if chat_id != owner:
                print(f"ignored message from non-owner chat {chat_id}", flush=True)
                continue
            fresh = text.lower().startswith("/new")
            if fresh:
                text = text[4:].strip() or "Hi — give me a one-line status of the listing store."
            print(f"owner: {text[:80]!r}", flush=True)
            try:
                _api("sendChatAction", {"chat_id": owner, "action": "typing"}, timeout=15)
            except Exception:
                pass
            reply = _ask_claude(text, fresh=fresh)
            for i in range(0, len(reply), 4000):
                try:
                    telegram.send_message(reply[i:i + 4000])
                except Exception as e:
                    print(f"send failed: {e}", flush=True)
            print(f"replied ({len(reply)} chars)", flush=True)


if __name__ == "__main__":
    main()
