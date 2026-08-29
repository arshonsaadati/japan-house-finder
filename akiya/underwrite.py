"""Underwriting model implementing the handoff P&L.

All money is computed in USD at a configurable FX rate (default ¥150/USD).
The bar: net operating yield (pre JP income tax) >= 6% of all-in cost.

Defaults encode the handoff's assumptions; every one is overridable. The
model is deliberately a set of pure functions so it can be tested against the
handoff's worked numbers ($30-37K gross -> $13-20K net, 7-10%, on $200K all-in).
"""

from __future__ import annotations

from dataclasses import dataclass, asdict

FX = 150.0  # yen per USD
NET_YIELD_BAR = 0.06
WITHHOLDING = 0.2042  # 20.42% non-resident withholding on net rental income


@dataclass
class Assumptions:
    # Acquisition
    price_yen: int
    reno_mult: float = 3.0            # reno = mult x purchase (handoff: 2-5x, pessimistic for snow)
    reno_yen: int | None = None       # explicit override; wins over reno_mult
    fx: float = FX
    closing_pct: float = 0.07         # closing costs on purchase
    furnishing_usd: float = 13_000.0
    contingency_pct: float = 0.10     # on (purchase+closing+reno+furnishing)

    # Revenue
    winter_nights: int = 100
    winter_adr_usd: float = 300.0
    shoulder_nights: int = 0          # ~0 for non-Furano Hokkaido
    shoulder_adr_usd: float = 120.0
    avg_stay_nights: float = 4.0      # for turnover / cleaning count

    # Operating costs
    mgmt_pct: float = 0.20            # management co. % of revenue (law requires one)
    ota_pct: float = 0.12             # Airbnb/Booking platform fee
    cleaning_per_turnover_usd: float = 80.0
    utilities_kerosene_usd: float = 2_500.0  # winter kerosene + electricity
    snow_clearing_usd: float = 1_500.0
    insurance_usd: float = 800.0
    tax_agent_usd: float = 1_500.0
    fixed_asset_tax_rate: float = 0.014   # ~1.4% of assessed value
    assessed_ratio: float = 0.6           # assessed value ~= 60% of purchase price

    # Guest-paid pass-through (excluded from owner P&L; reported for context)
    accommodation_tax_pct: float = 0.0    # set 0.03 for Kutchan/Niseko


@dataclass
class Result:
    all_in_usd: float
    acquisition_breakdown: dict[str, int]
    gross_revenue_usd: float
    opex_breakdown: dict[str, int]
    total_opex_usd: float
    noi_usd: float                # net operating income, pre JP income tax
    net_yield: float
    after_tax_noi_usd: float
    after_tax_yield: float
    passes_bar: bool
    accommodation_tax_collected_usd: float

    def to_dict(self) -> dict:
        return asdict(self)


def _reno_yen(a: Assumptions) -> int:
    return a.reno_yen if a.reno_yen is not None else int(a.price_yen * a.reno_mult)


def run(a: Assumptions) -> Result:
    purchase = a.price_yen / a.fx
    closing = purchase * a.closing_pct
    reno = _reno_yen(a) / a.fx
    subtotal = purchase + closing + reno + a.furnishing_usd
    contingency = subtotal * a.contingency_pct
    all_in = subtotal + contingency

    acquisition = {
        "purchase": round(purchase),
        "closing": round(closing),
        "renovation": round(reno),
        "furnishing": round(a.furnishing_usd),
        "contingency": round(contingency),
    }

    gross = (
        a.winter_nights * a.winter_adr_usd
        + a.shoulder_nights * a.shoulder_adr_usd
    )

    total_nights = a.winter_nights + a.shoulder_nights
    turnovers = total_nights / a.avg_stay_nights if a.avg_stay_nights else 0
    mgmt = gross * a.mgmt_pct
    ota = gross * a.ota_pct
    cleaning = turnovers * a.cleaning_per_turnover_usd
    fixed_asset_tax = (a.price_yen * a.assessed_ratio * a.fixed_asset_tax_rate) / a.fx

    opex = {
        "management": round(mgmt),
        "ota_fees": round(ota),
        "cleaning": round(cleaning),
        "utilities_kerosene": round(a.utilities_kerosene_usd),
        "snow_clearing": round(a.snow_clearing_usd),
        "insurance": round(a.insurance_usd),
        "fixed_asset_tax": round(fixed_asset_tax),
        "tax_agent": round(a.tax_agent_usd),
    }
    total_opex = sum(opex.values())
    noi = gross - total_opex
    net_yield = noi / all_in if all_in else 0.0

    # JP withholding applies to positive net rental income.
    after_tax_noi = noi - max(noi, 0) * WITHHOLDING
    after_tax_yield = after_tax_noi / all_in if all_in else 0.0

    accom_tax = gross * a.accommodation_tax_pct  # guest-paid, pass-through

    return Result(
        all_in_usd=round(all_in),
        acquisition_breakdown=acquisition,
        gross_revenue_usd=round(gross),
        opex_breakdown=opex,
        total_opex_usd=round(total_opex),
        noi_usd=round(noi),
        net_yield=net_yield,
        after_tax_noi_usd=round(after_tax_noi),
        after_tax_yield=after_tax_yield,
        passes_bar=net_yield >= NET_YIELD_BAR,
        accommodation_tax_collected_usd=round(accom_tax),
    )


def sensitivity(a: Assumptions) -> list[dict]:
    """Grid over reno multiple x winter-night count; report net yield each."""
    rows = []
    for reno_mult in (2.0, 3.0, 5.0):
        for nights in (a.winter_nights - 20, a.winter_nights, a.winter_nights + 20):
            variant = Assumptions(**{**asdict(a), "reno_mult": reno_mult,
                                     "reno_yen": None, "winter_nights": max(nights, 0)})
            r = run(variant)
            rows.append({
                "reno_mult": reno_mult,
                "winter_nights": max(nights, 0),
                "all_in_usd": r.all_in_usd,
                "noi_usd": r.noi_usd,
                "net_yield": r.net_yield,
                "passes": r.passes_bar,
            })
    return rows
