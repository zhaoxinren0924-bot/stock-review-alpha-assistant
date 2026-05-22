"""Tests for evidence-aware AI-generated action flow."""

from datetime import datetime

import pytest
from app.database import SessionLocal
from app.main import app, classify_source, create_tables
from app.models import Event
from httpx import ASGITransport, AsyncClient


async def create_test_stock(client: AsyncClient, stock_code: str) -> None:
    await client.delete(f"/api/v1/stocks/{stock_code}")
    await client.post(
        "/api/v1/stocks",
        json={
            "code": stock_code,
            "name": "测试股票",
            "industry": "AI 算力链",
            "market": "SZ",
        },
    )


@pytest.mark.asyncio
async def test_ai_chat_without_external_evidence_is_explicitly_bounded() -> None:
    """AI can organize user thought but must admit missing external evidence."""
    await create_tables()
    stock_code = "399993"
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        await create_test_stock(client, stock_code)

        chat_res = await client.post(
            "/api/v1/ai/chat",
            json={
                "stock_code": stock_code,
                "message": "我看好 AI 算力链，海外订单可能继续兑现",
                "history": [],
            },
        )

    body = chat_res.json()
    assert chat_res.status_code == 200
    assert "当前证据不足" in body["reply"]
    assert body["actions"][0]["type"] == "create_hypothesis"
    assert body["evidence_cards"] == []


@pytest.mark.asyncio
async def test_ai_chat_with_event_evidence_returns_evidence_cards() -> None:
    """AI response includes standardized source fields when evidence exists."""
    await create_tables()
    stock_code = "399996"
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        await create_test_stock(client, stock_code)

    db = SessionLocal()
    try:
        db.query(Event).filter(Event.stock_code == stock_code).delete()
        db.add(
            Event(
                stock_code=stock_code,
                fingerprint="ai-evidence-test-399996",
                title="公司披露海外算力订单进展",
                content="公告显示公司海外客户订单继续推进。",
                summary="海外订单继续推进，可作为成长逻辑的高置信线索。",
                source="CNInfo",
                source_provider="CNInfo",
                source_url="https://www.cninfo.com.cn/test",
                source_type="announcement",
                confidence=95,
                published_at=datetime(2026, 5, 20, 9, 0, 0),
                fetched_at=datetime(2026, 5, 20, 10, 0, 0),
            )
        )
        db.commit()
    finally:
        db.close()

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        chat_res = await client.post(
            "/api/v1/ai/chat",
            json={
                "stock_code": stock_code,
                "message": "这条订单公告影响了我的成长逻辑吗？",
                "history": [],
            },
        )

    body = chat_res.json()
    assert chat_res.status_code == 200
    assert body["actions"]
    assert body["evidence_cards"][0]["source_provider"] == "CNInfo"
    assert body["evidence_cards"][0]["source_url"] == "https://www.cninfo.com.cn/test"
    assert body["evidence_cards"][0]["fetched_at"].startswith("2026-05-20")
    assert body["evidence_cards"][0]["confidence"] == 95
    assert body["evidence_cards"][0]["source_level"] == "A"


@pytest.mark.asyncio
async def test_ai_apply_actions_create_and_update_hypothesis() -> None:
    """AI chat returns a pending action that can be applied and later updated."""
    await create_tables()
    stock_code = "399998"
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        await create_test_stock(client, stock_code)

        chat_res = await client.post(
            "/api/v1/ai/chat",
            json={
                "stock_code": stock_code,
                "message": "AI 资本开支持续增长，海外订单可能继续兑现",
                "history": [],
            },
        )
        assert chat_res.status_code == 200
        action = chat_res.json()["actions"][0]

        apply_res = await client.post("/api/v1/ai/actions/apply", json=action)
        assert apply_res.status_code == 200
        hypothesis_id = apply_res.json()["result"]["id"]

        update_res = await client.post(
            "/api/v1/ai/actions/apply",
            json={
                "type": "update_hypothesis_status",
                "payload": {
                    "stock_code": stock_code,
                    "hypothesis_id": hypothesis_id,
                    "status": "watching",
                    "reason": "订单兑现仍需下季度继续验证",
                },
            },
        )
        assert update_res.status_code == 200
        assert update_res.json()["result"]["status"] == "watching"

        list_res = await client.get(f"/api/v1/stocks/{stock_code}/hypotheses")
        assert list_res.json()["count"] >= 1


def test_source_classification_keeps_confidence_policy() -> None:
    """Source adapter keeps provider/type confidence semantics stable."""
    assert classify_source("CNInfo", "announcement")[0] == "A"
    assert classify_source("AKShare", "quote")[0] == "B"
    assert classify_source("Eastmoney", "news")[0] == "C"
    assert classify_source("user", "manual")[0] == "D"
