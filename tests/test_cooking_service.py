import pytest
from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock
from pydantic import ValidationError


# ─── Schema tests ──────────────────────────────────────────────────

from app.schemas.cooking import (
    CookRequest,
    CookResult,
    IngredientDeductionResult,
    IngredientUsage,
    InventoryDeduction,
)


def test_cook_request_valid():
    req = CookRequest(ingredients=[
        IngredientUsage(ingredient_master_id=5, quantity=Decimal("200.0")),
    ])
    assert req.ingredients[0].quantity == Decimal("200.0")
    assert req.ingredients[0].ingredient_master_id == 5


def test_cook_request_rejects_zero_quantity():
    with pytest.raises(ValidationError):
        CookRequest(ingredients=[IngredientUsage(ingredient_master_id=5, quantity=Decimal("0.0"))])


def test_cook_request_rejects_negative_quantity():
    with pytest.raises(ValidationError):
        CookRequest(ingredients=[IngredientUsage(ingredient_master_id=5, quantity=Decimal("-10.0"))])


def test_cook_request_rejects_duplicate_ingredient():
    with pytest.raises(ValidationError):
        CookRequest(ingredients=[
            IngredientUsage(ingredient_master_id=5, quantity=Decimal("100.0")),
            IngredientUsage(ingredient_master_id=5, quantity=Decimal("50.0")),
        ])


def test_cook_request_empty_ingredients_ok():
    req = CookRequest(ingredients=[])
    assert req.ingredients == []


def test_cook_result_schema():
    result = CookResult(recipe_id=7, recipe_name="닭볶음탕", deductions=[])
    assert result.recipe_id == 7
    assert result.deductions == []


def test_inventory_deduction_schema():
    d = InventoryDeduction(inventory_id=10, deducted=Decimal("150.0"), deleted=True)
    assert d.deleted is True


def test_ingredient_deduction_result_schema():
    r = IngredientDeductionResult(
        ingredient_master_id=5,
        ingredient_name="닭가슴살",
        requested=Decimal("200.0"),
        deducted=Decimal("200.0"),
        rows_affected=[InventoryDeduction(inventory_id=10, deducted=Decimal("150.0"), deleted=True)],
    )
    assert r.deducted == Decimal("200.0")
    assert len(r.rows_affected) == 1


# ─── _alpha_score tests ────────────────────────────────────────────

from app.services.cooking_service import _alpha_score


def test_alpha_score_one_day_left():
    exp = date.today() + timedelta(days=1)
    assert _alpha_score(3.0, 200.0, exp) == 3.0 * 200.0 / (1 ** 2 + 1)  # 300.0


def test_alpha_score_clips_expired_to_one():
    exp = date.today() - timedelta(days=5)  # 이미 만료
    assert _alpha_score(1.0, 100.0, exp) == 1.0 * 100.0 / (1 ** 2 + 1)  # 50.0


def test_alpha_score_sooner_expiry_ranks_higher():
    today = date.today()
    urgent = _alpha_score(1.0, 100.0, today + timedelta(days=1))
    safe = _alpha_score(1.0, 100.0, today + timedelta(days=10))
    assert urgent > safe


def test_alpha_score_larger_quantity_ranks_higher_same_expiry():
    today = date.today()
    big = _alpha_score(1.0, 200.0, today + timedelta(days=5))
    small = _alpha_score(1.0, 100.0, today + timedelta(days=5))
    assert big > small


# ─── cook_recipe service tests ─────────────────────────────────────

from app.services.cooking_service import cook_recipe


def _make_recipe(recipe_id=7, name="닭볶음탕"):
    from unittest.mock import MagicMock
    r = MagicMock()
    r.id = recipe_id
    r.name = name
    return r


@pytest.mark.asyncio
async def test_cook_recipe_recipe_not_found(mock_db, mock_redis):
    from fastapi import HTTPException
    mock_db.get = AsyncMock(return_value=None)

    with pytest.raises(HTTPException) as exc:
        await cook_recipe(mock_db, mock_redis, "user1", 9999, CookRequest(ingredients=[]))

    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_cook_recipe_empty_ingredients_skips_db(mock_db, mock_redis):
    recipe = _make_recipe()
    mock_db.get = AsyncMock(return_value=recipe)
    mock_db.commit = AsyncMock()

    result = await cook_recipe(mock_db, mock_redis, "user1", 7, CookRequest(ingredients=[]))

    assert result.recipe_id == 7
    assert result.recipe_name == "닭볶음탕"
    assert result.deductions == []
    mock_db.commit.assert_not_called()


