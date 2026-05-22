# Design System — A股基本面复盘助手

> **作用**：所有前端 Agent 的 visual constitution。颜色、间距、字体、组件规范必须严格遵循，不得自行发挥。
>
> **核心原则**：这不是静态看板，是"AI 把分析变成可保存成果"的交互系统。AI 成果卡、确认动作、编辑/保存/忽略流程是一等公民。

---

## 1. 布局体系

### 1.1 三栏结构（可调宽度）

```
┌─────────────────────────────────────────────────────────────┐
│  LeftSidebar        MainContent                RightPanel   │
│  (240px default)    (flex-1)                   (400px)      │
│  [220-320px]                                     [360-520px]│
│  ├← drag →┤                                      ├←drag→┤  │
├─────────────────────────────────────────────────────────────┤
│  240px              剩余空间                    400px        │
└─────────────────────────────────────────────────────────────┘
```

**三栏可调宽度（核心交互）**：

| 栏位 | 默认 | 可调范围 | 拖拽把手 |
|---|---|---|---|
| **LeftSidebar** | 240px | 220px - 320px | 右边缘 |
| **MainContent** | 剩余空间 | 最小 560px | — |
| **RightPanel** | 400px | 360px - 520px（展开时）| 左边缘 |

**右栏支持折叠**：

```
展开态：400px（默认）
折叠态：48px，只显示 AI 图标 + 未处理成果数量徽标
```

折叠/展开通过点击右栏左上角的「◀/▶」按钮切换，带 `transition-all duration-300` 动画。

**整体容器**：

```tsx
<div className="flex h-screen bg-slate-50" style={{ minWidth: 1366 }}>
  <LeftSidebar style={{ width: leftWidth, minWidth: 220, maxWidth: 320 }} />
  <DragHandle onDrag={(delta) => setLeftWidth(w => clamp(w + delta, 220, 320))} />
  <MainContent className="flex-1 min-w-[560px]" />
  <DragHandle onDrag={(delta) => setRightWidth(w => clamp(w - delta, 360, 520))} />
  <RightPanel style={{ width: rightCollapsed ? 48 : rightWidth, minWidth: rightCollapsed ? 48 : 360, maxWidth: rightCollapsed ? 48 : 520 }} />
</div>
```

**拖拽把手样式**：

```tsx
<div className="w-[1px] h-full bg-slate-200 hover:bg-blue-500 active:bg-blue-600 cursor-col-resize transition-colors" />
```

- 默认：`w-[1px] bg-slate-200`
- hover：`bg-blue-500`
- 拖动中：`bg-blue-600`
- 鼠标样式：`cursor-col-resize`

**宽度偏好持久化**（MVP 存 localStorage）：

```typescript
// config.ts
const STORAGE_KEY = 'sr_layout_prefs';

interface LayoutPrefs {
  leftWidth: number;      // 默认 240
  rightWidth: number;     // 默认 400
  rightCollapsed: boolean; // 默认 false
}

export function getLayoutPrefs(): LayoutPrefs {
  const raw = localStorage.getItem(STORAGE_KEY);
  if (raw) return JSON.parse(raw);
  return { leftWidth: 240, rightWidth: 400, rightCollapsed: false };
}

export function saveLayoutPrefs(prefs: LayoutPrefs): void {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(prefs));
}
```

**窗口太窄时的保底策略**（窗口宽度 < 1200px）：

1. 右栏自动折叠为 48px
2. 左栏保持 220px
3. 中栏尽可能保持空间

**最小支持宽度**：`1366px`（浏览器窗口）。右栏展开时 400px + 左侧 240px = 640px，中间剩余约 700px，六框架 2 列布局每列约 340px，足够展示中文内容。

### 1.2 RightPanel 内部结构

右侧面板必须采用 flex 纵向布局，避免整栏滚动时输入框漂移：

```tsx
<aside className="w-[400px] h-screen flex flex-col border-l border-slate-200 bg-white">
  {/* 顶部标题栏 — 固定 */}
  <header className="shrink-0 px-4 py-3 border-b border-slate-200">
    AI 基本面助手
  </header>

  {/* 消息列表 — 可滚动 */}
  <div className="flex-1 overflow-y-auto px-4 py-4 space-y-4">
    {/* messages */}
  </div>

  {/* 待保存成果 — 固定，可折叠 */}
  <div className="shrink-0 border-t border-slate-200">
    {/* pending actions */}
  </div>

  {/* 底部输入框 — 固定 */}
  <footer className="shrink-0 px-4 py-3 border-t border-slate-200">
    {/* input */}
  </footer>
</aside>
```

