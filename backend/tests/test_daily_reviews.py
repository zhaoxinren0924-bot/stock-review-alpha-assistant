"""Tests for structured daily review workflow."""

from datetime import date, datetime

import pytest
from app.database import SessionLocal
from app.main import (
    app,
    collect_daily_review_context,
    create_tables,
)
from app.models import DailyReview, Event, FundamentalMetric, QuoteSnapshot, Stock
from app.services.daily_market_prefill import MarketPrefillResult
from httpx import ASGITransport, AsyncClient


class _StubMarketService:
    """Deterministic stand-in for DailyMarketPrefillService used by tests."""

    def __init__(self, result: MarketPrefillResult) -> None:
        self._result = result

    def prefill(self, _review_date: date) -> MarketPrefillResult:
        return self._result


def _stub_empty_market(monkeypatch: pytest.MonkeyPatch) -> None:
    """Force the market prefill service to report all sections as missing."""
    result = MarketPrefillResult(
        content_patch={},
        filled={"index_rows": 0, "hotspot_rows": 0, "capital_rows": 0, "limit_rows": 0},
        missing=[
            "指数全量表现",
            "全市场涨停/跌停/连板/炸板数据",
            "成交额榜单与板块资金流",
        ],
        errors=[],
    )
    monkeypatch.setattr(
        "app.main.build_daily_market_prefill_service",
        lambda: _StubMarketService(result),
    )


async def create_test_stock(client: AsyncClient, stock_code: str) -> None:
    """Create a deterministic watchlist stock."""
    await client.delete(f"/api/v1/stocks/{stock_code}")
    await client.post(
        "/api/v1/stocks",
        json={
            "code": stock_code,
            "name": "每日复盘测试股",
            "industry": "AI 算力链",
            "market": "SZ",
        },
    )


@pytest.mark.asyncio
async def test_initialize_daily_review_creates_full_template() -> None:
    """Initialization creates the eight-section official template."""
    await create_tables()
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        first = await client.post("/api/v1/daily-reviews/2026-05-23/initialize")
        second = await client.post("/api/v1/daily-reviews/2026-05-23/initialize")

    assert first.status_code == 201
    assert second.status_code == 201
    body = first.json()
    assert body["review_date"] == "2026-05-23"
    assert body["status"] == "draft"
    assert set(body["content"]) == {
        "index_review",
        "hotspot_review",
        "capital_review",
        "limit_review",
        "watchlist_review",
        "fundamental_review",
        "tomorrow_plan",
        "weekly_review",
    }
    assert second.json()["id"] == body["id"]


