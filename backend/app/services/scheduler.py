"""Optional daily refresh scheduler."""

from __future__ import annotations

import logging
import os
from importlib import import_module

from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import Stock
from app.services.data_refresh import DEFAULT_REFRESH_TYPES, build_data_refresh_service

logger = logging.getLogger(__name__)
_scheduler: object | None = None


def start_daily_refresh_scheduler() -> None:
    """Start the daily data refresh job only when explicitly enabled."""
    global _scheduler
    if os.environ.get("ENABLE_DAILY_REFRESH", "").lower() != "true":
        return
    if _scheduler is not None:
        return

    try:
        scheduler_module = import_module("apscheduler.schedulers.background")
        background_scheduler = scheduler_module.BackgroundScheduler
    except Exception as exc:
        logger.warning("APScheduler is unavailable, daily refresh disabled: %s", exc)
        return

    scheduler = background_scheduler(timezone="Asia/Shanghai")
    scheduler.add_job(refresh_all_watchlist_stocks, "cron", hour=18, minute=30, id="daily_data_refresh")
    scheduler.start()
    _scheduler = scheduler
    logger.info("Daily data refresh scheduler started.")


def refresh_all_watchlist_stocks() -> None:
    """Refresh all watched stocks; one failure must not stop the batch."""
    db: Session = SessionLocal()
    try:
        stocks = db.query(Stock).all()
        service = build_data_refresh_service()
        for stock in stocks:
            try:
                result = service.refresh_stock(db, stock.code, DEFAULT_REFRESH_TYPES, lookback_days=30)
                logger.info("Refreshed %s: created=%s skipped=%s errors=%s", stock.code, result.created, result.skipped, result.errors)
            except Exception:
                logger.exception("Daily refresh failed for %s", stock.code)
    finally:
        db.close()
