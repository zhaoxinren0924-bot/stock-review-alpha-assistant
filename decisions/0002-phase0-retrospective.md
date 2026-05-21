# ADR-0002: Phase 0 基础设施实施复盘

**日期**: 2026-05-21
**状态**: 已完成
**作者**: Claude + zhaoyuerang

---

## 1. 项目当前状态

### 1.1 已完成的基础设施

| 模块 | 状态 | 关键产物 |
|---|---|---|
| 后端 API | ✅ 运行中 | FastAPI + SQLAlchemy + SQLite，股票池 CRUD |
| 前端页面 | ✅ 运行中 | React + Tailwind，股票列表/添加/删除 |
| GitHub 仓库 | ✅ | https://github.com/zhaoxinren0924-bot/stock-review-alpha-assistant |
| CI/CD | ✅ | GitHub Actions：ruff/mypy/pytest + tsc/build + secret scan |
| 分支保护 | ✅ | master 必须通过 PR + 3 个 status checks |
| Staging 部署 | ✅ | Render: https://stock-review-api.onrender.com |
| 错误监控 | ✅ | Rollbar，已验证收到 staging 环境错误 |
| 可用性监控 | ✅ | UptimeRobot，5 分钟轮询 /health |
| 数据库备份 | ✅ | `scripts/backup.py`，保留最近 30 份 |
| 单命令启动 | ✅ | `python main.py` 同时启动前后端 |

### 1.2 技术栈确认

- **后端**: FastAPI + SQLAlchemy + SQLite + Pydantic
- **前端**: React + Vite + TypeScript + Tailwind CSS
- **部署**: Render (Python Web Service + Static Site)
- **监控**: Rollbar (错误) + UptimeRobot (可用性)
- **数据源**: 待接入 a-stock-data

### 1.3 已知限制

- Render 免费版服务空闲时会休眠（cold start 约 10-30 秒）
- 前端静态站点尚未部署（Blueprint `runtime: static` 不支持，需手动创建）
- 数据库为 SQLite，单文件存储，不适合高并发（但 MVP 阶段足够）
- 没有持久化磁盘（Render 免费版），数据库每次重新部署会重置

---

## 2. 外部服务与工具的作用

本项目在 Phase 0 中使用了以下外部服务，每个的作用和替代方案：

| 服务 | URL | 在本项目中的作用 | 免费额度 | 替代方案 |
|---|---|---|---|---|
| **GitHub** | github.com | 代码托管 + Git 版本控制 + GitHub Actions CI/CD + 分支保护 + PR 流程 | 公共仓库免费 | GitLab, Gitee |
| **Render** | render.com | 云部署平台：托管后端 Python 服务 + 前端静态站点 | Web Service / Static Site 均免费（有限制） | Vercel（前端）+ Railway（后端）, Fly.io |
| **Rollbar** | rollbar.com | 错误监控：自动收集后端未捕获异常，按错误类型分组，邮件告警 | 5000 events/月 | Sentry（首选但注册失败）, Bugsnag, GlitchTip |
| **UptimeRobot** | uptimerobot.com | 可用性监控：每 5 分钟 ping /health 端点，服务宕机时发邮件告警 | 50 个监控项免费 | Pingdom（付费）, Better Uptime, StatusCake |
| **GitHub Actions** | github.com/features/actions | CI/CD 自动化：代码提交后自动运行 linter / 类型检查 / 单元测试 / 安全扫描 | 2000 分钟/月 | Travis CI, CircleCI |
| **TruffleHog** | github.com/trufflesecurity/trufflehog | 密钥泄露扫描：检测代码中是否意外提交了 API Key / Token / 密码 | 开源免费 | GitLeaks, detect-secrets |

### 服务之间的关系图

```
开发者本地
    │  git push
    ▼
GitHub 仓库 ←────── 分支保护 ──────→ PR 必须通过 CI
    │                                      │
    │  Blueprint 同步                        │  ruff / mypy / pytest
    ▼                                      ▼
Render 部署                         GitHub Actions CI
    │                                      │
    │  运行时异常                            │  pip-audit / npm audit
    ▼                                      ▼
Rollbar 错误监控 ←────────────────── TruffleHog 密钥扫描
    │
    │  宕机检测
    ▼
UptimeRobot 可用性监控 ────────────→ 邮件告警
```

