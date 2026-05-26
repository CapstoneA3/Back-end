import pytest
from unittest.mock import AsyncMock, MagicMock
from types import SimpleNamespace

from app.services.matching_service import match_items
from app.schemas.ocr import OcrRawItem


def _make_db_mock(names: list[tuple[int, str]]) -> AsyncMock:
    """(id, name) 리스트로 ingredient_master DB mock 생성."""
    masters = [SimpleNamespace(id=id_, name=name) for id_, name in names]
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = masters
    db = AsyncMock()
    db.execute = AsyncMock(return_value=mock_result)
    return db


@pytest.mark.asyncio
async def test_match_exact():
    db = _make_db_mock([(5, "닭가슴살"), (2, "달걀")])
    result = await match_items(db, [OcrRawItem(text="닭가슴살")])

    assert len(result) == 1
    assert result[0].raw_text == "닭가슴살"
    assert result[0].recommended_action == "register"
    assert result[0].candidates[0].ingredient_master_id == 5
    assert result[0].candidates[0].confidence == 100.0


@pytest.mark.asyncio
async def test_match_override_egg():
    db = _make_db_mock([(2, "달걀"), (5, "닭가슴살")])
    result = await match_items(db, [OcrRawItem(text="계란")])

    assert result[0].recommended_action == "register"
    assert result[0].candidates[0].ingredient_master_id == 2  # "달걀"로 매핑됨


@pytest.mark.asyncio
async def test_match_exclude_keyword():
    db = _make_db_mock([(1, "닭가슴살")])
    result = await match_items(db, [OcrRawItem(text="비닐봉투")])

    assert result[0].recommended_action == "skip"
    assert result[0].candidates == []


@pytest.mark.asyncio
async def test_match_fuzzy_high_confidence():
    db = _make_db_mock([(5, "닭가슴살"), (2, "달걀"), (10, "돼지고기")])
    result = await match_items(db, [OcrRawItem(text="닭가슴살200g")])

    assert result[0].recommended_action == "register"
    assert len(result[0].candidates) <= 3
    # 첫 번째 후보가 "닭가슴살"이어야 함
    assert result[0].candidates[0].ingredient_master_id == 5


@pytest.mark.asyncio
async def test_match_low_confidence_skip():
    db = _make_db_mock([(1, "사과"), (2, "배")])
    result = await match_items(db, [OcrRawItem(text="xyzabc_완전다름!!")])

    assert result[0].recommended_action == "skip"


@pytest.mark.asyncio
async def test_match_empty_items():
    db = _make_db_mock([(5, "닭가슴살")])
    result = await match_items(db, [])

    assert result == []


@pytest.mark.asyncio
async def test_match_multiple_items():
    db = _make_db_mock([(5, "닭가슴살"), (2, "달걀")])
    result = await match_items(db, [
        OcrRawItem(text="닭가슴살"),
        OcrRawItem(text="비닐봉투"),
        OcrRawItem(text="계란"),
    ])

    assert len(result) == 3
    assert result[0].recommended_action == "register"
    assert result[1].recommended_action == "skip"
    assert result[2].recommended_action == "register"
