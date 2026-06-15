你是 LightShield 项目的高级开发工程师，使用 GPT-5.5 模型。

## 项目背景
LightShield（轻盾）是开源轻量化安全自检 + 防御加固工具，Python 3.10+，Flask Web 仪表板。
当前版本 v0.0.36。阶段二 3/4 完成（PDF ✅ + CVE ✅ + Nuclei ✅），你的任务是完成第 4/4 步：Web UI 增强。

## 已有文件（重要——修改前请完整阅读）
```
lightshield/web/app.py              → Flask 应用工厂 + 安全头 + Session + 速率限制
lightshield/web/routes.py           → /api/* 路由蓝图（scan/report/harden）
lightshield/web/pages.py            → /dashboard /report/<id> /harden/<id> 页面路由
lightshield/web/auth.py             → 鉴权（login/logout/login_required）
lightshield/web/csrf.py             → CSRF 防护
lightshield/web/ratelimit.py        → 速率限制
lightshield/web/templates/base.html → Jinja 基础模板（所有页面继承此模板）
lightshield/web/templates/login.html
lightshield/web/templates/dashboard.html  → 扫描面板 + 历史记录
lightshield/web/templates/report.html     → 报告查看器（Markdown 渲染）
lightshield/web/templates/harden.html     → 加固建议 + 脚本生成
lightshield/web/static/style.css          → 全站样式（单文件）
```

## ⚠️ 关键合规约束（每项都要遵守）

R1: 不引入外部 CDN 依赖（除已存在的 marked.js CDN 外不新增）
R2: 所有下载操作需 CSRF 保护
R3: 不向外部发送用户数据
R4: 加固脚本下载前需确认所有权（复用已有 R4 checkbox）
R5: 不引入 eval()/new Function() 等动态代码执行
R6: 不修改现有的安全响应头（CSP/X-Frame/CORS 等）

---

## 任务：v0.0.37 Web UI 增强 —— 4 个子任务

### 子任务 1：加固脚本下载按钮

**现状**：harden.html 生成脚本后只显示路径文本，用户不知道脚本在哪、如何获取。
**目标**：Web 端可直接下载生成的加固脚本和回滚脚本。

具体工作：
1. **新增 API 端点** `GET /api/script/<scan_id>/<filename>`：
   - 从 `config.report_output_dir` 读取脚本文件
   - 白名单文件名校验（只允许 `harden_*.sh`, `harden_*.ps1`, `rollback_*.sh`, `rollback_*.ps1`）
   - 返回 `application/octet-stream` + `Content-Disposition: attachment`
   - 需 `@login_required` 鉴权
   - 输出文件不存在返回 404

