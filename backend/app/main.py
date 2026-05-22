"""Stock Review Alpha Assistant - Main Application."""

import json
import logging
import os
from datetime import date, datetime
from typing import Annotated

import rollbar
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from rollbar.contrib.fastapi import ReporterMiddleware as RollbarMiddleware
from sqlalchemy import inspect, text
from sqlalchemy.orm import Session

from app.database import engine, get_db
from app.models import (
    Base,
    CheckItem,
    Event,
    FundamentalMetric,
    Hypothesis,
    Impact,
    InvestmentCase,
    QuoteSnapshot,
    ReviewLog,
    Stock,
)
from app.schemas import (
    AiAction,
    AiActionApplyRequest,
    AiActionApplyResponse,
    AiChatRequest,
    AiChatResponse,
    AiProviderStatusResponse,
    CheckItemCreate,
    CheckItemListResponse,
    CheckItemResponse,
    CheckItemUpdate,
    DataRefreshRequest,
    DataRefreshResponse,
    EventListResponse,
    EventResponse,
    EvidenceCard,
    EvidenceListResponse,
    HypothesisCreate,
    HypothesisListResponse,
    HypothesisResponse,
    HypothesisUpdate,
    ImpactAnalysisResponse,
    ImpactResponse,
    MetricListResponse,
    MetricResponse,
    QuoteListResponse,
    QuoteResponse,
    ReviewCreate,
    ReviewListResponse,
    ReviewResponse,
    ReviewUpdate,
    StockCreate,
    StockListResponse,
    StockResponse,
)
from app.services.data_refresh import build_data_refresh_service
from app.services.llm.base import LLMProviderError, LLMRequest
from app.services.llm.factory import get_llm_provider
from app.services.scheduler import start_daily_refresh_scheduler

DbSession = Annotated[Session, Depends(get_db)]
logger = logging.getLogger(__name__)

load_dotenv()

# Initialize Rollbar if token is available
_rollbar_token = os.environ.get("ROLLBAR_ACCESS_TOKEN")
if _rollbar_token:
    rollbar.init(
        _rollbar_token,
        environment=os.environ.get("ROLLBAR_ENVIRONMENT", "development"),
    )

app = FastAPI(
    title="Stock Review Alpha Assistant",
    description="A-share fundamental review assistant API",
    version="0.1.0",
)

# CORS for frontend (local dev + Render static site)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "https://stock-review-web.onrender.com",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Rollbar error tracking middleware
if _rollbar_token:
    app.add_middleware(RollbarMiddleware)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Catch unhandled exceptions and report to Rollbar."""
    if _rollbar_token:
        rollbar.report_exc_info()
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"},
    )


@app.on_event("startup")
async def create_tables() -> None:
    """Create database tables on startup."""
    Base.metadata.create_all(bind=engine)
    ensure_sqlite_columns()
    start_daily_refresh_scheduler()


def ensure_sqlite_columns() -> None:
    """Add new MVP columns when an older local SQLite DB already exists."""
    if not str(engine.url).startswith("sqlite"):
        return

    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())
    column_specs = {
        "positions": {
            "user_id": "VARCHAR(50) NOT NULL DEFAULT 'default'",
            "updated_at": "DATETIME",
        },
        "investment_cases": {
            "user_id": "VARCHAR(50) NOT NULL DEFAULT 'default'",
        },
        "hypotheses": {
            "user_id": "VARCHAR(50) NOT NULL DEFAULT 'default'",
            "updated_at": "DATETIME",
        },
        "check_items": {
            "user_id": "VARCHAR(50) NOT NULL DEFAULT 'default'",
            "linked_hypothesis_id": "INTEGER",
            "completed_at": "DATETIME",
        },
        "review_logs": {
            "user_id": "VARCHAR(50) NOT NULL DEFAULT 'default'",
            "title": "VARCHAR(100)",
        },
        "events": {
            "raw_source_id": "INTEGER",
            "summary": "TEXT",
            "source_provider": "VARCHAR(50)",
            "source_url": "VARCHAR(1000)",
            "event_type": "VARCHAR(50)",
            "importance": "VARCHAR(20)",
            "sentiment": "VARCHAR(20)",
            "confidence": "INTEGER",
            "created_by": "VARCHAR(20) NOT NULL DEFAULT 'system'",
        },
        "impacts": {
            "metric_id": "INTEGER",
            "impact_direction": "VARCHAR(20)",
            "impact_strength": "INTEGER",
            "reason": "TEXT",
            "evidence_text": "TEXT",
            "confidence": "INTEGER",
            "generated_by": "VARCHAR(20) NOT NULL DEFAULT 'ai'",
            "user_confirmed": "BOOLEAN NOT NULL DEFAULT 0",
            "confirmed_at": "DATETIME",
        },
    }

    with engine.begin() as conn:
        for table_name, columns in column_specs.items():
            if table_name not in existing_tables:
                continue
            existing_columns = {col["name"] for col in inspector.get_columns(table_name)}
            for column_name, column_sql in columns.items():
                if column_name not in existing_columns:
                    conn.execute(text(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_sql}"))


@app.get("/")
async def root() -> dict[str, str]:
    """Root endpoint - health check."""
    return {"message": "Stock Review Alpha Assistant is running", "status": "ok"}


@app.get("/health")
async def health_check() -> dict[str, str]:
    """Health check endpoint for monitoring."""
    return {"status": "healthy", "version": "0.1.0"}


@app.get("/api/v1/stocks", response_model=StockListResponse)
async def list_stocks(db: DbSession) -> StockListResponse:
    """List all tracked stocks."""
    stocks = db.query(Stock).order_by(Stock.created_at.desc()).all()
    return StockListResponse(
        items=[StockResponse.model_validate(s) for s in stocks],
        count=len(stocks),
    )


@app.post("/api/v1/stocks", response_model=StockResponse, status_code=201)
async def create_stock(
    stock: StockCreate,
    db: DbSession,
) -> Stock:
    """Add a new stock to the watchlist."""
    existing = db.query(Stock).filter(Stock.code == stock.code).first()
    if existing:
        raise HTTPException(
            status_code=409,
            detail=f"Stock {stock.code} already exists",
        )

    db_stock = Stock(**stock.model_dump())
    db.add(db_stock)
    db.commit()
    db.refresh(db_stock)
    return db_stock


@app.get("/api/v1/stocks/{code}", response_model=StockResponse)
async def get_stock(code: str, db: DbSession) -> Stock:
    """Get a single stock by code."""
    stock = db.query(Stock).filter(Stock.code == code).first()
    if not stock:
        raise HTTPException(
            status_code=404,
            detail=f"Stock {code} not found",
        )
    return stock


@app.delete("/api/v1/stocks/{code}", status_code=204)
async def delete_stock(code: str, db: DbSession) -> None:
    """Remove a stock from the watchlist."""
    stock = db.query(Stock).filter(Stock.code == code).first()
    if not stock:
        raise HTTPException(
            status_code=404,
            detail=f"Stock {code} not found",
        )

    db.delete(stock)
    db.commit()


def get_stock_or_404(code: str, db: Session) -> Stock:
    """Return a stock or raise a 404."""
    stock = db.query(Stock).filter(Stock.code == code).first()
    if not stock:
        raise HTTPException(status_code=404, detail=f"Stock {code} not found")
    return stock


def get_or_create_case(code: str, db: Session) -> InvestmentCase:
    """Return the default user's investment case for a stock."""
    get_stock_or_404(code, db)
    case = (
        db.query(InvestmentCase)
        .filter(InvestmentCase.user_id == "default", InvestmentCase.stock_code == code)
        .first()
    )
    if case:
        return case

    case = InvestmentCase(user_id="default", stock_code=code)
    db.add(case)
    db.commit()
    db.refresh(case)
    return case


