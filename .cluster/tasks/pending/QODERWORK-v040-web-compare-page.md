# QoderWork 任务（模式 A：IDE/前端）— v0.0.40 Web「加固 + 复扫 + 对比」页面

> **Agent**：**QoderWork 模式 A**（原 Qoder IDE，Qwen-3.7-Max，已退役并入 QoderWork · 同模型零能力损失）
> **执行方式**：在 Qoder IDE 中打开项目 → 复制本 prompt 到 Quest Agent → 执行
> **版本**：v0.0.40 自动加固闭环｜**类型**：Web 前端 + 轻后端路由
> **依赖**：消费 `ClosedLoopResult.to_dict()` 形状（CodeBuddy verify 任务产出）+ Codex 的编排端点（可按契约 §8 形状先并行做 UI，集成在两者之后）。
> **冻结接口来源**：`docs/design-v040-closed-loop.md`（正式版）§8；决策见 `docs/adr-v040-execution-substrate.md`
> **改派记录**：2026-06-25 Qoder IDE 退役（无额度）→ 并入 QoderWork 模式 A（同模型 Qwen-3.7-Max + 同付费体系）

---

## 一、项目上下文（简短）

LightShield Web 面板（Flask + 原生 HTML/CSS，v0.0.37 已有脚本下载/SSE/主题/搜索，v0.0.39 已有 i18n `t()`）。本任务加一个「一键加固 → 复扫 → 前后对比」页面，让用户可视化看到加固前后风险变化。

## 二、⚠️ 合规约束（R1-R6）

- 页面**不直接执行加固**——只调后端编排端点；真机 APPLY 的双确认（R4）由后端强制，前端须提供明确的"我确认拥有该资产 + 确认执行"勾选/弹窗，缺确认禁用 APPLY 按钮。
- 默认呈现 **DRY_RUN（预检）**；APPLY（真改系统）必须用户显式切换 + 二次确认，UI 用醒目警示色。
- 脚本下载复用 v0.0.37 `/api/script/...` 白名单下载，**勿新开任意路径下载**（R 红线：防目录穿越）。

## 三、接口契约（严格按此）

### 3.1 后端路由（契约 §8）

`POST /api/harden/<scan_id>/verify`：触发 `core.run_harden_closed_loop(...)`，返回 `ClosedLoopResult.to_dict()`。
- 请求体含 `mode`（`dry_run`|`apply`）、`confirm_ownership`、`confirm_execute`、`os_platform`。
- `apply` 缺双确认 → 后端返 4xx + 错误文案（前端展示，不崩）。

### 3.2 页面消费 `ClosedLoopResult.to_dict()`（**不碰 Python 对象**）

字段：`target/mode/overall/before_scan/harden/execution/after_scan/verification`。
- **顶部徽章**：`overall` → `verified=绿` / `partial=黄` / `failed=红` / `generated_only=灰`。
- **before/after 对比表**：每行一个风险，列 = 类型 / 端口 / 严重度 / 状态。状态取自 `verification`：在 `resolved`→已修复✅ / `remaining`→仍存在⚠️ / `regressed`→新增🔴。
- **折叠区**：`execution.stdout` / `execution.stderr`（执行日志）+ 脚本下载（复用 v0.0.37 白名单端点）。
- DRY_RUN 时 `after_scan/verification` 为 `null` → 表格显示"预检模式，未复扫"占位，不报错。

### 3.3 i18n（契约 §8）

所有文案走 v0.0.39 `t()` / `window.t/tf`，键前缀 `closed_loop.*`（中英对称，由 CodeBuddy i18n 任务在 `locales/{zh-CN,en-US}.json` 补；**键名与 i18n 任务对齐**，缺键先列清单同步）。

## 四、代码要求

- 风格对齐现有 `templates/` 与 `web/` 既有页面（dashboard/harden/report），复用现有 CSS 变量/主题（暗色亮色）。
- 无内联明文中文/英文——全部 `t('closed_loop.xxx')`；aria-label 也走 i18n（延续 v0.0.39 规范）。
- 前后端分离：页面只依赖 `to_dict()` JSON，便于未来 SaaS 化。
- 路由加 CSRF 保护（复用 `web/csrf.py`）。
- 单测/前端测对齐 `tests/test_web_*.py` 风格（路由返回 200/4xx、缺确认拒绝、渲染含徽章）。
- `python -m pre_commit run --files <改动>` 过门禁。

## 五、验收

1. [ ] `POST /api/harden/<scan_id>/verify` 路由 + CSRF + 缺双确认 4xx。
2. [ ] 页面正确渲染 overall 徽章 + before/after 对比表（三状态着色）+ 执行日志折叠 + 白名单脚本下载。
3. [ ] DRY_RUN（after/verification=null）优雅降级不报错。
4. [ ] 全文案 i18n（closed_loop.*），键清单已与 CodeBuddy i18n 任务对齐。
5. [ ] Web 测试通过 + pre-commit 零违规。
6. [ ] ⚠️ CC 安全审查（前端安全：XSS/CSRF/下载路径，见 `.guardrails/REVIEW_CHECKLIST.md`）。