### 1.3 响应式

本项目**暂不做移动端适配**。最小支持宽度 1366px，目标设备为桌面浏览器。

---

## 2. 色彩体系

### 2.1 中性色（直接映射 Tailwind）

| 用途 | Tailwind 类 | 十六进制 |
|---|---|---|
| 页面背景 | `bg-slate-50` | `#f8fafc` |
| 卡片背景 | `bg-white` | `#ffffff` |
| 边框 | `border-slate-200` | `#e2e8f0` |
| 主标题文字 | `text-slate-900` | `#0f172a` |
| 正文文字 | `text-slate-700` | `#334155` |
| 辅助文字 | `text-slate-500` | `#64748b` |
| 禁用/占位 | `text-slate-400` | `#94a3b8` |
| 分割线 | `border-slate-100` | `#f1f5f9` |

### 2.2 主题色

| 用途 | Tailwind 类 | 十六进制 |
|---|---|---|
| 主按钮/主链接 | `bg-blue-600` / `text-blue-600` | `#2563eb` |
| 主按钮 Hover | `hover:bg-blue-700` | `#1d4ed8` |
| 主按钮文字 | `text-white` | — |
| 次按钮背景 | `bg-white` + `border-slate-200` | — |
| 次按钮文字 | `text-slate-700` | — |
| 危险操作 | `bg-red-600` / `hover:bg-red-700` | `#dc2626` |
| 危险文字 | `text-red-600` | `#dc2626` |

### 2.3 状态标签色（极其重要，必须统一）

所有状态标签使用 `StatusBadge` 组件（见 §4.4）。**禁止在任何地方自行定义状态颜色**。

| 状态值 | 显示文案 | 背景色 | 文字色 | 边框色 | 语义 |
|---|---|---|---|---|---|
| `stable` | 稳定 | `bg-blue-50` | `text-blue-700` | `border-blue-200` | 假设成立 |
| `strengthened` | 增强 | `bg-emerald-50` | `text-emerald-700` | `border-emerald-200` | 假设被增强 |
| `watching` | 待观察 | `bg-amber-50` | `text-amber-700` | `border-amber-200` | 需要跟踪 |
| `unverified` | 待验证 | `bg-slate-100` | `text-slate-600` | `border-slate-200` | 尚未验证 |
| `weakened` | 削弱 | `bg-orange-50` | `text-orange-700` | `border-orange-200` | 假设被削弱 |
| `at_risk` | 风险 | `bg-red-50` | `text-red-700` | `border-red-200` | 出现风险信号 |
| `archived` | 归档 | `bg-gray-100` | `text-gray-500` | `border-gray-200` | 已结束 |

**注意**：`undervalued`（合理偏低）和 `new_impact`（有新影响）**不是** Hypothesis 状态标签，它们是框架卡片的展示状态（见 §2.5）。

### 2.4 六框架编号色

| # | 框架 | 编号圆圈背景 | 编号文字色 |
|---|---|---|---|
| 1 | 生意质量 | `bg-blue-500` | `text-white` |
| 2 | 财务质量 | `bg-orange-500` | `text-white` |
| 3 | 成长逻辑 | `bg-blue-500` | `text-white` |
| 4 | 估值水平 | `bg-indigo-500` | `text-white` |
| 5 | 风险变化 | `bg-red-500` | `text-white` |
| 6 | 催化事件 | `bg-violet-500` | `text-white` |

### 2.5 A股特殊颜色与影响方向

**行情颜色（A 股习惯，与欧美相反）**：

| 用途 | 颜色 |
|---|---|
| 涨 / 浮盈 | `text-red-600` |
| 跌 / 浮亏 | `text-green-600` |

**假设影响方向（避免与行情红绿冲突，不用红绿）**：

| 方向 | 颜色 | 说明 |
|---|---|---|
| 增强 / 利好假设 | `text-blue-600` 或 `text-indigo-600` | 不用绿色，避免和"跌"混淆 |
| 削弱 / 利空假设 | `text-orange-600` | 不用红色，避免和"涨"混淆 |
| 风险警告 | `text-red-600` | 真正的风险信号用红色 |
| 中性影响 | `text-slate-500` | |

**框架卡片特殊状态（非假设级别）**：

| 状态 | 颜色 | 适用框架 |
|---|---|---|
| 合理偏低 | `bg-indigo-50 text-indigo-700` | 估值水平 |
| 合理 | `bg-slate-100 text-slate-600` | 估值水平 |
| 有新影响 | `bg-violet-50 text-violet-700` | 催化事件 |
| 无新动态 | `bg-slate-100 text-slate-600` | 催化事件 |