@app.get("/api/v1/stocks/{code}/hypotheses", response_model=HypothesisListResponse)
async def list_hypotheses(code: str, db: DbSession) -> HypothesisListResponse:
    """List hypotheses for a stock."""
    case = get_or_create_case(code, db)
    hypotheses = (
        db.query(Hypothesis)
        .filter(Hypothesis.user_id == "default", Hypothesis.case_id == case.id)
        .order_by(Hypothesis.created_at.desc())
        .all()
    )
    return HypothesisListResponse(
        items=[HypothesisResponse.model_validate(item) for item in hypotheses],
        count=len(hypotheses),
    )


@app.post(
    "/api/v1/stocks/{code}/hypotheses",
    response_model=HypothesisResponse,
    status_code=201,
)
async def create_hypothesis(
    code: str,
    hypothesis: HypothesisCreate,
    db: DbSession,
) -> Hypothesis:
    """Create a hypothesis for a stock."""
    case = get_or_create_case(code, db)
    db_hypothesis = Hypothesis(
        user_id="default",
        case_id=case.id,
        **hypothesis.model_dump(),
    )
    db.add(db_hypothesis)
    db.commit()
    db.refresh(db_hypothesis)
    return db_hypothesis


@app.put("/api/v1/hypotheses/{hypothesis_id}", response_model=HypothesisResponse)
async def update_hypothesis(
    hypothesis_id: int,
    hypothesis: HypothesisUpdate,
    db: DbSession,
) -> Hypothesis:
    """Update a hypothesis."""
    db_hypothesis = (
        db.query(Hypothesis)
        .filter(Hypothesis.id == hypothesis_id, Hypothesis.user_id == "default")
        .first()
    )
    if not db_hypothesis:
        raise HTTPException(status_code=404, detail=f"Hypothesis {hypothesis_id} not found")

    for field, value in hypothesis.model_dump(exclude_unset=True).items():
        setattr(db_hypothesis, field, value)
    db.commit()
    db.refresh(db_hypothesis)
    return db_hypothesis


@app.delete("/api/v1/hypotheses/{hypothesis_id}", status_code=204)
async def delete_hypothesis(hypothesis_id: int, db: DbSession) -> None:
    """Delete a hypothesis."""
    db_hypothesis = (
        db.query(Hypothesis)
        .filter(Hypothesis.id == hypothesis_id, Hypothesis.user_id == "default")
        .first()
    )
    if not db_hypothesis:
        raise HTTPException(status_code=404, detail=f"Hypothesis {hypothesis_id} not found")

    db.delete(db_hypothesis)
    db.commit()


@app.get("/api/v1/stocks/{code}/check-items", response_model=CheckItemListResponse)
async def list_check_items(code: str, db: DbSession) -> CheckItemListResponse:
    """List check items for a stock."""
    get_stock_or_404(code, db)
    items = (
        db.query(CheckItem)
        .filter(CheckItem.user_id == "default", CheckItem.stock_code == code)
        .order_by(CheckItem.created_at.desc())
        .all()
    )
    return CheckItemListResponse(
        items=[CheckItemResponse.model_validate(item) for item in items],
        count=len(items),
    )