@pytest.mark.asyncio
async def test_prefill_daily_review_uses_existing_watchlist_evidence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Prefill writes watchlist and company rows without inventing market-wide data."""
    _stub_empty_market(monkeypatch)
    await create_tables()
    stock_code = "399991"
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        await create_test_stock(client, stock_code)

    db = SessionLocal()
    try:
        db.query(Event).filter(Event.stock_code == stock_code).delete()
        db.query(FundamentalMetric).filter(FundamentalMetric.stock_code == stock_code).delete()
        db.query(QuoteSnapshot).filter(QuoteSnapshot.stock_code == stock_code).delete()
        db.add(
            Event(
                stock_code=stock_code,
                fingerprint="daily-review-event-399991",
                title="公司披露算力订单进展",
                content="公告显示客户订单继续推进。",
                summary="算力订单继续推进。",
                source="CNInfo",
                source_provider="CNInfo",
                source_url="https://www.cninfo.com.cn/daily",
                source_type="announcement",
                confidence=95,
                published_at=datetime(2026, 5, 22, 9, 0, 0),
                fetched_at=datetime(2026, 5, 22, 10, 0, 0),
            )
        )
        db.add(
            FundamentalMetric(
                stock_code=stock_code,
                metric_code="gross_margin",
                metric_name="销售毛利率",
                metric_category="financial_quality",
                value=31.5,
                unit="%",
                period="2026Q1",
                report_date=date(2026, 3, 31),
                source_provider="BaoStock",
            )
        )
        db.add(
            QuoteSnapshot(
                stock_code=stock_code,
                date=date(2026, 5, 22),
                close=123.4,
                pe=38.5,
                pb=6.2,
            )
        )
        db.commit()
    finally:
        db.close()

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        init_res = await client.post("/api/v1/daily-reviews/2026-05-23/initialize")
        review_id = init_res.json()["id"]
        prefill_res = await client.post(f"/api/v1/daily-reviews/{review_id}/prefill")

    assert prefill_res.status_code == 200
    body = prefill_res.json()
    assert body["filled"]["watchlist_targets"] >= 1
    assert body["filled"]["company_rows"] >= 1
    assert "指数全量表现" in body["missing"]
    assert body["evidence_cards"][0]["source_level"] in {"A", "B"}
    content = body["review"]["content"]
    assert content["watchlist_review"]["targets"]
    assert content["fundamental_review"]["company_rows"]


@pytest.mark.asyncio
async def test_prefill_wires_market_sections_into_daily_review(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Market prefill content_patch must land in sections 1-4 of the review content."""
    stub_patch = {
        "index_review": {
            "indices": [
                {
                    "name": "上证指数",
                    "change_pct": {"value": "0.50%", "source": "data_prefilled", "note": ""},
                    "turnover": {"value": "5230.00亿", "source": "data_prefilled", "note": ""},
                    "note": {"value": "收盘 3210.5", "source": "data_prefilled", "note": ""},
                }
            ],
            "leading_index": {"value": "上证指数", "source": "data_prefilled", "note": ""},
        },
        "hotspot_review": {
            "sentiment_metrics": {
                "limit_up_count": {"value": 38, "source": "data_prefilled", "note": ""},
                "limit_down_count": {"value": 5, "source": "data_prefilled", "note": ""},
            }
        },
        "capital_review": {
            "turnover_leaders": [
                {"target": {"value": "AI 算力", "source": "data_prefilled", "note": ""}}
            ]
        },
        "limit_review": {
            "opportunity_rows": [
                {"stock": {"value": "中际旭创", "source": "data_prefilled", "note": ""}}
            ]
        },
    }
    result = MarketPrefillResult(
        content_patch=stub_patch,
        filled={"index_rows": 1, "hotspot_rows": 2, "capital_rows": 1, "limit_rows": 1},
        missing=["恒生指数", "纳斯达克", "标普500"],
        errors=[],
    )
    monkeypatch.setattr(
        "app.main.build_daily_market_prefill_service",
        lambda: _StubMarketService(result),
    )

    await create_tables()
    db = SessionLocal()
    try:
        db.query(DailyReview).filter(DailyReview.review_date == date(2026, 5, 25)).delete()
        db.commit()
    finally:
        db.close()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        init_res = await client.post("/api/v1/daily-reviews/2026-05-25/initialize")
        review_id = init_res.json()["id"]
        prefill_res = await client.post(f"/api/v1/daily-reviews/{review_id}/prefill")

    assert prefill_res.status_code == 200
    body = prefill_res.json()
    content = body["review"]["content"]
    # Sections 1-4 must reflect the stub patch.
    assert content["index_review"]["indices"][0]["name"] == "上证指数"
    assert content["index_review"]["leading_index"]["value"] == "上证指数"
    assert content["hotspot_review"]["sentiment_metrics"]["limit_up_count"]["value"] == 38
    assert content["capital_review"]["turnover_leaders"][0]["target"]["value"] == "AI 算力"
    assert content["limit_review"]["opportunity_rows"][0]["stock"]["value"] == "中际旭创"
    # Filled counts and missing list must propagate through the response.
    assert body["filled"]["index_rows"] == 1
    assert body["filled"]["hotspot_rows"] == 2
    assert body["filled"]["capital_rows"] == 1
    assert body["filled"]["limit_rows"] == 1
    assert "恒生指数" in body["missing"]


def test_collect_context_for_market_section_excludes_watchlist() -> None:
    """Market sections 1-4 should not haul in the watchlist or evidence cards.

    Old behavior dumped 30 stocks + 12 evidence cards on every turn; this test
    locks in the new section-scoped behavior so we don't regress.
    """
    db = SessionLocal()
    try:
        # Ensure at least one watchlist stock exists so a regression would surface it.
        existing = db.query(Stock).filter(Stock.code == "999991").first()
        if existing is None:
            db.add(Stock(code="999991", name="测试股 A", industry="算力", market="SZ"))
            db.commit()
        review = DailyReview(
            user_id="default",
            review_date=date(2026, 5, 23),
            status="draft",
            content={
                "index_review": {"indices": [{"name": "上证指数"}], "leading_index": {"value": "上证指数"}},
                "hotspot_review": {"sentiment_metrics": {"limit_up_count": {"value": 38}}},
                "watchlist_review": {"targets": []},
                "fundamental_review": {"company_rows": []},
            },
        )
        db.query(DailyReview).filter(DailyReview.review_date == review.review_date).delete()
        db.commit()
        db.add(review)
        db.commit()
        db.refresh(review)

        items, evidence = collect_daily_review_context(review, db, section_key="hotspot_review")

        assert len(items) == 2  # meta + current_section only
        assert items[0]["type"] == "daily_review_meta"
        assert items[0]["current_section"] == "hotspot_review"
        assert items[1]["type"] == "current_section"
        assert items[1]["section_key"] == "hotspot_review"
        assert all(item["type"] != "watchlist_stock" for item in items)
        assert evidence == []

        db.delete(review)
        db.commit()
    finally:
        db.close()


