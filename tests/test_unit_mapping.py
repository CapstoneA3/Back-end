"""
식재료별 허용 단위 매핑 테스트.

INGREDIENT_UNITS는 CSV (docs/단위정리.csv)에서 추출한
427개 식재료별 기본 단위를 갖는 딕셔너리.
"""

from app.core.unit_mapping import INGREDIENT_UNITS


def test_all_427_ingredients_present():
    """427개 식재료가 모두 포함되어 있는지 확인."""
    assert len(INGREDIENT_UNITS) == 427, f"예상 427개, 실제 {len(INGREDIENT_UNITS)}개"


def test_each_ingredient_has_string_unit():
    """모든 식재료의 단위가 문자열인지 확인."""
    for ingredient, unit in INGREDIENT_UNITS.items():
        assert isinstance(unit, str), f"'{ingredient}'의 단위 '{unit}'가 str이 아님"
        assert len(unit) > 0, f"'{ingredient}'의 단위가 비어있음"


def test_sample_ingredients_have_correct_units():
    """샘플 식재료들이 올바른 단위를 갖는지 확인."""
    samples = {
        "쌀": "g",
        "달걀": "개",
        "우유": "ml",
        "갈비": "kg",
        "갈치": "마리",
        "김": "장",
        "두부": "모",
    }
    for ingredient, expected_unit in samples.items():
        assert ingredient in INGREDIENT_UNITS, f"'{ingredient}' 누락"
        assert INGREDIENT_UNITS[ingredient] == expected_unit, \
            f"'{ingredient}': 예상 '{expected_unit}', 실제 '{INGREDIENT_UNITS[ingredient]}'"


def test_units_are_not_quantity_ranges():
    """선택 가능한 수량 범위(amount_1~4)는 제외되었는지 확인."""
    # 숫자만 있는 단위는 없어야 함
    for ingredient, unit in INGREDIENT_UNITS.items():
        assert not unit.isdigit(), f"'{ingredient}'에 숫자만 있는 단위 '{unit}'"