@app.post(
    "/api/v1/stocks/{code}/check-items",
    response_model=CheckItemResponse,
    status_code=201,
)
async def create_check_item(
    code: str,
    check_item: CheckItemCreate,
    db: DbSession,
) -> CheckItem:
    """Create a check item for a stock."""
    get_stock_or_404(code, db)
    db_item = CheckItem(user_id="default", stock_code=code, **check_item.model_dump())
    db.add(db_item)
    db.commit()
    db.refresh(db_item)
    return db_item


@app.put("/api/v1/check-items/{check_item_id}", response_model=CheckItemResponse)
async def update_check_item(
    check_item_id: int,
    check_item: CheckItemUpdate,
    db: DbSession,
) -> CheckItem:
    """Update a check item."""
    db_item = (
        db.query(CheckItem)
        .filter(CheckItem.id == check_item_id, CheckItem.user_id == "default")
        .first()
    )
    if not db_item:
        raise HTTPException(status_code=404, detail=f"Check item {check_item_id} not found")

    for field, value in check_item.model_dump(exclude_unset=True).items():
        setattr(db_item, field, value)
    db.commit()
    db.refresh(db_item)
    return db_item


@app.delete("/api/v1/check-items/{check_item_id}", status_code=204)
async def delete_check_item(check_item_id: int, db: DbSession) -> None:
    """Delete a check item."""
    db_item = (
        db.query(CheckItem)
        .filter(CheckItem.id == check_item_id, CheckItem.user_id == "default")
        .first()
    )
    if not db_item:
        raise HTTPException(status_code=404, detail=f"Check item {check_item_id} not found")

    db.delete(db_item)
    db.commit()


@app.get("/api/v1/stocks/{code}/reviews", response_model=ReviewListResponse)
async def list_reviews(code: str, db: DbSession) -> ReviewListResponse:
    """List review records for a stock."""
    get_stock_or_404(code, db)
    reviews = (
        db.query(ReviewLog)
        .filter(ReviewLog.user_id == "default", ReviewLog.stock_code == code)
        .order_by(ReviewLog.created_at.desc())
        .all()
    )
    return ReviewListResponse(
        items=[ReviewResponse.model_validate(item) for item in reviews],
        count=len(reviews),
    )


@app.post("/api/v1/stocks/{code}/reviews", response_model=ReviewResponse, status_code=201)
async def create_review(
    code: str,
    review: ReviewCreate,
    db: DbSession,
) -> ReviewLog:
    """Create a review record for a stock."""
    get_stock_or_404(code, db)
    db_review = ReviewLog(user_id="default", stock_code=code, **review.model_dump())
    db.add(db_review)
    db.commit()
    db.refresh(db_review)
    return db_review


@app.put("/api/v1/reviews/{review_id}", response_model=ReviewResponse)
async def update_review(
    review_id: int,
    review: ReviewUpdate,
    db: DbSession,
) -> ReviewLog:
    """Update a review record."""
    db_review = (
        db.query(ReviewLog)
        .filter(ReviewLog.id == review_id, ReviewLog.user_id == "default")
        .first()
    )
    if not db_review:
        raise HTTPException(status_code=404, detail=f"Review {review_id} not found")

    for field, value in review.model_dump(exclude_unset=True).items():
        setattr(db_review, field, value)
    db.commit()
    db.refresh(db_review)
    return db_review


@app.delete("/api/v1/reviews/{review_id}", status_code=204)
async def delete_review(review_id: int, db: DbSession) -> None:
    """Delete a review record."""
    db_review = (
        db.query(ReviewLog)
        .filter(ReviewLog.id == review_id, ReviewLog.user_id == "default")
        .first()
    )
    if not db_review:
        raise HTTPException(status_code=404, detail=f"Review {review_id} not found")

    db.delete(db_review)
    db.commit()



SOURCE_LEVELS: dict[str, dict[str, int | str]] = {
    "A": {
        "label": "法定公告/财报",
        "confidence": 95,
        "boundary": "高置信法定披露，可优先用于增强或削弱投资假设。",
    },
    "B": {
        "label": "行情/估值/基础指标",
        "confidence": 82,
        "boundary": "中高置信结构化数据，适合做背景和趋势检查，不单独构成结论。",
    },
    "C": {
        "label": "新闻/媒体",
        "confidence": 62,
        "boundary": "新闻只能作为线索，需要公告、财报或后续数据交叉验证。",
    },
    "D": {
        "label": "用户输入",
        "confidence": 88,
        "boundary": "这是用户观点或复盘记录，价值高但属于主观假设，不是外部事实。",
    },
}

ALLOWED_AI_ACTIONS = {
    "create_hypothesis",
    "create_check_item",
    "create_review",
    "update_hypothesis_status",
}


def classify_source(source_provider: str | None, source_type: str | None) -> tuple[str, int, str]:
    """Return source level, confidence and evidence boundary."""
    provider = (source_provider or "").lower()
    source = (source_type or "").lower()

    if "cninfo" in provider or "巨潮" in provider or source in {"announcement", "report"}:
        level = "A"
    elif any(name in provider for name in ["tushare", "baostock", "akshare"]) or source in {
        "quote",
        "metric",
        "fundamental_metric",
    }:
        level = "B"
    elif any(name in provider for name in ["eastmoney", "东方财富", "news", "search"]) or source in {
        "news",
        "media",
    }:
        level = "C"
    else:
        level = "D"

    spec = SOURCE_LEVELS[level]
    return level, int(spec["confidence"]), str(spec["boundary"])


