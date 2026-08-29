from pathlib import Path

from akiya.sources import akiyabank_blogspot as bs
from akiya.sources import homes_akiyabank as hm
from akiya.sources import suumo as su

FIX = Path(__file__).parent / "fixtures"


def _blogspot():
    return bs.parse_feed((FIX / "blogspot_feed.json").read_text(encoding="utf-8"))


def test_blogspot_parses_all_structured_posts():
    listings = _blogspot()
    # 127 feed entries, 4 are sold-announcement posts with no structured data.
    assert len(listings) == 123


def test_blogspot_live_leads_match_handoff():
    by_id = {l.source_id: l for l in _blogspot()}
    yoichi = by_id["S-19-017"]
    assert yoichi.town == "Yoichi"
    assert yoichi.price_yen == 6_800_000
    assert yoichi.build_year == 1994
    assert yoichi.layout == "3LDK"
    assert yoichi.building_m2 == 112.61
    assert yoichi.status == "live"
    assert any("no parking" in f for f in yoichi.flags)

    suttsu = by_id["S-03-004"]
    assert suttsu.town == "Suttsu"
    assert suttsu.price_yen == 4_800_000
    assert suttsu.build_year == 1987
    assert any("unregistered" in f for f in suttsu.flags)


def test_blogspot_floor_area_sum():
    # S-17-002 has no total building area; floors are summed (68.04 + 68.04).
    by_id = {l.source_id: l for l in _blogspot()}
    furubira = by_id["S-17-002"]
    assert furubira.building_m2 == 136.08


def test_suumo_results_page():
    listings = su.parse_results_page((FIX / "suumo_otaru.html").read_text(encoding="utf-8"))
    assert len(listings) == 20
    # every card should have price, layout, both areas, build year
    for l in listings:
        assert l.price_yen is not None
        assert l.property_type == "detached"
        assert l.building_m2 is not None
        assert l.land_m2 is not None
        assert l.build_year is not None


def test_homes_detail_condo_detection():
    l = hm.parse_detail(
        (FIX / "homes_detail_b47650.html").read_text(encoding="utf-8"),
        "https://www.homes.co.jp/akiyabank/b-47650/",
        "売買居住用",
    )
    # RC structure + upper floor -> condo, not a detached house
    assert l.property_type == "condo"
    assert l.price_yen == 3_800_000
    assert l.build_year == 1982
    assert l.layout == "4LDK"
    assert l.town == "Otaru"


def test_homes_city_page_cards():
    cards = hm.parse_city_page((FIX / "homes_otaru.html").read_text(encoding="utf-8"))
    assert len(cards) == 6
    cats = [c[1] for c in cards]
    assert any("売買" in c for c in cats)
