"""Hard-criteria filter from the handoff.

Every listing is annotated with a verdict and reasons; nothing is silently
dropped, so rejects stay in the store for the record.

Verdicts:
  pass     — meets all hard criteria, price ≤ ¥7.5M
  stretch  — otherwise a pass but price ≤ ¥10M
  flagged  — a house worth a look but with an open question (unknown town
             ordinance, unregistered structure, 1981 build, etc.)
  reject   — fails a hard structural criterion (condo/land, pre-1981, too dear)
"""

from __future__ import annotations

from .models import Listing

PRICE_PASS = 7_500_000
PRICE_STRETCH = 10_000_000
MIN_BUILD_YEAR = 1981  # new seismic code (post-June 1981)

# Towns whose minpaku ordinance status is tracked in data/ordinances.md.
# Anything outside this set is flagged (unknown ordinance), not rejected.
KNOWN_TOWNS = {
    # Hokkaido (original)
    "Otaru", "Yoichi", "Kutchan", "Niseko", "Rankoshi",
    "Suttsu", "Furano", "Akaigawa",
    # Expansion (2026-08-31): Kyushu / Setouchi / Kansai / Tokyo isles.
    # Ordinances UNVERIFIED like the rest — see data/ordinances.md.
    "Itoshima", "Karatsu", "Onomichi", "Hatsukaichi", "Fukuyama",
    "Takehara", "Kurashiki", "Tonosho", "Shodoshima", "Awaji",
    "Sumoto", "Tanabe", "Kozushima",
}

REJECT_TYPES = {"condo", "land", "business"}


def annotate(listing: Listing) -> Listing:
    """Set listing.verdict and listing.verdict_reasons in place; return it."""
    reasons: list[str] = []
    verdict = "pass"

    def downgrade(to: str, reason: str) -> None:
        nonlocal verdict
        order = {"pass": 0, "stretch": 1, "flagged": 2, "reject": 3}
        if order[to] > order[verdict]:
            verdict = to
        reasons.append(reason)

    # Non-sale statuses are informational, not buy candidates.
    if listing.status == "sold":
        return _finalize(listing, "reject", ["already sold (成約済)"])
    if listing.status == "rental":
        return _finalize(listing, "reject", ["rental listing (賃貸)"])
    if listing.status == "negotiating":
        downgrade("flagged", "under negotiation (商談中) — may fall through")

    # 1. Detached only.
    if listing.property_type in REJECT_TYPES:
        downgrade("reject", f"not a detached house (type={listing.property_type})")
    elif listing.property_type == "mixed":
        downgrade("flagged", "mixed-use (店舗付) — review zoning/usage")
    elif listing.property_type == "unknown":
        downgrade("flagged", "property type unconfirmed — verify detached")

    # 2. Build year ≥ 1981.
    if listing.build_year is not None:
        if listing.build_year < MIN_BUILD_YEAR:
            downgrade("reject", f"pre-1981 seismic ({listing.build_year}) — reinforcement cost")
        elif listing.build_year == MIN_BUILD_YEAR:
            downgrade("flagged", "built 1981 — verify month vs June 1981 code date")
    else:
        downgrade("flagged", "build year unknown — verify ≥1981")

    # 3. Price.
    if listing.price_yen is None:
        downgrade("flagged", "price unknown")
    elif listing.price_yen > PRICE_STRETCH:
        downgrade("reject", f"over ¥10M (¥{listing.price_yen:,})")
    elif listing.price_yen > PRICE_PASS:
        downgrade("stretch", f"stretch price ¥{listing.price_yen:,} (>¥7.5M)")

    # 4. Town ordinance known?
    if listing.town not in KNOWN_TOWNS:
        town = listing.town or "unknown"
        downgrade("flagged", f"town '{town}' minpaku ordinance not vetted")

    # 5. Structure/title/access flags surfaced by the parsers.
    for f in listing.flags:
        if "unregistered" in f:
            downgrade("flagged", "unregistered structure (未登記) — title/finance risk")
        elif "no parking" in f:
            downgrade("flagged", "no parking — ski guests drive")
        elif "urbanization-control" in f:
            downgrade("flagged", "urbanization-control zone — reno/rebuild restricted")

    return _finalize(listing, verdict, reasons)


def _finalize(listing: Listing, verdict: str, reasons: list[str]) -> Listing:
    listing.verdict = verdict
    listing.verdict_reasons = reasons
    return listing


def annotate_all(listings: list[Listing]) -> list[Listing]:
    return [annotate(l) for l in listings]
