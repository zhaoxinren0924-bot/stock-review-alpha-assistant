"""Stock Review Alpha Assistant - Main Application."""

import asyncio
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
    DailyReview,
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
    DailyReviewCoachRequest,
    DailyReviewCoachResponse,
    DailyReviewListResponse,
    DailyReviewPrefillResponse,
    DailyReviewResponse,
    DailyReviewUpdate,
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
from app.services.daily_market_prefill import (
    _fmt_amount,
    _to_float,
    build_daily_market_prefill_service,
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
        "daily_reviews": {
            "user_id": "VARCHAR(50) NOT NULL DEFAULT 'default'",
            "updated_at": "DATETIME",
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


SOURCE_MANUAL = "manual"
SOURCE_DATA = "data_prefilled"
SOURCE_AI = "ai_generated"
SOURCE_INSUFFICIENT = "insufficient_evidence"


def field_value(value: object = "", source: str = SOURCE_MANUAL, note: str = "") -> dict[str, object]:
    """Build a traceable daily review field."""
    return {"value": value, "source": source, "note": note}


def build_daily_review_template(review_date: date) -> dict[str, object]:
    """Return the v1 structured daily review template."""
    is_weekend = review_date.weekday() >= 5
    return {
        "index_review": {
            "indices": [
                {"name": name, "change_pct": field_value(), "turnover": field_value(), "note": field_value()}
                for name in ["上证指数", "深证成指", "创业板指", "科创50", "中证2000", "恒生指数", "纳斯达克", "标普500"]
            ],
            "leading_index": field_value(),
            "market_style": field_value(),
            "external_impact": field_value("", SOURCE_INSUFFICIENT, "第一版尚未接入指数全量数据，需用户补充。"),
        },
        "hotspot_review": {
            "sentiment_metrics": {
                "limit_up_count": field_value("", SOURCE_INSUFFICIENT, "第一版尚未接入全市场涨停家数。"),
                "limit_down_count": field_value("", SOURCE_INSUFFICIENT, "第一版尚未接入全市场跌停家数。"),
                "streak_height": field_value("", SOURCE_INSUFFICIENT, "第一版尚未接入连板高度。"),
                "failed_board_rate": field_value("", SOURCE_INSUFFICIENT, "第一版尚未接入炸板率。"),
            },
            "main_sectors": [],
            "summary": field_value(),
        },
        "capital_review": {
            "turnover_leaders": [],
            "capital_direction": field_value("", SOURCE_INSUFFICIENT, "第一版尚未接入成交额榜单和资金流全量数据。"),
        },
        "limit_review": {
            "risk_rows": [],
            "opportunity_rows": [],
            "common_summary": field_value("", SOURCE_INSUFFICIENT, "第一版尚未接入涨跌停个股全量数据。"),
        },
        "watchlist_review": {
            "pool_status": {
                "holding_count": field_value(0, SOURCE_DATA, "来自当前关注股票数量。"),
                "monthly_added": field_value("", SOURCE_MANUAL),
                "monthly_removed": field_value("", SOURCE_MANUAL),
            },
            "targets": [],
        },
        "fundamental_review": {
            "macro_checklist": [],
            "industry_checklist": [],
            "company_rows": [],
            "risk_checklist": [
                {"label": "ST/退市风险", "checked": False, "source": SOURCE_MANUAL},
                {"label": "高质押/减持", "checked": False, "source": SOURCE_MANUAL},
                {"label": "业绩变脸/商誉减值", "checked": False, "source": SOURCE_MANUAL},
                {"label": "解禁/大额减持", "checked": False, "source": SOURCE_MANUAL},
            ],
        },
        "tomorrow_plan": {
            "market_view": field_value(),
            "position_plan": field_value(),
            "focus_sectors": [],
            "operation_plan": [],
            "lessons": field_value(),
        },
        "weekly_review": {
            "enabled": is_weekend,
            "market_style_summary": field_value(),
            "hotspot_evolution": field_value(),
            "capital_flow_summary": field_value(),
            "watchlist_audit": field_value(),
            "next_week_plan": field_value(),
            "pnl_attribution": field_value(),
        },
    }


def deep_merge_dict(base: dict[str, object], updates: dict[str, object]) -> dict[str, object]:
    """Merge nested dicts so section updates do not wipe the whole template."""
    merged = dict(base)
    for key, value in updates.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = deep_merge_dict(merged[key], value)  # type: ignore[arg-type]
        else:
            merged[key] = value
    return merged


def get_daily_review_or_404(review_id: int, db: Session) -> DailyReview:
    """Return the default user's daily review or raise a 404."""
    review = (
        db.query(DailyReview)
        .filter(DailyReview.id == review_id, DailyReview.user_id == "default")
        .first()
    )
    if not review:
        raise HTTPException(status_code=404, detail=f"Daily review {review_id} not found")
    return review


def normalize_daily_review_content(review: DailyReview) -> None:
    """Ensure older drafts have every v1 template section."""
    template = build_daily_review_template(_model_date(review.review_date))
    review.content = deep_merge_dict(template, review.content or {})


@app.get("/api/v1/daily-reviews", response_model=DailyReviewListResponse)
async def list_daily_reviews(
    db: DbSession,
    date_from: date | None = None,
    date_to: date | None = None,
) -> DailyReviewListResponse:
    """List structured daily reviews."""
    query = db.query(DailyReview).filter(DailyReview.user_id == "default")
    if date_from:
        query = query.filter(DailyReview.review_date >= date_from)
    if date_to:
        query = query.filter(DailyReview.review_date <= date_to)
    reviews = query.order_by(DailyReview.review_date.desc()).all()
    for review in reviews:
        normalize_daily_review_content(review)
    return DailyReviewListResponse(
        items=[DailyReviewResponse.model_validate(review) for review in reviews],
        count=len(reviews),
    )


@app.get("/api/v1/daily-reviews/{review_date}", response_model=DailyReviewResponse)
async def get_daily_review(review_date: date, db: DbSession) -> DailyReview:
    """Get one structured daily review by date."""
    review = (
        db.query(DailyReview)
        .filter(DailyReview.user_id == "default", DailyReview.review_date == review_date)
        .first()
    )
    if not review:
        raise HTTPException(status_code=404, detail=f"Daily review {review_date.isoformat()} not found")
    normalize_daily_review_content(review)
    return review


@app.post("/api/v1/daily-reviews/{review_date}/initialize", response_model=DailyReviewResponse, status_code=201)
async def initialize_daily_review(review_date: date, db: DbSession) -> DailyReview:
    """Create or return a daily review draft with the full v1 template."""
    existing = (
        db.query(DailyReview)
        .filter(DailyReview.user_id == "default", DailyReview.review_date == review_date)
        .first()
    )
    if existing:
        normalize_daily_review_content(existing)
        db.commit()
        db.refresh(existing)
        return existing

    review = DailyReview(
        user_id="default",
        review_date=review_date,
        status="draft",
        content=build_daily_review_template(review_date),
    )
    db.add(review)
    db.commit()
    db.refresh(review)
    return review


@app.put("/api/v1/daily-reviews/{review_id}", response_model=DailyReviewResponse)
async def update_daily_review(
    review_id: int,
    request: DailyReviewUpdate,
    db: DbSession,
) -> DailyReview:
    """Update top-level metadata or structured content for a daily review."""
    review = get_daily_review_or_404(review_id, db)
    for field, value in request.model_dump(exclude_unset=True).items():
        if field == "content" and isinstance(value, dict):
            normalize_daily_review_content(review)
            review.content = deep_merge_dict(review.content, value)
        else:
            setattr(review, field, value)
    review.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(review)
    normalize_daily_review_content(review)
    return review


def prefill_daily_review_content(
    review: DailyReview,
    db: Session,
) -> tuple[dict[str, object], dict[str, int], list[str], list[EvidenceCard]]:
    """Prefill the template using local stock/evidence data and market-wide feeds."""
    normalize_daily_review_content(review)
    content = dict(review.content)
    stocks = db.query(Stock).order_by(Stock.created_at.desc()).all()

    # Auto-refresh missing quote snapshots so watchlist/fundamental reviews have amount/close/pe/pb.
    refresh_service = build_data_refresh_service()
    for stock in stocks:
        has_quote = (
            db.query(QuoteSnapshot)
            .filter(QuoteSnapshot.stock_code == stock.code)
            .first()
            is not None
        )
        if not has_quote:
            refresh_service.refresh_stock(db, stock.code, {"quote"})

    evidence_cards: list[EvidenceCard] = []
    filled = {"watchlist_targets": 0, "company_rows": 0, "evidence_cards": 0}
    missing: list[str] = []

    # Sections 1-4: indices / hotspots / capital flow / limit boards (market-wide).
    market_service = build_daily_market_prefill_service()
    market_result = market_service.prefill(review.review_date)
    for section_key, patch in market_result.content_patch.items():
        if isinstance(patch, dict):
            content[section_key] = deep_merge_dict(
                content.get(section_key, {}),  # type: ignore[arg-type]
                patch,
            )
    filled.update(market_result.filled)
    missing.extend(market_result.missing)

    # Fallback: if market-wide capital data failed, use watchlist quotes sorted by amount.
    capital_section = content.get("capital_review", {})
    if not capital_section.get("turnover_leaders"):
        quote_leaders: list[dict[str, object]] = []
        for stock in stocks:
            q = (
                db.query(QuoteSnapshot)
                .filter(QuoteSnapshot.stock_code == stock.code)
                .order_by(QuoteSnapshot.date.desc())
                .first()
            )
            if q and q.amount:
                quote_leaders.append(
                    {
                        "target": field_value(stock.name, SOURCE_DATA),
                        "amount": field_value(_fmt_amount(q.amount), SOURCE_DATA),
                        "sector": field_value(stock.industry or ""),
                        "intent": field_value("", SOURCE_MANUAL, "主力意图猜测需要用户确认，系统不自动下结论。"),
                    }
                )
        quote_leaders.sort(
            key=lambda r: _to_float(r["amount"]["value"]) or 0,
            reverse=True,
        )
        if quote_leaders:
            content["capital_review"] = deep_merge_dict(
                content.get("capital_review", {}),
                {
                    "turnover_leaders": quote_leaders[:10],
                    "capital_direction": field_value(
                        "；".join(str(item["target"]["value"]) for item in quote_leaders[:3]),
                        SOURCE_DATA,
                        "来自自选股最新行情成交额，非全市场排名。",
                    ),
                },
            )
            filled["capital_rows"] = len(quote_leaders[:10])
            if "个股成交额排名" in missing:
                missing.remove("个股成交额排名")

    watchlist_targets = []
    company_rows = []
    for stock in stocks:
        latest_events = (
            db.query(Event)
            .filter(Event.stock_code == stock.code, Event.is_duplicate.is_(False))
            .order_by(Event.published_at.desc())
            .limit(3)
            .all()
        )
        latest_metrics = (
            db.query(FundamentalMetric)
            .filter(FundamentalMetric.stock_code == stock.code)
            .order_by(FundamentalMetric.created_at.desc())
            .limit(3)
            .all()
        )
        latest_quote = (
            db.query(QuoteSnapshot)
            .filter(QuoteSnapshot.stock_code == stock.code)
            .order_by(QuoteSnapshot.date.desc())
            .first()
        )

        event_summary = "；".join(event.summary or event.title for event in latest_events) or "暂无公告/新闻证据"
        metric_summary = "；".join(
            f"{metric.metric_name} {metric.value if metric.value is not None else '暂无'}{metric.unit or ''}"
            for metric in latest_metrics
        ) or "暂无指标证据"
        quote_summary = (
            f"收盘 {latest_quote.close if latest_quote and latest_quote.close is not None else '暂无'}，"
            f"PE {latest_quote.pe if latest_quote and latest_quote.pe is not None else '暂无'}，"
            f"PB {latest_quote.pb if latest_quote and latest_quote.pb is not None else '暂无'}"
        )

        watchlist_targets.append(
            {
                "stock_code": stock.code,
                "stock_name": stock.name,
                "technical_shape": field_value("", SOURCE_MANUAL),
                "daily_trend": field_value("", SOURCE_MANUAL),
                "intraday_position": field_value("", SOURCE_MANUAL),
                "planned_action": field_value("", SOURCE_MANUAL, "只记录用户计划，不代表系统建议。"),
                "fundamental_change": field_value(event_summary, SOURCE_DATA if latest_events else SOURCE_INSUFFICIENT),
            }
        )
        company_rows.append(
            {
                "stock_code": stock.code,
                "stock_name": stock.name,
                "earnings_expectation": field_value("", SOURCE_MANUAL),
                "announcement_news": field_value(event_summary, SOURCE_DATA if latest_events else SOURCE_INSUFFICIENT),
                "shareholder_changes": field_value("", SOURCE_MANUAL),
                "financial_risk": field_value(metric_summary, SOURCE_DATA if latest_metrics else SOURCE_INSUFFICIENT),
                "valuation_position": field_value(quote_summary, SOURCE_DATA if latest_quote else SOURCE_INSUFFICIENT),
            }
        )
        filled["watchlist_targets"] += 1
        filled["company_rows"] += 1

        for event in latest_events:
            evidence_cards.append(
                make_evidence_card(
                    source_type=event.source_type or event.event_type or "news",
                    source_provider=event.source_provider or event.source,
                    source_url=event.source_url,
                    title=f"{stock.name}：{event.title}",
                    summary=event.summary or event.content or event.title,
                    published_at=event.published_at,
                    fetched_at=event.fetched_at,
                    confidence=event.confidence,
                )
            )
        for metric in latest_metrics:
            evidence_cards.append(
                make_evidence_card(
                    source_type="fundamental_metric",
                    source_provider=metric.source_provider or "unknown",
                    title=f"{stock.name}：{metric.metric_name}",
                    summary=(
                        f"{metric.metric_name} 在 {metric.period or '未知期间'} 的值为 "
                        f"{metric.value if metric.value is not None else '暂无'}{metric.unit or ''}。"
                    ),
                    published_at=_date_start(metric.report_date),
                    fetched_at=metric.created_at,
                )
            )

    content["watchlist_review"] = deep_merge_dict(
        content.get("watchlist_review", {}),
        {
            "pool_status": {
                "holding_count": field_value(len(stocks), SOURCE_DATA, "来自当前关注股票数量。"),
            },
            "targets": watchlist_targets,
        },
    )
    content["fundamental_review"] = deep_merge_dict(
        content.get("fundamental_review", {}),
        {"company_rows": company_rows},
    )
    filled["evidence_cards"] = len(evidence_cards[:12])
    return content, filled, missing, evidence_cards[:12]


@app.post("/api/v1/daily-reviews/{review_id}/prefill", response_model=DailyReviewPrefillResponse)
async def prefill_daily_review(review_id: int, db: DbSession) -> DailyReviewPrefillResponse:
    """Prefill a daily review from existing watchlist, evidence and metrics."""
    review = get_daily_review_or_404(review_id, db)
    content, filled, missing, evidence_cards = prefill_daily_review_content(review, db)
    review.content = content
    review.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(review)
    normalize_daily_review_content(review)
    return DailyReviewPrefillResponse(
        review=DailyReviewResponse.model_validate(review),
        filled=filled,
        missing=missing,
        evidence_cards=evidence_cards,
    )


MARKET_DAILY_SECTIONS = {
    "index_review",
    "hotspot_review",
    "capital_review",
    "limit_review",
}
COMPANY_DAILY_SECTIONS = {
    "watchlist_review",
    "fundamental_review",
}


def _extract_stock_codes_from_section(section_content: object) -> list[str]:
    """Pick out unique stock_code strings from any list-of-dicts in a section."""
    codes: list[str] = []
    if not isinstance(section_content, dict):
        return codes
    for value in section_content.values():
        if not isinstance(value, list):
            continue
        for item in value:
            if isinstance(item, dict):
                code = item.get("stock_code")
                if isinstance(code, str) and code and code not in codes:
                    codes.append(code)
    return codes


def _condense_section_for_summary(section: object) -> dict[str, object]:
    """Keep only conclusion-type fields; drop long raw row lists.

    Each section field is either:
      - a {value, source, note} dict (a single conclusion field) → keep value
      - a nested dict of conclusion fields (e.g. sentiment_metrics) → keep values
      - a list of row dicts (e.g. indices, turnover_leaders) → drop
    """
    if not isinstance(section, dict):
        return {}
    out: dict[str, object] = {}
    for key, value in section.items():
        if isinstance(value, list):
            continue
        if isinstance(value, dict):
            inner_value = value.get("value")
            if inner_value not in (None, "", []):
                out[key] = inner_value
                continue
            nested: dict[str, object] = {}
            for nested_key, nested_val in value.items():
                if isinstance(nested_val, dict):
                    nv = nested_val.get("value")
                    if nv not in (None, "", []):
                        nested[nested_key] = nv
            if nested:
                out[key] = nested
            continue
        if value not in (None, "", []):
            out[key] = value
    return out


def collect_daily_review_context(
    review: DailyReview,
    db: Session,
    section_key: str | None = None,
) -> tuple[list[dict[str, object]], list[EvidenceCard]]:
    """Collect *section-scoped* daily-review context for the AI coach.

    Strategy: avoid dumping the whole review.content + 30 stocks + 12 evidence
    cards on every turn. Instead, scope what's included to what's actually
    relevant to the section the user is currently working in.
    """
    normalize_daily_review_content(review)
    content = review.content or {}

    meta: dict[str, object] = {
        "type": "daily_review_meta",
        "id": review.id,
        "review_date": _model_date(review.review_date).isoformat(),
        "status": review.status,
        "market_style": review.market_style,
        "main_sector": review.main_sector,
        "sentiment": review.sentiment,
        "current_section": section_key,
    }
    context_items: list[dict[str, object]] = [meta]
    evidence_cards: list[EvidenceCard] = []

    if section_key in MARKET_DAILY_SECTIONS:
        # Indices / hotspots / capital / limit boards: pure market-level work.
        # No need for any watchlist or per-stock evidence — that's noise here.
        section_content = content.get(section_key)
        if isinstance(section_content, dict):
            context_items.append({
                "type": "current_section",
                "section_key": section_key,
                "content": section_content,
            })
        return context_items, evidence_cards

    if section_key in COMPANY_DAILY_SECTIONS:
        # Watchlist / fundamental: include only stocks actually referenced
        # in this section, plus their evidence (2 cards/stock, not 3).
        section_content = content.get(section_key)
        if isinstance(section_content, dict):
            context_items.append({
                "type": "current_section",
                "section_key": section_key,
                "content": section_content,
            })
        codes = _extract_stock_codes_from_section(section_content)
        if not codes:
            recent_stocks = db.query(Stock).order_by(Stock.created_at.desc()).limit(8).all()
            codes = [stock.code for stock in recent_stocks]
        for code in codes[:8]:
            stock = db.query(Stock).filter(Stock.code == code).first()
            if stock is None:
                continue
            context_items.append({
                "type": "watchlist_stock",
                "code": stock.code,
                "name": stock.name,
                "industry": stock.industry,
            })
            evidence_cards.extend(collect_evidence_cards(stock.code, db, limit=2))
        return context_items, evidence_cards[:8]

    if section_key == "tomorrow_plan":
        # Tomorrow plan needs the *conclusions* of sections 1-6, not raw rows.
        summary: dict[str, object] = {}
        for key in (
            "index_review",
            "hotspot_review",
            "capital_review",
            "limit_review",
            "watchlist_review",
            "fundamental_review",
        ):
            section_obj = content.get(key)
            condensed = _condense_section_for_summary(section_obj)
            if condensed:
                summary[key] = condensed
        section_content = content.get("tomorrow_plan")
        if isinstance(section_content, dict):
            context_items.append({
                "type": "current_section",
                "section_key": "tomorrow_plan",
                "content": section_content,
            })
        if summary:
            context_items.append({
                "type": "review_summary",
                "sections": summary,
            })
        return context_items, evidence_cards

    # weekly_review or unknown: minimal context, just meta.
    return context_items, evidence_cards


def build_daily_review_coach_prompt(
    *,
    review: DailyReview,
    message: str,
    section_key: str | None,
    context_items: list[dict[str, object]],
    evidence_cards: list[EvidenceCard],
) -> str:
    """Build a strict prompt for the daily review coach."""
    context_json = json.dumps(context_items, ensure_ascii=False, default=str)
    evidence_json = json.dumps(
        [card.model_dump(mode="json") for card in evidence_cards],
        ensure_ascii=False,
        default=str,
    )
    return f"""
你是“A股每日复盘教练”，任务是引导用户把市场、板块、自选股和基本面观察沉淀为结构化每日复盘。

复盘日期：{_model_date(review.review_date).isoformat()}
当前 section：{section_key or "未指定"}
用户消息：
{message}

当前复盘和自选股上下文 JSON：
{context_json}

可用证据卡 JSON：
{evidence_json}

必须遵守：
1. 不得使用“买入”“卖出”“荐股”“建议建仓”“建议清仓”等措辞。
2. 不得预测短线涨跌，不得编造未提供的数据。
3. 必须区分：证据卡事实、用户观点、AI 推理、证据不足。
4. 如果证据不足，reply 必须明确包含“当前证据不足”。
5. actions 只能是 update_daily_review_section、create_daily_review_action、link_evidence_to_daily_review、create_check_item、create_review。
6. actions 是待保存成果，用户确认后才会写库。

只输出合法 JSON：
{{
  "reply": "中文回复",
  "actions": [
    {{
      "type": "update_daily_review_section",
      "payload": {{
        "daily_review_id": {review.id},
        "section_key": "{section_key or "tomorrow_plan"}",
        "patch": {{
          "summary": {{"value": "用户确认后的复盘要点", "source": "ai_generated", "note": "基于用户输入整理"}}
        }}
      }}
    }}
  ]
}}
""".strip()


def build_local_daily_review_actions(
    message: str,
    review_id: int,
    section_key: str | None,
    has_external_evidence: bool,
) -> list[AiAction]:
    """Build deterministic daily-review actions when LLM is unavailable."""
    target_section = section_key or "tomorrow_plan"
    note = "基于用户输入和现有证据整理，需用户确认。" if has_external_evidence else "当前证据不足，先沉淀为待验证观点。"
    return [
        AiAction(
            type="update_daily_review_section",
            payload={
                "daily_review_id": review_id,
                "section_key": target_section,
                "patch": {
                    "ai_notes": [
                        {
                            "value": message,
                            "source": SOURCE_AI,
                            "note": note,
                            "created_at": datetime.utcnow().isoformat(),
                        }
                    ]
                },
            },
        ),
        AiAction(
            type="create_daily_review_action",
            payload={
                "daily_review_id": review_id,
                "section_key": target_section,
                "content": f"继续验证：{message}",
                "source": SOURCE_AI,
            },
        ),
    ]


def build_local_daily_review_reply(has_external_evidence: bool) -> str:
    """Return a conservative daily-review coach fallback reply."""
    if not has_external_evidence:
        return (
            "当前证据不足：系统还没有足够的公告、指标、行情或新闻来验证这段复盘。"
            "我先把你的判断整理成待确认的复盘要点，并建议你补充触发条件和后续观察项。"
        )
    return (
        "我会把已有证据当作线索，而不是结论。下面的待保存成果会帮助你把今天的市场观察沉淀到复盘模板里。"
    )


def sanitize_daily_review_actions(raw_actions: object, review_id: int) -> list[AiAction]:
    """Validate LLM daily-review actions and keep only safe pending writes."""
    allowed = {
        "update_daily_review_section",
        "create_daily_review_action",
        "link_evidence_to_daily_review",
        "create_check_item",
        "create_review",
    }
    if not isinstance(raw_actions, list):
        return []
    actions: list[AiAction] = []
    for raw_action in raw_actions[:4]:
        if not isinstance(raw_action, dict):
            continue
        action_type = raw_action.get("type")
        payload = raw_action.get("payload")
        if action_type not in allowed or not isinstance(payload, dict):
            continue
        payload["daily_review_id"] = review_id
        actions.append(AiAction(type=str(action_type), payload=payload))
    return actions


def call_llm_daily_review_ai(prompt: str, review_id: int) -> tuple[str, list[AiAction]] | None:
    """Call the configured LLM for daily reviews with daily-review action validation."""
    provider = get_llm_provider()
    if provider is None:
        return None

    try:
        response = provider.complete(LLMRequest(prompt=prompt))
        data = parse_llm_json(response.text)
        reply = data.get("reply")
        if not isinstance(reply, str):
            return None
        actions = sanitize_daily_review_actions(data.get("actions"), review_id)
        return reply, actions
    except (LLMProviderError, TypeError):
        return None


DAILY_REVIEW_DELETABLE_FIELDS = {"ai_notes", "ai_actions", "linked_evidence"}


@app.delete(
    "/api/v1/daily-reviews/{review_id}/sections/{section_key}/items/{field}/{index}",
    response_model=DailyReviewResponse,
)
async def delete_daily_review_section_item(
    review_id: int,
    section_key: str,
    field: str,
    index: int,
    db: DbSession,
) -> DailyReviewResponse:
    """Remove one saved AI-proposed item (ai_notes / ai_actions / linked_evidence)
    from a daily review section by its position in the list."""
    if field not in DAILY_REVIEW_DELETABLE_FIELDS:
        raise HTTPException(
            status_code=422,
            detail=f"field must be one of {sorted(DAILY_REVIEW_DELETABLE_FIELDS)}",
        )
    if index < 0:
        raise HTTPException(status_code=422, detail="index must be >= 0")
    review = get_daily_review_or_404(review_id, db)
    normalize_daily_review_content(review)
    section = review.content.get(section_key)
    if not isinstance(section, dict):
        raise HTTPException(status_code=404, detail=f"Unknown daily review section: {section_key}")
    items = section.get(field)
    if not isinstance(items, list):
        raise HTTPException(
            status_code=404,
            detail=f"Section {section_key} has no {field} list",
        )
    if index >= len(items):
        raise HTTPException(
            status_code=404,
            detail=f"{field}[{index}] does not exist (length={len(items)})",
        )
    next_items = list(items)
    next_items.pop(index)
    next_section = dict(section)
    next_section[field] = next_items
    next_content = dict(review.content)
    next_content[section_key] = next_section
    review.content = next_content
    review.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(review)
    normalize_daily_review_content(review)
    return DailyReviewResponse.model_validate(review)


@app.post("/api/v1/daily-reviews/{review_id}/ai/coach", response_model=DailyReviewCoachResponse)
async def coach_daily_review(
    review_id: int,
    request: DailyReviewCoachRequest,
    db: DbSession,
) -> DailyReviewCoachResponse:
    """Guide a user through one daily review section and return pending actions."""
    review = get_daily_review_or_404(review_id, db)
    context_items, evidence_cards = collect_daily_review_context(
        review, db, section_key=request.section_key
    )
    has_external_evidence = any(card.source_level in {"A", "B", "C"} for card in evidence_cards)
    prompt = build_daily_review_coach_prompt(
        review=review,
        message=request.message,
        section_key=request.section_key,
        context_items=context_items,
        evidence_cards=evidence_cards,
    )
    llm_result = await asyncio.to_thread(call_llm_daily_review_ai, prompt, review_id)
    if llm_result:
        reply, actions = llm_result
        if not actions:
            actions = build_local_daily_review_actions(
                request.message,
                review_id,
                request.section_key,
                has_external_evidence,
            )
    else:
        reply = build_local_daily_review_reply(has_external_evidence)
        actions = build_local_daily_review_actions(
            request.message,
            review_id,
            request.section_key,
            has_external_evidence,
        )
    return DailyReviewCoachResponse(reply=reply, actions=actions, evidence_cards=evidence_cards)


@app.post("/api/v1/daily-reviews/{review_id}/actions/apply", response_model=AiActionApplyResponse)
async def apply_daily_review_action(
    review_id: int,
    request: AiActionApplyRequest,
    db: DbSession,
) -> AiActionApplyResponse:
    """Apply a user-confirmed daily review action."""
    review = get_daily_review_or_404(review_id, db)
    payload = request.payload
    if request.type == "update_daily_review_section":
        section_key = payload.get("section_key")
        patch = payload.get("patch")
        if not isinstance(section_key, str) or not isinstance(patch, dict):
            raise HTTPException(status_code=422, detail="payload.section_key and payload.patch are required")
        normalize_daily_review_content(review)
        current_section = review.content.get(section_key)
        if not isinstance(current_section, dict):
            raise HTTPException(status_code=422, detail=f"Unknown daily review section: {section_key}")
        next_content = dict(review.content)
        next_content[section_key] = deep_merge_dict(current_section, patch)
        review.content = next_content
        review.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(review)
        normalize_daily_review_content(review)
        return AiActionApplyResponse(
            type=request.type,
            result=DailyReviewResponse.model_validate(review).model_dump(mode="json"),
        )

    if request.type == "create_daily_review_action":
        section_key = payload.get("section_key")
        content_text = payload.get("content")
        if not isinstance(section_key, str) or not isinstance(content_text, str):
            raise HTTPException(status_code=422, detail="payload.section_key and payload.content are required")
        normalize_daily_review_content(review)
        section = review.content.get(section_key)
        if not isinstance(section, dict):
            raise HTTPException(status_code=422, detail=f"Unknown daily review section: {section_key}")
        actions = section.get("ai_actions")
        if not isinstance(actions, list):
            actions = []
        actions.append(
            {
                "content": content_text,
                "source": payload.get("source") if isinstance(payload.get("source"), str) else SOURCE_AI,
                "created_at": datetime.utcnow().isoformat(),
            }
        )
        section["ai_actions"] = actions
        next_content = dict(review.content)
        next_content[section_key] = section
        review.content = next_content
        review.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(review)
        return AiActionApplyResponse(
            type=request.type,
            result=DailyReviewResponse.model_validate(review).model_dump(mode="json"),
        )

    if request.type == "link_evidence_to_daily_review":
        section_key = payload.get("section_key")
        evidence = payload.get("evidence")
        if not isinstance(section_key, str) or not isinstance(evidence, dict):
            raise HTTPException(status_code=422, detail="payload.section_key and payload.evidence are required")
        normalize_daily_review_content(review)
        section = review.content.get(section_key)
        if not isinstance(section, dict):
            raise HTTPException(status_code=422, detail=f"Unknown daily review section: {section_key}")
        linked = section.get("linked_evidence")
        if not isinstance(linked, list):
            linked = []
        linked.append(evidence)
        section["linked_evidence"] = linked
        next_content = dict(review.content)
        next_content[section_key] = section
        review.content = next_content
        review.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(review)
        return AiActionApplyResponse(
            type=request.type,
            result=DailyReviewResponse.model_validate(review).model_dump(mode="json"),
        )

    if request.type == "create_check_item":
        stock_code = payload.get("stock_code")
        if not isinstance(stock_code, str):
            raise HTTPException(status_code=422, detail="payload.stock_code is required")
        get_stock_or_404(stock_code, db)
        check_item = CheckItem(
            user_id="default",
            stock_code=stock_code,
            content=_string_payload(payload.get("content")),
            due_date=_parse_date(payload.get("due_date")),
            source_type=_string_payload(payload.get("source_type"), "daily_review_ai"),
            linked_hypothesis_id=payload.get("linked_hypothesis_id")
            if isinstance(payload.get("linked_hypothesis_id"), int)
            else None,
        )
        db.add(check_item)
        db.commit()
        db.refresh(check_item)
        return AiActionApplyResponse(
            type=request.type,
            result=CheckItemResponse.model_validate(check_item).model_dump(mode="json"),
        )

    if request.type == "create_review":
        stock_code = payload.get("stock_code")
        if not isinstance(stock_code, str):
            raise HTTPException(status_code=422, detail="payload.stock_code is required")
        get_stock_or_404(stock_code, db)
        stock_review = ReviewLog(
            user_id="default",
            stock_code=stock_code,
            review_type=_string_payload(payload.get("review_type"), "daily_review"),
            title=payload.get("title") if isinstance(payload.get("title"), str) else None,
            content=_string_payload(payload.get("content")),
            conclusions=payload.get("conclusions") if isinstance(payload.get("conclusions"), str) else None,
            action_items=payload.get("action_items") if isinstance(payload.get("action_items"), list) else [],
            trigger_event_id=payload.get("trigger_event_id")
            if isinstance(payload.get("trigger_event_id"), int)
            else None,
        )
        db.add(stock_review)
        db.commit()
        db.refresh(stock_review)
        return AiActionApplyResponse(
            type=request.type,
            result=ReviewResponse.model_validate(stock_review).model_dump(mode="json"),
        )

    raise HTTPException(status_code=422, detail=f"Unsupported daily review action type: {request.type}")



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


def _model_date(value: object) -> date:
    """Convert an ORM date-ish value into a stdlib date for type checkers and JSON text."""
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value))


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
    llm_result = await asyncio.to_thread(call_llm_ai, prompt, request.stock_code)
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
