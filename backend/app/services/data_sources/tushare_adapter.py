"""Optional Tushare adapter, enabled only when TUSHARE_TOKEN is configured."""

from __future__ import annotations

import os
from datetime import datetime, timedelta
from importlib import import_module

from app.services.data_sources.base import (
    AdapterError,
    AdapterResult,
    DataSourceAdapter,
    MetricRecord,
    QuoteRecord,
)


class TushareAdapter(DataSourceAdapter):
    """Fetch Tushare Pro daily basic data when the user has a token."""

    provider_name = "Tushare"

    def fetch(self, stock_code: str, data_types: set[str], lookback_days: int) -> AdapterResult:
        token = os.environ.get("TUSHARE_TOKEN")
        if not token:
            return AdapterResult()

        try:
            ts = import_module("tushare")
        except Exception as exc:
            return AdapterResult(errors=[AdapterError(self.provider_name, "all", f"Tushare is unavailable: {exc}")])

        if not {"quote", "metric"} & data_types:
            return AdapterResult()

        fetched_at = datetime.utcnow()
        ts_code = _to_tushare_code(stock_code)
        start_date = (fetched_at - timedelta(days=max(lookback_days, 10))).strftime("%Y%m%d")
        end_date = fetched_at.strftime("%Y%m%d")

        try:
            pro = ts.pro_api(token)
            df = pro.daily_basic(ts_code=ts_code, start_date=start_date, end_date=end_date)
            if df.empty:
                return AdapterResult()
            row = df.sort_values("trade_date").tail(1).to_dict("records")[0]
            quote_date = datetime.strptime(str(row["trade_date"]), "%Y%m%d").date()
            quote = QuoteRecord(
                source_provider=self.provider_name,
                date=quote_date,
                fetched_at=fetched_at,
                close=_to_float(row.get("close")),
                pe=_to_float(row.get("pe")),
                pb=_to_float(row.get("pb")),
                market_cap=_to_float(row.get("total_mv")),
                raw_payload={str(key): value for key, value in row.items()},
            )
            metrics = [
                MetricRecord(
                    source_provider=self.provider_name,
                    metric_code="pe_ttm",
                    metric_name="市盈率",
                    metric_category="valuation",
                    value=_to_float(row.get("pe_ttm") or row.get("pe")),
                    unit="倍",
                    period=quote_date.isoformat(),
                    report_date=quote_date,
                    fetched_at=fetched_at,
                    raw_payload={"pe_ttm": row.get("pe_ttm"), "pe": row.get("pe")},
                ),
                MetricRecord(
                    source_provider=self.provider_name,
                    metric_code="pb",
                    metric_name="市净率",
                    metric_category="valuation",
                    value=_to_float(row.get("pb")),
                    unit="倍",
                    period=quote_date.isoformat(),
                    report_date=quote_date,
                    fetched_at=fetched_at,
                    raw_payload={"pb": row.get("pb")},
                ),
            ]
            return AdapterResult(quotes=[quote], metrics=metrics)
        except Exception as exc:
            return AdapterResult(errors=[AdapterError(self.provider_name, "daily_basic", str(exc))])


def _to_tushare_code(stock_code: str) -> str:
    if stock_code.startswith("6"):
        return f"{stock_code}.SH"
    if stock_code.startswith(("8", "4")):
        return f"{stock_code}.BJ"
    return f"{stock_code}.SZ"


def _to_float(value: object) -> float | None:
    try:
        if value is None or value == "":
            return None
        return float(str(value).replace(",", ""))
    except (TypeError, ValueError):
        return None
