"""Pydantic schemas for API request/response validation."""

from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class StockBase(BaseModel):
    """Base stock schema."""

    code: str = Field(..., min_length=1, max_length=8, description="Stock code")
    name: str = Field(..., min_length=1, max_length=50, description="Stock name")
    industry: str | None = Field(None, max_length=50, description="Industry")
    market: str | None = Field(None, max_length=10, description="Market (SH/SZ/BJ)")


class StockCreate(StockBase):
    """Schema for creating a stock."""


class StockResponse(StockBase):
    """Schema for stock response."""

    model_config = ConfigDict(from_attributes=True)

    created_at: datetime


class StockListResponse(BaseModel):
    """Schema for stock list response."""

    items: list[StockResponse]
    count: int


class HypothesisBase(BaseModel):
    """Base hypothesis schema."""

    category: str = Field(..., min_length=1, max_length=30)
    status: str = Field("unverified", min_length=1, max_length=20)
    content: dict[str, Any]
    confidence: int = Field(80, ge=0, le=100)
    evidence: str | None = None
    next_review_date: date | None = None


class HypothesisCreate(HypothesisBase):
    """Schema for creating a hypothesis."""


class HypothesisUpdate(BaseModel):
    """Schema for partially updating a hypothesis."""

    category: str | None = Field(None, min_length=1, max_length=30)
    status: str | None = Field(None, min_length=1, max_length=20)
    content: dict[str, Any] | None = None
    confidence: int | None = Field(None, ge=0, le=100)
    evidence: str | None = None
    next_review_date: date | None = None


class HypothesisResponse(HypothesisBase):
    """Schema for hypothesis response."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    updated_at: datetime


class HypothesisListResponse(BaseModel):
    """Schema for hypothesis list response."""

    items: list[HypothesisResponse]
    count: int


class CheckItemBase(BaseModel):
    """Base check item schema."""

    content: str = Field(..., min_length=1)
    due_date: date | None = None
    status: str = Field("pending", min_length=1, max_length=20)
    linked_hypothesis_id: int | None = None
    source_type: str | None = Field(None, max_length=30)


class CheckItemCreate(CheckItemBase):
    """Schema for creating a check item."""


class CheckItemUpdate(BaseModel):
    """Schema for partially updating a check item."""

    content: str | None = Field(None, min_length=1)
    due_date: date | None = None
    status: str | None = Field(None, min_length=1, max_length=20)
    linked_hypothesis_id: int | None = None
    source_type: str | None = Field(None, max_length=30)
    completed_at: datetime | None = None


class CheckItemResponse(CheckItemBase):
    """Schema for check item response."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    stock_code: str
    completed_at: datetime | None = None
    created_at: datetime


class CheckItemListResponse(BaseModel):
    """Schema for check item list response."""

    items: list[CheckItemResponse]
    count: int


class ReviewBase(BaseModel):
    """Base review schema."""

    review_type: str = Field(..., min_length=1, max_length=30)
    title: str | None = Field(None, max_length=100)
    content: str = Field(..., min_length=1)
    conclusions: str | None = None
    action_items: list[str] = Field(default_factory=list)
    trigger_event_id: int | None = None


class ReviewCreate(ReviewBase):
    """Schema for creating a review."""


class ReviewUpdate(BaseModel):
    """Schema for partially updating a review."""

    review_type: str | None = Field(None, min_length=1, max_length=30)
    title: str | None = Field(None, max_length=100)
    content: str | None = Field(None, min_length=1)
    conclusions: str | None = None
    action_items: list[str] | None = None
    trigger_event_id: int | None = None


class ReviewResponse(ReviewBase):
    """Schema for review response."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    stock_code: str
    created_at: datetime


class ReviewListResponse(BaseModel):
    """Schema for review list response."""

    items: list[ReviewResponse]
    count: int


class DailyReviewUpdate(BaseModel):
    """Schema for updating a structured daily review."""

    status: str | None = Field(None, min_length=1, max_length=20)
    market_style: str | None = Field(None, max_length=50)
    main_sector: str | None = Field(None, max_length=100)
    sentiment: str | None = Field(None, max_length=50)
    content: dict[str, Any] | None = None


class DailyReviewResponse(BaseModel):
    """Structured daily review response."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    review_date: date
    status: str
    market_style: str | None = None
    main_sector: str | None = None
    sentiment: str | None = None
    content: dict[str, Any]
    created_at: datetime
    updated_at: datetime


class DailyReviewListResponse(BaseModel):
    """Daily review list response."""

    items: list[DailyReviewResponse]
    count: int


