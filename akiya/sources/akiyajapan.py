"""akiyajapan.com — English-language aggregator, the richest listing source.

Access notes (see DECISIONS.md):
- The site blocks non-browser agents (Cloudflare + UA gate) and runs a scraper
  honeypot at /resources/, which we never touch. We read only the allowed
  /city/{slug} pages via a real browser at low volume.
- Their own Dataset schema declares the listings CC BY-NC 4.0 — non-commercial
  reuse with attribution — which fits this personal, non-commercial search.
- Login is NOT required: /city pages render full data + photos publicly, so we
  never handle the account password.
- /city/{slug} renders the first ~100 listings server-side; going deeper uses
  the robots-disallowed /api, so we stop at 100 per city and log the cap.

Cards carry clean data attributes (data-property-id, data-uuid) and USD prices;
exact JPY comes from the page's RealEstateListing JSON-LD where present, else we
convert USD→JPY and flag it approximate.
"""

from __future__ import annotations

import json
import re
import time

from bs4 import BeautifulSoup

from ..models import Listing, parse_area, town_from_text

BASE = "https://www.akiyajapan.com"
PAGE_CAP = 100  # server-rendered ceiling per city page
USD_TO_JPY = 150.0

# English town name -> akiyajapan city slug (lowercase romaji).
CITY_SLUGS = {
    "Otaru": "otaru", "Yoichi": "yoichi", "Kutchan": "kutchan",
    "Niseko": "niseko", "Rankoshi": "rankoshi", "Suttsu": "suttsu",
    "Furano": "furano", "Akaigawa": "akaigawa",
}
DEFAULT_TOWNS = ["Otaru", "Yoichi", "Kutchan", "Niseko", "Rankoshi", "Furano"]

_TYPE_MAP = {
    "House": "detached",
    "Apartment": "condo",
    "Land": "land",
    "Business": "mixed",  # often convertible store+residence; flag for review
}


def _jpy_from_jsonld(html: str) -> dict[str, int]:
    """Map property URL -> exact JPY price from RealEstateListing JSON-LD."""
    out: dict[str, int] = {}
    soup = BeautifulSoup(html, "html.parser")
    for s in soup.find_all("script", type="application/ld+json"):
        txt = (s.string or "").strip()
        if "RealEstateListing" not in txt:
            continue
        try:
            data = json.loads(txt)
        except Exception:
            continue
        items = data.get("itemListElement", []) if isinstance(data, dict) else []
        for it in items:
            item = it.get("item", {})
            url = item.get("url", "")
            offer = item.get("offers", {})
            if url and offer.get("priceCurrency") == "JPY":
                try:
                    out[url.rstrip("/")] = int(float(offer["price"]))
                except (KeyError, ValueError):
                    pass
    return out


def _card_type_and_layout(card) -> tuple[str, str | None]:
    prop_type = "unknown"
    layout = None
    for sp in card.select("span"):
        t = sp.get_text(strip=True)
        if t in _TYPE_MAP:
            prop_type = _TYPE_MAP[t]
        elif re.fullmatch(r"\d+S?LDK|\d+[SLDK]{1,3}", t):
            layout = t
    return prop_type, layout


def parse_city_page(html: str, town: str) -> list[Listing]:
    soup = BeautifulSoup(html, "html.parser")
    jpy = _jpy_from_jsonld(html)
    listings: list[Listing] = []
    for card in soup.select("[class*=property-card]"):
        pid = card.get("data-property-id")
        uuid = card.get("data-uuid")
        a = card.find("a", href=re.compile(r"/property/"))
        href = a["href"] if a else (f"/property/{uuid}" if uuid else None)
        if not (pid or uuid) or not href:
            continue
        url = href if href.startswith("http") else BASE + href

        prop_type, layout = _card_type_and_layout(card)

        # Price: prefer exact JPY from JSON-LD, else convert the USD badge.
        price_yen = jpy.get(url.rstrip("/"))
        flags: list[str] = []
        if price_yen is None:
            badge = card.select_one('[class*=price-badge]')
            usd = None
            if badge:
                m = re.search(r"\$([\d,]+)", badge.get_text())
                if m:
                    usd = int(m.group(1).replace(",", ""))
            if usd is not None:
                price_yen = int(usd * USD_TO_JPY)
                flags.append("price approx (USD-derived)")

        # Two m² values: assign larger -> land, smaller -> building (houses).
        areas = sorted(
            (parse_area(d.get_text()) for d in card.find_all("div")
             if re.fullmatch(r"\d+(?:\.\d+)?m²", d.get_text(strip=True))),
            reverse=True,
        )
        areas = [a for a in areas if a]
        land_m2 = areas[0] if len(areas) >= 2 else (areas[0] if prop_type == "land" and areas else None)
        building_m2 = areas[1] if len(areas) >= 2 else (areas[0] if prop_type in ("detached", "condo") and len(areas) == 1 else None)

        yr = None
        yel = card.select_one('[title^="Built "]')
        if yel:
            m = re.search(r"(\d{4})", yel.get("title", ""))
            if m:
                yr = int(m.group(1))

        images = []
        for im in card.select("img"):
            src = im.get("src") or ""
            if isinstance(src, list):
                src = src[0] if src else ""
            if src.startswith("http") and "cdn" in src and src not in images:
                images.append(src)

        if "Parking" not in card.get_text():
            pass  # akiyajapan lists Parking as a positive tag when present

        listings.append(
            Listing(
                source="akiyajapan",
                source_id=str(pid or uuid),
                url=url,
                title=(a.get_text(strip=True) if a else "") or f"{town} property",
                town=town_from_text(card.get_text()) or town,
                address=None,
                price_yen=price_yen,
                layout=layout,
                building_m2=building_m2,
                land_m2=land_m2,
                build_year=yr,
                property_type=prop_type,
                status="live",
                flags=flags,
                image_urls=images,
                raw={"uuid": uuid, "property_id": pid},
            )
        )
    return listings


def fetch(client, towns: list[str] | None = None, log=None) -> list[Listing]:
    from ..browser import HardBlocked

    towns = towns or DEFAULT_TOWNS
    listings: list[Listing] = []
    for town in towns:
        slug = CITY_SLUGS.get(town)
        if not slug:
            continue
        html = None
        # On a Cloudflare hard block, back off and retry a couple of times.
        for attempt in range(3):
            try:
                html = client.get(
                    f"{BASE}/city/{slug}", wait_selector="[class*=property-card]"
                )
                break
            except HardBlocked:
                if log:
                    log(f"akiyajapan {town}: Cloudflare block, backing off "
                        f"{45 * (attempt + 1)}s (attempt {attempt + 1}/3)")
                time.sleep(45 * (attempt + 1))
            except Exception:
                break
        if not html:
            if log:
                log(f"akiyajapan {town}: skipped (still blocked or unavailable)")
            continue
        page = parse_city_page(html, town)
        listings.extend(page)
        if len(page) >= PAGE_CAP and log:
            log(f"akiyajapan {town}: hit {PAGE_CAP}-listing page cap — more exist "
                f"(deeper pages need the robots-disallowed API; skipped)")
    return listings
