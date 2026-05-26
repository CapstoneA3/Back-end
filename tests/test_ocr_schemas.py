import pytest
from datetime import date
from decimal import Decimal
from pydantic import ValidationError

from app.schemas.ocr import (
    OcrRawItem,
    OcrCandidate,
    OcrScanCandidate,
    OcrScanResult,
    OcrConfirmItem,
    OcrConfirmRequest,
    OcrConfirmError,
    OcrConfirmResult,
)


def test_ocr_raw_item():
    item = OcrRawItem(text="닭가슴살200g")
    assert item.text == "닭가슴살200g"


def test_ocr_candidate():
    c = OcrCandidate(ingredient_master_id=5, ingredient_name="닭가슴살", confidence=95.2)
    assert c.confidence == 95.2


def test_ocr_scan_candidate_register():
    c = OcrScanCandidate(
        raw_text="닭가슴살200g",
        recommended_action="register",
        candidates=[OcrCandidate(ingredient_master_id=5, ingredient_name="닭가슴살", confidence=95.2)],
    )
    assert c.recommended_action == "register"
    assert len(c.candidates) == 1


def test_ocr_scan_candidate_skip():
    c = OcrScanCandidate(raw_text="비닐봉투", recommended_action="skip", candidates=[])
    assert c.candidates == []


def test_ocr_scan_result():
    r = OcrScanResult(items=[])
    assert r.items == []


def test_ocr_confirm_item_with_expire():
    item = OcrConfirmItem(
        ingredient_master_id=5,
        quantity=Decimal("200.0"),
        expire_date=date(2026, 6, 10),
    )
    assert item.expire_date == date(2026, 6, 10)


def test_ocr_confirm_item_without_expire():
    item = OcrConfirmItem(ingredient_master_id=5, quantity=Decimal("1.0"))
    assert item.expire_date is None


def test_ocr_confirm_item_rejects_zero_quantity():
    with pytest.raises(ValidationError):
        OcrConfirmItem(ingredient_master_id=5, quantity=Decimal("0"))


def test_ocr_confirm_request():
    req = OcrConfirmRequest(items=[
        OcrConfirmItem(ingredient_master_id=5, quantity=Decimal("200.0")),
    ])
    assert len(req.items) == 1


def test_ocr_confirm_result_defaults():
    r = OcrConfirmResult(registered=[], errors=[])
    assert r.registered == []
    assert r.errors == []


def test_ocr_confirm_error():
    e = OcrConfirmError(ingredient_master_id=999, reason="Ingredient not found")
    assert e.ingredient_master_id == 999
