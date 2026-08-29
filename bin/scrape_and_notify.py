#!/usr/bin/env python3
"""Scrape akiya listings; Telegram-notify about genuinely new buys.

Option B architecture: the scrape + new-listing detection is deterministic;
when something new IS found, headless `claude -p` writes the analyst summary
that gets sent (with the raw listing links appended). If the Claude call
fails or times out, we fall back to the plain deterministic message — an
alert is never dropped because the model hiccuped.

Run from cron:  /home/arshons/Code/japan-house-finder/.venv/bin/python \
                /home/arshons/Code/japan-house-finder/bin/scrape_and_notify.py
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
AKIYA = REPO / ".venv" / "bin" / "akiya"
CLAUDE = Path.home() / ".local" / "bin" / "claude"
STORE = REPO / "data" / "listings.json"
NOTIFY_VERDICTS = {"pass", "stretch"}
MAX_IN_MESSAGE = 10
CLAUDE_TIMEOUT_S = 240

sys.path.insert(0, str(REPO / "bin"))
import telegram  # noqa: E402


def _keys() -> dict[str, dict]:
    if not STORE.exists():
        return {}
    d = json.loads(STORE.read_text(encoding="utf-8"))
    return {f"{l['source']}:{l['source_id']}": l for l in d.get("listings", [])}


def _fmt(l: dict) -> list[str]:
    price = f"¥{l['price_yen']:,}" if l.get("price_yen") else "price ?"
    usd = f" (~${round(l['price_yen'] / 150):,})" if l.get("price_yen") else ""
    bits = " · ".join(x for x in [
        l.get("town") or "?",
        f"{price}{usd}",
        l.get("layout") or "",
        f"built {l['build_year']}" if l.get("build_year") else "",
        f"{l['building_m2']:.0f}m²" if l.get("building_m2") else "",
        l.get("verdict", ""),
    ] if x)
    return [bits, l.get("url", "")]


def _plain_message(new: list[dict]) -> str:
    lines = [f"\U0001f3e0 {len(new)} new Hokkaido listing(s) worth a look:", ""]
    for l in new[:MAX_IN_MESSAGE]:
        lines += _fmt(l) + [""]
    if len(new) > MAX_IN_MESSAGE:
        lines.append(f"…and {len(new) - MAX_IN_MESSAGE} more (akiya list --verdict pass)")
    return "\n".join(lines)


def _claude_summary(new: list[dict]) -> str | None:
    """Ask headless Claude for a short opinionated take on the new listings."""
    slim = [
        {k: l.get(k) for k in (
            "town", "price_yen", "layout", "build_year", "building_m2",
            "land_m2", "verdict", "verdict_reasons", "flags", "source", "url",
        )}
        for l in new[:MAX_IN_MESSAGE]
    ]
    prompt = f"""You are the analyst for our Hokkaido fixer-upper → Airbnb hunt.
Context (from HANDOFF.md): budget ≤¥7.5M purchase (≤¥10M stretch); renovation
typically 2–5× purchase; underwrite at 6% net yield on all-in cost; ski-season
model ≈ 90–110 winter nights at $260–320 ADR (Otaru: year-round canal tourism,
but not a true ski asset); detached, built ≥1981 only; town minpaku ordinances
still unverified.

{len(slim)} NEW listing(s) appeared today (JSON below). Write the Telegram
message we receive: 2–6 sentences of sharp, opinionated triage — which one(s)
deserve attention first and why, what smells off, and any dealbreaker flags.
Rough yield intuition is welcome; no fabricated facts. Plain text only (no
markdown), then end with one line per listing: "town ¥price — URL" using the
exact URLs given.

{json.dumps(slim, ensure_ascii=False)}"""
    try:
        r = subprocess.run(
            [str(CLAUDE), "-p", prompt],
            capture_output=True, text=True, timeout=CLAUDE_TIMEOUT_S,
            cwd=str(REPO),
        )
        out = (r.stdout or "").strip()
        if r.returncode == 0 and 40 < len(out) <= 4000:
            return out
        print(f"claude -p unusable (rc={r.returncode}, len={len(out)}); falling back")
    except Exception as e:
        print(f"claude -p failed: {e}; falling back")
    return None


def main() -> int:
    before = set(_keys())
    subprocess.run([str(AKIYA), "scrape"], cwd=str(REPO), check=False)
    after = _keys()

    new = [l for k, l in after.items()
           if k not in before and l.get("verdict") in NOTIFY_VERDICTS]
    new.sort(key=lambda l: l.get("price_yen") or 0)

    if not new:
        print("no new pass/stretch listings")
        if os.environ.get("AKIYA_DIGEST"):
            n_pass = sum(1 for l in after.values() if l.get("verdict") == "pass")
            telegram.send_message(
                f"\u2705 akiya cron ran fine — no new listings this time. "
                f"Store: {len(after)} listings, {n_pass} passing."
            )
        return 0

    text = _claude_summary(new) or _plain_message(new)
    telegram.send_message(text)

    imgs = new[0].get("image_urls") or []
    if imgs:
        cheapest = new[0]
        cap = f"Cheapest new: {cheapest.get('town')} ¥{cheapest.get('price_yen', 0):,}"
        try:
            telegram.send_photo(imgs[0], caption=cap)
        except Exception:
            pass
    print(f"notified: {len(new)} new listings")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