class DailyReviewPrefillResponse(BaseModel):
    """Result of applying available data to the daily review template."""

    review: DailyReviewResponse
    filled: dict[str, int]
    missing: list[str]
    evidence_cards: list["EvidenceCard"]


class DailyReviewCoachRequest(BaseModel):
    """AI coach request for one daily review section."""

    message: str = Field(..., min_length=1)
    section_key: str | None = Field(None, max_length=50)
    history: list[dict[str, Any]] = Field(default_factory=list)


class DailyReviewCoachResponse(BaseModel):
    """AI coach response for daily review workflow."""

    reply: str
    actions: list["AiAction"]
    evidence_cards: list["EvidenceCard"]


class DataRefreshRequest(BaseModel):
    """Request for refreshing data sources for a stock."""

    types: list[str] = Field(default_factory=lambda: ["announcement", "news", "quote", "metric"])
    lookback_days: int = Field(30, ge=1, le=365)


class DataRefreshResponse(BaseModel):
    """Refresh result with non-fatal provider errors."""

    stock_code: str
    created: dict[str, int]
    skipped: dict[str, int]
    errors: list[dict[str, str]]
    refreshed_at: datetime


class EventResponse(BaseModel):
    """Normalized market event response."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    stock_code: str
    title: str
    summary: str | None = None
    source_provider: str | None = None
    source_url: str | None = None
    source_type: str
    event_type: str | None = None
    confidence: int | None = None
    published_at: datetime
    fetched_at: datetime


class EventListResponse(BaseModel):
    """Event list response."""

    items: list[EventResponse]
    count: int


class MetricResponse(BaseModel):
    """Fundamental metric response."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    stock_code: str
    metric_code: str
    metric_name: str
    metric_category: str | None = None
    value: float | None = None
    unit: str | None = None
    period: str | None = None
    report_date: date | None = None
    source_provider: str | None = None
    created_at: datetime


class MetricListResponse(BaseModel):
    """Metric list response."""

    items: list[MetricResponse]
    count: int


class QuoteResponse(BaseModel):
    """Quote snapshot response."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    stock_code: str
    date: date
    open_price: float | None = None
    high: float | None = None
    low: float | None = None
    close: float | None = None
    volume: int | None = None
    amount: float | None = None
    pe: float | None = None
    pb: float | None = None
    market_cap: float | None = None
    created_at: datetime


class QuoteListResponse(BaseModel):
    """Quote list response."""

    items: list[QuoteResponse]
    count: int


class EvidenceListResponse(BaseModel):
    """Evidence card list response."""

    items: list["EvidenceCard"]
    count: int


class ImpactResponse(BaseModel):
    """AI-generated impact response."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    event_id: int
    hypothesis_id: int | None = None
    metric_id: int | None = None
    impact_direction: str | None = None
    impact_strength: int | None = None
    reason: str | None = None
    evidence_text: str | None = None
    confidence: int | None = None
    user_confirmed: bool = False


class ImpactAnalysisResponse(BaseModel):
    """Event impact analysis with pending actions."""

    reply: str
    actions: list["AiAction"]
    evidence_cards: list["EvidenceCard"]
    impacts: list[ImpactResponse]


class AiChatRequest(BaseModel):
    """Schema for AI chat requests."""

    stock_code: str = Field(..., min_length=1, max_length=8)
    message: str = Field(..., min_length=1)
    history: list[dict[str, Any]] = Field(default_factory=list)


class AiAction(BaseModel):
    """Structured AI-generated action waiting for user confirmation."""

    type: str
    payload: dict[str, Any]


class EvidenceCard(BaseModel):
    """Standardized evidence shown before AI-derived conclusions."""

    source_level: str
    source_type: str
    source_provider: str
    source_url: str | None = None
    title: str
    summary: str
    published_at: datetime | None = None
    fetched_at: datetime | None = None
    confidence: int = Field(..., ge=0, le=100)
    evidence_boundary: str


class AiChatResponse(BaseModel):
    """Schema for AI chat responses."""

    reply: str
    actions: list[AiAction]
    evidence_cards: list[EvidenceCard] = Field(default_factory=list)


class AiProviderStatusResponse(BaseModel):
    """Non-sensitive AI provider status."""

    provider: str | None
    configured: bool


class AiActionApplyRequest(AiAction):
    """Schema for applying an AI action."""


class AiActionApplyResponse(BaseModel):
    """Schema for an applied AI action."""

    type: str
    result: dict[str, Any]