# ─── Deduction logic tests ─────────────────────────────────────────

def _make_im(mid=5, name="닭가슴살", risk_factor="3", bit_id=42):
    im = MagicMock()
    im.id = mid
    im.name = name
    im.risk_factor = Decimal(risk_factor)
    im.bit_id = bit_id
    return im


def _make_inv(item_id=10, user_id="user1", mid=5, quantity="200", days=3):
    item = MagicMock()
    item.id = item_id
    item.user_id = user_id
    item.ingredient_master_id = mid
    item.quantity = Decimal(quantity)
    item.expire_date = date.today() + timedelta(days=days)
    return item


def _db_result(rows):
    """db.execute()가 반환하는 결과 객체 목업."""
    r = MagicMock()
    r.scalars.return_value.all.return_value = rows
    return r


@pytest.mark.asyncio
async def test_cook_recipe_single_row_full_deduction(mock_db, mock_redis):
    """200g 요청, 200g 재고 1행 → 행 삭제 + 비트 클리어."""
    recipe = _make_recipe()
    im = _make_im()
    item = _make_inv(item_id=10, quantity="200", days=3)

    mock_db.get = AsyncMock(return_value=recipe)
    mock_db.execute = AsyncMock(side_effect=[_db_result([im]), _db_result([item])])
    mock_db.delete = AsyncMock()
    mock_db.commit = AsyncMock()
    mock_redis.get = AsyncMock(return_value=(0).to_bytes(54, "big"))
    mock_redis.set = AsyncMock()

    result = await cook_recipe(
        mock_db, mock_redis, "user1", 7,
        CookRequest(ingredients=[IngredientUsage(ingredient_master_id=5, quantity=Decimal("200"))]),
    )

    assert result.recipe_id == 7
    d = result.deductions[0]
    assert d.ingredient_master_id == 5
    assert d.requested == Decimal("200")
    assert d.deducted == Decimal("200")
    assert len(d.rows_affected) == 1
    assert d.rows_affected[0].inventory_id == 10
    assert d.rows_affected[0].deducted == Decimal("200")
    assert d.rows_affected[0].deleted is True
    mock_db.delete.assert_called_once_with(item)
    mock_redis.set.assert_called_once()  # 재고 소진 → 비트 클리어


@pytest.mark.asyncio
async def test_cook_recipe_alpha_order_sooner_expiry_first(mock_db, mock_redis):
    """item1(7일), item2(1일) 순서로 전달해도 item2부터 차감."""
    recipe = _make_recipe()
    im = _make_im()
    item1 = _make_inv(item_id=10, quantity="100", days=7)  # α낮음
    item2 = _make_inv(item_id=11, quantity="100", days=1)  # α높음

    mock_db.get = AsyncMock(return_value=recipe)
    # DB는 item1, item2 순서로 반환 (정렬 전)
    mock_db.execute = AsyncMock(side_effect=[_db_result([im]), _db_result([item1, item2])])
    mock_db.delete = AsyncMock()
    mock_db.commit = AsyncMock()
    mock_redis.get = AsyncMock(return_value=(0).to_bytes(54, "big"))
    mock_redis.set = AsyncMock()

    result = await cook_recipe(
        mock_db, mock_redis, "user1", 7,
        CookRequest(ingredients=[IngredientUsage(ingredient_master_id=5, quantity=Decimal("120"))]),
    )

    d = result.deductions[0]
    assert d.deducted == Decimal("120")
    # item2(1일, α높음) 먼저 전량 소진
    assert d.rows_affected[0].inventory_id == 11
    assert d.rows_affected[0].deducted == Decimal("100")
    assert d.rows_affected[0].deleted is True
    # item1(7일)에서 나머지 20g 차감
    assert d.rows_affected[1].inventory_id == 10
    assert d.rows_affected[1].deducted == Decimal("20")
    assert d.rows_affected[1].deleted is False
    # item1에 80g 잔여 → 비트 클리어 없음
    mock_redis.set.assert_not_called()


