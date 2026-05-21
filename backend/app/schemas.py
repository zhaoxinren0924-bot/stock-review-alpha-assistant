"""Pydantic schemas for API request/response validation."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class StockBase(BaseModel):
    """Base stock schema."""

    code: str = Field(..., min_length=1, max_length=8, description="股票代码")
    name: str = Field(..., min_length=1, max_length=50, description="股票名称")
    industry: str | None = Field(None, max_length=50, description="所属行业")
    market: str | None = Field(None, max_length=10, description="市场 (SH/SZ/BJ)")


class StockCreate(StockBase):
    """Schema for creating a stock."""


class StockResponse(StockBase):
    """Schema for stock response."""

    model_config = ConfigDict(from_attributes=True)

    created_at: datetime


class StockListResponse(BaseModel):
    """Schema for stock list response."""

    stocks: list[StockResponse]
    count: int
