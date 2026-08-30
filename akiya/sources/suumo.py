"""suumo.jp — general used-detached-house market (中古一戸建て).

Richest source: every field is on the results page in `div.property_unit`
dt/dd pairs. All listings here are detached houses by definition of the
section, so property_type is always 'detached'.

Etiquette (enforced in code): never build `sort=` URLs (robots-disallowed),
throttle ≥30s (see fetch.DOMAIN_DELAYS), cap pages per run, disk-cache.
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

BASE = "https://suumo.jp"

# Confirmed sc_ slugs for target/adjacent cities. Small Shiribeshi towns
# (Yoichi, Kutchan, Niseko…) are gun-level and may not have their own sc_
# page; those are covered by the akiya-bank sources instead.
CITY_SLUGS = {
    "Otaru": "sc_otaru",
    "Furano": "sc_furano",
    "Sapporo": "sa_sapporo",
    "Asahikawa": "sc_asahikawa",
}
DEFAULT_TOWNS = ["Otaru", "Furano"]

MAX_PAGES = 10  # safety cap per city per run

# SUUMO's image CDN is a resizer: the list page asks for w=192&h=144 thumbnails,
# but the same `src` serves up to ~1200px wide. Width-only keeps the aspect
# ratio (floor plans are portrait); w>=2000 returns HTTP 400.
HIRES_WIDTH = 1200
_RESIZE_RE = re.compile(r"(https://img\d+\.suumo\.com/jj/resizeImage\?src=[^&\s\"']+)")


def hires(url: str) -> str:
    """Rewrite a resizeImage thumbnail URL to the hi-res variant (idempotent)."""
    m = _RESIZE_RE.match(url)
    return f"{m.group(1)}&w={HIRES_WIDTH}" if m else url


def parse_detail_gallery(html: str, source_id: str) -> list[str]:
    """All photos of one listing from its detail page (nc_<id>), hi-res, in
    photo order. The page also embeds thumbnails of *other* listings, so only
    keep images whose CDN path contains this listing's id.
    """
    seen: list[str] = []
    for base in _RESIZE_RE.findall(html):
        if f"%2F{source_id}%2F" not in base and f"/{source_id}/" not in base:
            continue
        if base not in seen:
            seen.append(base)
    seen.sort()  # …_0001.jpg, _0002.jpg … = the site's own photo order
    return [f"{b}&w={HIRES_WIDTH}" for b in seen]


_COORD_RE = re.compile(r"(?:init)?(Ido|Keido)\s*:\s*'([0-9.]+)'")


def parse_detail_coords(html: str) -> tuple[float, float] | None:
    """SUUMO's map init script carries `Ido : '43.13…'` / `Keido : '141.16…'`
    (緯度/経度). Returns (lat, lng) if both are present and plausible for Japan."""
    found = {k: float(v) for k, v in _COORD_RE.findall(html)}
    lat, lng = found.get("Ido"), found.get("Keido")
    if lat is None or lng is None or not (24 < lat < 46 and 122 < lng < 154):
        return None
    return lat, lng


def enrich_from_detail(client, listing: Listing) -> Listing:
    """Fetch the detail page (throttled + cached by the client) and fill in the
    full hi-res gallery and coordinates. Mutates and returns `listing`."""
    html = client.get(listing.url)
    listing.image_urls = parse_detail_gallery(html, listing.source_id) or [hires(u) for u in listing.image_urls]
    coords = parse_detail_coords(html)
    if coords:
        listing.lat, listing.lng = coords
    return listing


def fetch_gallery(client, listing: Listing) -> list[str]:
    """Back-compat: just the gallery."""
    return enrich_from_detail(client, listing).image_urls


def _city_url(slug: str, page: int) -> str:
    url = f"{BASE}/chukoikkodate/hokkaido_/{slug}/"
    if page > 1:
        url += f"?page={page}"
    return url


def parse_results_page(html: str) -> list[Listing]:
    soup = BeautifulSoup(html, "html.parser")
    out: list[Listing] = []
    for unit in soup.select("div.property_unit"):
        specs: dict[str, str] = {}
        for dt, dd in zip(unit.select("dt"), unit.select("dd")):
            k = dt.get_text(" ", strip=True)
            v = dd.get_text(" ", strip=True)
            if k:
                specs[k] = v
        a = unit.find("a", href=re.compile(r"/nc_\d+"))
        if not a:
            continue
        # Photos are lazy-loaded: real URL sits in the `rel` attribute (bs4
        # parses rel as a list); `src` is a 1px placeholder gif.
        images: list[str] = []
        for im in unit.select("img"):
            src = im.get("rel") or im.get("data-src") or ""
            if isinstance(src, list):
                src = src[0] if src else ""
            if src and "suumo.com" in src and "resizeImage" in src:
                src = hires(src)
                if src not in images:
                    images.append(src)
        url = a["href"]
        if url.startswith("/"):
            url = BASE + url
        m = re.search(r"nc_(\d+)", url)
        source_id = m.group(1) if m else url
        address = specs.get("所在地")
        out.append(
            Listing(
                source="suumo",
                source_id=source_id,
                url=url,
                title=specs.get("物件名") or address or "",
                town=town_from_text(address),
                address=address,
                price_yen=parse_price(specs.get("販売価格") or specs.get("価格")),
                layout=parse_layout(specs.get("間取り")),
                building_m2=parse_area(specs.get("建物面積")),
                land_m2=parse_area(specs.get("土地面積")),
                build_year=parse_build_year(specs.get("築年月")),
                property_type="detached",
                status="live",
                flags=[],
                image_urls=images,
                raw={"station": specs.get("沿線・駅"), "specs": specs},
            )
        )
    return out


def _has_next_page(html: str, page: int) -> bool:
    # SUUMO paginates with ?page=N links; stop when the next number is absent.
    return bool(re.search(rf'\?page={page + 1}"', html))


def fetch(client, towns: list[str] | None = None, max_pages: int = MAX_PAGES) -> list[Listing]:
    towns = towns or DEFAULT_TOWNS
    listings: list[Listing] = []
    for town in towns:
        slug = CITY_SLUGS.get(town)
        if not slug:
            continue
        for page in range(1, max_pages + 1):
            html = client.get(_city_url(slug, page))
            page_listings = parse_results_page(html)
            if not page_listings:
                break
            listings.extend(page_listings)
            if not _has_next_page(html, page):
                break
    return listings
