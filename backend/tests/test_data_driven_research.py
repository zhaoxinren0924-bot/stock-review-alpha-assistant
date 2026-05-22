"""Tests for data-driven evidence refresh and impact analysis."""

from datetime import date, datetime

import pytest
from app.main import app, create_tables
from app.services.data_refresh import DataRefreshService
from app.services.data_sources.base import (
    AdapterError,
    AdapterResult,
    EventRecord,
    MetricRecord,
    QuoteRecord,
    SourceRecord,
)
from httpx import ASGITransport, AsyncClient


class FakeAdapter:
    """Deterministic adapter for API tests."""

    provider_name = "FakeCNInfo"

    def fetch(self, stock_code: str, data_types: set[str], lookback_days: int) -> AdapterResult:
        fetched_at = datetime(2026, 5, 22, 18, 0, 0)
        published_at = datetime(2026, 5, 20, 9, 0, 0)
        title = f"{stock_code} 海外算力订单进展公告"
        return AdapterResult(
            raw_sources=[
                SourceRecord(
                    source_type="announcement",
                    source_provider="CNInfo",
                    source_url="https://www.cninfo.com.cn/fake",
                    title=title,
                    raw_content="公司披露海外算力订单继续推进。",
                    raw_payload={"title": "海外算力订单进展公告"},
                    published_at=published_at,
                    fetched_at=fetched_at,
                    confidence=95,
                )
            ],
            events=[
                EventRecord(
                    source_type="announcement",
                    source_provider="CNInfo",
                    source_url="https://www.cninfo.com.cn/fake",
                    title=title,
                    summary="公司披露海外算力订单继续推进。",
                    content="公司披露海外算力订单继续推进。",
                    event_type="announcement",
                    published_at=published_at,
                    fetched_at=fetched_at,
                    confidence=95,
                )
            ],
            quotes=[
                QuoteRecord(
                    source_provider="AKShare",
                    date=date(2026, 5, 22),
                    fetched_at=fetched_at,
                    close=123.4,
                    pe=38.5,
                    pb=6.2,
                )
            ],
            metrics=[
                MetricRecord(
                    source_provider="BaoStock",
                    metric_code="gp_margin",
                    metric_name="销售毛利率",
                    metric_category="financial_quality",
                    value=31.5,
                    unit="%",
                    period="2026Q1",
                    report_date=date(2026, 3, 31),
                    fetched_at=fetched_at,
                    raw_payload={"gpMargin": 31.5},
                )
            ],
            errors=[AdapterError(provider="BrokenProvider", data_type="news", message="temporary failure")],
        )


async def create_test_stock(client: AsyncClient, stock_code: str) -> None:
    await client.delete(f"/api/v1/stocks/{stock_code}")
    await client.post(
        "/api/v1/stocks",
        json={
            "code": stock_code,
            "name": "数据测试股",
            "industry": "AI 算力链",
            "market": "SZ",
        },
    )


@pytest.mark.asyncio
async def test_manual_refresh_writes_standardized_evidence(monkeypatch: pytest.MonkeyPatch) -> None:
    """Manual refresh writes raw sources, events, quotes and metrics and keeps errors non-fatal."""
    await create_tables()
    stock_code = "399995"
    monkeypatch.setattr(
        "app.main.build_data_refresh_service",
        lambda: DataRefreshService(adapters=[FakeAdapter()]),
    )
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        await create_test_stock(client, stock_code)

        refresh_res = await client.post(
            f"/api/v1/stocks/{stock_code}/data/refresh",
            json={"types": ["announcement", "news", "quote", "metric"], "lookback_days": 30},
        )
        assert refresh_res.status_code == 200
        body = refresh_res.json()
        assert body["created"].get("raw_sources", 0) + body["skipped"].get("raw_sources", 0) >= 1
        assert body["created"].get("events", 0) + body["skipped"].get("events", 0) >= 1
        assert body["created"].get("quotes", 0) + body["skipped"].get("quotes", 0) >= 1
        assert body["created"].get("metrics", 0) + body["skipped"].get("metrics", 0) >= 1
        assert body["errors"][0]["provider"] == "BrokenProvider"

        duplicate_res = await client.post(
            f"/api/v1/stocks/{stock_code}/data/refresh",
            json={"types": ["announcement", "news", "quote", "metric"], "lookback_days": 30},
        )
        assert duplicate_res.status_code == 200
        duplicate = duplicate_res.json()
        assert duplicate["skipped"]["events"] >= 1
        assert duplicate["skipped"]["quotes"] >= 1
        assert duplicate["skipped"]["metrics"] >= 1

        evidence_res = await client.get(f"/api/v1/stocks/{stock_code}/evidence")
        assert evidence_res.status_code == 200
        evidence = evidence_res.json()
        assert evidence["count"] >= 3
        assert evidence["items"][0]["source_level"] in {"A", "B"}


@pytest.mark.asyncio
async def test_event_impact_analysis_creates_pending_actions(monkeypatch: pytest.MonkeyPatch) -> None:
    """Event impact analysis maps evidence to a hypothesis without directly mutating it."""
    await create_tables()
    stock_code = "399994"
    monkeypatch.setattr(
        "app.main.build_data_refresh_service",
        lambda: DataRefreshService(adapters=[FakeAdapter()]),
    )
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        await create_test_stock(client, stock_code)
        await client.post(
            f"/api/v1/stocks/{stock_code}/hypotheses",
            json={
                "category": "growth_logic",
                "status": "unverified",
                "content": {"title": "海外算力订单增长", "summary": "订单兑现支撑成长逻辑"},
                "confidence": 70,
            },
        )
        await client.post(
            f"/api/v1/stocks/{stock_code}/data/refresh",
            json={"types": ["announcement", "quote", "metric"], "lookback_days": 30},
        )
        events_res = await client.get(f"/api/v1/stocks/{stock_code}/events")
        event_id = events_res.json()["items"][0]["id"]

        analysis_res = await client.post(f"/api/v1/stocks/{stock_code}/events/{event_id}/analyze-impact")
        assert analysis_res.status_code == 200
        analysis = analysis_res.json()
        assert analysis["impacts"][0]["user_confirmed"] is False
        assert analysis["actions"][0]["type"] == "update_hypothesis_status"
        assert analysis["evidence_cards"][0]["source_level"] == "A"