2. **修改 harden.html**：
   - 结果面板 (#harden-result) 中每条脚本路径后添加下载按钮（<a> 链接）
   - 下载 URL：`/api/script/{{ scan_id }}/<filename>`
   - 添加 CSRF token（通过 data-attribute 或 URL 参数，推荐用 cookie 方式）

3. **修改 report.html 底部操作区**：
   - 如果有加固脚本（从 harden API 查询），显示下载按钮

---

### 子任务 2：SSE 实时进度推送

**现状**：dashboard.html 用 `setTimeout(pollScan, 1500)` 轮询扫描状态。
**目标**：用 Server-Sent Events (SSE) 替代轮询，实时推送扫描进度。

具体工作：
1. **新增 SSE 端点** `GET /api/scan/<task_id>/stream`：
   - Content-Type: `text/event-stream`
   - 从 `core.get_scan_status(task_id)` 读取状态
   - 每 500ms 发送一次 `data: {"status": "...", "ports": N, "findings": N, ...}`
   - 当状态变为 completed/partial/failed 时发送 `event: done` 后关闭连接
   - 超时回退：60 秒无完成 → 发送 `event: timeout` 后关闭
   - 任务不存在 → 立即返回 `event: error` 并关闭

2. **修改 dashboard.html 的 JS**：
   - 将 `pollScan()` 轮询函数替换为 `EventSource` SSE 监听
   - 保留 `pollScan()` 作为 fallback（浏览器不支持 SSE 时）
   - UI 进度条：在 status-console 中显示扫描进度（进度条动画）
   - 展示实时数字：端口数、发现数随扫描推进更新

3. **注意**：
   - Flask 默认是线程模型，SSE 不会阻塞其他请求
   - 每个 SSE 连接需要一个线程，合理超时避免资源泄漏
   - 不加额外的 Python 依赖

---

### 子任务 3：暗色/亮色主题切换

**现状**：只有亮色主题，无切换功能。
**目标**：支持暗色/亮色主题切换，遵从用户偏好。

具体工作：
1. **修改 style.css**：
   - 引入 CSS 变量（`:root` / `[data-theme="dark"]`）管理颜色
   - 需要变量的元素：背景色、文字色、边框色、面板底色、表格交替行色、按钮色、badge 色
   - 暗色主题颜色建议：深灰底 (#1a1a2e 或 #0d1117)、浅灰文字 (#c9d1d9)、面板 (#161b22)、强调色保持（蓝/绿/红不变）
   - 过渡动画：`transition: background-color 0.3s, color 0.3s`

2. **修改 base.html**：
   - `<html>` 标签添加 `data-theme` 属性，默认 "light"
   - 顶部导航栏添加主题切换按钮（☀/🌙 图标或纯 CSS toggle）
   - 按钮样式：圆角，与现有 ghost-button 风格一致

3. **JS 逻辑**（base.html `<script>` 中）：
   - 首次访问检查 `localStorage.getItem("ls-theme")`
   - 无偏好时检查 `window.matchMedia("(prefers-color-scheme: dark)")`
   - 点击切换 → 更新 `data-theme` 属性 + 写入 `localStorage`
   - 切换时更新按钮图标/文字

4. **注意**：暗色模式要保证所有文字可读（对比度 ≥4.5:1），badge 色在暗底上仍需醒目。

---

### 子任务 4：仪表板搜索 + 筛选

**现状**：dashboard.html 的扫描历史列表无搜索/筛选功能。
**目标**：添加搜索框，支持按目标、扫描 ID、状态筛选历史记录。

具体工作：
1. **修改 dashboard.html**：
   - 历史面板标题旁添加搜索输入框（`<input type="search" placeholder="搜索目标或扫描ID...">`）
   - 搜索框右侧添加状态筛选下拉（`全部 / completed / partial / failed / running`）
   - 搜索为纯客户端实现（无需后端改动——历史记录已全量返回到 Jinja）

2. **JS 筛选逻辑**：
   - 监听搜索框 `input` 事件 + 下拉 `change` 事件
   - 对 `<tbody>` 中的 `<tr>` 进行 `display: none` / `display: ""` 切换
   - 匹配规则：大小写不敏感，目标地址 + 扫描 ID 字段模糊匹配
   - 无匹配结果时显示空状态提示："没有匹配的记录"
   - 搜索结果数量提示："显示 3/20 条记录"

3. **URL 参数支持**：
   - 搜索词写入 URL query: `/dashboard?q=192.168&status=completed`
   - 页面加载时从 URL 读取参数并填入搜索框 + 筛选下拉
   - 用于深链接和书签

4. **注意**：搜索框样式与现有 scan-form 一致（label + input 组合），不破坏现有布局。

---

## 接口契约

### 新增 API（routes.py）

```python
@api_bp.route("/script/<scan_id>/<filename>", methods=["GET"])
@login_required
def api_download_script(scan_id: str, filename: str):
    """下载生成的加固/回滚脚本。"""

@api_bp.route("/scan/<task_id>/stream", methods=["GET"])
@login_required
def api_scan_stream(task_id: str):
    """SSE 实时推送扫描进度。"""
```

### 修改的模板
- `base.html`：主题切换按钮 + JS
- `dashboard.html`：SSE 替换轮询 + 搜索筛选
- `harden.html`：下载按钮
- `report.html`：脚本下载按钮（底部操作区）
- `style.css`：CSS 变量 + 暗色主题 + 搜索框样式 + 进度条样式

---

## 代码规范
- Python 3.10+ 类型标注，中文注释
- JS 使用 `async/await` + `fetch`，不引入 jQuery
- CSS 使用 CSS 变量，不引入 CSS 框架
- 所有 Flask 端点：鉴权 + 异常处理 + 审计日志
- 模板引擎：Jinja2（Flask 默认）
- 不新增 Python 或 JS 依赖

## 输出文件
只修改/创建以下文件（共 6 个）：
1. `lightshield/web/routes.py` — 新增 2 个 API 端点
2. `lightshield/web/templates/base.html` — 主题切换
3. `lightshield/web/templates/dashboard.html` — SSE + 搜索
4. `lightshield/web/templates/harden.html` — 下载按钮
5. `lightshield/web/templates/report.html` — 脚本下载入口
6. `lightshield/web/static/style.css` — 暗色主题 + CSS 变量 + 新组件样式

## 验收标准
- 加固脚本下载：生成后点击下载按钮 → 浏览器下载 .sh/.ps1 文件
- SSE 进度：提交扫描 → 实时看到端口数/发现数变化 → 完成后自动显示报告链接
- 主题切换：点击切换按钮 → 亮/暗切换 → 刷新后保持偏好
- 搜索筛选：输入关键词 → 实时过滤历史 → URL 参数同步
- 不破坏现有功能：登录/扫描/报告查看/加固建议 全流程正常
- 所有新增 API 端点有 CSRF 保护（GET 请求除外）
