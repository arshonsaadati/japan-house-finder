from akiya.models import (
    parse_price,
    parse_area,
    parse_build_year,
    parse_layout,
    town_from_text,
)


def test_parse_price_man():
    assert parse_price("680万円") == 6_800_000
    assert parse_price("480万円") == 4_800_000
    assert parse_price("1,500万円") == 15_000_000


def test_parse_price_oku():
    assert parse_price("1億2000万円") == 120_000_000
    assert parse_price("2億円") == 200_000_000


def test_parse_price_bare_yen_and_fullwidth():
    assert parse_price("3,800,000円") == 3_800_000
    assert parse_price("３８０万円") == 3_800_000  # full-width digits


def test_parse_price_none():
    assert parse_price(None) is None
    assert parse_price("応談") is None


def test_parse_area_m2_variants():
    assert parse_area("112.61㎡（約34坪）") == 112.61
    assert parse_area("450.36m 2 （登記）") == 450.36  # SUUMO superscript split
    assert parse_area("77.76m²") == 77.76


def test_parse_area_tsubo_conversion():
    # 25.1坪 -> ~82.98 m²
    v = parse_area("約25.1坪")
    assert v is not None and 82 < v < 84


def test_parse_build_year_gregorian_and_wareki():
    assert parse_build_year("1994年築") == 1994
    assert parse_build_year("1994年11月") == 1994
    assert parse_build_year("昭和62年") == 1987
    assert parse_build_year("平成6年築") == 1994
    assert parse_build_year("令和2年") == 2020


def test_parse_build_year_relative_age():
    # 築36年 resolved against a fixed reference year
    assert parse_build_year("木造2階建 7DK 築36年", this_year=2026) == 1990


def test_parse_layout():
    assert parse_layout("5LDK   140.9㎡") == "5LDK"
    assert parse_layout("1994年築　3LDK　112.61㎡") == "3LDK"
    assert parse_layout("3LDK+S") == "3LDK+S"
    assert parse_layout("土地のみ") is None


def test_town_from_text():
    assert town_from_text("余市町黒川町") == "Yoichi"
    assert town_from_text("北海道 小樽市 銭函") == "Otaru"
    assert town_from_text("寿都町開進町") == "Suttsu"
    assert town_from_text("東京都新宿区") is None
