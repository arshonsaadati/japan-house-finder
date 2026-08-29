from akiya.filters import annotate
from akiya.models import Listing


def _mk(**kw) -> Listing:
    base = dict(
        source="test", source_id="x", url="u", property_type="detached",
        status="live", town="Otaru", price_yen=5_000_000, build_year=1995,
    )
    base.update(kw)
    return Listing(**base)


def test_clean_pass():
    l = annotate(_mk())
    assert l.verdict == "pass"


def test_price_stretch():
    l = annotate(_mk(price_yen=9_000_000))
    assert l.verdict == "stretch"


def test_price_over_ceiling_rejects():
    l = annotate(_mk(price_yen=15_000_000))
    assert l.verdict == "reject"


def test_pre_1981_rejects():
    l = annotate(_mk(build_year=1975))
    assert l.verdict == "reject"


def test_condo_rejects():
    l = annotate(_mk(property_type="condo"))
    assert l.verdict == "reject"


def test_sold_rejects():
    l = annotate(_mk(status="sold"))
    assert l.verdict == "reject"


def test_unknown_town_flagged_not_rejected():
    l = annotate(_mk(town="Furubira"))
    assert l.verdict == "flagged"


def test_unregistered_flag_downgrades_to_flagged():
    l = annotate(_mk(flags=["unregistered structure (未登記)"]))
    assert l.verdict == "flagged"


def test_negotiating_flagged():
    l = annotate(_mk(status="negotiating"))
    assert l.verdict == "flagged"


def test_worst_reason_wins():
    # pre-1981 (reject) beats unknown-town (flagged)
    l = annotate(_mk(build_year=1970, town="Nowhere"))
    assert l.verdict == "reject"
