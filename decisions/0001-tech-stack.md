# ADR-0001: 技术栈选择

## 状态

Accepted

## 背景

需要为 A 股基本面复盘助手选择一套技术栈，约束条件：
- 个人项目，开发资源有限（主要依赖 AI 编程助手）
- 数据源以 a-stock-data（Python 工具包）为核心
- 需要精致 UI（信息密度高，不是 admin 面板风格）
- 本地优先（数据在自己电脑上），但可在线访问
- 未来可能扩展给 5-20 个朋友使用

## 决策

### 后端：FastAPI (Python)

**考虑过**：
- Next.js 全栈：前端统一技术栈，但 a-stock-data 是 Python 包，跨语言调用增加复杂度
- Django：太重，不适合轻量 API 服务
- Flask：可以，但 FastAPI 的现代特性（自动文档、类型校验、异步）更适合 AI 辅助开发

**选择 FastAPI 的原因**：
1. a-stock-data 原生 Python 包，零转换成本集成
2. 自动 OpenAPI 文档，调试方便
3. Pydantic 类型校验与前端 TypeScript 天然对应
4. SQLAlchemy 2.0 异步支持良好

### 前端：React + Vite + TypeScript + Tailwind + shadcn/ui

**考虑过**：
- Streamlit：开发极快，但 UI 信息密度低，难以做出精致的投资工具界面
- Vue：可以，但 React + shadcn/ui 生态更丰富
- Next.js：太重，本项目不需要 SSR/SEO

**选择 React 的原因**：
1. shadcn/ui 组件库可做出高信息密度的专业界面
2. Tailwind CSS 原子化样式，快速迭代
3. Vite 构建速度远快于 CRA

### 数据库：SQLite

**考虑过**：
- PostgreSQL：更强大，但本地运行需要额外安装和配置
- MongoDB：不适合结构化关系数据（持仓/假设/事件/影响之间存在复杂关系）

**选择 SQLite 的原因**：
1. 文件级数据库，复制粘贴即可备份/迁移
2. 零配置，用户无需安装数据库服务
3. 单用户场景下性能完全足够
4. SQLAlchemy 抽象了底层，未来迁移到 PostgreSQL 只需改连接字符串

### ETL：Pandas

**决策**：Pandas 负责数据清洗/标准化/去重/指标计算，清洗后立即写入 SQLite。业务查询不走 Pandas，直接走 SQL。

原因：Pandas 在批量数据操作上有巨大效率优势，但不适合持久存储和单条查询。

### AI：Claude API

**考虑过**：
- 本地模型（Qwen/ChatGLM）：可离线运行，但 7B/14B 模型在复杂推理任务上效果不如 Claude
- OpenAI GPT：可以，但 Claude 在长文本理解和结构化输出上更适合本场景

**选择 Claude 的原因**：
1. 长上下文支持（投资假设 + 事件内容 + 历史校准数据需要长上下文）
2. 结构化输出能力强（必须输出可保存的成果）
3. 用户自付 API Key，平台无成本压力

### 部署：Render (staging) + 本地运行 (production)

**决策**：staging 用 Render 免费版自动部署（供 demo 和测试），production 是用户本地运行。

原因：投资数据（持仓/成本/盈亏）极其敏感，本地存储是最安全的方式。在线部署仅用于展示和测试。

## 后果

### 正面
- 开发效率高，a-stock-data 直接 import 使用
- UI 精致度可达商业产品级别
- 本地运行零服务器成本
- 数据完全可控，无隐私风险

### 负面
- SQLite 不适合高并发，未来扩展到 50+ 用户需迁移到 PostgreSQL
- 免费数据源有频率限制，用户多了可能需要付费数据接口
- Python + Node 双技术栈，开发环境需要配置两份

## 相关决策

- ADR-0002: 数据库 Schema 设计（待写）
- ADR-0003: AI 过滤 Pipeline 设计（待写）