---

## 3. 实施过程记录

### 2.1 时间线

```
2026-05-21
  ├── 对话恢复 → 摸底项目状态
  ├── Step 1: 本地基础设施（.env.example, backup.py, README 更新）
  ├── Step 2: GitHub 分支保护（API 配置）
  ├── Step 3: Render 部署（Blueprint 多次试错 → 最终成功）
  ├── Step 4: Rollbar 集成（替代 Sentry，Sentry 注册页打不开）
  ├── Step 5: UptimeRobot 监控配置
  └── Step 6: 备份恢复实测（写入测试数据 → 备份 → 验证恢复）
```

### 2.2 关键决策点

| 决策 | 选择 | 原因 |
|---|---|---|
| Rollbar vs Sentry | Rollbar | Sentry signup 页面被浏览器/网络拦截，多次尝试失败 |
| Blueprint vs 手动创建 | Blueprint | Infrastructure as Code，代码变更自动同步部署 |
| 只部署后端 | 前端延后 | Blueprint `runtime: static` 不支持，减少阻塞 |
| 单命令启动 | `main.py` 脚本 | 同时启动 uvicorn + vite，符合 CLAUDE.md "单命令启动"约束 |

---

## 4. 问题与解决方案

### 3.1 问题清单

#### P1: GitHub Token 在聊天中发送后被撤销
- **现象**: Token 刚发出就返回 401 Bad credentials
- **原因**: GitHub 自动安全机制检测到 token 泄露（公开渠道）
- **解决**: 用户在 VSCode 终端本地运行 API 命令，不再在聊天中发送完整 token
- **教训**: ⚠️ **敏感凭证绝不通过聊天发送**，只在用户本地终端操作

#### P2: Git push 网络超时
- **现象**: `fatal: unable to access '...': Recv failure: Connection was reset`
- **原因**: 当前环境的网络到 GitHub 不稳定
- **解决**: 用户在 VSCode 终端执行 `git push`，网络环境不同
- **教训**: 推送/拉取操作优先让用户在本地终端执行

#### P3: Render Blueprint `type: static` 不支持
- **现象**: `unknown type "static"`
- **原因**: Render Blueprint 语法中静态站点用 `runtime: static` 而不是 `type: static`
- **解决**: 改为 `type: web` + `runtime: static`
- **后续**: 仍有问题，最终简化为只部署后端 API
- **教训**: Render Blueprint 文档要仔细核对，免费版功能有裁剪

#### P4: Render 上数据库表不存在 → 500 错误
- **现象**: API 返回 `{"detail":"Internal server error"}`
- **原因**: Render 是新环境，SQLite 数据库文件和表都不存在
- **解决**: 在 main.py 中添加 `@app.on_event("startup")` 自动创建表
- **教训**: 云部署必须考虑"冷启动"状态，数据库初始化不能依赖手动操作

#### P5: Render 上 data 目录不存在 → SQLite 无法写入
- **现象**: 仍返回 500，Rollbar 报告 `sqlite3.OperationalError`
- **原因**: `os.path.join(PROJECT_ROOT, "data", "portfolio.db")` 的目录不存在
- **解决**: database.py 中添加 `os.makedirs(_DB_DIR, exist_ok=True)`
- **教训**: 文件系统操作必须确保目录存在，不能假设环境已准备好

#### P6: Sentry 注册页面打不开
- **现象**: `sentry.io/signup/` 无法访问
- **原因**: 浏览器插件/广告拦截/VPN/防火墙拦截
- **解决**: 换用 Rollbar 作为替代方案
- **教训**: 备选方案要提前准备，不阻塞主流程

#### P7: Rollbar Account Token vs Project Token 混淆
- **现象**: 用 Account token 发送错误验证通过，但 Render 配置后收不到错误
- **原因**: 后端需要 `post_server_item` scope 的 **Project Access Token**，不是 Account token
- **解决**: 在 Project Settings → Project Access Tokens 中创建新 token
- **教训**: Rollbar 有两层 token（Account 和 Project），后端集成必须确认 scope

