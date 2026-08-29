from akiya.underwrite import Assumptions, run, sensitivity


def test_reproduces_handoff_shape():
    # ~$200K all-in ski property, 100 winter nights @ $300 => gross $30K,
    # net in the handoff's $12-20K / 6-10% band.
    a = Assumptions(price_yen=9_750_000, reno_yen=70_000 * 150, winter_adr_usd=300, winter_nights=100)
    r = run(a)
    assert r.gross_revenue_usd == 30_000
    assert 9_000 <= r.noi_usd <= 20_000
    assert 0.05 <= r.net_yield <= 0.11


def test_reno_multiple_default():
    a = Assumptions(price_yen=6_800_000, reno_mult=3.0)
    r = run(a)
    # reno = 3 x purchase
    assert r.acquisition_breakdown["renovation"] == round(6_800_000 * 3 / 150)


def test_explicit_reno_overrides_multiple():
    a = Assumptions(price_yen=6_800_000, reno_mult=3.0, reno_yen=1_000_000)
    r = run(a)
    assert r.acquisition_breakdown["renovation"] == round(1_000_000 / 150)


def test_bar_pass_fail():
    good = run(Assumptions(price_yen=3_000_000, reno_mult=2.0, winter_nights=110, winter_adr_usd=320))
    bad = run(Assumptions(price_yen=6_800_000, reno_mult=3.0, winter_nights=90, winter_adr_usd=260))
    assert good.net_yield > bad.net_yield
    assert good.passes_bar is (good.net_yield >= 0.06)
    assert bad.passes_bar is False


def test_after_tax_less_than_pretax():
    r = run(Assumptions(price_yen=5_000_000))
    assert r.after_tax_noi_usd < r.noi_usd
    assert abs(r.after_tax_noi_usd - r.noi_usd * (1 - 0.2042)) < 2


def test_accommodation_tax_is_passthrough():
    # Guest-paid; it should not change owner NOI.
    base = run(Assumptions(price_yen=5_000_000))
    taxed = run(Assumptions(price_yen=5_000_000, accommodation_tax_pct=0.03))
    assert base.noi_usd == taxed.noi_usd
    assert taxed.accommodation_tax_collected_usd > 0


def test_sensitivity_grid_shape():
    rows = sensitivity(Assumptions(price_yen=5_000_000, winter_nights=100))
    assert len(rows) == 9  # 3 reno multiples x 3 night counts
    assert {r["reno_mult"] for r in rows} == {2.0, 3.0, 5.0}
