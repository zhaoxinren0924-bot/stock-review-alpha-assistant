"""Tests for the stock research loop APIs."""

import pytest
from app.main import app, create_tables
from httpx import ASGITransport, AsyncClient


@pytest.mark.asyncio
async def test_hypothesis_check_item_review_loop() -> None:
    """Create a stock, hypothesis, check item, and review."""
    await create_tables()
    stock_code = "399999"
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        await client.delete(f"/api/v1/stocks/{stock_code}")
        await client.post(
            "/api/v1/stocks",
            json={
                "code": stock_code,
                "name": "中际旭创",
                "industry": "AI 算力链",
                "market": "SZ",
            },
        )

        hypothesis_res = await client.post(
            f"/api/v1/stocks/{stock_code}/hypotheses",
            json={
                "category": "growth_logic",
                "status": "unverified",
                "content": {
                    "title": "AI 算力需求持续增长",
                    "summary": "海外 AI 资本开支继续支撑光模块需求。",
                },
                "confidence": 75,
                "evidence": "用户初始买入逻辑",
                "next_review_date": "2026-06-30",
            },
        )
        assert hypothesis_res.status_code == 201
        hypothesis = hypothesis_res.json()
        assert hypothesis["content"]["title"] == "AI 算力需求持续增长"

        list_res = await client.get(f"/api/v1/stocks/{stock_code}/hypotheses")
        assert list_res.status_code == 200
        assert list_res.json()["count"] == 1

        check_item_res = await client.post(
            f"/api/v1/stocks/{stock_code}/check-items",
            json={
                "content": "下季度检查海外订单是否继续增长",
                "due_date": "2026-06-30",
                "linked_hypothesis_id": hypothesis["id"],
                "source_type": "manual",
            },
        )
        assert check_item_res.status_code == 201
        assert check_item_res.json()["linked_hypothesis_id"] == hypothesis["id"]

        review_res = await client.post(
            f"/api/v1/stocks/{stock_code}/reviews",
            json={
                "review_type": "quarterly",
                "title": "Q2 假设复盘",
                "content": "继续观察订单和毛利率变化。",
                "conclusions": "假设暂未证伪。",
                "action_items": ["跟踪海外订单", "检查毛利率"],
            },
        )
        assert review_res.status_code == 201
        assert review_res.json()["action_items"] == ["跟踪海外订单", "检查毛利率"]


@pytest.mark.asyncio
async def test_create_hypothesis_returns_404_for_missing_stock() -> None:
    """Creating a hypothesis requires an existing stock."""
    await create_tables()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/v1/stocks/000000/hypotheses",
            json={
                "category": "business_quality",
                "status": "stable",
                "content": {"title": "测试", "summary": "测试"},
            },
        )

    assert response.status_code == 404