---

## 5. 经验教训（可标准化）

### 4.1 项目启动 checklist（以后复用）

```markdown
## 新项目基础设施 checklist

### 仓库
- [ ] GitHub repo 创建
- [ ] .gitignore（Python + Node + OS）
- [ ] README.md（一句话定义 + 快速开始 + 技术栈）
- [ ] LICENSE
- [ ] CLAUDE.md（项目宪法）

### CI/CD
- [ ] GitHub Actions：linter + type check + unit tests
- [ ] GitHub Actions：security scan（pip-audit + npm audit）
- [ ] GitHub Actions：secret leakage scan（TruffleHog）
- [ ] 分支保护：必须通过 PR + status checks

### 部署
- [ ] render.yaml（Blueprint 配置）
- [ ] 环境变量模板 .env.example
- [ ] 数据库启动自动初始化（startup event）
- [ ] 数据目录自动创建（os.makedirs）

### 监控
- [ ] 错误监控（Rollbar/Sentry）Project Access Token
- [ ] 可用性监控（UptimeRobot）
- [ ] 健康检查端点 `/health`

### 数据安全
- [ ] 备份脚本
- [ ] 备份恢复实测记录
```

### 4.2 render.yaml 模板（后端-only，可靠版本）

```yaml
services:
  - type: web
    name: {project-name}-api
    runtime: python
    plan: free
    branch: master
    rootDir: backend
    buildCommand: pip install -r requirements.txt
    startCommand: uvicorn app.main:app --host 0.0.0.0 --port $PORT
    envVars:
      - key: PYTHON_VERSION
        value: 3.12
      - key: ENVIRONMENT
        value: staging
      # 其他环境变量在 dashboard 上手动配置（安全）
```

**注意**: 
- 不要在这里放敏感 token（ROLLBAR_ACCESS_TOKEN 等），在 Render dashboard 手动配置
- `disk` 免费版不支持，不要写
- `runtime: static` Blueprint 不支持，静态站点手动创建

### 4.3 数据库部署最佳实践

```python
# database.py — 自动创建目录
data_dir = Path(__file__).parent.parent.parent / "data"
data_dir.mkdir(parents=True, exist_ok=True)

# main.py — 自动创建表
@app.on_event("startup")
async def create_tables():
    Base.metadata.create_all(bind=engine)
```

### 4.4 敏感凭证管理规范

| 场景 | 做法 | 绝不 |
|---|---|---|
| GitHub Token | 用户本地终端操作 | 聊天发送完整 token |
| API Key | .env.example 留空模板 | 硬编码到代码 |
| Render env var | dashboard 手动配置 | 写入 render.yaml |
| Rollbar token | dashboard 手动配置 | 提交到 git |

### 4.5 用户协作模式（非技术用户）

**有效模式**:
1. 给出精确的点击步骤（按钮名称、字段名称）
2. 提供直接 URL（避免用户自己找）
3. 让用户在本地终端执行命令（不代劳网络敏感操作）
4. 截图确认后再下一步

**避免**:
1. 假设用户知道技术术语（token、scope、env var）
2. 让用户同时处理多个并行任务（容易遗漏）
3. 在聊天中传递敏感凭证

---

## 6. 产出物清单

```
stock-review-alpha-assistant/
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py          ← 含 startup 事件 + Rollbar + CORS
│   │   ├── database.py      ← 自动创建 data 目录
│   │   ├── models.py
│   │   └── schemas.py       ← 新增
│   ├── tests/
│   └── requirements.txt     ← 添加 rollbar
├── frontend/
│   └── src/
│       └── App.tsx          ← 股票池页面
├── scripts/
│   └── backup.py            ← 新增
├── data/
│   └── backups/             ← 备份文件
├── .github/workflows/ci.yml
├── decisions/
│   ├── 0001-tech-stack.md
│   └── 0002-phase0-retrospective.md  ← 本文档
├── render.yaml              ← 新增（修正后版本）
├── main.py                  ← 新增（单命令启动）
├── .env.example             ← 更新
├── README.md                ← 更新
└── CLAUDE.md
```

