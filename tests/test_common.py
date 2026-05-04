from app.schemas.common import ApiResponse, ApiErrorResponse


def test_api_response_success():
    resp = ApiResponse(success=True, data={"key": "value"}, message="ok")
    assert resp.success is True
    assert resp.data == {"key": "value"}


def test_api_response_error():
    resp = ApiErrorResponse(error={"code": "NOT_FOUND", "message": "없음"})
    assert resp.success is False
    assert resp.error.code == "NOT_FOUND"
