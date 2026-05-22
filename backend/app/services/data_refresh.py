"""Refresh and persist standardized evidence from provider adapters."""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from app.models import Event, FundamentalMetric, QuoteSnapshot, RawSource
from app.services.data_sources.akshare_adapter import AkshareAdapter
from app.services.data_sources.baostock_adapter import BaoStockAdapter
from app.services.data_sources.base import (
    AdapterError,
    DataSourceAdapter,
    EventRecord,
    MetricRecord,
    QuoteRecord,
    SourceRecord,
)
from app.services.data_sources.tushare_adapter import TushareAdapter

DEFAULT_REFRESH_TYPES = {"announcement", "news", "quote", "metric"}


@dataclass
class RefreshSummary:
    """Result of refreshing one stock."""

    stock_code: str
    created: dict[str, int] = field(default_factory=dict)
    skipped: dict[str, int] = field(default_factory=dict)
    errors: list[dict[str, str]] = field(default_factory=list)
    refreshed_at: datetime = field(default_factory=datetime.utcnow)


class DataRefreshService:
    """Orchestrate provider adapters and write normalized evidence to SQLite."""

    def __init__(self, adapters: list[DataSourceAdapter] | None = None) -> None:
        self.adapters = adapters or [AkshareAdapter(), BaoStockAdapter(), TushareAdapter()]

    def refresh_stock(
        self,
        db: Session,
        stock_code: str,
        data_types: set[str] | None = None,
        lookback_days: int = 30,
    ) -> RefreshSummary:
        requested = data_types or DEFAULT_REFRESH_TYPES
        created: Counter[str] = Counter()
        skipped: Counter[str] = Counter()
        errors: list[dict[str, str]] = []

        for adapter in self.adapters:
            result = adapter.fetch(stock_code, requested, lookback_days)
            for error in result.errors:
                errors.append(_error_dict(error))
            raw_by_key = self._persist_raw_sources(db, result.raw_sources, created, skipped)
            self._persist_events(db, stock_code, result.events, raw_by_key, created, skipped)
            self._persist_quotes(db, stock_code, result.quotes, created, skipped)
            self._persist_metrics(db, stock_code, result.metrics, raw_by_key, created, skipped)

        db.commit()
        return RefreshSummary(
            stock_code=stock_code,
            created=dict(created),
            skipped=dict(skipped),
            errors=errors,
        )

    def _persist_raw_sources(
        self,
        db: Session,
        records: list[SourceRecord],
        created: Counter[str],
        skipped: Counter[str],
    ) -> dict[str, RawSource]:
        raw_by_key: dict[str, RawSource] = {}
        for record in records:
            checksum = _checksum(
                {
                    "provider": record.source_provider,
                    "type": record.source_type,
                    "title": record.title,
                    "published_at": record.published_at.isoformat(),
                    "payload": record.raw_payload,
                }
            )
            existing = db.query(RawSource).filter(RawSource.checksum == checksum).first()
            key = _source_key(record.source_provider, record.source_type, record.title, record.published_at)
            if existing:
                raw_by_key[key] = existing
                skipped["raw_sources"] += 1
                continue
            raw_source = RawSource(
                source_type=record.source_type,
                source_provider=record.source_provider,
                source_url=record.source_url,
                source_id=record.source_id,
                title=record.title,
                raw_content=record.raw_content,
                raw_payload=record.raw_payload,
                published_at=record.published_at,
                fetched_at=record.fetched_at,
                checksum=checksum,
            )
            db.add(raw_source)
            db.flush()
            raw_by_key[key] = raw_source
            created["raw_sources"] += 1
        return raw_by_key

    def _persist_events(
        self,
        db: Session,
        stock_code: str,
        records: list[EventRecord],
        raw_by_key: dict[str, RawSource],
        created: Counter[str],
        skipped: Counter[str],
    ) -> None:
        for record in records:
            fingerprint = _fingerprint(stock_code, record.source_provider, record.source_type, record.title, record.published_at)
            if db.query(Event).filter(Event.fingerprint == fingerprint).first():
                skipped["events"] += 1
                continue
            key = record.raw_source_key or _source_key(
                record.source_provider,
                record.source_type,
                record.title,
                record.published_at,
            )
            raw_source = raw_by_key.get(key)
            db.add(
                Event(
                    raw_source_id=raw_source.id if raw_source else None,
                    stock_code=stock_code,
                    fingerprint=fingerprint,
                    title=record.title,
                    content=record.content,
                    summary=record.summary,
                    source=record.source_provider,
                    source_provider=record.source_provider,
                    source_url=record.source_url,
                    source_type=record.source_type,
                    event_type=record.event_type,
                    confidence=record.confidence,
                    published_at=record.published_at,
                    fetched_at=record.fetched_at,
                    created_by="system",
                )
            )
            created["events"] += 1

    def _persist_quotes(
        self,
        db: Session,
        stock_code: str,
        records: list[QuoteRecord],
        created: Counter[str],
        skipped: Counter[str],
    ) -> None:
        for record in records:
            existing = (
                db.query(QuoteSnapshot)
                .filter(QuoteSnapshot.stock_code == stock_code, QuoteSnapshot.date == record.date)
                .first()
            )
            if existing:
                skipped["quotes"] += 1
                continue
            db.add(
                QuoteSnapshot(
                    stock_code=stock_code,
                    date=record.date,
                    open_price=record.open_price,
                    high=record.high,
                    low=record.low,
                    close=record.close,
                    volume=record.volume,
                    amount=record.amount,
                    pe=record.pe,
                    pb=record.pb,
                    market_cap=record.market_cap,
                    created_at=record.fetched_at,
                )
            )
            created["quotes"] += 1

    def _persist_metrics(
        self,
        db: Session,
        stock_code: str,
        records: list[MetricRecord],
        raw_by_key: dict[str, RawSource],
        created: Counter[str],
        skipped: Counter[str],
    ) -> None:
        for record in records:
            existing = (
                db.query(FundamentalMetric)
                .filter(
                    FundamentalMetric.stock_code == stock_code,
                    FundamentalMetric.metric_code == record.metric_code,
                    FundamentalMetric.period == record.period,
                    FundamentalMetric.source_provider == record.source_provider,
                )
                .first()
            )
            if existing:
                skipped["metrics"] += 1
                continue
            raw_source = None
            if record.source_url:
                raw_source = raw_by_key.get(
                    _source_key(record.source_provider, "metric", record.metric_name, record.fetched_at)
                )
            db.add(
                FundamentalMetric(
                    stock_code=stock_code,
                    metric_code=record.metric_code,
                    metric_name=record.metric_name,
                    metric_category=record.metric_category,
                    value=record.value,
                    unit=record.unit,
                    period=record.period,
                    report_date=record.report_date,
                    source_provider=record.source_provider,
                    raw_source_id=raw_source.id if raw_source else None,
                    created_at=record.fetched_at,
                )
            )
            created["metrics"] += 1


def build_data_refresh_service() -> DataRefreshService:
    """Factory kept separate so tests can monkeypatch provider behavior."""
    return DataRefreshService()


def _checksum(payload: dict[str, Any]) -> str:
    text = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _fingerprint(stock_code: str, provider: str, source_type: str, title: str, published_at: datetime) -> str:
    text = f"{stock_code}|{provider}|{source_type}|{title}|{published_at.isoformat()}"
    return hashlib.md5(text.encode("utf-8"), usedforsecurity=False).hexdigest()


def _source_key(provider: str, source_type: str, title: str, published_at: datetime) -> str:
    return f"{provider}|{source_type}|{title}|{published_at.isoformat()}"


def _error_dict(error: AdapterError) -> dict[str, str]:
    return {
        "provider": error.provider,
        "type": error.data_type,
        "message": error.message,
    }
