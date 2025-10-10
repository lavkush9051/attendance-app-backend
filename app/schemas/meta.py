from pydantic import BaseModel
from typing import Optional, Any, Dict

class ApiResponse(BaseModel):
    status: str
    message: Optional[str] = None
    data: Optional[Any] = None
    error: Optional[str] = None

class SuccessResponse(ApiResponse):
    status: str = "success"

class ErrorResponse(ApiResponse):
    status: str = "failed"
    error: str

class PaginationMeta(BaseModel):
    total: int
    page: int
    per_page: int
    total_pages: int

class PaginatedResponse(BaseModel):
    items: list
    meta: PaginationMeta