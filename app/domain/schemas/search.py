from enum import Enum
from math import ceil
from typing import Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class SortBy(str, Enum):
    price_asc = "price_asc"
    price_desc = "price_desc"
    name_asc = "name_asc"
    name_desc = "name_desc"


class ProductSearchParams(BaseModel):
    q: str | None = None
    sku: str | None = None
    category_id: str | None = None
    category_slug: str | None = None
    min_price: float | None = None
    max_price: float | None = None
    page: int = Field(1, ge=1)
    limit: int = Field(20, ge=1, le=100)
    sort_by: SortBy = SortBy.name_asc


class PaginatedResponse(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int
    limit: int
    pages: int

    @classmethod
    def build(cls, items: list[T], total: int, page: int, limit: int) -> "PaginatedResponse[T]":
        return cls(items=items, total=total, page=page, limit=limit, pages=ceil(total / limit) if limit else 0)
