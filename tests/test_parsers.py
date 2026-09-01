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


def test_akiyajapan_api_parsing():
    import json
    from akiya.sources import akiyajapan as aj
    data = json.loads((FIX / "akiyajapan_api_otaru.json").read_text(encoding="utf-8"))
    listings = [aj.parse_result(r, "Otaru") for r in data["results"]]
    assert len(listings) == 50
    for l in listings:
        assert l.source_id
        assert l.url.startswith("https://")
        assert l.price_yen is not None          # exact JPY, not approximated
        assert l.property_type == "detached"    # this fixture is type=house
        assert l.town == "Otaru"
    # labeled sizes come straight from the API (no size-guessing)
    sized = [l for l in listings if l.building_m2 and l.land_m2]
    assert sized  # at least some have both
    # build years are real ints
    assert all(isinstance(l.build_year, int) for l in listings if l.build_year is not None)


def test_akiyajapan_feature_flags():
    import json
    from akiya.sources import akiyajapan as aj
    data = json.loads((FIX / "akiyajapan_api_otaru.json").read_text(encoding="utf-8"))
    # A result missing "parking" in features should get the no-parking flag.
    no_parking = next(
        (r for r in data["results"] if "parking" not in (r.get("features") or [])), None
    )
    if no_parking:
        l = aj.parse_result(no_parking, "Otaru")
        assert any("no parking" in f for f in l.flags)


def test_akiyajapan_cdn_image_mapping():
    from akiya.sources.akiyajapan import _cdn_image
    # www.akiyajapan.com/storage/... 404s; must map to the DO Spaces CDN.
    api_url = "https://www.akiyajapan.com/storage/property/hm/hm_abc_123.jpg"
    out = _cdn_image(api_url)
    assert out == "https://akiyajapan.sgp1.cdn.digitaloceanspaces.com/storage/property/hm/hm_abc_123.jpg"
    assert _cdn_image(None) is None


def test_suumo_hires_rewrite():
    from akiya.sources.suumo import hires, HIRES_WIDTH

    thumb = ("https://img01.suumo.com/jj/resizeImage?src=gazo%2Fbukken%2F010%2FN010000"
             "%2Fimg%2F196%2F20742196%2F20742196_0001.jpg&w=192&h=144")
    hi = hires(thumb)
    assert hi.endswith(f"&w={HIRES_WIDTH}") and "h=144" not in hi
    assert hires(hi) == hi  # idempotent
    assert hires("https://example.com/x.jpg") == "https://example.com/x.jpg"


def test_suumo_detail_gallery():
    from akiya.sources.suumo import parse_detail_gallery, HIRES_WIDTH

    html = (FIX / "suumo_detail_20742196.html").read_text(encoding="utf-8")
    urls = parse_detail_gallery(html, "20742196")
    assert len(urls) >= 5
    assert all(u.endswith(f"&w={HIRES_WIDTH}") for u in urls)
    assert all("20742196" in u for u in urls)
    assert urls[0].split("&")[0].endswith("20742196_0001.jpg")
    assert len(set(urls)) == len(urls)


def test_suumo_detail_coords():
    from akiya.sources.suumo import parse_detail_coords

    html = (FIX / "suumo_detail_20742196.html").read_text(encoding="utf-8")
    lat, lng = parse_detail_coords(html)
    assert abs(lat - 43.1365) < 0.001 and abs(lng - 141.1630) < 0.001
    assert parse_detail_coords("<html>no map</html>") is None


def test_akiyajapan_property_gallery_excludes_related_listings():
    from akiya.sources.akiyajapan import parse_property_gallery
    cdn = "https://akiyajapan.sgp1.cdn.digitaloceanspaces.com/storage/property"
    own = "aaaa1111"
    html = (
        f'<img src="{cdn}/hm/mine1.jpg"><img src="{cdn}/hm/mine1.jpg">'
        f'<a href="/property/{own}"><img src="{cdn}/hm/mine2.jpg"></a>'
        f'<a href="/property/bbbb2222"><img src="{cdn}/hm/theirs.jpg"></a>'
    )
    urls = parse_property_gallery(html, own)
    assert urls == [f"{cdn}/hm/mine1.jpg", f"{cdn}/hm/mine2.jpg"]
    assert parse_property_gallery("<html>none</html>", own) == []


def test_akiyajapan_property_gallery_real_fixture():
    from akiya.sources.akiyajapan import parse_property_gallery
    html = (FIX / "akiyajapan_property.html").read_text(encoding="utf-8")
    own = "53616c7465645f5f3c1e169b81628fb42f64cbaeb5b32e4d62890e28cc9dcfd5"
    urls = parse_property_gallery(html, own)
    # This listing owns exactly the hm_766bcf6f… photos; the page also embeds
    # 11 related-listing covers that must all be excluded.
    assert urls, "gallery should not be empty"
    assert all("766bcf6f" in u for u in urls), urls
    # thumbs are normalized to their full-res .jpg twins and deduped
    assert len(urls) == 4
    assert all(u.endswith(".jpg") and "_thumb" not in u for u in urls)
    for foreign in ("9c414009", "bb3220c5", "ec3adc8c", "3ba3ef4f"):
        assert not any(foreign in u for u in urls)


def test_akiyajapan_photo_set_ids():
    from akiya.sources.akiyajapan import photo_set_ids
    cdn = "https://akiyajapan.sgp1.cdn.digitaloceanspaces.com/storage/property"
    urls = [
        f"{cdn}/hm/hm_766bcf6f-a19d-11f1-a659-a6ae20f6eefe_10e0a79d7ea52.jpg",
        f"{cdn}/hm/hm_766bcf6f-a19d-11f1-a659-a6ae20f6eefe_4657c03e52abf_thumb.webp",
        f"{cdn}/sp/sp_9c414009-8f8a-11f1-a659-a6ae20f6eefe_aaa.jpg",
    ]
    ids = photo_set_ids(urls)
    assert ids == {"766bcf6f-a19d-11f1-a659-a6ae20f6eefe",
                   "9c414009-8f8a-11f1-a659-a6ae20f6eefe"}
    assert photo_set_ids(["https://example.com/x.jpg"]) == set()


def test_suumo_city_url_prefecture_forms():
    from akiya.sources.suumo import _city_url, CITY_SLUGS
    pref, slug = CITY_SLUGS["Otaru"]
    assert _city_url(pref, slug, 1) == "https://suumo.jp/chukoikkodate/hokkaido_/sc_otaru/"
    pref, slug = CITY_SLUGS["Onomichi"]
    assert _city_url(pref, slug, 2) == "https://suumo.jp/chukoikkodate/hiroshima/sc_onomichi/?page=2"


def test_suumo_gallery_excludes_promo_images():
    from akiya.sources.suumo import parse_detail_gallery
    html = (FIX / "suumo_detail_kurashiki_20511819.html").read_text(encoding="utf-8")
    urls = parse_detail_gallery(html, "20511819")
    assert len(urls) == 26  # 28 own-id images minus the gift + pamphlet promos
    # the two promo files (0030 = プレゼント, 0031 = pamphlet) must be gone
    assert not any("_0030.jpg" in u or "_0031.jpg" in u for u in urls)
    assert all("20511819" in u for u in urls)