def test_collect_context_for_company_section_scopes_to_linked_stocks() -> None:
    """Company sections 5-6 should include only stocks actually referenced in that section."""
    db = SessionLocal()
    try:
        # Three watchlist stocks exist; only one is referenced in the section.
        for code, name in [("999992", "AA"), ("999993", "BB"), ("999994", "CC")]:
            if not db.query(Stock).filter(Stock.code == code).first():
                db.add(Stock(code=code, name=name, industry="算力", market="SZ"))
        db.commit()
        review = DailyReview(
            user_id="default",
            review_date=date(2026, 5, 24),
            status="draft",
            content={
                "watchlist_review": {
                    "targets": [
                        {"stock_code": "999993", "stock_name": "BB"},
                    ]
                },
                "fundamental_review": {"company_rows": []},
            },
        )
        db.query(DailyReview).filter(DailyReview.review_date == review.review_date).delete()
        db.commit()
        db.add(review)
        db.commit()
        db.refresh(review)

        items, _evidence = collect_daily_review_context(
            review, db, section_key="watchlist_review"
        )

        watchlist_codes = [
            item["code"] for item in items if item["type"] == "watchlist_stock"
        ]
        assert watchlist_codes == ["999993"]  # only the referenced one, not all 3+ in DB

        db.delete(review)
        db.commit()
    finally:
        db.close()


def test_collect_context_for_tomorrow_plan_condenses_other_sections() -> None:
    """Section 7 (tomorrow_plan) sees conclusions of sections 1-6, not raw rows."""
    db = SessionLocal()
    try:
        review = DailyReview(
            user_id="default",
            review_date=date(2026, 5, 25),
            status="draft",
            content={
                "index_review": {
                    "indices": [
                        {"name": f"X{i}", "change_pct": {"value": "1%"}} for i in range(20)
                    ],
                    "leading_index": {"value": "创业板指", "source": "data_prefilled"},
                    "market_style": {"value": "小盘成长", "source": "ai_generated"},
                },
                "hotspot_review": {
                    "main_sectors": [{"sector": {"value": f"板块{i}"}} for i in range(15)],
                    "sentiment_metrics": {
                        "limit_up_count": {"value": 38, "source": "data_prefilled"},
                        "limit_down_count": {"value": 5, "source": "data_prefilled"},
                    },
                },
                "tomorrow_plan": {"market_view": {"value": ""}},
            },
        )
        db.query(DailyReview).filter(DailyReview.review_date == review.review_date).delete()
        db.commit()
        db.add(review)
        db.commit()
        db.refresh(review)

        items, _ = collect_daily_review_context(
            review, db, section_key="tomorrow_plan"
        )

        summary_items = [item for item in items if item["type"] == "review_summary"]
        assert len(summary_items) == 1
        summary = summary_items[0]["sections"]
        # Raw row lists must be stripped.
        assert "indices" not in summary["index_review"]
        assert "main_sectors" not in summary["hotspot_review"]
        # Conclusion fields retained.
        assert summary["index_review"]["leading_index"] == "创业板指"
        assert summary["index_review"]["market_style"] == "小盘成长"
        assert summary["hotspot_review"]["sentiment_metrics"]["limit_up_count"] == 38

        db.delete(review)
        db.commit()
    finally:
        db.close()