def _iso(value: object) -> str | None:
    if value is None:
        return None
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return str(value)


def _date_start(value: object) -> datetime | None:
    if isinstance(value, datetime):
        return value
    if isinstance(value, date):
        return datetime.combine(value, datetime.min.time())
    return None


def _parse_date(value: object) -> date | None:
    if value is None or value == "":
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, str):
        return date.fromisoformat(value)
    raise HTTPException(status_code=422, detail="Invalid date value")


def _string_payload(value: object, fallback: str = "") -> str:
    return value if isinstance(value, str) else fallback


def make_evidence_card(
    *,
    source_type: str,
    source_provider: str,
    title: str,
    summary: str,
    source_url: str | None = None,
    published_at: datetime | None = None,
    fetched_at: datetime | None = None,
    confidence: int | None = None,
) -> EvidenceCard:
    """Build a normalized evidence card for AI and frontend display."""
    level, default_confidence, boundary = classify_source(source_provider, source_type)
    return EvidenceCard(
        source_level=level,
        source_type=source_type,
        source_provider=source_provider,
        source_url=source_url,
        title=title,
        summary=summary,
        published_at=published_at,
        fetched_at=fetched_at,
        confidence=confidence if confidence is not None else default_confidence,
        evidence_boundary=boundary,
    )


def collect_ai_context(stock_code: str, db: Session) -> tuple[Stock, list[dict[str, object]], list[EvidenceCard]]:
    """Collect saved research context and standardized evidence for the AI."""
    stock = get_stock_or_404(stock_code, db)
    case = get_or_create_case(stock_code, db)
    hypotheses = (
        db.query(Hypothesis)
        .filter(Hypothesis.user_id == "default", Hypothesis.case_id == case.id)
        .order_by(Hypothesis.created_at.desc())
        .limit(12)
        .all()
    )
    check_items = (
        db.query(CheckItem)
        .filter(CheckItem.user_id == "default", CheckItem.stock_code == stock_code)
        .order_by(CheckItem.created_at.desc())
        .limit(8)
        .all()
    )
    reviews = (
        db.query(ReviewLog)
        .filter(ReviewLog.user_id == "default", ReviewLog.stock_code == stock_code)
        .order_by(ReviewLog.created_at.desc())
        .limit(8)
        .all()
    )
    events = (
        db.query(Event)
        .filter(Event.stock_code == stock_code, Event.is_duplicate.is_(False))
        .order_by(Event.published_at.desc())
        .limit(8)
        .all()
    )
    metrics = (
        db.query(FundamentalMetric)
        .filter(FundamentalMetric.stock_code == stock_code)
        .order_by(FundamentalMetric.report_date.desc().nullslast(), FundamentalMetric.created_at.desc())
        .limit(8)
        .all()
    )
    quotes = (
        db.query(QuoteSnapshot)
        .filter(QuoteSnapshot.stock_code == stock_code)
        .order_by(QuoteSnapshot.date.desc())
        .limit(3)
        .all()
    )

    context_items: list[dict[str, object]] = [
        {
            "type": "stock",
            "code": stock.code,
            "name": stock.name,
            "industry": stock.industry,
            "market": stock.market,
        }
    ]
    context_items.extend(
        {
            "type": "hypothesis",
            "id": item.id,
            "category": item.category,
            "status": item.status,
            "content": item.content,
            "confidence": item.confidence,
            "evidence": item.evidence,
        }
        for item in hypotheses
    )
    context_items.extend(
        {
            "type": "check_item",
            "id": item.id,
            "content": item.content,
            "status": item.status,
            "due_date": _iso(item.due_date),
        }
        for item in check_items
    )
    context_items.extend(
        {
            "type": "review",
            "id": item.id,
            "title": item.title,
            "content": item.content,
            "conclusions": item.conclusions,
            "created_at": _iso(item.created_at),
        }
        for item in reviews
    )

    evidence_cards: list[EvidenceCard] = []
    for event in events:
        evidence_cards.append(
            make_evidence_card(
                source_type=event.source_type or event.event_type or "news",
                source_provider=event.source_provider or event.source,
                source_url=event.source_url,
                title=event.title,
                summary=event.summary or event.content or event.title,
                published_at=event.published_at,
                fetched_at=event.fetched_at,
                confidence=event.confidence,
            )
        )

    for metric in metrics:
        title = f"{metric.metric_name}: {metric.value if metric.value is not None else '暂无值'}{metric.unit or ''}"
        evidence_cards.append(
            make_evidence_card(
                source_type="fundamental_metric",
                source_provider=metric.source_provider or "unknown",
                title=title,
                summary=(
                    f"{metric.metric_name} 在 {metric.period or '未知期间'} 的值为 "
                    f"{metric.value if metric.value is not None else '暂无'}{metric.unit or ''}。"
                ),
                published_at=_date_start(metric.report_date),
                fetched_at=metric.created_at,
            )
        )

    for quote in quotes:
        evidence_cards.append(
            make_evidence_card(
                source_type="quote",
                source_provider="local_quote_snapshot",
                title=f"{_iso(quote.date) or '未知日期'} 行情快照",
                summary=(
                    f"收盘价 {quote.close if quote.close is not None else '暂无'}，"
                    f"PE {quote.pe if quote.pe is not None else '暂无'}，"
                    f"PB {quote.pb if quote.pb is not None else '暂无'}。"
                ),
                published_at=_date_start(quote.date),
                fetched_at=quote.created_at,
            )
        )

    return stock, context_items, evidence_cards[:12]