---

## 7. 下一步建议

### 6.1 近期（1-2 周）

1. **前端静态站点部署** — 手动在 Render 创建 Static Site，或等 Blueprint 支持 static
2. **投资假设管理** — 核心业务功能，六框架录入
3. **接入 a-stock-data** — 自动回填股票信息

### 6.2 中期（1 个月）

1. **AI 对话窗口** — 右侧聊天面板
2. **持仓记录** — 成本/数量/浮盈亏
3. **个人规则系统** — 投资规则检查

### 6.3 技术债务

1. Render 免费版数据库会重置 → 考虑持久化磁盘或定期备份到外部存储
2. 前端 proxy 配置硬编码 localhost:8000 → 需要支持生产环境 API URL
3. 没有前端路由 → 需要 React Router

---

## 8. 成功指标检查

Phase 0 验收标准（原始蓝图）vs 实际结果：

| 验收标准 | 预期 | 实际 | 状态 |
|---|---|---|---|
| GitHub repo 已创建 | 看到仓库 | ✅ https://github.com/zhaoxinren0924-bot/stock-review-alpha-assistant | 通过 |
| CLAUDE.md 内容完整 | 含蓝图+技术栈+不变量 | ✅ 完整 | 通过 |
| dummy PR 质量门跑过 | 所有 CI 通过 | ✅ 分支保护 + 3 个 checks | 通过 |
| Staging hello world | 能访问页面 | ✅ /health 返回 healthy | 通过 |
| Sentry 看到错误 | 故意触发错误 | ⚠️ Sentry 打不开，改用 Rollbar，已验证收到错误 | 通过（替代方案） |
| 数据库备份文件 | 实际从备份恢复 | ✅ 备份+恢复+验证完整 | 通过 |
| decisions/0001-tech-stack.md | 存在 | ✅ 已存在 | 通过 |

**Phase 0 总体评分：7/7 通过。**

---

## 9. 服务之间的数据流向

### 9.1 完整链路（从代码提交到用户访问）

```
┌─────────────┐     git push      ┌─────────────┐
│  开发者本地  │ ───────────────→ │   GitHub    │
│  (VSCode)   │                  │   仓库      │
└─────────────┘                  └──────┬──────┘
                                        │
                    ┌───────────────────┼───────────────────┐
                    │                   │                   │
                    ▼                   ▼                   ▼
           ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
           │ GitHub      │    │ GitHub      │    │ GitHub      │
           │ Actions     │    │ Actions     │    │ Actions     │
           │ (Backend)   │    │ (Frontend)  │    │ (Secrets)   │
           │ ruff/mypy   │    │ tsc/build   │    │ TruffleHog  │
           │ pytest      │    │ npm audit   │    │ scan        │
           └──────┬──────┘    └──────┬──────┘    └──────┬──────┘
                  │                   │                   │
                  └───────────────────┼───────────────────┘
                                      │ all pass
                                      ▼
                              ┌─────────────┐
                              │  分支保护    │
                              │  (PR 合并)   │
                              └──────┬──────┘
                                     │
                                     │ Blueprint sync
                                     ▼
                              ┌─────────────┐
                              │   Render    │
                              │   部署      │
                              │  (Staging)  │
                              └──────┬──────┘
                                     │
                    ┌────────────────┼────────────────┐
                    │                │                │
                    ▼                ▼                ▼
           ┌─────────────┐  ┌─────────────┐  ┌─────────────┐
           │   用户访问   │  │   Rollbar   │  │ UptimeRobot │
           │  (浏览器)    │  │  (错误上报)  │  │ (健康检查)  │
           │             │  │             │  │             │
           │ GET /stocks │  │ 500 异常    │  │ GET /health │
           │             │  │             │  │             │
           └─────────────┘  └──────┬──────┘  └──────┬──────┘
                                   │                │
                                   ▼                ▼
                          ┌─────────────┐  ┌─────────────┐
                          │ Rollbar     │  │ UptimeRobot │
                          │ Dashboard   │  │ Dashboard   │
                          │ (错误分组)   │  │ (可用率统计) │
                          └──────┬──────┘  └──────┬──────┘
                                 │                │
                                 ▼                ▼
                          ┌─────────────┐  ┌─────────────┐
                          │  邮件告警    │  │  邮件告警    │
                          │ (新错误)     │  │ (宕机)       │
                          └─────────────┘  └─────────────┘
```