---

## 3. 字体与排版

### 3.1 字体栈

```css
font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, "Noto Sans", "PingFang SC", "Microsoft YaHei", sans-serif;
```

Tailwind 默认即可，**不要引入 Google Fonts 或其他字体**。

### 3.2 字号层级

| 层级 | Tailwind | 用途 |
|---|---|---|
| 页面标题 | `text-xl font-bold` | "招商银行 · 基本面看板" |
| 区域标题 | `text-base font-semibold` | "复盘记录与检查项" |
| 卡片标题 | `text-sm font-semibold` | "生意质量" |
| 正文 | `text-sm` | 核心判断段落 |
| 辅助文字 | `text-xs` | 标签、日期、指标名 |
| 数据数字 | `text-base font-semibold` | 14.6%、0.86 |

### 3.3 行高

- 标题：`leading-tight`（1.25）
- 正文：`leading-relaxed`（1.625）
- 数据：`leading-none`

---

## 4. 组件规范

### 4.1 卡片（Card）

所有白色内容块使用统一卡片样式：

```tsx
<div className="bg-white rounded-lg border border-slate-200 p-5">
```

- `rounded-lg`（**8px**，不是 12px）
- `border border-slate-200`
- `p-5`（20px 内边距）
- 无阴影（`shadow-none`），hover 也不加阴影

### 4.2 按钮（Button）

#### 主按钮（Primary）

```tsx
<button className="h-9 px-4 bg-blue-600 text-white text-sm font-medium rounded-lg hover:bg-blue-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed">
```

#### 次按钮（Secondary）

```tsx
<button className="h-9 px-4 bg-white border border-slate-200 text-slate-700 text-sm font-medium rounded-lg hover:bg-slate-50 transition-colors disabled:opacity-50">
```

#### 危险按钮（Destructive）

```tsx
<button className="h-9 px-4 bg-red-600 text-white text-sm font-medium rounded-lg hover:bg-red-700 transition-colors">
```

#### 图标按钮（Icon Button）

```tsx
<button className="h-9 w-9 flex items-center justify-center text-slate-400 hover:text-slate-600 hover:bg-slate-100 rounded-lg transition-colors">
```

#### 按钮状态

| 状态 | 样式 |
|---|---|
| 默认 | 如上 |
| Hover | 背景色变深 |
| Active/Pressed | `scale-[0.98]` 微缩放 |
| Disabled | `opacity-50 cursor-not-allowed` |
| Loading | 显示 Spinner，文字隐藏或保留 |
| Small | `h-7 text-xs px-3` |
| Full Width | `w-full` |

- 圆角统一 `rounded-lg`（8px）
- 高度统一：标准 `h-9`（36px），小尺寸 `h-7`（28px）

### 4.3 表单输入（Input / Textarea / Select）

#### 文本输入框

```tsx
<input
  className="h-9 w-full px-3 text-sm border border-slate-200 rounded-lg bg-white
    placeholder:text-slate-400
    focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500
    disabled:bg-slate-50 disabled:text-slate-400"
/>
```

#### 文本域

```tsx
<textarea
  className="min-h-[80px] w-full px-3 py-2 text-sm border border-slate-200 rounded-lg bg-white
    placeholder:text-slate-400
    focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500
    resize-y"
/>
```

#### 下拉选择

```tsx
<select
  className="h-9 w-full px-3 text-sm border border-slate-200 rounded-lg bg-white
    focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500"
>
```

#### 表单状态

| 状态 | 样式 |
|---|---|
| 默认 | 灰色边框 `border-slate-200` |
| Focus | 蓝色边框 `border-blue-500` + 淡蓝色 ring |
| Error | 红色边框 `border-red-500` + 红色 ring |
| Disabled | 灰色背景 `bg-slate-50` |

#### 表单标签与错误提示

```tsx
<div className="space-y-1.5">
  <label className="text-sm font-medium text-slate-700">核心判断</label>
  <input ... />
  <p className="text-xs text-red-600">请输入核心判断</p>
</div>
```

- 标签：`text-sm font-medium text-slate-700`
- 错误提示：`text-xs text-red-600`
- 帮助文字：`text-xs text-slate-500`
- 标签与输入框间距：`space-y-1.5`

### 4.4 StatusBadge（状态标签）— 必须复用

**路径**：`src/components/stock/StatusBadge.tsx`

