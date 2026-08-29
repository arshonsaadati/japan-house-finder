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

    images = [r["image"]] if r.get("image") else []

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