### 9.2 数据流说明

| 阶段 | 数据内容 | 流向 | 触发条件 |
|---|---|---|---|
| **代码提交** | 源代码变更 | 本地 → GitHub | `git push` |
| **CI 检查** | 测试结果、lint 报告、安全扫描 | GitHub → GitHub Actions | 每次 push / PR |
| **自动部署** | 最新代码、环境变量 | GitHub → Render | master 分支合并后 |
| **API 请求** | JSON 数据（股票信息） | 用户浏览器 → Render | 用户操作 |
| **错误上报** | 异常堆栈、环境信息 | Render → Rollbar | 发生未捕获异常 |
| **健康检查** | HTTP 状态码 | Render ← UptimeRobot | 每 5 分钟 |
| **告警通知** | 错误摘要 / 宕机信息 | Rollbar/UptimeRobot → 邮箱 | 错误发生 / 宕机时 |

---

## 10. 操作手册（Step-by-Step）

### 10.1 GitHub 仓库创建

**前提**: 已有 GitHub 账号

1. 访问 https://github.com/new
2. Repository name: `stock-review-alpha-assistant`
3. Description: `A股基本面复盘智能助手`
4. Visibility: **Public**
5. 勾选 **Add a README file**
6. 点击 **Create repository**

### 10.2 GitHub Actions CI 配置

**文件**: `.github/workflows/ci.yml`

已创建，包含 3 个 job:
- `backend-quality`: ruff + mypy + pytest + pip-audit
- `frontend-quality`: tsc + build + npm audit
- `secret-scan`: TruffleHog

**验证**: 提交代码后打开仓库 Actions 标签，看到工作流运行。

### 10.3 分支保护配置

**方式 A（API，推荐）**:
```bash
# 需要 GitHub Token（repo 权限）
curl -X PUT \
  -H "Authorization: token YOUR_TOKEN" \
  -H "Accept: application/vnd.github+json" \
  https://api.github.com/repos/OWNER/REPO/branches/BRANCH/protection \
  -d '{
    "required_status_checks": {
      "strict": true,
      "contexts": ["Backend Quality","Frontend Quality","Secret Leakage Scan"]
    },
    "required_pull_request_reviews": {"required_approving_review_count": 0},
    "restrictions": null
  }'
```

**方式 B（网页手动）**:
1. Settings → Branches → Add rule
2. Branch name pattern: `master`
3. 勾选 "Require a pull request before merging"
4. 勾选 "Require status checks to pass before merging"
5. 搜索并勾选: `Backend Quality`, `Frontend Quality`, `Secret Leakage Scan`
6. 点击 Create

### 10.4 Render Blueprint 部署

**前提**: 已有 Render 账号，GitHub 已授权连接

1. 访问 https://dashboard.render.com/blueprints
2. 点击 **New Blueprint Instance**
3. 选择 GitHub 仓库 `stock-review-alpha-assistant`
4. 确认读取到 `render.yaml`
5. 点击 **Apply**
6. 等待 2-3 分钟部署完成
7. 点击服务名查看 URL

**环境变量配置**（敏感信息）:
1. 点击服务 `stock-review-api`
2. 左侧 Environment 标签
3. Add Environment Variable
4. 添加 `ROLLBAR_ACCESS_TOKEN`
5. Save Changes（自动重新部署）

### 10.5 Rollbar 项目创建与集成

**前提**: 已有 Rollbar 账号

