"""akiyabank.blogspot.com — Shiribeshi/Niseko-area akiya bank.

The Blogspot JSON feed returns the whole blog in one request, full post
bodies in content.$t. Fields are labeled plain text inside HTML; we strip
tags and regex the labels.
"""

from __future__ import annotations

import html
import json
import re

from ..models import (
    Listing,
    parse_area,
    parse_build_year,
    parse_layout,
    parse_price,
    town_from_text,
)

FEED_URL = "https://akiyabank.blogspot.com/feeds/posts/default?alt=json&max-results=500"

# Status is encoded in post labels (categories).
_SOLD = "成約済"
_NEGO = "商談中"
_RENTAL = "賃貸"


def _strip_html(body: str) -> str:
    t = re.sub(r"<br\s*/?>", "\n", body, flags=re.IGNORECASE)
    t = re.sub(r"</(div|p|tr)>", "\n", t, flags=re.IGNORECASE)
    t = re.sub(r"<[^>]+>", "", t)
    return html.unescape(t)


def _field(text: str, label: str) -> str | None:
    """Grab the value after 'ラベル：' up to the next newline."""
    m = re.search(re.escape(label) + r"[：:]\s*([^\n]+)", text)
    return m.group(1).strip() if m else None


def _status(labels: list[str]) -> str:
    if _SOLD in labels:
        return "sold"
    if _RENTAL in labels:
        return "rental"
    if _NEGO in labels:
        return "negotiating"
    return "live"


def parse_entry(entry: dict) -> Listing | None:
    title = entry.get("title", {}).get("$t", "")
    labels = [c["term"] for c in entry.get("category", [])]
    url = next(
        (l["href"] for l in entry.get("link", []) if l.get("rel") == "alternate"),
        "",
    )
    body = _strip_html(entry.get("content", {}).get("$t", ""))

    source_id = _field(body, "登録#") or _field(title, "登録#")
    if not source_id:
        # ID also appears in the title: 【売却】余市町　住宅　S-19-017
        m = re.search(r"([A-Z]-\d{2}-\d{3})", title)
        source_id = m.group(1) if m else None
    if not source_id:
        return None
    source_id = source_id.split()[0]  # trim trailing status text

    address = _field(body, "住所")
    building_line = _field(body, "建物")  # "5LDK 140.9㎡ ... 1987年頃築"
    land_line = _field(body, "土地")

    building_m2 = parse_area(building_line)
    if building_m2 is None:
        # Some posts split floor areas on the next line: "1F 68.04㎡ 2F 68.04㎡".
        floors = re.findall(r"\d+F\s*([\d.]+)\s*㎡", body)
        if floors:
            building_m2 = round(sum(float(x) for x in floors), 2)
    other = _field(body, "その他") or ""
    # 未登記 etc. can appear on the その他 line or elsewhere in the body.
    other_full = other + "\n" + body

    flags: list[str] = []
    if "未登記" in other_full:
        flags.append("unregistered structure (未登記)")
    if "駐車スペースなし" in other_full or "駐車場なし" in other_full:
        flags.append("no parking (駐車スペースなし)")
    if "上下水道" in other_full:
        flags.append("town water/sewer (上下水道)")

    # Property type from title/labels.
    prop = "detached"
    if "土地" in title and "住宅" not in title:
        prop = "land"
    elif "店舗" in title or "店舗付" in "".join(labels):
        prop = "mixed"

    return Listing(
        source="blogspot",
        source_id=source_id,
        url=url,
        title=title,
        town=town_from_text(address) or town_from_text(title),
        address=address,
        price_yen=parse_price(_field(body, "価格")),
        layout=parse_layout(building_line),
        building_m2=building_m2,
        land_m2=parse_area(land_line),
        build_year=parse_build_year(building_line),
        property_type=prop,
        status=_status(labels),
        flags=flags,
        raw={"labels": labels, "other": other},
    )


def parse_feed(feed_json: str) -> list[Listing]:
    data = json.loads(feed_json)
    entries = data.get("feed", {}).get("entry", [])
    out = []
    for e in entries:
        listing = parse_entry(e)
        if listing:
            out.append(listing)
    return out


def fetch(client) -> list[Listing]:
    return parse_feed(client.get(FEED_URL))
