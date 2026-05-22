"""AKShare adapter for the first data-driven MVP."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from importlib import import_module
from typing import Any

from app.services.data_sources.base import (
    AdapterError,
    AdapterResult,
    DataSourceAdapter,
    EventRecord,
    MetricRecord,
    QuoteRecord,
    SourceRecord,
)


class AkshareAdapter(DataSourceAdapter):
    """Fetch A-share evidence from AKShare when the package is installed."""

    provider_name = "AKShare"

    def fetch(self, stock_code: str, data_types: set[str], lookback_days: int) -> AdapterResult:
        try:
            ak = import_module("akshare")
        except Exception as exc:
            return AdapterResult(
                errors=[
                    AdapterError(
                        provider=self.provider_name,
                        data_type="all",
                        message=f"AKShare is unavailable: {exc}",
                    )
                ]
            )

        raw_sources: list[SourceRecord] = []
        events: list[EventRecord] = []
        quotes: list[QuoteRecord] = []
        metrics: list[MetricRecord] = []
        errors: list[AdapterError] = []
        fetched_at = datetime.utcnow()

        if {"announcement", "news"} & data_types:
            event_result = self._fetch_events(ak, stock_code, data_types, lookback_days, fetched_at)
            raw_sources.extend(event_result.raw_sources)
            events.extend(event_result.events)
            errors.extend(event_result.errors)

        if "quote" in data_types:
            quote_result = self._fetch_quote(ak, stock_code, fetched_at)
            quotes.extend(quote_result.quotes)
            errors.extend(quote_result.errors)

        if "metric" in data_types:
            metric_result = self._fetch_metrics(ak, stock_code, fetched_at)
            metrics.extend(metric_result.metrics)
            errors.extend(metric_result.errors)

        return AdapterResult(
            raw_sources=raw_sources,
            events=events,
            quotes=quotes,
            metrics=metrics,
            errors=errors,
        )

    def _fetch_events(
        self,
        ak: Any,
        stock_code: str,
        data_types: set[str],
        lookback_days: int,
        fetched_at: datetime,
    ) -> AdapterResult:
        raw_sources: list[SourceRecord] = []
        events: list[EventRecord] = []
        errors: list[AdapterError] = []
        cutoff = fetched_at - timedelta(days=lookback_days)

        try:
            if "announcement" in data_types and hasattr(ak, "stock_notice_report"):
                df = ak.stock_notice_report(symbol=stock_code)
                for row in df.head(20).to_dict("records"):
                    raw, event = self._event_from_row(row, "announcement", fetched_at)
                    if event.published_at >= cutoff:
                        raw_sources.append(raw)
                        events.append(event)
        except Exception as exc:
            errors.append(AdapterError(self.provider_name, "announcement", str(exc)))

        try:
            if "news" in data_types and hasattr(ak, "stock_news_em"):
                df = ak.stock_news_em(symbol=stock_code)
                for row in df.head(20).to_dict("records"):
                    raw, event = self._event_from_row(row, "news", fetched_at)
                    if event.published_at >= cutoff:
                        raw_sources.append(raw)
                        events.append(event)
        except Exception as exc:
            errors.append(AdapterError(self.provider_name, "news", str(exc)))

        return AdapterResult(raw_sources=raw_sources, events=events, errors=errors)

    def _fetch_quote(self, ak: Any, stock_code: str, fetched_at: datetime) -> AdapterResult:
        try:
            end_date = fetched_at.strftime("%Y%m%d")
            start_date = (fetched_at - timedelta(days=10)).strftime("%Y%m%d")
            df = ak.stock_zh_a_hist(
                symbol=stock_code,
                period="daily",
                start_date=start_date,
                end_date=end_date,
                adjust="",
            )
            if df.empty:
                return AdapterResult()
            row = df.tail(1).to_dict("records")[0]
            quote = QuoteRecord(
                source_provider=self.provider_name,
                date=_parse_date(row.get("日期")) or fetched_at.date(),
                fetched_at=fetched_at,
                open_price=_to_float(row.get("开盘")),
                high=_to_float(row.get("最高")),
                low=_to_float(row.get("最低")),
                close=_to_float(row.get("收盘")),
                volume=_to_int(row.get("成交量")),
                amount=_to_float(row.get("成交额")),
                raw_payload=_clean_payload(row),
            )
            return AdapterResult(quotes=[quote])
        except Exception as exc:
            return AdapterResult(errors=[AdapterError(self.provider_name, "quote", str(exc))])

    def _fetch_metrics(self, ak: Any, stock_code: str, fetched_at: datetime) -> AdapterResult:
        metrics: list[MetricRecord] = []
        errors: list[AdapterError] = []

        try:
            if hasattr(ak, "stock_individual_info_em"):
                df = ak.stock_individual_info_em(symbol=stock_code)
                info = {str(row.get("item")): row.get("value") for row in df.to_dict("records")}
                for code, name, key, unit in [
                    ("total_market_cap", "总市值", "总市值", "元"),
                    ("float_market_cap", "流通市值", "流通市值", "元"),
                ]:
                    if key in info:
                        metrics.append(
                            MetricRecord(
                                source_provider=self.provider_name,
                                metric_code=code,
                                metric_name=name,
                                metric_category="valuation",
                                value=_to_float(info[key]),
                                unit=unit,
                                period=fetched_at.strftime("%Y-%m-%d"),
                                report_date=fetched_at.date(),
                                fetched_at=fetched_at,
                                raw_payload={key: info[key]},
                            )
                        )
        except Exception as exc:
            errors.append(AdapterError(self.provider_name, "metric", str(exc)))

        return AdapterResult(metrics=metrics, errors=errors)

    def _event_from_row(
        self,
        row: dict[str, Any],
        source_type: str,
        fetched_at: datetime,
    ) -> tuple[SourceRecord, EventRecord]:
        title = _first_text(row, ["公告标题", "标题", "title", "新闻标题"]) or "未命名事件"
        content = _first_text(row, ["内容", "摘要", "summary", "新闻内容"]) or title
        published_at = _parse_datetime(
            _first_text(row, ["公告日期", "发布时间", "日期", "time", "datetime"])
        ) or fetched_at
        source_url = _first_text(row, ["网址", "链接", "url", "公告链接"])
        confidence = 95 if source_type == "announcement" else 62
        raw_payload = _clean_payload(row)
        raw = SourceRecord(
            source_type=source_type,
            source_provider=self.provider_name,
            source_url=source_url,
            title=title,
            raw_content=content,
            raw_payload=raw_payload,
            published_at=published_at,
            fetched_at=fetched_at,
            confidence=confidence,
        )
        event = EventRecord(
            source_type=source_type,
            source_provider=self.provider_name,
            source_url=source_url,
            title=title,
            summary=content[:300],
            content=content,
            event_type=source_type,
            confidence=confidence,
            published_at=published_at,
            fetched_at=fetched_at,
        )
        return raw, event


def _first_text(row: dict[str, Any], keys: list[str]) -> str | None:
    for key in keys:
        value = row.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    return None


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    text = value.replace("/", "-").strip()
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%Y%m%d"):
        try:
            return datetime.strptime(text[: len(fmt)], fmt)
        except ValueError:
            continue
    return None


def _parse_date(value: object) -> date | None:
    parsed = _parse_datetime(str(value)) if value is not None else None
    return parsed.date() if parsed else None


def _to_float(value: object) -> float | None:
    try:
        if value is None or value == "":
            return None
        return float(str(value).replace(",", ""))
    except (TypeError, ValueError):
        return None


def _to_int(value: object) -> int | None:
    number = _to_float(value)
    return int(number) if number is not None else None


def _clean_payload(row: dict[str, Any]) -> dict[str, Any]:
    return {str(key): None if value != value else value for key, value in row.items()}
