# QoderWork 任务 — v0.0.40 Web「加固+复扫+对比」页面

> **Agent**：QoderWork 模式 A（Qwen-3.7-Max）
> **状态**：🟢 可开工 — 后端路由 `POST /api/harden/<scan_id>/verify` 已就绪，i18n 并行补全中
> **类型**：Web 前端 + 轻后端路由消费
> **依赖**：全部就绪 ✅

---

## 一、项目上下文

LightShield Web 面板（Flask + 原生 HTML/CSS + Jinja2）。已有页面：dashboard / harden / report / docs。v0.0.37 有脚本下载 + SSE + 主题切换 + 搜索。v0.0.39 有 `t()` / `window.t` / `window.tf` i18n。

本任务新增「加固闭环」页面 — 让用户可视化看到加固前后风险变化。

---

## 二、后端接口（已就绪，消费即可）

```
POST /api/harden/<scan_id>/verify
Content-Type: application/json
X-CSRF-Token: <csrf_token>

请求体:
{
    "mode": "dry_run",           // "dry_run" | "apply"
    "os_platform": "linux",      // "linux" | "windows"
    "confirm_ownership": false,  // APPLY 必须 true
    "confirm_execute": false     // APPLY 必须 true
}

响应 200:
{
    "success": true,
    "target": "127.0.0.1",
    "mode": "dry_run",
    "os_platform": "linux",
    "overall": "generated_only",   // verified|partial|failed|generated_only
    "before_scan": { "status": "...", "findings": [...] },
    "harden": { "action_count": 3, "status": "..." },
    "execution": { "status": "...", "stdout": "...", "stderr": "..." } | null,
    "after_scan": { "status": "...", "findings": [...] } | null,
    "verification": {
        "verdict": "verified",
        "resolved": [{ "vuln_type": "...", "port": 22, "severity": "high", "title": "..." }],
        "remaining": [...],
        "regressed": [...],
        "before_count": 2,
        "after_count": 0
    } | null,
    "audit_id": "CL-...",
    "scan_id": "LS-..."
}

APPLY 缺双确认 → 400:
{ "error": true, "message": "[R4] APPLY 真机执行需要...", "code": 400 }
```

---

## 三、页面规格

### 3.1 路由

新增 Flask 路由（在 `lightshield/web/routes.py` 中添加）：

```python
@pages_bp.route("/harden/<scan_id>/verify")
@login_required
def harden_verify_page(scan_id: str):
    """渲染加固闭环对比页面。"""
    return render_template("harden_verify.html", scan_id=scan_id)
```

### 3.2 页面结构（`templates/harden_verify.html`）

```
┌─────────────────────────────────────────┐
│  🔄 加固闭环对比                        │  ← t('closed_loop.title')
│  target: 127.0.0.1  模式: 预检          │
│  ┌─────────────────────────────────┐    │
│  │  ✅ 已验证  /  ⚠️ 部分修复 等  │    │  ← overall 徽章
│  └─────────────────────────────────┘    │
│                                         │
│  [Dry Run 预检] [Apply 真机执行]        │  ← 模式切换标签
│  ☑ 我确认拥有该资产                     │  ← R4 确认（APPLY 必勾）
│  ☑ 确认在真机执行加固                   │  ← R4 确认（APPLY 必勾）
│  ⚠️ 应用模式将真实修改本机系统...        │  ← 仅 APPLY 时显示
│  [开始闭环扫描]                          │  ← POST /api/harden/.../verify
│                                         │
│  ┌─── before/after 对比表 ──────────┐   │
│  │ 类型 │ 端口 │ 严重度 │ 状态      │   │
│  │ sqli │  -   │ high   │ ✅ 已修复 │   │
│  │ port │ 3306 │ medium │ ⚠️ 仍存在 │   │
│  │ xss  │  -   │ low    │ 🔴 新增   │   │
│  └──────────────────────────────────┘   │
│                                         │
│  ▶ 执行日志（折叠）                      │  ← execution.stdout/stderr
│  📥 下载加固脚本 / 回滚脚本               │  ← 复用 /api/script/... 白名单
└─────────────────────────────────────────┘
```