def collect_evidence_cards(stock_code: str, db: Session, limit: int = 20) -> list[EvidenceCard]:
    """Collect the latest event, metric and quote evidence cards for a stock."""
    get_stock_or_404(stock_code, db)
    cards: list[EvidenceCard] = []
    events = (
        db.query(Event)
        .filter(Event.stock_code == stock_code, Event.is_duplicate.is_(False))
        .order_by(Event.published_at.desc())
        .limit(limit)
        .all()
    )
    for event in events:
        cards.append(
            make_evidence_card(
                source_type=event.source_type or event.event_type or "news",
                source_provider=event.source_provider or event.source,
                source_url=event.source_url,
                title=event.title,
                summary=event.summary or event.content or event.title,
                published_at=event.published_at,
                fetched_at=event.fetched_at,
                confidence=event.confidence,
            )
        )

    metrics = (
        db.query(FundamentalMetric)
        .filter(FundamentalMetric.stock_code == stock_code)
        .order_by(FundamentalMetric.created_at.desc())
        .limit(limit)
        .all()
    )
    for metric in metrics:
        cards.append(
            make_evidence_card(
                source_type="fundamental_metric",
                source_provider=metric.source_provider or "unknown",
                title=f"{metric.metric_name}: {metric.value if metric.value is not None else '暂无'}{metric.unit or ''}",
                summary=(
                    f"{metric.metric_name} 在 {metric.period or '未知期间'} 的值为 "
                    f"{metric.value if metric.value is not None else '暂无'}{metric.unit or ''}。"
                ),
                published_at=_date_start(metric.report_date),
                fetched_at=metric.created_at,
            )
        )

    quotes = (
        db.query(QuoteSnapshot)
        .filter(QuoteSnapshot.stock_code == stock_code)
        .order_by(QuoteSnapshot.date.desc())
        .limit(limit)
        .all()
    )
    for quote in quotes:
        cards.append(
            make_evidence_card(
                source_type="quote",
                source_provider="quote_snapshot",
                title=f"{_iso(quote.date) or '未知日期'} 行情快照",
                summary=(
                    f"收盘价 {quote.close if quote.close is not None else '暂无'}，"
                    f"PE {quote.pe if quote.pe is not None else '暂无'}，"
                    f"PB {quote.pb if quote.pb is not None else '暂无'}。"
                ),
                published_at=_date_start(quote.date),
                fetched_at=quote.created_at,
            )
        )
    return cards[:limit]


@app.post("/api/v1/stocks/{code}/data/refresh", response_model=DataRefreshResponse)
async def refresh_stock_data(
    code: str,
    request: DataRefreshRequest,
    db: DbSession,
) -> DataRefreshResponse:
    """Refresh external evidence for the selected stock."""
    get_stock_or_404(code, db)
    service = build_data_refresh_service()
    result = service.refresh_stock(db, code, set(request.types), request.lookback_days)
    return DataRefreshResponse(
        stock_code=result.stock_code,
        created=result.created,
        skipped=result.skipped,
        errors=result.errors,
        refreshed_at=result.refreshed_at,
    )


@app.get("/api/v1/stocks/{code}/evidence", response_model=EvidenceListResponse)
async def list_evidence(code: str, db: DbSession, limit: int = 20) -> EvidenceListResponse:
    """List standardized evidence cards for a stock."""
    cards = collect_evidence_cards(code, db, max(1, min(limit, 100)))
    return EvidenceListResponse(items=cards, count=len(cards))


@app.get("/api/v1/stocks/{code}/events", response_model=EventListResponse)
async def list_events(
    code: str,
    db: DbSession,
    type: str | None = None,  # noqa: A002
    limit: int = 20,
) -> EventListResponse:
    """List normalized announcement and news events."""
    get_stock_or_404(code, db)
    query = db.query(Event).filter(Event.stock_code == code, Event.is_duplicate.is_(False))
    if type:
        query = query.filter(Event.source_type == type)
    events = query.order_by(Event.published_at.desc()).limit(max(1, min(limit, 100))).all()
    return EventListResponse(
        items=[EventResponse.model_validate(event) for event in events],
        count=len(events),
    )


@app.get("/api/v1/stocks/{code}/metrics", response_model=MetricListResponse)
async def list_metrics(
    code: str,
    db: DbSession,
    category: str | None = None,
    limit: int = 20,
) -> MetricListResponse:
    """List normalized fundamental and valuation metrics."""
    get_stock_or_404(code, db)
    query = db.query(FundamentalMetric).filter(FundamentalMetric.stock_code == code)
    if category:
        query = query.filter(FundamentalMetric.metric_category == category)
    metrics = query.order_by(FundamentalMetric.created_at.desc()).limit(max(1, min(limit, 100))).all()
    return MetricListResponse(
        items=[MetricResponse.model_validate(metric) for metric in metrics],
        count=len(metrics),
    )


