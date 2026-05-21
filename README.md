# Stock Review Alpha Assistant

A股基本面复盘智能助手 —— AI 驱动的投资假设管理与复盘平台。

## 一句话定义

为有一定投资经验、但不想和量化拼短线速度的 A 股个人投资者，提供一个 AI 驱动的基本面假设管理与复盘平台，解决买入理由散落、基本面变化难跟踪、复盘难沉淀、反复犯同类错误的问题。

## 核心功能

1. **股票池与持仓管理** — 添加关注公司、记录持仓成本/数量、展示仓位与浮盈亏
2. **基本面假设管理** — 围绕生意质量、财务质量、成长逻辑、估值水平、风险变化、催化事件六框架建立可验证假设
3. **AI 复盘与成果生成** — 自然语言输入转化为结构化成果（假设/复盘/检查项）
4. **公告/新闻影响判断** — 自动跟踪关注股票动态，AI 筛选有价值信息并判断影响
5. **个人规则与错误画像** — 投资规则检查、复盘归因、常见错误统计

## 技术栈

- **后端**: FastAPI + SQLAlchemy + SQLite + Pandas
- **前端**: React + Vite + TypeScript + Tailwind CSS + shadcn/ui
- **AI**: Claude API (Anthropic)
- **数据源**: a-stock-data (A股7层数据工具包)
- **部署**: Render (staging) / 本地运行 (production)

## 快速开始

```bash
# 安装依赖
pip install -r backend/requirements.txt
cd frontend && npm install && cd ..

# 配置环境变量
cp .env.example .env
# 编辑 .env 填入 CLAUDE_API_KEY

# 启动
python backend/app/main.py
```

访问 http://localhost:8000

## 数据安全

- 所有数据存储在本地 SQLite 文件 (`data/portfolio.db`)
- 每日自动备份到 `data/backups/`
- 备份文件可直接复制迁移，无平台锁定

## License

MIT
