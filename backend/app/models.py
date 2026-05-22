"""SQLAlchemy models for the application."""

from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Stock(Base):
    """Tracked stocks."""

    __tablename__ = "stocks"

    code: Mapped[str] = mapped_column(String(8), primary_key=True)
    name: Mapped[str] = mapped_column(String(50), nullable=False)
    industry: Mapped[str | None] = mapped_column(String(50))
    market: Mapped[str | None] = mapped_column(String(10))
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow
    )

    positions: Mapped[list["Position"]] = relationship(
        "Position", back_populates="stock", cascade="all, delete-orphan"
    )
    cases: Mapped[list["InvestmentCase"]] = relationship(
        "InvestmentCase", back_populates="stock", cascade="all, delete-orphan"
    )


class RawSource(Base):
    """Raw external source payloads before business interpretation."""

    __tablename__ = "raw_sources"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_type: Mapped[str] = mapped_column(String(30), nullable=False)
    source_provider: Mapped[str] = mapped_column(String(50), nullable=False)
    source_url: Mapped[str | None] = mapped_column(String(1000))
    source_id: Mapped[str | None] = mapped_column(String(100))
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    raw_content: Mapped[str | None] = mapped_column(Text)
    raw_payload: Mapped[dict | None] = mapped_column(JSON)
    published_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    fetched_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    checksum: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Position(Base):
    """User's stock positions."""

    __tablename__ = "positions"
    __table_args__ = (UniqueConstraint("user_id", "stock_code"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[str] = mapped_column(
        String(50), nullable=False, default="default"
    )
    stock_code: Mapped[str] = mapped_column(
        String(8), ForeignKey("stocks.code"), nullable=False
    )
    cost_price: Mapped[float] = mapped_column(Float, nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    buy_date: Mapped[Date] = mapped_column(Date, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    stock: Mapped["Stock"] = relationship("Stock", back_populates="positions")


class InvestmentCase(Base):
    """Investment thesis for a stock."""

    __tablename__ = "investment_cases"
    __table_args__ = (UniqueConstraint("user_id", "stock_code"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[str] = mapped_column(
        String(50), nullable=False, default="default"
    )
    stock_code: Mapped[str] = mapped_column(
        String(8), ForeignKey("stocks.code"), nullable=False
    )
    summary: Mapped[str | None] = mapped_column(Text)
    confidence: Mapped[int] = mapped_column(Integer, default=3)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    stock: Mapped["Stock"] = relationship("Stock", back_populates="cases")
    hypotheses: Mapped[list["Hypothesis"]] = relationship(
        "Hypothesis", back_populates="case", cascade="all, delete-orphan"
    )


class Hypothesis(Base):
    """Specific investment hypothesis."""

    __tablename__ = "hypotheses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[str] = mapped_column(
        String(50), nullable=False, default="default"
    )
    case_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("investment_cases.id"), nullable=False
    )
    category: Mapped[str] = mapped_column(String(30), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="unverified")
    content: Mapped[dict] = mapped_column(JSON, nullable=False)
    confidence: Mapped[int] = mapped_column(Integer, default=80)
    evidence: Mapped[str | None] = mapped_column(Text)
    next_review_date: Mapped[Date | None] = mapped_column(Date)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    case: Mapped["InvestmentCase"] = relationship(
        "InvestmentCase", back_populates="hypotheses"
    )


class CheckItem(Base):
    """Actionable check items."""

    __tablename__ = "check_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[str] = mapped_column(
        String(50), nullable=False, default="default"
    )
    stock_code: Mapped[str] = mapped_column(
        String(8), ForeignKey("stocks.code"), nullable=False
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    due_date: Mapped[Date | None] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(20), default="pending")
    linked_hypothesis_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("hypotheses.id")
    )
    source_type: Mapped[str | None] = mapped_column(String(30))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow
    )


class Event(Base):
    """News/announcement events."""

    __tablename__ = "events"
    __table_args__ = (UniqueConstraint("fingerprint"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    raw_source_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("raw_sources.id")
    )
    stock_code: Mapped[str] = mapped_column(
        String(8), ForeignKey("stocks.code"), nullable=False
    )
    fingerprint: Mapped[str] = mapped_column(String(32), nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    content: Mapped[str | None] = mapped_column(Text)
    summary: Mapped[str | None] = mapped_column(Text)
    source: Mapped[str] = mapped_column(String(50), nullable=False)
    source_provider: Mapped[str | None] = mapped_column(String(50))
    source_url: Mapped[str | None] = mapped_column(String(1000))
    source_type: Mapped[str] = mapped_column(String(20), nullable=False)
    event_type: Mapped[str | None] = mapped_column(String(50))
    importance: Mapped[str | None] = mapped_column(String(20))
    sentiment: Mapped[str | None] = mapped_column(String(20))
    confidence: Mapped[int | None] = mapped_column(Integer)
    created_by: Mapped[str] = mapped_column(String(20), default="system")
    published_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow
    )
    quality_score: Mapped[float | None] = mapped_column(Float)
    quality_issues: Mapped[str | None] = mapped_column(Text)
    is_duplicate: Mapped[bool] = mapped_column(Boolean, default=False)
    master_event_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("events.id")
    )
    related_sources: Mapped[dict | None] = mapped_column(JSON)


class Impact(Base):
    """AI-generated impact assessment."""

    __tablename__ = "impacts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("events.id"), nullable=False
    )
    hypothesis_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("hypotheses.id")
    )
    metric_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("fundamental_metrics.id")
    )
    impact_direction: Mapped[str | None] = mapped_column(String(20))
    impact_strength: Mapped[int | None] = mapped_column(Integer)
    reason: Mapped[str | None] = mapped_column(Text)
    evidence_text: Mapped[str | None] = mapped_column(Text)
    confidence: Mapped[int | None] = mapped_column(Integer)
    generated_by: Mapped[str] = mapped_column(String(20), default="ai")
    user_confirmed: Mapped[bool] = mapped_column(Boolean, default=False)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime)
    ai_direction: Mapped[str | None] = mapped_column(String(20))
    ai_confidence: Mapped[float | None] = mapped_column(Float)
    ai_reasoning: Mapped[str | None] = mapped_column(Text)
    ai_judgment_at: Mapped[datetime | None] = mapped_column(DateTime)
    user_correction: Mapped[str | None] = mapped_column(String(20))
    user_confidence: Mapped[float | None] = mapped_column(Float)
    user_reasoning: Mapped[str | None] = mapped_column(Text)
    corrected_at: Mapped[datetime | None] = mapped_column(DateTime)
    user_feedback: Mapped[str | None] = mapped_column(String(20))
    feedback_at: Mapped[datetime | None] = mapped_column(DateTime)