```tsx
interface StatusBadgeProps {
  status: 'stable' | 'strengthened' | 'watching' | 'unverified' | 'weakened' | 'at_risk' | 'archived';
  size?: 'sm' | 'md';
}
```

样式映射见 §2.3。组件封装后**任何 Agent 不得自行实现状态标签**。

### 4.5 编号圆圈

六框架卡片左上角的编号：

```tsx
<span className="inline-flex items-center justify-center w-6 h-6 rounded-full text-xs font-bold text-white bg-blue-500">
  1
</span>
```

- 尺寸：`w-6 h-6`（24px）
- 字体：`text-xs font-bold`
- 颜色：见 §2.4

### 4.6 表格

复盘记录表格：

```tsx
<table className="w-full text-sm">
  <thead className="border-b border-slate-200">
    <tr className="text-slate-500 text-xs">
      <th className="text-left py-3 px-4 font-medium">日期</th>
      {/* ... */}
    </tr>
  </thead>
  <tbody className="divide-y divide-slate-100">
    <tr className="hover:bg-slate-50">
      <td className="py-3 px-4 text-slate-700">05-18</td>
      {/* ... */}
    </tr>
  </tbody>
</table>
```

- 表头：`text-xs text-slate-500 font-medium`
- 行高：`py-3`（12px 垂直内边距）
- 行分割线：`divide-y divide-slate-100`
- hover：`hover:bg-slate-50`

---

## 5. 间距体系

### 5.1 页面级间距

- 主内容区内边距：`p-6`（24px）
- 卡片之间间距：`gap-4`（16px）
- 卡片内部元素间距：`space-y-3` 或 `gap-3`（12px）

### 5.2 概览卡片行

4 列等宽：
```tsx
<div className="grid grid-cols-4 gap-4">
```

### 5.3 六框架网格

**2 列 × 3 行**（不是 2 行 × 3 列）：

```tsx
<div className="grid grid-cols-2 gap-4">
  {/* 6 张卡片，每行 2 张，共 3 行 */}
</div>
```

中栏宽度约 700px，每列约 340px，适合中文内容和指标展示。

---

## 6. 核心组件（产品差异化）

### 6.1 AI 成果卡（AISuggestedActionCard）

这是产品最核心的差异化组件，**必须单独规范**。

**路径**：`src/components/ai/AISuggestedActionCard.tsx`

#### 结构

```tsx
interface AISuggestedActionCardProps {
  type: 'update_hypothesis_status' | 'create_check_item' | 'create_review' | 'update_position_notes';
  title: string;           // "更新 H1 状态"
  description: string;     // "从「待验证」→「待观察」"
  reason?: string;         // "净息差下降削弱了利润改善预期"
  affectedObject?: string; // "H1 零售业务恢复带来利润改善"
  confidence?: number;     // 0-100，可选
  onSave: () => void;
  onEdit: () => void;
  onDismiss: () => void;
  status: 'pending' | 'applying' | 'applied' | 'dismissed' | 'failed';
}
```

#### 样式

```tsx
<div className="bg-blue-50 border border-blue-200 rounded-lg p-4 space-y-3">
  {/* 头部：图标 + 标题 + 状态 */}
  <div className="flex items-start justify-between">
    <div className="flex items-center gap-2">
      <div className="w-8 h-8 rounded-lg bg-blue-100 flex items-center justify-center">
        <Icon className="w-4 h-4 text-blue-600" />
      </div>
      <div>
        <div className="text-sm font-semibold text-slate-900">{title}</div>
        <div className="text-xs text-slate-500">{description}</div>
      </div>
    </div>
    <StatusBadge status="pending" />
  </div>

  {/* 原因（可选） */}
  {reason && (
    <div className="text-xs text-slate-600 bg-white rounded-md p-2.5 border border-blue-100">
      {reason}
    </div>
  )}

  {/* 操作按钮 */}
  <div className="flex items-center gap-2">
    <button className="h-8 px-3 bg-blue-600 text-white text-xs font-medium rounded-md hover:bg-blue-700">
      保存成果
    </button>
    <button className="h-8 px-3 bg-white border border-slate-200 text-slate-700 text-xs font-medium rounded-md hover:bg-slate-50">
      编辑
    </button>    
    <button className="h-8 px-3 text-slate-400 text-xs hover:text-slate-600">
      忽略
    </button>
  </div>
</div>
```

#### 状态样式

| 状态 | 卡片背景 | 边框 |
|---|---|---|
| `pending` | `bg-blue-50` | `border-blue-200` |
| `applying` | `bg-blue-50` | `border-blue-300` + spinner |
| `applied` | `bg-green-50` | `border-green-200` + 对勾图标 |
| `dismissed` | `bg-slate-50` | `border-slate-200` + 降低透明度 |
| `failed` | `bg-red-50` | `border-red-200` + 错误提示 |

