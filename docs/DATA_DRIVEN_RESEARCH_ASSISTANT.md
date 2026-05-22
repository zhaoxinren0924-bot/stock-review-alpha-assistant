# 数据驱动 A 股基本面研究助手

## 当前阶段能力

系统已经从“AI 整理用户想法”升级为“证据驱动的复盘闭环”：

1. 用户维护关注股票、投资假设、检查项和复盘记录。
2. 用户可手动刷新当前股票的数据证据。
3. 系统将外部数据标准化为公告/新闻事件、行情快照、基础指标和证据卡。
4. AI 右栏基于证据卡和用户已有假设生成待保存成果。
5. 用户确认后，AI 成果才写入假设、检查项或复盘。
6. 可选每日自动刷新，默认关闭。

## 数据源分级策略

| 等级 | 来源类型 | 默认来源 | 用途 |
|---|---|---|---|
| A | 法定公告/财报 | AKShare/CNInfo 方向 | 高置信证据，优先用于判断假设增强或削弱 |
| B | 行情/估值/基础指标 | AKShare、BaoStock、可选 Tushare | 背景数据和趋势检查，不单独构成结论 |
| C | 新闻/媒体 | AKShare 东方财富类接口 | 只能作为线索，需要公告或指标交叉验证 |
| D | 用户输入 | 用户假设、复盘、检查项 | 高价值主观观点，但不是外部事实 |

免费数据源不保证交易级实时性；页面和 AI 回复必须明确证据边界。

## 数据流

```text
Provider Adapter
  -> SourceRecord / EventRecord / QuoteRecord / MetricRecord
  -> raw_sources
  -> events / quote_snapshots / fundamental_metrics
  -> evidence_cards
  -> AI impact analysis
  -> pending actions
  -> user-confirmed writes
```

关键规则：

- API 层不直接消费 pandas DataFrame。
- 原始 payload 进入 `raw_sources`，标准化数据进入业务表。
- `checksum` 和 `fingerprint` 用于去重。
- 单个数据源失败时返回 `errors`，不阻断其它数据源。
- AI 不自动改用户决策，只生成待确认 actions。

## API 契约

### 手动刷新

```http
POST /api/v1/stocks/{code}/data/refresh
```

Request:

```json
{
  "types": ["announcement", "news", "quote", "metric"],
  "lookback_days": 30
}
```

Response:

```json
{
  "stock_code": "300308",
  "created": {"events": 1, "quotes": 1},
  "skipped": {"events": 0},
  "errors": [],
  "refreshed_at": "2026-05-22T18:30:00"
}
```

### 证据查询

```http
GET /api/v1/stocks/{code}/evidence?limit=20
GET /api/v1/stocks/{code}/events?type=&limit=20
GET /api/v1/stocks/{code}/metrics?category=&limit=20
GET /api/v1/stocks/{code}/quotes?limit=20
```

所有列表接口返回 `{ "items": [...], "count": 0 }`。

### 事件影响分析

```http
POST /api/v1/stocks/{code}/events/{event_id}/analyze-impact
```

Response:

```json
{
  "reply": "...",
  "actions": [],
  "evidence_cards": [],
  "impacts": []
}
```

`impacts.user_confirmed` 默认是 `false`；用户确认 action 后才更新假设状态或创建复盘。

## 前端交互

主页面新增“数据证据”模块：

- “刷新数据”按钮触发当前股票数据采集。
- 三列展示最新公告/新闻、核心指标、行情/估值。
- 证据卡展示来源等级、来源、时间、摘要和证据边界。
- 点击证据卡会把证据上下文带入右侧 AI 输入框。

右侧 AI 复盘引导器：

- 显示本次回答使用的证据卡。
- 无外部证据时显示“当前证据不足”。
- 只展示待保存成果，不自动写入用户数据。

## 每日刷新

环境变量：

```env
ENABLE_DAILY_REFRESH=true
```

启用后，系统在 FastAPI 启动时注册 APScheduler 后台任务，每天 18:30 刷新关注股票的公告、新闻、行情和指标。

默认关闭，避免本地开发或免费数据源限制导致误触发。

## 验收 Checklist

后端：

- 手动刷新写入 `raw_sources/events/quote_snapshots/fundamental_metrics`。
- 重复刷新不会重复写入。
- 单个 provider 失败不影响其它 provider。
- evidence API 返回标准证据卡。
- 事件影响分析生成 `impacts` 和待确认 actions。
- 无证据时 AI 明确提示证据不足。

前端：

- 刷新数据按钮可点击，有 loading 状态。
- 刷新失败显示结构化错误。
- 证据卡显示 A/B/C/D 等级。
- 点击证据卡能进入右栏追问。
- 保存成果后主内容区刷新。

命令：

```powershell
backend\venv\Scripts\python.exe -m pytest
backend\venv\Scripts\python.exe -m ruff check backend\app backend\tests
backend\venv\Scripts\python.exe -m mypy backend\app backend\tests
cd frontend; npm run build
powershell -ExecutionPolicy Bypass -File scripts\check_ai_right_panel.ps1
```