class ReviewLog(Base):
    """Review records."""

    __tablename__ = "review_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[str] = mapped_column(
        String(50), nullable=False, default="default"
    )
    stock_code: Mapped[str] = mapped_column(
        String(8), ForeignKey("stocks.code"), nullable=False
    )
    review_type: Mapped[str | None] = mapped_column(String(30))
    title: Mapped[str | None] = mapped_column(String(100))
    trigger_event_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("events.id")
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    conclusions: Mapped[str | None] = mapped_column(Text)
    action_items: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow
    )


class UserRule(Base):
    """Personal investment rules."""

    __tablename__ = "user_rules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[str] = mapped_column(
        String(50), nullable=False, default="default"
    )
    rule_text: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str | None] = mapped_column(String(30))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    violation_count: Mapped[int] = mapped_column(Integer, default=0)
    last_violated_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow
    )


class ErrorPattern(Base):
    """Error pattern statistics."""

    __tablename__ = "error_patterns"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    pattern_name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    occurrence_count: Mapped[int] = mapped_column(Integer, default=0)
    last_occurred: Mapped[Date | None] = mapped_column(Date)
    associated_rules: Mapped[dict | None] = mapped_column(JSON)


class QuoteSnapshot(Base):
    """Daily quote snapshots."""

    __tablename__ = "quote_snapshots"
    __table_args__ = (UniqueConstraint("stock_code", "date"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    stock_code: Mapped[str] = mapped_column(
        String(8), ForeignKey("stocks.code"), nullable=False
    )
    date: Mapped[Date] = mapped_column(Date, nullable=False)
    open_price: Mapped[float | None] = mapped_column("open", Float)
    high: Mapped[float | None] = mapped_column(Float)
    low: Mapped[float | None] = mapped_column(Float)
    close: Mapped[float | None] = mapped_column(Float)
    volume: Mapped[int | None] = mapped_column(Integer)
    amount: Mapped[float | None] = mapped_column(Float)
    pe: Mapped[float | None] = mapped_column(Float)
    pb: Mapped[float | None] = mapped_column(Float)
    market_cap: Mapped[float | None] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow
    )


class FundamentalMetric(Base):
    """Normalized fundamental metrics used by theme and industry templates."""

    __tablename__ = "fundamental_metrics"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    stock_code: Mapped[str] = mapped_column(
        String(8), ForeignKey("stocks.code"), nullable=False
    )
    metric_code: Mapped[str] = mapped_column(String(50), nullable=False)
    metric_name: Mapped[str] = mapped_column(String(100), nullable=False)
    metric_category: Mapped[str | None] = mapped_column(String(30))
    value: Mapped[float | None] = mapped_column(Float)
    unit: Mapped[str | None] = mapped_column(String(20))
    period: Mapped[str | None] = mapped_column(String(20))
    report_date: Mapped[Date | None] = mapped_column(Date)
    source_provider: Mapped[str | None] = mapped_column(String(50))
    raw_source_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("raw_sources.id")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
