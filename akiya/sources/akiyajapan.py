"""akiyajapan.com — via its documented public JSON API. Richest source.

Access notes (see DECISIONS.md):
- We use the public `/api/v1/properties/search` endpoint that the site
  documents for AI/assistant integration (llms.txt, openapi.json). It needs no
  auth, is rate-limited to 60 req/min, returns exact JPY prices, labeled
  house/land sizes, bedrooms, build year, features, and photos, and paginates
  over the full inventory (no 100-per-city HTML cap).
- We send an honest tool User-Agent (no browser disguise), stay well under the
  60/min limit (see fetch.DOMAIN_DELAYS), cache responses, and record the
  attribution string the API returns (their data is CC BY-NC 4.0).
- **Tradeoff the owner accepted:** robots.txt lists `Disallow: /api`, even
  though llms.txt advertises this same API for assistants. Chosen for the data
  quality + full coverage; kept low-volume and attributed.

We ingest `house` (→detached) and `business` (→mixed, often convertible
store+residence) up to the reject price ceiling, and let filters.py judge them.
"""

from __future__ import annotations

import re

from ..models import Listing, parse_layout

API = "https://www.akiyajapan.com/api/v1/properties/search"
PER_PAGE = 50
PRICE_CEILING_YEN = 10_000_000  # our stretch ceiling; above this we'd reject anyway
MAX_PAGES = 40                  # safety cap per (city, type)

CITY_SLUGS = {
    "Otaru": "otaru", "Yoichi": "yoichi", "Kutchan": "kutchan",
    "Niseko": "niseko", "Rankoshi": "rankoshi", "Suttsu": "suttsu",
    "Furano": "furano", "Akaigawa": "akaigawa",
}
DEFAULT_TOWNS = ["Otaru", "Yoichi", "Kutchan", "Niseko", "Rankoshi", "Suttsu", "Furano", "Akaigawa"]

_TYPE_MAP = {"house": "detached", "business": "mixed"}
_FETCH_TYPES = ("house", "business")

# The API returns image URLs on www.akiyajapan.com/storage/... which 404;
# the actual files live on their DigitalOcean Spaces CDN.
_CDN = "https://akiyajapan.sgp1.cdn.digitaloceanspaces.com"


def _cdn_image(url: str | None) -> str | None:
    if not url:
        return None
    m = re.search(r"(/storage/.*)$", url)
    return _CDN + m.group(1) if m else url


def _flags_from_features(features: list[str]) -> list[str]:
    flags: list[str] = []
    fs = set(features or [])
    if "parking" not in fs:
        flags.append("no parking listed — ski guests drive")
    if "boundary-undetermined" in fs:
        flags.append("boundary undetermined (境界未確定) — survey before offer")
    if "old-house" in fs or "showa-house" in fs:
        flags.append("old/showa house — verify condition & insulation")
    if "move-in-ready" in fs or "renovated" in fs:
        flags.append("listed move-in-ready/renovated (verify)")
    return flags


def parse_result(r: dict, town_hint: str | None = None) -> Listing:
    api_type = (r.get("property_type") or "").lower()
    prop_type = _TYPE_MAP.get(api_type, "unknown")

    features = r.get("features") or []
    beds = r.get("bedrooms")
    # Prefer an LDK layout parsed from the title; else express bedroom count.
    layout = parse_layout(r.get("title")) or (f"{beds}BR" if beds is not None else None)

    img = _cdn_image(r.get("image"))
    images = [img] if img else []

    return Listing(
        source="akiyajapan",
        source_id=str(r.get("id") or r.get("url", "")),
        url=r.get("url", ""),
        title=r.get("title", ""),
        town=r.get("city") or town_hint,
        address=None,
        price_yen=r.get("price_jpy"),
        layout=layout,
        building_m2=r.get("house_size_sqm"),
        land_m2=r.get("land_size_sqm"),
        build_year=r.get("year_built"),
        property_type=prop_type,
        status="live",
        flags=_flags_from_features(features),
        image_urls=images,
        raw={
            "bedrooms": beds,
            "features": features,
            "price_usd_approx": r.get("price_usd_approx"),
            "listing_type": r.get("listing_type"),
        },
    )


def _search_url(city_slug: str, ptype: str, page: int) -> str:
    return (
        f"{API}?prefecture=Hokkaido&city={city_slug}&type={ptype}"
        f"&listing_type=buy&max_price_jpy={PRICE_CEILING_YEN}"
        f"&per_page={PER_PAGE}&page={page}"
    )


def fetch(client, towns: list[str] | None = None, log=None) -> list[Listing]:
    towns = towns or DEFAULT_TOWNS
    listings: list[Listing] = []
    attribution = None
    for town in towns:
        slug = CITY_SLUGS.get(town)
        if not slug:
            continue
        for ptype in _FETCH_TYPES:
            page = 1
            total_pages = 1
            while page <= total_pages and page <= MAX_PAGES:
                try:
                    data = client.get_json(_search_url(slug, ptype, page))
                except Exception as e:
                    if log:
                        log(f"akiyajapan {town}/{ptype} p{page}: {e}")
                    break
                attribution = attribution or data.get("attribution")
                total_pages = data.get("total_pages", 1) or 1
                for r in data.get("results", []):
                    listings.append(parse_result(r, town))
                page += 1
    if attribution and log:
        log(f"akiyajapan attribution: {attribution}")
    return listings


# --- Property-page gallery enrichment (headed browser; see DECISIONS.md) ---
#
# The API list response carries one cover image; full galleries (10-15 photos)
# live on the robots-ALLOWED /property/{uuid} pages, which Cloudflare now
# gates behind an interactive challenge. A headed real-Chrome session with a
# persisted storage_state (~/.akiya-cf-state.json) clears it — the human
# clicks "verify" once and the clearance cookie is reused for every
# subsequent page. The tool itself never clicks the challenge.

_CDN_SRC = re.compile(r"https://akiyajapan\.sgp1\.cdn\.digitaloceanspaces\.com/storage/property/[^\s\"'\\)>]+")


def parse_property_gallery(html: str, own_uuid: str) -> list[str]:
    """The listing's OWN photos from a rendered /property page.

    The page embeds a related/similar-properties strip whose cover photos
    live on the same CDN path — every one of those sits inside an
    <a href="/property/<other-uuid>"> card. Rule (verified against a real
    fixture): keep a CDN <img> only if no ancestor <a> links to a DIFFERENT
    property. Filename uuids are unrelated to the listing uuid, so DOM
    context is the only reliable signal.
    """
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    seen: list[str] = []
    for img in soup.find_all("img"):
        src = img.get("src") or img.get("data-src") or ""
        if isinstance(src, list):
            src = src[0] if src else ""
        m = _CDN_SRC.match(src)
        if not m:
            continue
        a = img.find_parent("a")
        href = (a.get("href") if a else "") or ""
        if isinstance(href, list):
            href = href[0] if href else ""
        if "/property/" in href and own_uuid not in href:
            continue  # related-listing card, not our photo
        u = m.group(0).rstrip("\\'\"")
        if u not in seen:
            seen.append(u)
    return seen[:16]


def enrich_from_detail(browser, listing: Listing) -> Listing:
    """Fetch the listing's property page in the given BrowserSession and fill
    in the full gallery. Mutates and returns `listing`."""
    html = browser.get_html(listing.url, challenge_timeout_ms=180_000)
    own_uuid = listing.url.rstrip("/").rsplit("/", 1)[-1]
    gallery = parse_property_gallery(html, own_uuid)
    if gallery:
        listing.image_urls = gallery
    return listing