@app.get("/api/v1/stocks/{code}/quotes", response_model=QuoteListResponse)
async def list_quotes(code: str, db: DbSession, limit: int = 20) -> QuoteListResponse:
    """List quote snapshots."""
    get_stock_or_404(code, db)
    quotes = (
        db.query(QuoteSnapshot)
        .filter(QuoteSnapshot.stock_code == code)
        .order_by(QuoteSnapshot.date.desc())
        .limit(max(1, min(limit, 100)))
        .all()
    )
    return QuoteListResponse(
        items=[QuoteResponse.model_validate(quote) for quote in quotes],
        count=len(quotes),
    )


@app.post(
    "/api/v1/stocks/{code}/events/{event_id}/analyze-impact",
    response_model=ImpactAnalysisResponse,
)
async def analyze_event_impact(
    code: str,
    event_id: int,
    db: DbSession,
) -> ImpactAnalysisResponse:
    """Analyze how one event may affect saved investment hypotheses."""
    stock = get_stock_or_404(code, db)
    event = db.query(Event).filter(Event.id == event_id, Event.stock_code == code).first()
    if not event:
        raise HTTPException(status_code=404, detail=f"Event {event_id} not found")

    case = get_or_create_case(code, db)
    hypotheses = (
        db.query(Hypothesis)
        .filter(Hypothesis.user_id == "default", Hypothesis.case_id == case.id)
        .order_by(Hypothesis.created_at.desc())
        .all()
    )
    evidence_card = make_evidence_card(
        source_type=event.source_type,
        source_provider=event.source_provider or event.source,
        source_url=event.source_url,
        title=event.title,
        summary=event.summary or event.content or event.title,
        published_at=event.published_at,
        fetched_at=event.fetched_at,
        confidence=event.confidence,
    )

    actions: list[AiAction] = []
    impacts: list[Impact] = []
    if not hypotheses:
        reply = (
            f"这条事件来自 {evidence_card.source_provider}，但当前还没有可对照的投资假设。"
            "我先生成一个检查项，提醒你补充“为什么关注这家公司”的核心逻辑。"
        )
        actions.append(
            AiAction(
                type="create_check_item",
                payload={
                    "stock_code": code,
                    "content": f"补充投资假设后复盘事件：{event.title}",
                    "source_type": "ai_suggested",
                },
            )
        )
    else:
        target = _select_related_hypothesis(hypotheses, event)
        reason = (
            f"事件「{event.title}」可能影响假设："
            f"{_hypothesis_title(target)}。当前只判断为待观察，需要后续公告或财务指标验证。"
        )
        impact = Impact(
            event_id=event.id,
            hypothesis_id=target.id,
            impact_direction="watching",
            impact_strength=2,
            reason=reason,
            evidence_text=event.summary or event.content or event.title,
            confidence=evidence_card.confidence,
            generated_by="ai",
            user_confirmed=False,
        )
        db.add(impact)
        db.commit()
        db.refresh(impact)
        impacts.append(impact)
        reply = (
            f"我把这条事件与「{stock.name}」的一条投资假设做了映射。"
            "它不是买卖结论，只是提示这条假设进入待观察状态。"
        )
        actions.extend(
            [
                AiAction(
                    type="update_hypothesis_status",
                    payload={
                        "stock_code": code,
                        "hypothesis_id": target.id,
                        "status": "watching",
                        "reason": reason,
                    },
                ),
                AiAction(
                    type="create_review",
                    payload={
                        "stock_code": code,
                        "review_type": "event",
                        "title": f"事件复盘：{event.title[:40]}",
                        "content": reason,
                        "conclusions": "待用户确认后沉淀为事件复盘。",
                        "action_items": [f"继续跟踪：{event.title}"],
                        "trigger_event_id": event.id,
                    },
                ),
            ]
        )

    return ImpactAnalysisResponse(
        reply=reply,
        actions=actions,
        evidence_cards=[evidence_card],
        impacts=[ImpactResponse.model_validate(impact) for impact in impacts],
    )


def _select_related_hypothesis(hypotheses: list[Hypothesis], event: Event) -> Hypothesis:
    """Pick a likely related hypothesis using a tiny deterministic overlap score."""
    event_text = f"{event.title} {event.summary or ''} {event.content or ''}".lower()
    best = hypotheses[0]
    best_score = -1
    for hypothesis in hypotheses:
        content = json.dumps(hypothesis.content, ensure_ascii=False).lower()
        tokens = {token for token in content.replace("，", " ").replace("。", " ").split() if len(token) >= 2}
        score = sum(1 for token in tokens if token in event_text)
        if score > best_score:
            best = hypothesis
            best_score = score
    return best


def _hypothesis_title(hypothesis: Hypothesis) -> str:
    content = hypothesis.content if isinstance(hypothesis.content, dict) else {}
    title = content.get("title") or content.get("core_judgment") or content.get("summary")
    return str(title) if title else f"假设 #{hypothesis.id}"