1. 访问 https://rollbar.com/ 登录
2. 点击 **Create New Project**
3. Project Name: `stock-review-alpha`
4. Framework: Python
5. 进入项目 → Settings → **Project Access Tokens**
6. 点击 **Create New Token**
7. Name: `backend-server`
8. Scopes: 勾选 `post_server_item`
9. 点击 Create → **立即复制 token**（只显示一次）

**后端代码集成**（已内嵌在 `backend/app/main.py`）:
```python
import rollbar
import os

token = os.environ.get("ROLLBAR_ACCESS_TOKEN")
if token:
    rollbar.init(token, environment="staging")
```

**验证**: 访问一个会报错的 API 端点，然后查看 Rollbar Items 页面。

### 10.6 UptimeRobot 监控创建

**前提**: 已有 UptimeRobot 账号

1. 访问 https://dashboard.uptimerobot.com/
2. 点击 **+ New** → **Monitor**
3. Monitor Type: **HTTP(s)**
4. Friendly Name: `stock-review-api`
5. URL: `https://stock-review-api.onrender.com/health`
6. Monitoring Interval: **5 minutes**（免费版最短）
7. Alert Contacts: 勾选你的邮箱
8. 点击 **Create Monitor**

**验证**: 等待 5 分钟后，看到监控项状态为 Up（绿色）。

### 10.7 本地开发环境配置

```bash
# 1. 克隆仓库
git clone https://github.com/zhaoxinren0924-bot/stock-review-alpha-assistant.git
cd stock-review-alpha-assistant

# 2. 后端依赖
cd backend
python -m venv venv
./venv/Scripts/pip install -r requirements.txt
cd ..

# 3. 前端依赖
cd frontend
npm install
cd ..

# 4. 环境变量
cp .env.example .env
# 编辑 .env，填入 CLAUDE_API_KEY 等

# 5. 启动（单命令）
python main.py
# 前端 http://localhost:5173
# 后端 http://localhost:8000
```

---

## 11. 成本估算

### 11.1 当前免费版 vs 生产级付费版

| 服务 | 当前（免费） | 限制 | 升级到生产级（预估月费） | 建议升级时机 |
|---|---|---|---|---|
| **GitHub** | 公共仓库免费 | 无 | Pro $4/月（私有仓库+高级CI） | 需要私有仓库时 |
| **Render** | Web Service + Static Site 免费 | 服务休眠（15分钟无请求后）、无持久化磁盘、每月750小时运行时间 | Starter $7/月（不休眠）+ Disk $0.25/GB/月 | 用户超过10人、需要7x24稳定 |
| **Rollbar** | 5000 events/月 | 无高级功能 | Essentials $49/月（100K events） | 错误量超过5000/月 |
| **UptimeRobot** | 50 监控项、5分钟间隔 | 无短信/电话告警 | Pro $15/月（1分钟间隔+高级告警） | 需要1分钟级监控 |
| **GitHub Actions** | 2000 分钟/月 | 超出后 $0.008/分钟 | Team $4/月（3000分钟） | CI 时间超限时 |

### 11.2 项目初期（1-10 用户）

**推荐**: 全部免费版
- 月费: **$0**
- Render 服务会有冷启动，但个人使用无感知
- Rollbar 5000 events 足够 MVP 阶段

### 11.3 项目成长期（10-100 用户）

**推荐升级**:
- Render Starter: $7/月（解决冷启动）
- Rollbar Essentials: $49/月（更多错误额度）
- **月费合计**: ~$56/月

### 11.4 项目成熟期（100+ 用户）

**推荐升级**:
- Render + Disk: ~$15/月
- Rollbar Advanced: $99/月
- UptimeRobot Pro: $15/月
- GitHub Team: $4/月
- **月费合计**: ~$133/月

### 11.5 成本优化建议

1. **Render 冷启动**: 用 UptimeRobot 每 5 分钟 ping 一次，保持服务活跃（免费版技巧）
2. **Rollbar 额度**: 只上报 production/staging 错误，development 环境不上报
3. **GitHub Actions**: 缓存 pip/npm 依赖，减少构建时间
4. **数据库**: MVP 阶段 SQLite 足够，用户量大了再考虑 PostgreSQL（Render 支持）