@pytest.mark.asyncio
async def test_update_tomorrow_plan_persists_structured_fields() -> None:
    """tomorrow_plan now holds structured arrays (operation_plan, lessons) plus
    field-value enums (market_expectation, position_plan). Verify a PUT with a
    content patch survives a round trip via the normal update endpoint."""
    await create_tables()
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        await client.post("/api/v1/daily-reviews/2026-05-27/initialize")
        review = (await client.get("/api/v1/daily-reviews/2026-05-27")).json()

        patch_content = {
            "tomorrow_plan": {
                "market_expectation": {"value": "bullish", "source": "manual", "note": ""},
                "position_plan": {"value": "add", "source": "manual", "note": ""},
                "focus_sectors": ["AI 算力", "创新药"],
                "operation_plan": [
                    {
                        "stock_code": "300308",
                        "stock_name": "中际旭创",
                        "direction": "buy",
                        "trigger_condition": "突破 20 日线",
                        "target_price": "180",
                        "stop_loss": "150",
                    },
                ],
                "lessons": [
                    {"lesson_type": "追高", "description": "在涨停板上车,第二天回吐 7%"},
                ],
            }
        }
        updated = await client.put(
            f"/api/v1/daily-reviews/{review['id']}",
            json={"content": patch_content},
        )
        assert updated.status_code == 200
        plan = updated.json()["content"]["tomorrow_plan"]
        assert plan["market_expectation"]["value"] == "bullish"
        assert plan["position_plan"]["value"] == "add"
        assert plan["focus_sectors"] == ["AI 算力", "创新药"]
        assert len(plan["operation_plan"]) == 1
        assert plan["operation_plan"][0]["stock_name"] == "中际旭创"
        assert plan["operation_plan"][0]["trigger_condition"] == "突破 20 日线"
        assert len(plan["lessons"]) == 1
        assert plan["lessons"][0]["lesson_type"] == "追高"

        # Replacing operation_plan with empty array must drop the row entirely.
        cleared = await client.put(
            f"/api/v1/daily-reviews/{review['id']}",
            json={"content": {"tomorrow_plan": {"operation_plan": []}}},
        )
        assert cleared.status_code == 200
        assert cleared.json()["content"]["tomorrow_plan"]["operation_plan"] == []
        # Other fields untouched.
        assert cleared.json()["content"]["tomorrow_plan"]["market_expectation"]["value"] == "bullish"


@pytest.mark.asyncio
async def test_delete_daily_review_section_item_removes_only_target() -> None:
    """DELETE endpoint must pop only the indexed item from the requested field."""
    await create_tables()
    db = SessionLocal()
    try:
        db.query(DailyReview).filter(DailyReview.review_date == date(2026, 5, 26)).delete()
        db.commit()
        review = DailyReview(
            user_id="default",
            review_date=date(2026, 5, 26),
            status="draft",
            content={
                "hotspot_review": {
                    "ai_notes": [
                        {"value": "笔记 A", "source": "ai_generated"},
                        {"value": "笔记 B", "source": "ai_generated"},
                        {"value": "笔记 C", "source": "ai_generated"},
                    ],
                    "ai_actions": [
                        {"content": "继续验证 X", "source": "ai_generated"},
                    ],
                },
            },
        )
        db.add(review)
        db.commit()
        db.refresh(review)
        review_id = review.id
    finally:
        db.close()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Delete middle ai_notes entry (index 1).
        res = await client.delete(
            f"/api/v1/daily-reviews/{review_id}/sections/hotspot_review/items/ai_notes/1"
        )
        assert res.status_code == 200
        notes = res.json()["content"]["hotspot_review"]["ai_notes"]
        assert [n["value"] for n in notes] == ["笔记 A", "笔记 C"]
        # ai_actions list is untouched.
        actions = res.json()["content"]["hotspot_review"]["ai_actions"]
        assert len(actions) == 1

        # Out-of-range index returns 404.
        oob = await client.delete(
            f"/api/v1/daily-reviews/{review_id}/sections/hotspot_review/items/ai_notes/99"
        )
        assert oob.status_code == 404

        # Disallowed field returns 422.
        bad_field = await client.delete(
            f"/api/v1/daily-reviews/{review_id}/sections/hotspot_review/items/indices/0"
        )
        assert bad_field.status_code == 422


@pytest.mark.asyncio
async def test_daily_review_ai_action_requires_apply(monkeypatch: pytest.MonkeyPatch) -> None:
    """AI coach returns pending actions, and apply mutates only after confirmation."""
    await create_tables()
    monkeypatch.setattr("app.main.get_llm_provider", lambda: None)
    db = SessionLocal()
    try:
        db.query(DailyReview).filter(DailyReview.review_date == date(2026, 5, 24)).delete()
        db.commit()
    finally:
        db.close()
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        init_res = await client.post("/api/v1/daily-reviews/2026-05-24/initialize")
        review_id = init_res.json()["id"]

        coach_res = await client.post(
            f"/api/v1/daily-reviews/{review_id}/ai/coach",
            json={
                "section_key": "hotspot_review",
                "message": "今天 AI 算力扩散，但我不确定持续性。",
                "history": [],
            },
        )
        assert coach_res.status_code == 200
        action = coach_res.json()["actions"][0]
        assert action["type"] == "update_daily_review_section"

        before = await client.get("/api/v1/daily-reviews/2026-05-24")
        assert "ai_notes" not in before.json()["content"]["hotspot_review"]

        apply_res = await client.post(
            f"/api/v1/daily-reviews/{review_id}/actions/apply",
            json=action,
        )

    assert apply_res.status_code == 200
    updated = apply_res.json()["result"]["content"]["hotspot_review"]
    assert updated["ai_notes"][0]["source"] == "ai_generated"
