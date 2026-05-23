# 数据架构

## 核心原则

系统不是简单抓数据，而是建立可追溯的证据链：数据从哪里来、影响哪家公司、可能影响哪条投资假设、用户是否确认。

## 数据层次

1. `raw_sources`：保存外部来源的原始 payload、来源、抓取时间和 checksum。
2. `events`：标准化公告、新闻、政策、财报事件。
3. `quote_snapshots`：标准化行情和估值快照。
4. `fundamental_metrics`：标准化财务、估值、经营指标。
5. `impacts`：AI 对事件/指标影响假设的判断，默认待用户确认。
6. `hypotheses/check_items/review_logs`：用户确认后的研究资产。

## 证据等级

- A：法定公告/财报，高置信。
- B：行情/估值/基础指标，中高置信。
- C：新闻/媒体，线索性质。
- D：用户输入，主观观点。

## 去重策略

- `raw_sources.checksum`：基于 provider、类型、标题、发布时间、payload 生成。
- `events.fingerprint`：基于股票、provider、类型、标题、发布时间生成。
- `quote_snapshots`：按 `(stock_code, date)` 去重。
- `fundamental_metrics`：按 `stock_code + metric_code + period + source_provider` 去重。

## 写入边界

AI 只能写入 `impacts.user_confirmed=false` 的判断或返回 pending actions。假设状态、检查项、复盘记录必须由用户点击确认后写入。