### 6.2 假设状态概览（替代 HealthGauge）

MVP 阶段**弱化分数概念**，用状态数量表达：

```tsx
<div className="bg-white rounded-lg border border-slate-200 p-5">
  <div className="text-xs text-slate-500 mb-3">假设状态概览</div>
  <div className="grid grid-cols-3 gap-3">
    <div className="text-center">
      <div className="text-xl font-bold text-blue-600">2</div>
      <div className="text-xs text-slate-500">稳定</div>
    </div>
    <div className="text-center">
      <div className="text-xl font-bold text-amber-600">2</div>
      <div className="text-xs text-slate-500">待观察</div>
    </div>
    <div className="text-center">
      <div className="text-xl font-bold text-red-600">1</div>
      <div className="text-xs text-slate-500">风险</div>
    </div>
  </div>
</div>
```

- 不显示 72/100 的抽象分数
- 显示各状态的数量分布
- 点击可下钻到对应框架

**后续扩展**：如需分数，必须显示计算说明（"基于 6 条假设状态、风险数量和待复盘项计算"）。

### 6.3 左侧导航菜单

```tsx
<nav className="space-y-1">
  <a className={cn(
    "flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition-colors",
    isActive ? "bg-blue-50 text-blue-700" : "text-slate-600 hover:bg-slate-100"
  )}>
    <Icon className="w-5 h-5" />
    <span>总览</span>
  </a>
</nav>
```

- 图标：lucide-react，尺寸 `w-5 h-5`
- 激活态：`bg-blue-50 text-blue-700`
- 非激活：`text-slate-600 hover:bg-slate-100`

### 6.4 关注公司列表项

```tsx
<div className="flex items-center justify-between px-3 py-2.5 rounded-lg hover:bg-slate-50 cursor-pointer">
  <div>
    <div className="text-sm font-medium text-slate-900">招商银行</div>
    <div className="text-xs text-slate-500">600036</div>
  </div>
  <StatusBadge status="watching" />
</div>
```

- 行高：`py-2.5`（10px 垂直内边距）
- hover：`hover:bg-slate-50`
- 状态标签必须复用 `StatusBadge`

---

## 7. 不变量约束

以下约束来自项目宪法，设计系统必须遵守：

1. **界面简洁、信息密度高**：卡片内边距不超过 `p-5`，行间距不超过 `gap-4`，拒绝大面积留白。
2. **不做行情软件的复制品**：不使用 K 线红绿色、不使用涨跌幅箭头动画、不堆盘口数据。
3. **用户自己做最终决策**：AI 面板和卡片中禁止使用"买入""卖出""建议建仓"等措辞，使用"需要关注""建议复盘""待观察"。
4. **A 股颜色习惯**：涨/盈利 = 红色，跌/亏损 = 绿色（与欧美相反）。
5. **AI 成果是一等公民**：AI 成果卡必须醒目、可交互，不能让用户感觉 AI 只是聊天机器人。
6. **金融工具视觉克制**：圆角统一 8px（`rounded-lg`），拒绝大圆角、渐变、阴影。
7. **三栏可调但不乱**：左栏 220-320px，右栏 360-520px（可折叠为 48px），中栏最小 560px。宽度偏好存 localStorage。窗口太窄时右栏自动折叠，优先保证中栏空间。

---

## 8. 文件清单（Agent 必须遵守的路径）

| 组件 | 必须路径 |
|---|---|
| 状态标签 | `src/components/stock/StatusBadge.tsx` |
| 假设状态概览 | `src/components/stock/StatusOverview.tsx` |
| 六框架网格容器 | `src/components/stock/FrameworkGrid.tsx` |
| AI 成果卡 | `src/components/ai/AISuggestedActionCard.tsx` |
| 左侧边栏 | `src/components/layout/LeftSidebar.tsx` |
| 右侧面板 | `src/components/layout/RightPanel.tsx` |
| 三栏布局 | `src/components/layout/AppLayout.tsx` |
| 拖拽把手 | `src/components/layout/DragHandle.tsx` |
| 布局偏好管理 | `src/hooks/useLayoutPrefs.ts` |

**禁止**在 `src/components/ui/` 之外创建新的 shadcn/ui 组件副本。所有基础 UI（Button、Card、Badge、Dialog、Input、Textarea、Select 等）必须从 `@/components/ui/*` import。