@pytest.mark.asyncio
async def test_cook_recipe_partial_deduction_insufficient_stock(mock_db, mock_redis):
    """100g 요청, 60g 재고 → 60g 차감 후 완전 소진 → 비트 클리어."""
    recipe = _make_recipe()
    im = _make_im()
    item = _make_inv(item_id=10, quantity="60", days=3)

    mock_db.get = AsyncMock(return_value=recipe)
    mock_db.execute = AsyncMock(side_effect=[_db_result([im]), _db_result([item])])
    mock_db.delete = AsyncMock()
    mock_db.commit = AsyncMock()
    mock_redis.get = AsyncMock(return_value=(0).to_bytes(54, "big"))
    mock_redis.set = AsyncMock()

    result = await cook_recipe(
        mock_db, mock_redis, "user1", 7,
        CookRequest(ingredients=[IngredientUsage(ingredient_master_id=5, quantity=Decimal("100"))]),
    )

    d = result.deductions[0]
    assert d.requested == Decimal("100")
    assert d.deducted == Decimal("60")  # 보유량만 차감
    assert d.rows_affected[0].deleted is True
    mock_redis.set.assert_called_once()  # 재고 완전 소진


@pytest.mark.asyncio
async def test_cook_recipe_no_inventory_for_ingredient(mock_db, mock_redis):
    """해당 재료 재고 없음 → deducted=0, 비트 클리어 없음."""
    recipe = _make_recipe()
    im = _make_im()

    mock_db.get = AsyncMock(return_value=recipe)
    mock_db.execute = AsyncMock(side_effect=[_db_result([im]), _db_result([])])
    mock_db.commit = AsyncMock()
    mock_redis.set = AsyncMock()

    result = await cook_recipe(
        mock_db, mock_redis, "user1", 7,
        CookRequest(ingredients=[IngredientUsage(ingredient_master_id=5, quantity=Decimal("100"))]),
    )

    d = result.deductions[0]
    assert d.deducted == Decimal("0")
    assert d.rows_affected == []
    mock_redis.set.assert_not_called()


@pytest.mark.asyncio
async def test_cook_recipe_multiple_ingredients(mock_db, mock_redis):
    """재료 2개 요청: 첫 번째 소진(비트 클리어), 두 번째 잔여 있음."""
    recipe = _make_recipe()
    im_a = _make_im(mid=5, name="닭가슴살", bit_id=42)
    im_b = _make_im(mid=12, name="양파", risk_factor="1", bit_id=10)
    item_a = _make_inv(item_id=10, mid=5, quantity="100", days=2)
    item_b = _make_inv(item_id=20, mid=12, quantity="200", days=5)

    mock_db.get = AsyncMock(return_value=recipe)
    mock_db.execute = AsyncMock(
        side_effect=[_db_result([im_a, im_b]), _db_result([item_a, item_b])]
    )
    mock_db.delete = AsyncMock()
    mock_db.commit = AsyncMock()
    mock_redis.get = AsyncMock(return_value=(0).to_bytes(54, "big"))
    mock_redis.set = AsyncMock()

    result = await cook_recipe(
        mock_db, mock_redis, "user1", 7,
        CookRequest(ingredients=[
            IngredientUsage(ingredient_master_id=5, quantity=Decimal("100")),   # 전량 소진
            IngredientUsage(ingredient_master_id=12, quantity=Decimal("50")),   # 150g 잔여
        ]),
    )

    assert len(result.deductions) == 2
    da = next(d for d in result.deductions if d.ingredient_master_id == 5)
    db_ = next(d for d in result.deductions if d.ingredient_master_id == 12)

    assert da.deducted == Decimal("100")
    assert da.rows_affected[0].deleted is True

    assert db_.deducted == Decimal("50")
    assert db_.rows_affected[0].deleted is False

    # 닭가슴살(42번 비트)만 클리어, 양파는 잔여 있으므로 set 1회
    assert mock_redis.set.call_count == 1


@pytest.mark.asyncio
async def test_cook_recipe_unknown_ingredient_master(mock_db, mock_redis):
    """IngredientMaster에 없는 ingredient_master_id → ingredient_name=str(mid), 비트 클리어 없음."""
    recipe = _make_recipe()
    item = _make_inv(item_id=10, mid=99, quantity="100", days=3)

    mock_db.get = AsyncMock(return_value=recipe)
    # IngredientMaster 조회 결과 없음 (unknown id)
    mock_db.execute = AsyncMock(side_effect=[_db_result([]), _db_result([item])])
    mock_db.delete = AsyncMock()
    mock_db.commit = AsyncMock()
    mock_redis.set = AsyncMock()

    result = await cook_recipe(
        mock_db, mock_redis, "user1", 7,
        CookRequest(ingredients=[IngredientUsage(ingredient_master_id=99, quantity=Decimal("100"))]),
    )

    d = result.deductions[0]
    assert d.ingredient_name == "99"  # fallback: str(mid)
    assert d.deducted == Decimal("100")  # 재고는 정상 차감
    mock_redis.set.assert_not_called()  # im is None → 비트 클리어 없음
