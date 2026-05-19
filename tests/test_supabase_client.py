from unittest.mock import AsyncMock, patch
import app.core.supabase_client as sc


async def test_get_supabase_returns_client():
    sc._client = None
    mock_client = object()
    with patch("app.core.supabase_client.acreate_client", new=AsyncMock(return_value=mock_client)):
        result = await sc.get_supabase()
    assert result is mock_client
    sc._client = None


async def test_get_supabase_is_singleton():
    sc._client = None
    mock_client = object()
    with patch("app.core.supabase_client.acreate_client", new=AsyncMock(return_value=mock_client)) as m:
        await sc.get_supabase()
        await sc.get_supabase()
    assert m.call_count == 1
    sc._client = None
