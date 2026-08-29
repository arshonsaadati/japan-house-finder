"""Listing schema and Japanese real-estate text normalizers."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field, asdict
from datetime import date
from typing import Any

TSUBO_TO_M2 = 3.30579

# Municipality canonicalization for the target region (and neighbors that
# show up in the same sources). Keys are matched as substrings of addresses.
TOWNS: dict[str, str] = {
    "小樽市": "Otaru",
    "余市町": "Yoichi",
    "倶知安町": "Kutchan",
    "ニセコ町": "Niseko",
    "蘭越町": "Rankoshi",
    "寿都町": "Suttsu",
    "赤井川村": "Akaigawa",
    "富良野市": "Furano",
    "岩内町": "Iwanai",
    "共和町": "Kyowa",
    "京極町": "Kyogoku",
    "喜茂別町": "Kimobetsu",
    "仁木町": "Niki",
    "積丹町": "Shakotan",
    "古平町": "Furubira",
    "黒松内町": "Kuromatsunai",
    "泊村": "Tomari",
    "真狩村": "Makkari",
    "留寿都村": "Rusutsu",
    "島牧村": "Shimamaki",
    "神恵内村": "Kamoenai",
    "札幌市": "Sapporo",
}

# Era bases: era year 1 starts in the base+1 gregorian year (昭和1 = 1926).
_WAREKI_BASE = {"昭和": 1925, "平成": 1988, "令和": 2018, "大正": 1911}


def _norm(text: str) -> str:
    """NFKC-normalize so full-width digits/punctuation become ASCII."""
    return unicodedata.normalize("NFKC", text)


def parse_price(text: str | None) -> int | None:
    """'680万円' -> 6_800_000; '1,200万円' -> 12_000_000; '1億2000万円' -> 120_000_000.

    Also accepts bare yen amounts like '4,800,000円' or '3.8万円' (rent).
    """
    if not text:
        return None
    t = _norm(text).replace(",", "")
    m = re.search(r"(?:(\d+(?:\.\d+)?)億)?(?:(\d+(?:\.\d+)?)万)?(?:(\d+))?円", t)
    if not m or not any(m.groups()):
        return None
    oku, man, en = m.groups()
    total = 0.0
    if oku:
        total += float(oku) * 100_000_000
    if man:
        total += float(man) * 10_000
    if en and not (oku or man):
        total += float(en)
    return int(total) if total else None


def parse_area(text: str | None) -> float | None:
    """'112.61㎡（約34坪）' -> 112.61; '約25.1坪' -> m²; '450.36m 2 （登記）' -> 450.36.

    SUUMO renders m² as m<sup>2</sup>, which flattens to 'm 2' with a space —
    hence the tolerant unit pattern below.
    """
    if not text:
        return None
    t = _norm(text)
    m = re.search(r"(\d+(?:\.\d+)?)\s*(?:㎡|m\s*[²2]|平米|平方メートル)", t, re.IGNORECASE)
    if m:
        return float(m.group(1))
    m = re.search(r"(\d+(?:\.\d+)?)\s*坪", t)
    if m:
        return round(float(m.group(1)) * TSUBO_TO_M2, 2)
    return None


def parse_build_year(text: str | None, this_year: int | None = None) -> int | None:
    """'1994年築' / '1994年11月' / '昭和62年' / '平成6年築' / '築36年' -> gregorian year.

    '築N年' is a relative age (N years old); resolved against `this_year`
    (defaults to the current year).
    """
    if not text:
        return None
    t = _norm(text)
    # Relative age: 築36年 -> current year minus 36.
    m = re.search(r"築\s*(\d{1,3})\s*年", t)
    if m:
        year_now = this_year or date.today().year
        return year_now - int(m.group(1))
    for era, base in _WAREKI_BASE.items():
        m = re.search(era + r"\s*(\d{1,2}|元)\s*年", t)
        if m:
            y = 1 if m.group(1) == "元" else int(m.group(1))
            return base + y
    m = re.search(r"(19\d{2}|20\d{2})\s*年", t)
    if m:
        return int(m.group(1))
    return None


def parse_layout(text: str | None) -> str | None:
    """Extract '3LDK', '5LDK+S', '2DK' etc."""
    if not text:
        return None
    t = _norm(text).upper()
    m = re.search(r"(\d+[SLDK]{1,3}(?:\+\d*S)?)", t)
    if m:
        layout = m.group(1)
        # Guard against matching pure numbers or areas: require a letter.
        if re.search(r"[SLDK]", layout):
            return layout
    return None


def town_from_text(text: str | None) -> str | None:
    """Find a known municipality name anywhere in address/title text."""
    if not text:
        return None
    for jp, en in TOWNS.items():
        if jp in text:
            return en
        # Sources sometimes drop the suffix (余市 for 余市町).
        if jp[:-1] in text and len(jp) >= 3:
            return en
    return None


@dataclass
class Listing:
    source: str
    source_id: str
    url: str
    title: str = ""
    town: str | None = None
    address: str | None = None
    price_yen: int | None = None
    layout: str | None = None
    building_m2: float | None = None
    land_m2: float | None = None
    build_year: int | None = None
    property_type: str = "unknown"  # detached | condo | land | business | mixed | unknown
    status: str = "live"  # live | negotiating | sold | rental
    flags: list[str] = field(default_factory=list)
    image_urls: list[str] = field(default_factory=list)   # remote listing photos
    local_images: list[str] = field(default_factory=list)  # downloaded file paths
    raw: dict[str, Any] = field(default_factory=dict)
    # Filled by filters.annotate():
    verdict: str | None = None  # pass | stretch | flagged | reject
    verdict_reasons: list[str] = field(default_factory=list)
    # Filled by the store:
    first_seen: str | None = None
    last_seen: str | None = None
    history: list[dict[str, Any]] = field(default_factory=list)

    @property
    def key(self) -> str:
        return f"{self.source}:{self.source_id}"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Listing":
        known = {f for f in cls.__dataclass_fields__}
        return cls(**{k: v for k, v in d.items() if k in known})
