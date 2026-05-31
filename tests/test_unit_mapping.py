from app.core.unit_mapping import CATEGORY_UNITS

EXPECTED_CATEGORIES = [
    "곡류/면/떡", "육류", "생선/해산물", "채소", "계란/콩/두부",
    "유제품/치즈", "김치/절임/묵", "해조류/건어물", "과일/견과",
    "가공식품/기타", "조미료",
]


def test_all_categories_present():
    for cat in EXPECTED_CATEGORIES:
        assert cat in CATEGORY_UNITS, f"카테고리 '{cat}' 누락"


def test_each_value_is_nonempty_list():
    for cat, units in CATEGORY_UNITS.items():
        assert isinstance(units, list) and len(units) > 0, f"'{cat}' 단위 목록 비어있음"


def test_all_units_are_strings():
    for cat, units in CATEGORY_UNITS.items():
        for u in units:
            assert isinstance(u, str), f"'{cat}'의 단위 '{u}'가 str이 아님"


def test_default_units_per_category():
    assert CATEGORY_UNITS["채소"][0] == "g"
    assert CATEGORY_UNITS["육류"][0] == "g"
    assert CATEGORY_UNITS["계란/콩/두부"][0] == "개"
    assert CATEGORY_UNITS["유제품/치즈"][0] == "ml"
    assert CATEGORY_UNITS["조미료"][0] == "g"
