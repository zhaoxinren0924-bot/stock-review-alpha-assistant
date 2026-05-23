"""Market-level prefill for the structured daily review template."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from importlib import import_module
from typing import Any


@dataclass
class MarketPrefillResult:
    """Market-level section patch and source errors."""

    content_patch: dict[str, object] = field(default_factory=dict)
    filled: dict[str, int] = field(default_factory=dict)
    missing: list[str] = field(default_factory=list)
    errors: list[dict[str, str]] = field(default_factory=list)


class DailyMarketPrefillService:
    """Fetch market-wide data used by daily review sections 1-4."""

    provider_name = "AKShare"

    def prefill(self, review_date: date) -> MarketPrefillResult:
        """Build a patch for index, hotspot, capital and limit-review sections."""
        try:
            ak = import_module("akshare")
        except Exception as exc:
            return MarketPrefillResult(
                missing=["指数复盘", "热点复盘", "资金复盘", "涨跌停复盘"],
                errors=[{"provider": self.provider_name, "type": "all", "message": str(exc)}],
            )

        result = MarketPrefillResult()
        date_text = review_date.strftime("%Y%m%d")

        index_patch, index_count, index_missing, index_errors = self._build_index_review(ak, review_date)
        hotspot_patch, hotspot_count, hotspot_missing, hotspot_errors = self._build_hotspot_review(ak, date_text)
        capital_patch, capital_count, capital_missing, capital_errors = self._build_capital_review(ak)
        limit_patch, limit_count, limit_missing, limit_errors = self._build_limit_review(ak, date_text)

        result.content_patch = {
            "index_review": index_patch,
            "hotspot_review": hotspot_patch,
            "capital_review": capital_patch,
            "limit_review": limit_patch,
        }
        result.filled = {
            "index_rows": index_count,
            "hotspot_rows": hotspot_count,
            "capital_rows": capital_count,
            "limit_rows": limit_count,
        }
        result.missing = index_missing + hotspot_missing + capital_missing + limit_missing
        result.errors = index_errors + hotspot_errors + capital_errors + limit_errors
        return result

    def _build_index_review(
        self,
        ak: Any,
        review_date: date,
    ) -> tuple[dict[str, object], int, list[str], list[dict[str, str]]]:
        indices = [
            ("上证指数", "000001"),
            ("深证成指", "399001"),
            ("创业板指", "399006"),
            ("科创50", "000688"),
            ("中证2000", "932000"),
        ]
        rows: list[dict[str, object]] = []
        missing = ["恒生指数", "纳斯达克", "标普500"]
        errors: list[dict[str, str]] = []
        start_date = (review_date - timedelta(days=12)).strftime("%Y%m%d")
        end_date = review_date.strftime("%Y%m%d")

        for name, symbol in indices:
            try:
                df = ak.index_zh_a_hist(symbol=symbol, period="daily", start_date=start_date, end_date=end_date)
                records = _records(df)
                if not records:
                    rows.append(_index_row(name, "", "", "暂无数据", "insufficient_evidence"))
                    missing.append(name)
                    continue
                row = records[-1]
                rows.append(
                    _index_row(
                        name,
                        _fmt_percent(_first_value(row, ["涨跌幅", "change_pct"])),
                        _fmt_amount(_first_value(row, ["成交额", "amount"])),
                        f"收盘 {(_first_value(row, ['收盘', 'close']) or '暂无')}",
                        "data_prefilled",
                    )
                )
            except Exception as exc:
                errors.append({"provider": self.provider_name, "type": f"index:{name}", "message": str(exc)})
                rows.append(_index_row(name, "", "", "接口失败", "insufficient_evidence"))
                missing.append(name)

        leading = ""
        scored = [
            (row["name"], _to_float(_field_value(row["change_pct"])))
            for row in rows
            if _to_float(_field_value(row["change_pct"])) is not None
        ]
        if scored:
            leading = str(max(scored, key=lambda item: item[1] or -999)[0])

        return (
            {
                "indices": rows,
                "leading_index": _field(leading, "data_prefilled" if leading else "insufficient_evidence"),
                "market_style": _field("", "manual", "需要结合指数、板块和用户观察确认。"),
                "external_impact": _field("", "insufficient_evidence", "境外指数第一版暂不自动采集。"),
            },
            len([row for row in rows if _field_source(row["change_pct"]) == "data_prefilled"]),
            missing,
            errors,
        )

    def _build_hotspot_review(
        self,
        ak: Any,
        date_text: str,
    ) -> tuple[dict[str, object], int, list[str], list[dict[str, str]]]:
        errors: list[dict[str, str]] = []
        missing: list[str] = []
        zt_rows = self._safe_records(ak, "stock_zt_pool_em", {"date": date_text}, "limit_up", errors)
        dt_rows = self._safe_records(ak, "stock_zt_pool_dtgc_em", {"date": date_text}, "limit_down", errors)
        zbgc_rows = self._safe_records(ak, "stock_zt_pool_zbgc_em", {"date": date_text}, "failed_board", errors)

        sectors = self._safe_records(ak, "stock_board_concept_name_em", {}, "concept_board", errors)
        main_sectors: list[dict[str, object]] = []
        for row in sectors[:8]:
            main_sectors.append(
                {
                    "sector": _field(_first_value(row, ["板块名称", "名称", "name"]) or ""),
                    "limit_up_count": _field(_first_value(row, ["涨停家数", "涨停数"]) or "", "data_prefilled"),
                    "leader": _field(_first_value(row, ["领涨股票", "龙头股"]) or "", "data_prefilled"),
                    "driver": _field("", "manual", "驱动逻辑需要结合公告、新闻或用户观察。"),
                    "sustainability": _field("", "manual", "持续性判断需要用户确认。"),
                    "change_pct": _field(_fmt_percent(_first_value(row, ["涨跌幅", "涨幅"])), "data_prefilled"),
                }
            )

        if not zt_rows:
            missing.append("涨停家数")
        if not dt_rows:
            missing.append("跌停家数")
        if not zbgc_rows:
            missing.append("炸板率")
        if not main_sectors:
            missing.append("主线板块")

        failed_rate = ""
        if zt_rows or zbgc_rows:
            denominator = len(zt_rows) + len(zbgc_rows)
            failed_rate = f"{len(zbgc_rows) / denominator * 100:.1f}%" if denominator else ""

        streak_height = _max_number(zt_rows, ["连板数", "连续涨停", "几天几板"])
        return (
            {
                "sentiment_metrics": {
                    "limit_up_count": _field(len(zt_rows), "data_prefilled" if zt_rows else "insufficient_evidence"),
                    "limit_down_count": _field(len(dt_rows), "data_prefilled" if dt_rows else "insufficient_evidence"),
                    "streak_height": _field(streak_height or "", "data_prefilled" if streak_height else "insufficient_evidence"),
                    "failed_board_rate": _field(failed_rate, "data_prefilled" if failed_rate else "insufficient_evidence"),
                },
                "main_sectors": main_sectors,
                "summary": _field("", "manual", "主线判断由用户结合涨停扩散、资金和消息面确认。"),
            },
            len(main_sectors) + len(zt_rows) + len(dt_rows) + len(zbgc_rows),
            missing,
            errors,
        )

    def _build_capital_review(self, ak: Any) -> tuple[dict[str, object], int, list[str], list[dict[str, str]]]:
        errors: list[dict[str, str]] = []
        rows = self._safe_records(
            ak,
            "stock_sector_fund_flow_rank",
            {"indicator": "今日", "sector_type": "概念资金流"},
            "sector_fund_flow",
            errors,
        )
        leaders: list[dict[str, object]] = []
        for row in rows[:10]:
            leaders.append(
                {
                    "target": _field(_first_value(row, ["名称", "板块名称", "name"]) or ""),
                    "amount": _field(_fmt_amount(_first_value(row, ["今日主力净流入-净额", "主力净流入", "净额"]))),
                    "sector": _field(_first_value(row, ["类型", "板块"]) or "概念资金流"),
                    "intent": _field("", "manual", "主力意图猜测需要用户确认，系统不自动下结论。"),
                }
            )

        missing = [] if leaders else ["板块资金流"]
        return (
            {
                "turnover_leaders": leaders,
                "capital_direction": _field(
                    "；".join(str(_field_value(item["target"])) for item in leaders[:3]),
                    "data_prefilled" if leaders else "insufficient_evidence",
                    "来自东方财富板块资金流排名，仅作为线索。",
                ),
            },
            len(leaders),
            missing,
            errors,
        )

    def _build_limit_review(
        self,
        ak: Any,
        date_text: str,
    ) -> tuple[dict[str, object], int, list[str], list[dict[str, str]]]:
        errors: list[dict[str, str]] = []
        zt_rows = self._safe_records(ak, "stock_zt_pool_em", {"date": date_text}, "limit_up", errors)
        dt_rows = self._safe_records(ak, "stock_zt_pool_dtgc_em", {"date": date_text}, "limit_down", errors)

        risk_rows = [
            {
                "stock": _field(_first_value(row, ["名称", "股票简称", "name"]) or ""),
                "change_pct": _field(_fmt_percent(_first_value(row, ["涨跌幅", "跌幅"]))),
                "sector": _field(_first_value(row, ["所属行业", "所属概念", "行业"]) or ""),
                "reason": _field(_first_value(row, ["跌停原因", "原因"]) or "", "data_prefilled"),
                "similar_risk": _field("", "manual"),
            }
            for row in dt_rows[:10]
        ]
        opportunity_rows = [
            {
                "stock": _field(_first_value(row, ["名称", "股票简称", "name"]) or ""),
                "streak": _field(_first_value(row, ["连板数", "连续涨停", "几天几板"]) or ""),
                "sector": _field(_first_value(row, ["所属行业", "所属概念", "行业"]) or ""),
                "driver": _field(_first_value(row, ["涨停原因类别", "涨停原因", "原因"]) or "", "data_prefilled"),
                "leader_effect": _field("", "manual", "是否由龙头带动需要用户确认。"),
            }
            for row in zt_rows[:10]
        ]

        missing = []
        if not risk_rows:
            missing.append("跌停股池")
        if not opportunity_rows:
            missing.append("涨停股池")

        return (
            {
                "risk_rows": risk_rows,
                "opportunity_rows": opportunity_rows,
                "common_summary": _field("", "manual", "共性总结由用户复盘确认。"),
            },
            len(risk_rows) + len(opportunity_rows),
            missing,
            errors,
        )

    def _safe_records(
        self,
        ak: Any,
        func_name: str,
        kwargs: dict[str, object],
        data_type: str,
        errors: list[dict[str, str]],
    ) -> list[dict[str, Any]]:
        if not hasattr(ak, func_name):
            errors.append({"provider": self.provider_name, "type": data_type, "message": f"{func_name} unavailable"})
            return []
        try:
            return _records(getattr(ak, func_name)(**kwargs))
        except Exception as exc:
            errors.append({"provider": self.provider_name, "type": data_type, "message": str(exc)})
            return []


def build_daily_market_prefill_service() -> DailyMarketPrefillService:
    """Factory kept separate so tests can monkeypatch market prefill behavior."""
    return DailyMarketPrefillService()


def _field(value: object = "", source: str = "data_prefilled", note: str = "") -> dict[str, object]:
    return {"value": value, "source": source, "note": note}


def _field_value(field: object) -> object:
    if isinstance(field, dict):
        return field.get("value")
    return field


def _field_source(field: object) -> str:
    if isinstance(field, dict):
        source = field.get("source")
        return str(source) if source is not None else ""
    return ""


def _index_row(name: str, change_pct: str, turnover: str, note: str, source: str) -> dict[str, object]:
    return {
        "name": name,
        "change_pct": _field(change_pct, source),
        "turnover": _field(turnover, source),
        "note": _field(note, source),
    }


def _records(df: object) -> list[dict[str, Any]]:
    if df is None or getattr(df, "empty", True):
        return []
    return getattr(df, "to_dict")("records")


def _first_value(row: dict[str, Any], keys: list[str]) -> object | None:
    normalized = {str(key).strip(): value for key, value in row.items()}
    for key in keys:
        if key in normalized and normalized[key] not in (None, ""):
            return normalized[key]
    for key, value in normalized.items():
        if any(candidate in key for candidate in keys) and value not in (None, ""):
            return value
    return None


def _to_float(value: object) -> float | None:
    try:
        if value is None or value == "":
            return None
        text = str(value).replace(",", "").replace("%", "").strip()
        return float(text)
    except (TypeError, ValueError):
        return None


def _max_number(rows: list[dict[str, Any]], keys: list[str]) -> int | None:
    values = [_to_float(_first_value(row, keys)) for row in rows]
    numbers = [int(value) for value in values if value is not None]
    return max(numbers) if numbers else None


def _fmt_percent(value: object) -> str:
    number = _to_float(value)
    if number is None:
        return str(value) if value not in (None, "") else ""
    return f"{number:.2f}%"


def _fmt_amount(value: object) -> str:
    number = _to_float(value)
    if number is None:
        return str(value) if value not in (None, "") else ""
    if abs(number) >= 100_000_000:
        return f"{number / 100_000_000:.2f}亿"
    if abs(number) >= 10_000:
        return f"{number / 10_000:.2f}万"
    return f"{number:.2f}"