def build_local_ai_actions(message: str, stock_code: str, has_external_evidence: bool) -> list[AiAction]:
    """Build deterministic evidence-aware actions when no LLM key is configured."""
    text = message.strip()
    lower_text = text.lower()
    actions: list[AiAction] = []

    if any(keyword in text for keyword in ["检查", "跟踪", "下季度", "关注", "验证"]):
        actions.append(
            AiAction(
                type="create_check_item",
                payload={
                    "stock_code": stock_code,
                    "content": text if text.startswith("检查") else f"检查：{text}",
                    "due_date": None,
                    "source_type": "ai_suggested",
                },
            )
        )

    if any(keyword in text for keyword in ["复盘", "总结", "结论"]) or "review" in lower_text:
        actions.append(
            AiAction(
                type="create_review",
                payload={
                    "stock_code": stock_code,
                    "review_type": "event",
                    "title": "AI 整理的复盘记录",
                    "content": text,
                    "conclusions": "待用户确认后沉淀为复盘记录。",
                    "action_items": [],
                },
            )
        )

    if not actions:
        confidence = 62 if not has_external_evidence else 72
        evidence = "AI 根据用户输入整理，尚缺外部证据验证"
        if has_external_evidence:
            evidence = "AI 根据用户输入和当前证据卡整理，需用户确认"
        actions.append(
            AiAction(
                type="create_hypothesis",
                payload={
                    "stock_code": stock_code,
                    "category": "growth_logic",
                    "status": "unverified",
                    "content": {
                        "title": text[:40],
                        "summary": text,
                    },
                    "confidence": confidence,
                    "evidence": evidence,
                    "next_review_date": None,
                },
            )
        )

    return actions[:3]


def build_local_ai_reply(stock: Stock, has_external_evidence: bool) -> str:
    """Return a conservative fallback reply with explicit evidence boundary."""
    if not has_external_evidence:
        return (
            "当前证据不足：我只看到了你输入的关注逻辑或系统内已有记录，尚未看到公告、财报、行情或新闻证据。"
            f"我先把你关于「{stock.name}」的想法拆成可验证成果，保存前请确认它是否真实代表你的判断。"
        )
    return (
        f"我会把「{stock.name}」的现有证据当作线索，而不是直接给买卖结论。"
        "下面是可保存成果：你可以确认它是否对应你的买入逻辑，并继续追问哪条假设被增强或削弱。"
    )


def build_ai_prompt(
    *,
    stock: Stock,
    message: str,
    context_items: list[dict[str, object]],
    evidence_cards: list[EvidenceCard],
    has_external_evidence: bool,
) -> str:
    """Build the constrained prompt for the A-share fundamental review coach."""
    context_json = json.dumps(context_items, ensure_ascii=False, default=str)
    evidence_json = json.dumps(
        [card.model_dump(mode="json") for card in evidence_cards],
        ensure_ascii=False,
        default=str,
    )
    return f"""
你是“A股基本面复盘教练”，你的目标不是荐股，而是帮助用户把“为什么关注这只股票”沉淀为可验证假设、检查项或复盘记录。

当前股票：
- 代码：{stock.code}
- 名称：{stock.name}
- 行业/主题：{stock.industry or "未知"}

用户消息：
{message}

系统已保存上下文 JSON：
{context_json}

标准化证据卡 JSON：
{evidence_json}

外部证据是否充足：{has_external_evidence}

必须遵守：
1. 不得回答“该买/该卖/建议建仓/建议清仓”，不得预测短线涨跌。
2. 不得编造未提供的数据、公告、新闻或财务指标。
3. 必须说明证据边界：哪些来自证据卡，哪些只是用户观点，哪些仍不确定。
4. 如果外部证据不足，reply 必须包含“当前证据不足”，但仍可追问用户并整理用户观点。
5. actions 必须是数组，且 type 只能是 create_hypothesis、create_check_item、create_review、update_hypothesis_status。
6. actions 是待保存成果，用户确认后才会写库。

只输出合法 JSON，不要 Markdown，不要额外解释。格式：
{{
  "reply": "给用户看的中文回复",
  "actions": [
    {{
      "type": "create_hypothesis",
      "payload": {{
        "stock_code": "{stock.code}",
        "category": "growth_logic",
        "status": "unverified",
        "content": {{"title": "一句话假设", "summary": "如何验证这条假设"}},
        "confidence": 60,
        "evidence": "证据边界说明",
        "next_review_date": null
      }}
    }}
  ]
}}
""".strip()


def sanitize_ai_actions(raw_actions: object, stock_code: str) -> list[AiAction]:
    """Validate LLM actions and keep only supported, safe writes."""
    if not isinstance(raw_actions, list):
        return []

    actions: list[AiAction] = []
    for raw_action in raw_actions[:3]:
        if not isinstance(raw_action, dict):
            continue
        action_type = raw_action.get("type")
        payload = raw_action.get("payload")
        if action_type not in ALLOWED_AI_ACTIONS or not isinstance(payload, dict):
            continue
        payload["stock_code"] = stock_code
        actions.append(AiAction(type=str(action_type), payload=payload))
    return actions


def parse_llm_json(text: str) -> dict[str, object]:
    """Parse strict JSON or extract the first JSON object from provider text."""
    try:
        data = json.loads(text)
        return data if isinstance(data, dict) else {}
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start < 0 or end <= start:
            return {}
        try:
            data = json.loads(text[start : end + 1])
            return data if isinstance(data, dict) else {}
        except json.JSONDecodeError:
            return {}


def call_llm_ai(prompt: str, stock_code: str) -> tuple[str, list[AiAction]] | None:
    """Call the configured LLM provider; return None so local fallback can handle failures."""
    provider = get_llm_provider()
    if provider is None:
        return None

    try:
        response = provider.complete(LLMRequest(prompt=prompt))
        data = parse_llm_json(response.text)
        reply = data.get("reply")
        if not isinstance(reply, str):
            return None
        actions = sanitize_ai_actions(data.get("actions"), stock_code)
        return reply, actions
    except (LLMProviderError, TypeError):
        return None


