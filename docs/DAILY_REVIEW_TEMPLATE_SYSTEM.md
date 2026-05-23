# 结构化每日复盘系统

## 目标

每日复盘不是一篇自由笔记，而是一个固定工作流：先判断市场风格，再观察热点、资金、自选股和基本面证据，最后沉淀明日观察计划。AI 的角色是复盘教练，帮助用户追问和整理，不替代用户做决策。

## 与股票复盘的关系

- `ReviewLog`：单只股票的事件复盘、季度复盘、检查项沉淀。
- `DailyReview`：市场级每日复盘，覆盖指数、热点、资金、自选股、基本面和明日计划。
- AI 生成的内容都是待保存成果，必须用户确认后才写入。

## DailyReview v1 Schema

`daily_reviews.content` 是 JSON，顶层固定为 8 个 section：

- `index_review`：指数表现、领涨指数、市场风格、外部影响。
- `hotspot_review`：涨停家数、跌停家数、连板高度、炸板率、主线板块。
- `capital_review`：成交额榜单、资金扎堆方向。
- `limit_review`：跌幅榜排雷、涨停榜机会、共性总结。
- `watchlist_review`：关注股票池、重点标的、技术形态、基本面变化。
- `fundamental_review`：宏观、行业、公司公告新闻、财务风险、估值位置。
- `tomorrow_plan`：市场判断、仓位计划、关注板块、触发条件、今日教训。
- `weekly_review`：周末系统复盘，周末默认启用。

每个可判断字段使用统一来源标记：

- `manual`：需要用户手动填写。
- `data_prefilled`：来自系统已有数据。
- `ai_generated`：AI 根据用户输入和证据整理。
- `insufficient_evidence`：当前证据不足。

## 数据预填边界

预填分两路：

**本地数据(始终启用)**

- 自选股列表来自 `stocks`。
- 公告/新闻来自 `events/evidence`。
- 指标/估值来自 `fundamental_metrics/quote_snapshots`。
- 基本面变化来自近期证据卡。

**市场全量数据(由 `DailyMarketPrefillService` 通过 AKShare 抓取)**

- 指数：上证、深证成指、创业板指、科创 50、中证 2000(境外指数仍 missing)。
- 热点：涨停池、跌停池、炸板池、概念板块涨停家数、连板高度、炸板率。
- 资金：东方财富板块资金流前 10。
- 涨跌停：跌停股池前 10(排雷)与涨停股池前 10(找共性)，含驱动原因。

AKShare 不可用或单个接口失败时，对应字段写 `insufficient_evidence`，并在响应的 `missing` 与 `errors` 中明示来源。免费数据源只用于研究复盘，不保证交易级实时性。需要 AI 自由发挥的字段(主线判断、持续性、主力意图、共性总结)仍保留 `manual`，等用户或 AI 确认后才填。

## API

```text
GET    /api/v1/daily-reviews?date_from=&date_to=
GET    /api/v1/daily-reviews/{date}
POST   /api/v1/daily-reviews/{date}/initialize
PUT    /api/v1/daily-reviews/{id}
POST   /api/v1/daily-reviews/{id}/prefill
POST   /api/v1/daily-reviews/{id}/ai/coach
POST   /api/v1/daily-reviews/{id}/actions/apply
```

## AI 边界

AI 必须：

- 说明证据边界。
- 在证据不足时明确提示“当前证据不足”。
- 返回 `reply + evidence_cards + actions`。
- 只生成待保存成果。

AI 禁止：

- 荐股。
- 预测短线涨跌。
- 编造未提供的数据、公告、新闻或财务指标。
- 直接写库。

## 验收 Checklist

- 初始化当天复盘能生成完整 8 section 模板。
- 重复初始化不会重复创建。
- 数据预填能生成自选股和公司基本面行。
- 缺失的全市场数据明确显示“当前证据不足”。
- AI 教练能围绕当前 section 生成待保存成果。
- 用户确认后，DailyReview JSON 才会更新。
- 公司研究页、股票假设、检查项、复盘 API 不受影响。
