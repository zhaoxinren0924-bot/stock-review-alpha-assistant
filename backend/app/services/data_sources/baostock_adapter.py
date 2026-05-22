"""BaoStock adapter for quote and financial metric fallback data."""

from __future__ import annotations

from datetime import datetime, timedelta
from importlib import import_module

from app.services.data_sources.base import (
    AdapterError,
    AdapterResult,
    DataSourceAdapter,
    MetricRecord,
    QuoteRecord,
)


class BaoStockAdapter(DataSourceAdapter):
    """Fetch daily quotes and simple finance metrics from BaoStock."""

    provider_name = "BaoStock"

    def fetch(self, stock_code: str, data_types: set[str], lookback_days: int) -> AdapterResult:
        try:
            bs = import_module("baostock")
        except Exception as exc:
            return AdapterResult(
                errors=[
                    AdapterError(
                        provider=self.provider_name,
                        data_type="all",
                        message=f"BaoStock is unavailable: {exc}",
                    )
                ]
            )

        errors: list[AdapterError] = []
        quotes: list[QuoteRecord] = []
        metrics: list[MetricRecord] = []
        fetched_at = datetime.utcnow()
        bs_code = _to_baostock_code(stock_code)

        login_result = bs.login()
        if getattr(login_result, "error_code", "0") != "0":
            return AdapterResult(
                errors=[AdapterError(self.provider_name, "all", getattr(login_result, "error_msg", "login failed"))]
            )

        try:
            if "quote" in data_types:
                quotes.extend(self._fetch_quotes(bs, bs_code, lookback_days, fetched_at))
            if "metric" in data_types:
                metrics.extend(self._fetch_metrics(bs, bs_code, fetched_at))
        except Exception as exc:
            errors.append(AdapterError(self.provider_name, "all", str(exc)))
        finally:
            bs.logout()

        return AdapterResult(quotes=quotes, metrics=metrics, errors=errors)

    def _fetch_quotes(
        self,
        bs: object,
        bs_code: str,
        lookback_days: int,
        fetched_at: datetime,
    ) -> list[QuoteRecord]:
        start_date = (fetched_at - timedelta(days=max(lookback_days, 10))).strftime("%Y-%m-%d")
        end_date = fetched_at.strftime("%Y-%m-%d")
        rs = bs.query_history_k_data_plus(  # type: ignore[attr-defined]
            bs_code,
            "date,open,high,low,close,volume,amount,peTTM,pbMRQ",
            start_date=start_date,
            end_date=end_date,
            frequency="d",
            adjustflag="3",
        )
        rows: list[dict[str, str]] = []
        while rs.error_code == "0" and rs.next():
            rows.append(dict(zip(rs.fields, rs.get_row_data(), strict=False)))
        if not rows:
            return []
        row = rows[-1]
        quote_date = datetime.strptime(row["date"], "%Y-%m-%d").date()
        return [
            QuoteRecord(
                source_provider=self.provider_name,
                date=quote_date,
                fetched_at=fetched_at,
                open_price=_to_float(row.get("open")),
                high=_to_float(row.get("high")),
                low=_to_float(row.get("low")),
                close=_to_float(row.get("close")),
                volume=_to_int(row.get("volume")),
                amount=_to_float(row.get("amount")),
                pe=_to_float(row.get("peTTM")),
                pb=_to_float(row.get("pbMRQ")),
                raw_payload=row,
            )
        ]

    def _fetch_metrics(self, bs: object, bs_code: str, fetched_at: datetime) -> list[MetricRecord]:
        rs = bs.query_profit_data(code=bs_code, year=fetched_at.year, quarter=max((fetched_at.month - 1) // 3, 1))  # type: ignore[attr-defined]
        rows: list[dict[str, str]] = []
        while rs.error_code == "0" and rs.next():
            rows.append(dict(zip(rs.fields, rs.get_row_data(), strict=False)))
        if not rows:
            return []
        row = rows[-1]
        report_date = fetched_at.date()
        metric_map = [
            ("roe_avg", "平均净资产收益率", "roeAvg", "%"),
            ("np_margin", "销售净利率", "npMargin", "%"),
            ("gp_margin", "销售毛利率", "gpMargin", "%"),
        ]
        metrics: list[MetricRecord] = []
        for code, name, key, unit in metric_map:
            metrics.append(
                MetricRecord(
                    source_provider=self.provider_name,
                    metric_code=code,
                    metric_name=name,
                    metric_category="financial_quality",
                    value=_to_float(row.get(key)),
                    unit=unit,
                    period=f"{fetched_at.year}Q{max((fetched_at.month - 1) // 3, 1)}",
                    report_date=report_date,
                    fetched_at=fetched_at,
                    raw_payload={key: row.get(key)},
                )
            )
        return metrics


def _to_baostock_code(stock_code: str) -> str:
    if stock_code.startswith("6"):
        return f"sh.{stock_code}"
    return f"sz.{stock_code}"


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
