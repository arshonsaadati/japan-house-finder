"""JSON-backed listing store with first_seen / last_seen / change history."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from .models import Listing

DEFAULT_PATH = Path(__file__).resolve().parent.parent / "data" / "listings.json"

# Fields whose changes we record in a listing's history.
TRACKED = ("price_yen", "status", "verdict")

_STATUS_RANK = {"live": 0, "negotiating": 1, "sold": 2, "rental": 3}
_CORE_FIELDS = ("price_yen", "layout", "building_m2", "land_m2", "build_year", "town")


def _completeness(l: Listing) -> int:
    return sum(getattr(l, f) is not None for f in _CORE_FIELDS)


def dedupe(listings: list[Listing]) -> list[Listing]:
    """Collapse same-key listings within one scrape.

    A property is sometimes relisted (sale + rental variants share an ID).
    Keep the most actionable: live > negotiating > sold > rental, breaking
    ties by field completeness.
    """
    best: dict[str, Listing] = {}
    for l in listings:
        cur = best.get(l.key)
        if cur is None:
            best[l.key] = l
            continue
        rank = (_STATUS_RANK.get(l.status, 9), -_completeness(l))
        cur_rank = (_STATUS_RANK.get(cur.status, 9), -_completeness(cur))
        if rank < cur_rank:
            best[l.key] = l
    return list(best.values())


class Store:
    def __init__(self, path: Path | None = None):
        self.path = path or DEFAULT_PATH
        self.listings: dict[str, Listing] = {}
        self._load()

    def _load(self) -> None:
        if self.path.exists():
            data = json.loads(self.path.read_text(encoding="utf-8"))
            for d in data.get("listings", []):
                l = Listing.from_dict(d)
                self.listings[l.key] = l

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "updated": date.today().isoformat(),
            "count": len(self.listings),
            "listings": [l.to_dict() for l in self.listings.values()],
        }
        self.path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True),
            encoding="utf-8",
        )

    def upsert(self, incoming: list[Listing], today: str | None = None) -> dict[str, list[Listing]]:
        """Merge a fresh scrape into the store.

        Returns a change report: {'new','price','status','gone'} lists.
        'gone' = keys in the store for a scraped source but not seen this run.
        """
        today = today or date.today().isoformat()
        incoming = dedupe(incoming)
        report: dict[str, list[Listing]] = {"new": [], "price": [], "status": [], "gone": []}
        seen_keys = {l.key for l in incoming}
        scraped_sources = {l.source for l in incoming}

        for fresh in incoming:
            existing = self.listings.get(fresh.key)
            if existing is None:
                fresh.first_seen = today
                fresh.last_seen = today
                self.listings[fresh.key] = fresh
                report["new"].append(fresh)
                continue

            # Record tracked-field changes.
            changes = []
            for field_name in TRACKED:
                old = getattr(existing, field_name)
                new = getattr(fresh, field_name)
                if old != new:
                    changes.append({"field": field_name, "from": old, "to": new, "on": today})
            if changes:
                fresh.history = existing.history + changes
                if any(c["field"] == "price_yen" for c in changes):
                    report["price"].append(fresh)
                if any(c["field"] == "status" for c in changes):
                    report["status"].append(fresh)
            else:
                fresh.history = existing.history

            fresh.first_seen = existing.first_seen or today
            fresh.last_seen = today
            self.listings[fresh.key] = fresh

        # Anything from a scraped source not seen this run has likely churned out.
        for key, l in self.listings.items():
            if l.source in scraped_sources and key not in seen_keys:
                if l.status != "sold" and l.last_seen != today:
                    report["gone"].append(l)

        return report

    def query(
        self,
        verdict: str | None = None,
        town: str | None = None,
        max_price: int | None = None,
        source: str | None = None,
    ) -> list[Listing]:
        out = list(self.listings.values())
        if verdict:
            out = [l for l in out if l.verdict == verdict]
        if town:
            out = [l for l in out if (l.town or "").lower() == town.lower()]
        if max_price is not None:
            out = [l for l in out if l.price_yen is not None and l.price_yen <= max_price]
        if source:
            out = [l for l in out if l.source == source]
        out.sort(key=lambda l: (l.price_yen is None, l.price_yen or 0))
        return out

    def get(self, key: str) -> Listing | None:
        return self.listings.get(key)
