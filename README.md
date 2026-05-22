# Stock Review Alpha Assistant

A 股基本面复盘助手，一个面向个人投资者的证据驱动研究平台。

## 一句话定义

为有一定投资经验、希望用基本面而不是短线量化竞争的 A 股个人投资者，提供一个“股票 → 数据证据 → 投资假设 → 检查项 → 复盘”的研究助手。

## 当前能力

1. 管理关注股票。
2. 维护投资假设、检查项、复盘记录。
3. 手动刷新当前股票的公告、新闻、行情、估值和基础指标。
4. 将外部数据标准化为证据卡，并标注来源等级和置信边界。
5. 右侧 AI 复盘引导器把用户想法或证据卡转成待保存成果。
6. 用户确认后，才写入假设、检查项或复盘。
7. 可选每日 18:30 自动刷新关注股票数据。

## 技术栈

- 后端：FastAPI + SQLAlchemy + SQLite
- 前端：React + Vite + TypeScript + Tailwind CSS
- AI：通用 LLM provider 接口，支持 Claude、Kimi、Minimax、OpenAI-compatible
- 数据源：AKShare、BaoStock、可选 Tushare
- 调度：APScheduler，可通过环境变量开启

## 快速开始

```powershell
cd backend
.\venv\Scripts\pip.exe install -r requirements.txt
cd ..

cd frontend
npm install
cd ..

python main.py
```

访问：

- 前端：http://127.0.0.1:5173
- 后端：http://127.0.0.1:8000

## AI 配置

Claude：

```env
LLM_PROVIDER=anthropic
ANTHROPIC_API_KEY=你的 key
ANTHROPIC_MODEL=claude-3-5-haiku-latest
```

Kimi：

```env
LLM_PROVIDER=kimi
KIMI_API_KEY=你的 key
KIMI_BASE_URL=https://api.moonshot.cn/v1
KIMI_MODEL=moonshot-v1-8k
```

Minimax：

```env
LLM_PROVIDER=minimax
MINIMAX_API_KEY=你的 key
MINIMAX_PROTOCOL=anthropic
MINIMAX_ANTHROPIC_BASE_URL=https://api.minimaxi.com/anthropic
MINIMAX_MODEL=MiniMax-M2.7
```

不配置 key 时，系统会自动降级为本地规则 fallback。

## 数据与调度

```env
TUSHARE_TOKEN=可选
ENABLE_DAILY_REFRESH=false
```

## 重要边界

- 免费数据源不保证交易级实时性。
- 新闻只作为线索，不能作为结论。
- AI 不荐股、不预测短线涨跌、不自动买卖。
- AI 只生成待确认成果，用户确认后才写库。

## 验收命令

```powershell
backend\venv\Scripts\python.exe -m pytest
backend\venv\Scripts\python.exe -m ruff check backend\app backend\tests
backend\venv\Scripts\python.exe -m mypy backend\app backend\tests
cd frontend; npm run build
powershell -ExecutionPolicy Bypass -File scripts\check_ai_right_panel.ps1
```

## 更多文档

- [数据驱动研究助手](docs/DATA_DRIVEN_RESEARCH_ASSISTANT.md)
- [通用模型接口](docs/LLM_PROVIDER_INTERFACE.md)
- [AI 右栏检查清单](docs/AI_RIGHT_PANEL_CHECKLIST.md)
