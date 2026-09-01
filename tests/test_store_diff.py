from akiya.models import Listing
from akiya.store import Store, dedupe


def _mk(source_id, **kw) -> Listing:
    base = dict(source="s", source_id=source_id, url="u", status="live", price_yen=5_000_000)
    base.update(kw)
    return Listing(**base)


def test_dedupe_prefers_live_over_sold():
    live = _mk("A", status="live")
    sold = _mk("A", status="sold")
    kept = dedupe([sold, live])
    assert len(kept) == 1
    assert kept[0].status == "live"


def test_dedupe_breaks_ties_by_completeness():
    sparse = _mk("A", status="sold", build_year=None, layout=None)
    full = _mk("A", status="sold", build_year=1995, layout="3LDK", building_m2=100.0)
    kept = dedupe([sparse, full])
    assert kept[0].build_year == 1995


def test_upsert_new_then_no_change(tmp_path):
    store = Store(path=tmp_path / "s.json")
    r1 = store.upsert([_mk("A")], today="2026-01-01")
    assert len(r1["new"]) == 1
    store.save()

    store2 = Store(path=tmp_path / "s.json")
    r2 = store2.upsert([_mk("A")], today="2026-01-02")
    assert r2["new"] == []
    assert r2["price"] == []
    assert store2.get("s:A").first_seen == "2026-01-01"
    assert store2.get("s:A").last_seen == "2026-01-02"


def test_upsert_price_change_recorded(tmp_path):
    store = Store(path=tmp_path / "s.json")
    store.upsert([_mk("A", price_yen=5_000_000)], today="2026-01-01")
    store.save()

    store2 = Store(path=tmp_path / "s.json")
    r = store2.upsert([_mk("A", price_yen=4_000_000)], today="2026-01-02")
    assert len(r["price"]) == 1
    hist = store2.get("s:A").history
    assert any(c["field"] == "price_yen" and c["to"] == 4_000_000 for c in hist)


def test_upsert_gone_detection(tmp_path):
    store = Store(path=tmp_path / "s.json")
    store.upsert([_mk("A"), _mk("B")], today="2026-01-01")
    store.save()

    store2 = Store(path=tmp_path / "s.json")
    r = store2.upsert([_mk("A")], today="2026-01-02")  # B disappeared
    gone_ids = [l.source_id for l in r["gone"]]
    assert gone_ids == ["B"]


def test_query_sorts_by_price(tmp_path):
    store = Store(path=tmp_path / "s.json")
    store.upsert([_mk("A", price_yen=9_000_000), _mk("B", price_yen=3_000_000)], today="2026-01-01")
    result = store.query()
    assert [l.source_id for l in result] == ["B", "A"]


def test_upsert_preserves_enrichment(tmp_path):
    store = Store(path=tmp_path / "s.json")
    rich = _mk("A")
    rich.image_urls = ["u1", "u2", "u3"]
    rich.local_images = ["/x/00.jpg"]
    store.upsert([rich], today="2026-01-01")
    store.save()

    store2 = Store(path=tmp_path / "s.json")
    fresh = _mk("A")
    fresh.image_urls = ["cover_only"]  # API knows just the cover
    store2.upsert([fresh], today="2026-01-02")
    kept = store2.get("s:A")
    assert kept.image_urls == ["u1", "u2", "u3"]
    assert kept.local_images == ["/x/00.jpg"]

    # but a genuinely richer fresh scrape wins
    store3 = Store(path=tmp_path / "s.json")
    richer = _mk("A")
    richer.image_urls = ["n1", "n2", "n3", "n4"]
    store3.upsert([richer], today="2026-01-03")
    # (store2 wasn't saved; richer vs original 3 urls)
    assert store3.get("s:A").image_urls == ["n1", "n2", "n3", "n4"]