@app.post("/api/v1/ai/chat", response_model=AiChatResponse)
async def ai_chat(request: AiChatRequest, db: DbSession) -> AiChatResponse:
    """Turn user text and saved evidence into structured, user-confirmed actions."""
    stock, context_items, evidence_cards = collect_ai_context(request.stock_code, db)
    has_external_evidence = any(card.source_level in {"A", "B", "C"} for card in evidence_cards)
    prompt = build_ai_prompt(
        stock=stock,
        message=request.message,
        context_items=context_items,
        evidence_cards=evidence_cards,
        has_external_evidence=has_external_evidence,
    )
    llm_result = call_llm_ai(prompt, request.stock_code)
    if llm_result:
        reply, actions = llm_result
        if not actions:
            actions = build_local_ai_actions(request.message, request.stock_code, has_external_evidence)
    else:
        reply = build_local_ai_reply(stock, has_external_evidence)
        actions = build_local_ai_actions(request.message, request.stock_code, has_external_evidence)

    return AiChatResponse(reply=reply, actions=actions, evidence_cards=evidence_cards)


@app.get("/api/v1/ai/provider-status", response_model=AiProviderStatusResponse)
async def ai_provider_status() -> AiProviderStatusResponse:
    """Return non-sensitive provider status for local setup checks."""
    provider = get_llm_provider()
    return AiProviderStatusResponse(
        provider=provider.provider_name if provider else os.environ.get("LLM_PROVIDER"),
        configured=provider is not None,
    )


@app.post("/api/v1/ai/actions/apply", response_model=AiActionApplyResponse)
async def apply_ai_action(
    request: AiActionApplyRequest,
    db: DbSession,
) -> AiActionApplyResponse:
    """Apply a user-confirmed AI action."""
    action_type = request.type
    payload = request.payload
    stock_code = payload.get("stock_code")
    if not isinstance(stock_code, str):
        raise HTTPException(status_code=422, detail="payload.stock_code is required")

    if action_type == "create_hypothesis":
        case = get_or_create_case(stock_code, db)
        hypothesis = Hypothesis(
            user_id="default",
            case_id=case.id,
            category=_string_payload(payload.get("category"), "growth_logic"),
            status=_string_payload(payload.get("status"), "unverified"),
            content=payload.get("content") if isinstance(payload.get("content"), dict) else {},
            confidence=int(payload.get("confidence", 70)),
            evidence=payload.get("evidence") if isinstance(payload.get("evidence"), str) else None,
            next_review_date=_parse_date(payload.get("next_review_date")),
        )
        db.add(hypothesis)
        db.commit()
        db.refresh(hypothesis)
        return AiActionApplyResponse(
            type=action_type,
            result=HypothesisResponse.model_validate(hypothesis).model_dump(mode="json"),
        )

    if action_type == "create_check_item":
        get_stock_or_404(stock_code, db)
        check_item = CheckItem(
            user_id="default",
            stock_code=stock_code,
            content=_string_payload(payload.get("content")),
            due_date=_parse_date(payload.get("due_date")),
            source_type=_string_payload(payload.get("source_type"), "ai_suggested"),
            linked_hypothesis_id=payload.get("linked_hypothesis_id")
            if isinstance(payload.get("linked_hypothesis_id"), int)
            else None,
        )
        db.add(check_item)
        db.commit()
        db.refresh(check_item)
        return AiActionApplyResponse(
            type=action_type,
            result=CheckItemResponse.model_validate(check_item).model_dump(mode="json"),
        )

    if action_type == "create_review":
        get_stock_or_404(stock_code, db)
        review = ReviewLog(
            user_id="default",
            stock_code=stock_code,
            review_type=_string_payload(payload.get("review_type"), "event"),
            title=payload.get("title") if isinstance(payload.get("title"), str) else None,
            content=_string_payload(payload.get("content")),
            conclusions=payload.get("conclusions") if isinstance(payload.get("conclusions"), str) else None,
            action_items=payload.get("action_items") if isinstance(payload.get("action_items"), list) else [],
            trigger_event_id=payload.get("trigger_event_id")
            if isinstance(payload.get("trigger_event_id"), int)
            else None,
        )
        db.add(review)
        db.commit()
        db.refresh(review)
        return AiActionApplyResponse(
            type=action_type,
            result=ReviewResponse.model_validate(review).model_dump(mode="json"),
        )

    if action_type == "update_hypothesis_status":
        hypothesis_id = payload.get("hypothesis_id")
        status = payload.get("status")
        if not isinstance(hypothesis_id, int) or not isinstance(status, str):
            raise HTTPException(status_code=422, detail="payload.hypothesis_id and payload.status are required")
        case = get_or_create_case(stock_code, db)
        updated_hypothesis = (
            db.query(Hypothesis)
            .filter(
                Hypothesis.id == hypothesis_id,
                Hypothesis.user_id == "default",
                Hypothesis.case_id == case.id,
            )
            .first()
        )
        if not updated_hypothesis:
            raise HTTPException(status_code=404, detail=f"Hypothesis {hypothesis_id} not found")
        reason = payload.get("reason")
        updated_hypothesis.status = status
        if isinstance(reason, str) and reason:
            updated_hypothesis.evidence = reason
        db.commit()
        db.refresh(updated_hypothesis)
        return AiActionApplyResponse(
            type=action_type,
            result=HypothesisResponse.model_validate(updated_hypothesis).model_dump(mode="json"),
        )

    raise HTTPException(status_code=422, detail=f"Unsupported action type: {action_type}")
