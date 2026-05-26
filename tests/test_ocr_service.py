import pytest
import httpx
from unittest.mock import patch, AsyncMock, MagicMock

from app.services.ocr_service import scan_receipt
from app.schemas.ocr import OcrRawItem


def _make_clova_response(items: list[dict]) -> MagicMock:
    resp = MagicMock()
    resp.raise_for_status = MagicMock()
    resp.json.return_value = {
        "images": [{
            "receipt": {
                "result": {
                    "subResults": [{"items": items}]
                }
            }
        }]
    }
    return resp


def _patch_client(mock_response: MagicMock):
    """httpx.AsyncClient context manager 패치 헬퍼."""
    mock_instance = AsyncMock()
    mock_instance.post = AsyncMock(return_value=mock_response)
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=mock_instance)
    cm.__aexit__ = AsyncMock(return_value=None)
    return patch("app.services.ocr_service.httpx.AsyncClient", return_value=cm)


@pytest.mark.asyncio
async def test_scan_receipt_parses_items():
    mock_resp = _make_clova_response([
        {"name": {"text": "닭가슴살200g"}},
        {"name": {"text": "달걀 10구"}},
    ])
    with _patch_client(mock_resp):
        result = await scan_receipt(b"fake_image", "receipt.jpg")

    assert len(result) == 2
    assert result[0].text == "닭가슴살200g"
    assert result[1].text == "달걀 10구"


@pytest.mark.asyncio
async def test_scan_receipt_skips_empty_text():
    mock_resp = _make_clova_response([
        {"name": {"text": "닭가슴살"}},
        {"name": {"text": "   "}},   # 공백만 있는 텍스트 → 제외
    ])
    with _patch_client(mock_resp):
        result = await scan_receipt(b"fake_image", "receipt.jpg")

    assert len(result) == 1
    assert result[0].text == "닭가슴살"


@pytest.mark.asyncio
async def test_scan_receipt_empty_subresults():
    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json.return_value = {
        "images": [{"receipt": {"result": {"subResults": []}}}]
    }
    with _patch_client(mock_resp):
        result = await scan_receipt(b"fake_image", "receipt.jpg")

    assert result == []


@pytest.mark.asyncio
async def test_scan_receipt_timeout_propagates():
    mock_instance = AsyncMock()
    mock_instance.post = AsyncMock(side_effect=httpx.TimeoutException("timeout"))
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=mock_instance)
    cm.__aexit__ = AsyncMock(return_value=None)

    with patch("app.services.ocr_service.httpx.AsyncClient", return_value=cm):
        with pytest.raises(httpx.TimeoutException):
            await scan_receipt(b"fake_image", "receipt.jpg")
