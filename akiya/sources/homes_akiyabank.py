"""homes.co.jp/akiyabank — LIFULL HOME'S akiya bank.

List pages carry only type/address/price. Real specs live on detail pages
`/akiyabank/b-{id}/` as th/td rows. City slugs are gun+town and are learned
from the Hokkaido prefecture index, not guessed.
"""

from __future__ import annotations

import re

from bs4 import BeautifulSoup

from ..models import (
    Listing,
    parse_area,
    parse_build_year,
    parse_layout,
    parse_price,
    town_from_text,
)

BASE = "https://www.homes.co.jp"
PREF_INDEX = f"{BASE}/akiyabank/tohoku/hokkaido/"  # Hokkaido lives under /tohoku/

# English town names (models.TOWNS values) we care about → resolved to slugs
# at runtime from the prefecture index. Slugs are gun+town, so we match by the
# town's romaji appearing as the slug tail (yoichi_yoichi, isoya_rankoshi…).
DEFAULT_TOWNS = [
    "Otaru", "Yoichi", "Kutchan", "Niseko", "Rankoshi",
    "Suttsu", "Furano", "Akaigawa",
]

# Romaji tails used to match slugs to our English town names.
_SLUG_HINT = {
    "Otaru": "otaru", "Yoichi": "yoichi", "Kutchan": "kutchan",
    "Niseko": "niseko", "Rankoshi": "rankoshi", "Suttsu": "suttsu",
    "Furano": "furano", "Akaigawa": "akaigawa",
}


def _sale_type(category: str) -> tuple[str, bool]:
    """Map HOME'S category label -> (property_type, is_relevant_for_sale)."""
    if "賃貸" in category:
        return "rental", False
    if "土地" in category:
        return "land", False
    if "事業" in category:
        return "business", False
    return "detached", True  # 売買居住用 — could be house or condo; detail refines


def discover_slugs(client) -> dict[str, str]:
    """town English name -> HOME'S city slug, from the prefecture index."""
    html = client.get(PREF_INDEX)
    slugs = set(re.findall(r"/akiyabank/hokkaido/([a-z_0-9]+)/", html))
    out: dict[str, str] = {}
    for town, hint in _SLUG_HINT.items():
        for slug in slugs:
            # match hint as a whole slug segment (yoichi, or *_yoichi)
            parts = slug.split("_")
            if hint == slug or hint in parts:
                out[town] = slug
                break
    return out


def parse_city_page(html: str) -> list[tuple[str, str, str]]:
    """Return (detail_url, category_label, address) for each card on a city page."""
    soup = BeautifulSoup(html, "html.parser")
    cards = []
    for box in soup.select("div.mod-result-bukkenBox"):
        a = box.find("a", href=re.compile(r"/akiyabank/b-\d+/"))
        if not a:
            continue
        url = a["href"]
        if url.startswith("/"):
            url = BASE + url
        text = box.get_text(" ", strip=True)
        cat = ""
        for label in ("売買居住用", "賃貸居住用", "売買土地", "売買事業用", "賃貸事業用"):
            if label in text:
                cat = label
                break
        m = re.search(r"所在地\s*([^\n・]+?)(?:Point|価格|賃料|土地面積|詳細|$)", text)
        addr = m.group(1).strip() if m else None
        cards.append((url, cat, addr))
    # de-dupe by url, keep first
    seen = {}
    for url, cat, addr in cards:
        seen.setdefault(url, (url, cat, addr))
    return list(seen.values())


def _spec_pairs(soup: BeautifulSoup) -> dict[str, str]:
    """Flatten the detail-page th/td spec rows into a dict."""
    specs: dict[str, str] = {}
    for tbl in soup.find_all("table"):
        for tr in tbl.find_all("tr"):
            cells = tr.find_all(["th", "td"])
            # rows alternate th,td[,th,td]
            i = 0
            while i + 1 < len(cells):
                k = cells[i].get_text(" ", strip=True)
                v = cells[i + 1].get_text(" ", strip=True)
                if k and k not in specs:
                    specs[k] = v
                i += 2
    return specs


def parse_detail(html: str, url: str, category: str = "") -> Listing:
    soup = BeautifulSoup(html, "html.parser")
    specs = _spec_pairs(soup)
    m = re.search(r"b-(\d+)", url)
    source_id = m.group(1) if m else url

    address = specs.get("所在地")
    structure = specs.get("建物構造", "")
    floors = specs.get("地上階", "")
    remarks = specs.get("備考", "")
    zoning = specs.get("用途地域") or specs.get("都市計画")

    prop_type, _ = _sale_type(category)
    # Refine detached vs condo: RC/SRC structure or an above-ground floor number
    # means an apartment/condo unit, not a detached house.
    if prop_type == "detached":
        if re.search(r"RC|鉄筋|鉄骨", structure) or re.search(r"\d+階", floors):
            prop_type = "condo"

    flags: list[str] = []
    parking = specs.get("駐車場", "")
    if parking and ("無" in parking or "なし" in parking):
        flags.append("no parking (駐車場なし)")
    if "未登記" in remarks:
        flags.append("unregistered structure (未登記)")
    if zoning:
        flags.append(f"zoning: {zoning}")
    if "市街化調整区域" in (zoning or ""):
        flags.append("urbanization-control zone (市街化調整区域) — build/reno restricted")

    build_field = specs.get("築年月(築年数)") or specs.get("築年月")
    # land area sometimes only in 備考 as 土地面積：995.48㎡
    land = parse_area(specs.get("土地面積"))
    if land is None:
        mland = re.search(r"土地面積[：: ]*([\d.]+\s*㎡)", remarks)
        if mland:
            land = parse_area(mland.group(1))

    return Listing(
        source="homes",
        source_id=source_id,
        url=url,
        title=(specs.get("物件名") or address or "").strip(),
        town=town_from_text(address),
        address=address,
        price_yen=parse_price(specs.get("価格") or specs.get("賃料")),
        layout=parse_layout(specs.get("間取り")),
        building_m2=parse_area(specs.get("建物面積") or specs.get("専有面積")),
        land_m2=land,
        build_year=parse_build_year(build_field),
        property_type=prop_type,
        status="rental" if category and "賃貸" in category else "live",
        flags=flags,
        raw={"category": category, "structure": structure, "specs": specs},
    )


def fetch(client, towns: list[str] | None = None, sales_only: bool = True) -> list[Listing]:
    towns = towns or DEFAULT_TOWNS
    slugs = discover_slugs(client)
    listings: list[Listing] = []
    for town in towns:
        slug = slugs.get(town)
        if not slug:
            continue
        city_html = client.get(
            f"{BASE}/akiyabank/hokkaido/{slug}/", wait_selector="h1.mod-result-title1"
        )
        for url, cat, _addr in parse_city_page(city_html):
            if sales_only and cat and "賃貸" in cat:
                continue
            detail_html = client.get(url, wait_selector="table")
            listings.append(parse_detail(detail_html, url, cat))
    return listings
