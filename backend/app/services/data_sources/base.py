"""Common DTOs and adapter interface for market data providers."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any, Protocol

DataType = str


@dataclass(frozen=True)
class AdapterError:
    """A structured provider error that should not fail the whole refresh."""

    provider: str
    data_type: DataType
    message: str


@dataclass(frozen=True)
class SourceRecord:
    """Raw source payload before normalization."""

    source_type: str
    source_provider: str
    title: str
    published_at: datetime
    fetched_at: datetime
    source_url: str | None = None
    source_id: str | None = None
    raw_content: str | None = None
    raw_payload: dict[str, Any] | None = None
    confidence: int = 70


@dataclass(frozen=True)
class EventRecord:
    """Normalized announcement or news event."""

    source_type: str
    source_provider: str
    title: str
    summary: str
    published_at: datetime
    fetched_at: datetime
    source_url: str | None = None
    content: str | None = None
    event_type: str | None = None
    confidence: int = 70
    raw_source_key: str | None = None


@dataclass(frozen=True)
class QuoteRecord:
    """Normalized daily quote and valuation snapshot."""

    source_provider: str
    date: date
    fetched_at: datetime
    open_price: float | None = None
    high: float | None = None
    low: float | None = None
    close: float | None = None
    volume: int | None = None
    amount: float | None = None
    pe: float | None = None
    pb: float | None = None
    market_cap: float | None = None
    source_url: str | None = None
    raw_payload: dict[str, Any] | None = None
    confidence: int = 82


@dataclass(frozen=True)
class MetricRecord:
    """Normalized fundamental or valuation metric."""

    source_provider: str
    metric_code: str
    metric_name: str
    fetched_at: datetime
    value: float | None = None
    unit: str | None = None
    period: str | None = None
    report_date: date | None = None
    metric_category: str | None = None
    source_url: str | None = None
    raw_payload: dict[str, Any] | None = None
    confidence: int = 82


@dataclass(frozen=True)
class AdapterResult:
    """Provider result split into normalized payloads and non-fatal errors."""

    raw_sources: list[SourceRecord] = field(default_factory=list)
    events: list[EventRecord] = field(default_factory=list)
    quotes: list[QuoteRecord] = field(default_factory=list)
    metrics: list[MetricRecord] = field(default_factory=list)
    errors: list[AdapterError] = field(default_factory=list)


class DataSourceAdapter(Protocol):
    """Provider interface used by the refresh service."""

    provider_name: str

    def fetch(self, stock_code: str, data_types: set[DataType], lookback_days: int) -> AdapterResult:
        """Fetch and normalize provider records for one stock."""
