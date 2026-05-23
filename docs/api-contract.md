# API Contract — A 股基本面复盘助手

## 通用约定

- 后端字段：`snake_case`
- 前端字段：`camelCase`
- API URL：`kebab-case`
- 成功响应直接返回资源对象或 `{ "items": [], "count": 0 }`
- 错误响应：`{ "detail": "..." }`

## Stock

```http
GET    /api/v1/stocks
POST   /api/v1/stocks
GET    /api/v1/stocks/{code}
DELETE /api/v1/stocks/{code}
```

## Research Loop

```http
GET    /api/v1/stocks/{code}/hypotheses
POST   /api/v1/stocks/{code}/hypotheses
PUT    /api/v1/hypotheses/{id}
DELETE /api/v1/hypotheses/{id}

GET    /api/v1/stocks/{code}/check-items
POST   /api/v1/stocks/{code}/check-items
PUT    /api/v1/check-items/{id}
DELETE /api/v1/check-items/{id}

GET    /api/v1/stocks/{code}/reviews
POST   /api/v1/stocks/{code}/reviews
PUT    /api/v1/reviews/{id}
DELETE /api/v1/reviews/{id}
```

## Data Refresh

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
  "created": {"events": 1},
  "skipped": {"events": 0},
  "errors": [],
  "refreshed_at": "2026-05-22T18:30:00"
}
```

## Evidence

```http
GET /api/v1/stocks/{code}/evidence?limit=20
GET /api/v1/stocks/{code}/events?type=&limit=20
GET /api/v1/stocks/{code}/metrics?category=&limit=20
GET /api/v1/stocks/{code}/quotes?limit=20
```

Evidence card:

```json
{
  "source_level": "A",
  "source_type": "announcement",
  "source_provider": "CNInfo",
  "source_url": "https://...",
  "title": "公告标题",
  "summary": "摘要",
  "published_at": "2026-05-22T09:00:00",
  "fetched_at": "2026-05-22T18:30:00",
  "confidence": 95,
  "evidence_boundary": "高置信法定披露，可优先用于增强或削弱投资假设。"
}
```

## AI

```http
POST /api/v1/ai/chat
POST /api/v1/ai/actions/apply
POST /api/v1/stocks/{code}/events/{event_id}/analyze-impact
```

`ai/chat` 响应：

```json
{
  "reply": "...",
  "actions": [],
  "evidence_cards": []
}
```

允许的 actions：

- `create_hypothesis`
- `create_check_item`
- `create_review`
- `update_hypothesis_status`

AI 不能直接替用户做投资决策；所有 actions 必须由用户确认后应用。