### 3.3 交互逻辑（前端 JS）

1. 页面加载 → 不自动请求，等待用户选择模式和确认
2. 模式默认 `dry_run`
3. 用户切到 `apply` → 显示 R4 确认勾选框 + 警告文案
4. `apply` 模式两个勾选框未全打勾 → 「开始闭环扫描」按钮置灰
5. 点击按钮 → `POST /api/harden/<scan_id>/verify` with JSON body + CSRF header
6. 响应回来 → 渲染 overall 徽章 + before/after 对比表 + 执行日志折叠
7. 轮询/SSE 非必需（闭环同步返回），但可显示一个 loading 状态

### 3.4 对比表渲染逻辑

对比表**不依赖 verification 分桶**—直接从 before.findings 和 after.findings 计算每行的状态：

- 在 `before` 中 且 不在 `after` 中 → ✅ 已修复（绿色）
- 在 `before` 中 且 在 `after` 中 → ⚠️ 仍存在（黄色）
- 不在 `before` 中 且 在 `after` 中 → 🔴 新增风险（红色）

比对键：`(vuln_type, port)` 相同视为同一风险。

### 3.5 DRY_RUN 降级

`after_scan` / `verification` 为 `null` 时 → 对比表显示占位文案 `t('closed_loop.empty_dryrun')`，不报错。

### 3.6 i18n 键清单（已存在于 locales，直接 `t('closed_loop.XXX')` 消费）

```
closed_loop.title
closed_loop.mode_dry_run
closed_loop.mode_apply
closed_loop.overall_verified
closed_loop.overall_partial
closed_loop.overall_failed
closed_loop.overall_generated_only
closed_loop.col_type
closed_loop.col_port
closed_loop.col_severity
closed_loop.col_status
closed_loop.status_resolved
closed_loop.status_remaining
closed_loop.status_regressed
closed_loop.exec_log
closed_loop.exec_download
closed_loop.confirm_ownership
closed_loop.confirm_execute
closed_loop.warn_apply
closed_loop.empty_dryrun
```

> 这 20 个键由 CodeBuddy 在并行任务中填充。你直接用 `t('closed_loop.xxx')` 引用即可，**勿在 HTML 中写死中英文**。

---

## 四、合规约束

- 页面**不直接执行加固**——只调后端 `/api/harden/<scan_id>/verify`
- APPLY 按钮必须在双确认勾选后才可点击（前端拦截 + 后端二次校验）
- 脚本下载复用 v0.0.37 `/api/script/<scan_id>/<filename>` 白名单下载，**勿新开任意路径下载**
- CSRF：POST 请求必须携带 `X-CSRF-Token` header（从 `session._csrf_token` 读取）

---

## 五、代码要求

- 风格对齐现有 `templates/`（dashboard / harden / report），复用 CSS 变量/主题
- 无内联明文中文/英文——全部 `t('closed_loop.xxx')`
- 前后端分离：页面只依赖 `to_dict()` JSON
- 单测对齐 `tests/test_web_*.py` 风格
- `python -m pre_commit run --files <改动>` 过门禁

---

## 六、验收

1. [ ] `/harden/<scan_id>/verify` 页面可访问（需登录）
2. [ ] DRY_RUN 模式 → 正确展示「预检模式未复扫」占位
3. [ ] APPLY 模式 → 缺双确认按钮置灰 + 勾选后可点击
4. [ ] 对比表三状态着色（已修复✅绿 / 仍存在⚠️黄 / 新增🔴红）
5. [ ] 执行日志折叠区 + 脚本下载链接
6. [ ] 全文案走 i18n（无硬编码中文/英文）
7. [ ] Web 测试通过 + pre-commit 零违规
