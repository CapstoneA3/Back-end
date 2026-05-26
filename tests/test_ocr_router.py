import pytest
from decimal import Decimal
from datetime import date
from types import SimpleNamespace
from io import BytesIO
from unittest.mock import patch, AsyncMock

import httpx
from fastapi import HTTPException

from app.schemas.ocr import OcrScanCandidate, OcrCandidate, OcrScanResult


def _make_scan_candidates() -> list[OcrScanCandidate]:
    return [
        OcrScanCandidate(
            raw_text="닭가슴살200g",
            recommended_action="register",
            candidates=[OcrCandidate(ingredient_master_id=5, ingredient_name="닭가슴살", confidence=95.0)],
        ),
        OcrScanCandidate(raw_text="비닐봉투", recommended_action="skip", candidates=[]),
    ]


def _make_mock_userinventory(ingredient_master_id: int = 5) -> SimpleNamespace:
    """InventoryRead.model_validate(obj) 호환 SimpleNamespace."""
    return SimpleNamespace(
        id=1,
        user_id="user1",
        ingredient_master_id=ingredient_master_id,
        quantity=Decimal("200.0"),
        unit="g",
        expire_date=date(2026, 6, 10),
        created_at=date(2026, 5, 27),
        ingredient=SimpleNamespace(
            id=ingredient_master_id, bit_id=4, name="닭가슴살",
            category="육류", default_shelf_days=5, risk_factor=Decimal("3.0"),
        ),
    )


@pytest.mark.asyncio
async def test_scan_success(client):
    mock_raw = [type("R", (), {"text": "닭가슴살200g"})()]
    mock_candidates = _make_scan_candidates()

    with patch("app.routers.ocr.scan_receipt", AsyncMock(return_value=mock_raw)), \
         patch("app.routers.ocr.match_items", AsyncMock(return_value=mock_candidates)):
        resp = await client.post(
            "/api/v1/ocr/scan",
            files={"image": ("receipt.jpg", BytesIO(b"fake"), "image/jpeg")},
        )

    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    items = body["data"]["items"]
    assert len(items) == 2
    assert items[0]["recommended_action"] == "register"
    assert items[1]["recommended_action"] == "skip"


@pytest.mark.asyncio
async def test_scan_timeout_returns_504(client):
    with patch("app.routers.ocr.scan_receipt",
               AsyncMock(side_effect=httpx.TimeoutException("timeout"))):
        resp = await client.post(
            "/api/v1/ocr/scan",
            files={"image": ("receipt.jpg", BytesIO(b"fake"), "image/jpeg")},
        )

    assert resp.status_code == 504
    assert "timeout" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_confirm_all_success(client):
    mock_inv = _make_mock_userinventory()

    with patch("app.routers.ocr.register_ingredient", AsyncMock(return_value=mock_inv)):
        resp = await client.post(
            "/api/v1/ocr/confirm",
            json={"items": [{"ingredient_master_id": 5, "quantity": "200.0"}]},
        )

    assert resp.status_code == 201
    data = resp.json()["data"]
    assert len(data["registered"]) == 1
    assert data["errors"] == []


@pytest.mark.asyncio
async def test_confirm_partial_failure(client):
    async def side_effect(db, redis, user_id, inv_create):
        if inv_create.ingredient_master_id == 999:
            raise HTTPException(status_code=404, detail="Ingredient not found")
        return _make_mock_userinventory(inv_create.ingredient_master_id)

    with patch("app.routers.ocr.register_ingredient", AsyncMock(side_effect=side_effect)):
        resp = await client.post(
            "/api/v1/ocr/confirm",
            json={"items": [
                {"ingredient_master_id": 5, "quantity": "1.0"},
                {"ingredient_master_id": 999, "quantity": "1.0"},
            ]},
        )

    assert resp.status_code == 201
    data = resp.json()["data"]
    assert len(data["registered"]) == 1
    assert len(data["errors"]) == 1
    assert data["errors"][0]["ingredient_master_id"] == 999
    assert data["errors"][0]["reason"] == "Ingredient not found"


@pytest.mark.asyncio
async def test_confirm_rejects_zero_quantity(client):
    with patch("app.routers.ocr.register_ingredient", AsyncMock()) as mock_reg:
        resp = await client.post(
            "/api/v1/ocr/confirm",
            json={"items": [{"ingredient_master_id": 5, "quantity": "0"}]},
        )

    assert resp.status_code == 422
    mock_reg.assert_not_called()
