from typing import Generic, TypeVar, Optional
from pydantic import BaseModel

T = TypeVar("T")


class ApiResponse(BaseModel, Generic[T]):
    success: bool = True
    data: Optional[T] = None
    message: str = ""


class ErrorDetail(BaseModel):
    code: str
    message: str


class ApiErrorResponse(BaseModel):
    success: bool = False
    error: ErrorDetail
