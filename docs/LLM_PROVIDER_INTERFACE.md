# 通用模型接口

系统的 AI 层通过统一 provider 接口接入模型，业务代码不直接依赖 Claude、Kimi 或 Minimax。

## 统一接口

后端统一使用：

- `LLMRequest`
  - `prompt`
  - `response_format`
  - `temperature`
  - `max_tokens`
- `LLMResponse`
  - `text`
  - `provider`
  - `model`

业务层只关心模型返回的 JSON 文本：

```json
{
  "reply": "给用户看的回复",
  "actions": []
}
```

## Provider 选择

通过环境变量选择：

```env
LLM_PROVIDER=anthropic
```

支持值：

- `anthropic` 或 `claude`
- `kimi` 或 `moonshot`
- `minimax`
- `openai_compatible`

如果未配置 key 或调用失败，系统自动降级为本地规则 fallback。

本地检查：

```http
GET /api/v1/ai/provider-status
```

只返回非敏感状态：

```json
{
  "provider": "minimax",
  "configured": true
}
```

## Claude 配置

```env
LLM_PROVIDER=anthropic
ANTHROPIC_API_KEY=你的 key
ANTHROPIC_MODEL=claude-3-5-haiku-latest
```

兼容旧配置：

```env
CLAUDE_API_KEY=你的 key
CLAUDE_MODEL=claude-3-5-haiku-latest
```

## Kimi 配置

Kimi 使用 OpenAI-compatible adapter：

```env
LLM_PROVIDER=kimi
KIMI_API_KEY=你的 Moonshot Key
KIMI_BASE_URL=https://api.moonshot.cn/v1
KIMI_MODEL=moonshot-v1-8k
```

## Minimax 配置

Minimax 默认使用 Anthropic-compatible adapter：

```env
LLM_PROVIDER=minimax
MINIMAX_API_KEY=你的 Minimax Key
MINIMAX_PROTOCOL=anthropic
MINIMAX_ANTHROPIC_BASE_URL=https://api.minimaxi.com/anthropic
MINIMAX_MODEL=MiniMax-M2.7
```

如果要切回 OpenAI-compatible adapter：

```env
LLM_PROVIDER=minimax
MINIMAX_API_KEY=你的 Minimax Key
MINIMAX_PROTOCOL=openai
MINIMAX_BASE_URL=https://api.minimax.io/v1
MINIMAX_MODEL=MiniMax-M2.7
```

## 任意 OpenAI-compatible 模型

```env
LLM_PROVIDER=openai_compatible
LLM_PROVIDER_NAME=my_provider
LLM_API_KEY=你的 key
LLM_BASE_URL=https://example.com/v1
LLM_MODEL=your-model
```

## 新增 Provider 步骤

1. 在 `backend/app/services/llm/` 新增 provider 文件。
2. 实现 `is_configured()` 和 `complete(request)`。
3. 在 `factory.py` 注册 `LLM_PROVIDER` 名称。
4. 增加 provider 选择测试。
5. 不修改 `/api/v1/ai/chat` 的响应契约。
