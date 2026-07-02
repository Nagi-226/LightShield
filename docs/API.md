# LightShield 轻盾 — API 参考

> **版本**：v0.0.39（对应 OpenAPI 规范 `lightshield/web/static/openapi.json`）
> **机器可读规范**：`http://127.0.0.1:5000/static/openapi.json`（Swagger UI 接线由 Claude Code 后续完成，不属于本版范围）
> **适用对象**：LightShield Web API 的集成方、自动化脚本作者、二次开发者。

---

## 总览

### 基址

```
http://127.0.0.1:5000
```

由配置项 `config.web_host` / `config.web_port` 决定，默认 `127.0.0.1:5000`。生产部署建议置于反向代理（Nginx 等）之后。

### 鉴权方式

**Flask 签名 Session Cookie**。调用 `POST /api/login` 成功后，服务端下发名为 `session` 的签名 Cookie，后续所有需登录端点都需携带该 Cookie（HTTP 客户端的 Cookie Jar 通常会自动管理）。

- 默认凭证：`admin` / `lightshield`，可由环境变量 `LS_WEB_USERNAME` / `LS_WEB_PASSWORD` 覆盖。
- Session 有效期 8 小时，Cookie 带 `HttpOnly` + `SameSite=Lax` 标志。
- 同一 IP 连续登录失败 5 次后进入**指数退避锁定期**（2s → 4s → 8s → ... → 最长 64s）。

### CSRF 防护

已登录用户的**非安全方法**（POST / PUT / DELETE / PATCH）必须额外携带 CSRF 令牌：

- 请求头：`X-CSRF-Token: <令牌>`
- 令牌来源：任意已登录页面的 `<meta name="csrf-token" content="...">`，或会话首次访问时写入 `session._csrf_token`。

豁免端点：`POST /api/login`、`POST /api/logout`。GET 下载端点 `/api/script/...` 另有查询参数回退通道（见下）。

### 速率限制

所有 `/api/*` 端点均受**每 IP 每小时速率限制**，默认 100 次/小时（`config.rate_limit_per_hour`，可配置）。超限返回：

```json
{ "error": true, "message": "请求过于频繁，每小时限制 100 次", "code": 429 }
```

### 错误信封

所有失败响应统一格式：

```json
{ "error": true, "message": "<中文说明>", "code": <HTTP 状态码> }
```

`code` 字段恒等于 HTTP 响应行状态码。

### 合规红线（R1–R6）

- **R1** 禁止主动攻击；**R2** 禁止批量扫描公网 IP 段（单目标校验）；**R3** 禁止远控/后门；
- **R4** 仅允许自查自有资产（加固/下载需所有权确认）；**R5** MSF 仅 `auxiliary/scanner`；**R6** 扫描频率限制。

---

## 鉴权流程

```
1. POST /api/login            → 拿到 session Cookie
2. 访问任意已登录页面（或读 <meta>）→ 拿到 CSRF 令牌
3. POST /api/scan 等非安全方法   → 带上 Cookie + X-CSRF-Token
4. GET  类端点                   → 仅需 Cookie
5. POST /api/logout            → 注销
```

---

## 端点目录

| # | 方法 | 路径 | 鉴权 | 所属分组 |
|---|------|------|:--:|------|
| 1 | POST | `/api/login` | 公开 | 鉴权 |
| 2 | POST | `/api/logout` | 公开 | 鉴权 |
| 3 | POST | `/api/scan` | 登录 + CSRF | 扫描 |
| 4 | GET | `/api/scan/{task_id}` | 登录 | 扫描 |
| 5 | GET | `/api/scan/{task_id}/stream` | 登录 | 扫描 |
| 6 | GET | `/api/report/{scan_id}` | 登录 | 报告 |
| 7 | POST | `/api/harden/{scan_id}` | 登录 + CSRF | 加固 |
| 8 | POST | `/api/harden/{scan_id}/verify` | 登录 + CSRF | 加固闭环 |
| 9 | GET | `/api/script/{scan_id}/{filename}` | 登录 + CSRF + R4 | 加固 |

---

# 鉴权

## 1. POST /api/login — 用户登录

**用途**：校验凭证并下发 Session Cookie。CSRF 豁免。

**请求示例**：

```bash
curl -i -c cookies.txt -X POST http://127.0.0.1:5000/api/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"lightshield"}'
```

**成功响应**（`200`）：

```json
{ "success": true, "message": "登录成功" }
```

**错误码**：

| 状态码 | 说明 |
|:--:|------|
| 400 | 请求体为空，或缺少 username / password |
| 401 | 用户名或密码错误，或该 IP 处于登录锁定期 |
| 429 | 触发速率限制 |

---

## 2. POST /api/logout — 用户登出

**用途**：清除 Session。CSRF 豁免。即使未登录也返回 200。

**请求示例**：

```bash
curl -i -b cookies.txt -X POST http://127.0.0.1:5000/api/logout
```

**成功响应**（`200`）：

```json
{ "success": true, "message": "已登出" }
```

**错误码**：

| 状态码 | 说明 |
|:--:|------|
| 429 | 触发速率限制 |

---

# 扫描

## 3. POST /api/scan — 提交扫描任务

**用途**：异步提交扫描任务，立即返回 `task_id`。`target` 经 **R2 双层校验**（API 层 + core 内部），必须是单一 IP 或域名，拒绝 CIDR / 网段 / 通配符。

**请求示例**：

```bash
# 先从页面 meta 取 CSRF 令牌（此处假设为 $TOKEN）
curl -i -b cookies.txt -X POST http://127.0.0.1:5000/api/scan \
  -H "Content-Type: application/json" \
  -H "X-CSRF-Token: $TOKEN" \
  -d '{"target":"192.168.1.10","scan_types":["port_scan","service_detect"],"confirm_ownership":true}'
```

**成功响应**（`202`）：

```json
{
  "task_id": "LS-20260615-153012-a1b2",
  "status": "accepted",
  "target": "192.168.1.10"
}
```

**错误码**：

| 状态码 | 说明 |
|:--:|------|
| 400 | 请求体为空 / 缺 target / R2 校验失败（消息以 `[R2 违规]` 开头） |
| 401 | 未登录 |
| 403 | CSRF 校验失败 |
| 500 | 扫描提交失败（core 异常） |
| 429 | 触发速率限制 |

---

## 4. GET /api/scan/{task_id} — 查询扫描状态

**用途**：返回任务当前状态快照。状态机：`pending → running → completed / partial / failed`（另有 `cancelled`）。

**请求示例**：

```bash
curl -i -b cookies.txt http://127.0.0.1:5000/api/scan/LS-20260615-153012-a1b2
```

**成功响应**（`200`）：

```json
{
  "task_id": "LS-20260615-153012-a1b2",
  "status": "running",
  "target": "192.168.1.10",
  "ports": 7,
  "findings": 1
}
```

**错误码**：

| 状态码 | 说明 |
|:--:|------|
| 401 | 未登录 |
| 404 | 任务不存在 |
| 429 | 触发速率限制 |

> 💡 推荐改用下方的 SSE 端点实时订阅进度，避免高频轮询。

---

## 5. GET /api/scan/{task_id}/stream — 订阅扫描进度（SSE）

**用途**：以 Server-Sent Events 推送进度快照，每 0.5 秒一帧。

**事件类型**：

| event | 含义 |
|------|------|
| （默认 `data`） | 进度快照 JSON，含 `status` / `ports` / `findings` 等 |
| `done` | 扫描进入终态（completed / partial / failed），连接随后关闭 |
| `timeout` | 连接达 20 秒仍未完成，连接关闭 |
| `error` | 任务不存在（404）或状态读取异常（500），连接关闭 |

**请求示例**：

```bash
curl -N -b cookies.txt http://127.0.0.1:5000/api/scan/LS-20260615-153012-a1b2/stream
```

**成功响应**（`200`，`text/event-stream`）：

```
data: {"task_id":"LS-20260615-153012-a1b2","status":"running","ports":7,"findings":1}

event: done
data: {"task_id":"LS-20260615-153012-a1b2","status":"completed","ports":12,"findings":3}

```

**错误码**：

| 状态码 | 说明 |
|:--:|------|
| 401 | 未登录（在 SSE 建立前以 JSON 返回） |
| 429 | 触发速率限制 |

---

# 报告

## 6. GET /api/report/{scan_id} — 获取扫描报告

**用途**：按指定格式返回报告。仅 `completed` / `partial` 状态的扫描可生成报告，其余返回 409。

**查询参数**：

| 参数 | 必填 | 默认 | 取值 |
|------|:--:|------|------|
| `format` | 否 | `markdown` | `markdown` / `text` / `pdf`（非法值回退 markdown） |

**请求示例**：

```bash
# Markdown
curl -b cookies.txt http://127.0.0.1:5000/api/report/LS-20260615-153012-a1b2

# PDF（下载附件）
curl -b cookies.txt -OJ http://127.0.0.1:5000/api/report/LS-20260615-153012-a1b2?format=pdf
```

**成功响应**（`200`）：

- `markdown` / `text` → `Content-Type: text/plain; charset=utf-8`，正文为报告文本。
- `pdf` → `Content-Type: application/pdf`，`Content-Disposition: attachment; filename="lightshield-<scan_id>.pdf"`。

**错误码**：

| 状态码 | 说明 |
|:--:|------|
| 401 | 未登录 |
| 404 | 扫描记录不存在 |
| 409 | 扫描尚未完成（消息含当前状态） |
| 500 | 仓库初始化 / 数据解析 / 报告生成失败 |
| 429 | 触发速率限制 |

---

# 加固

## 7. POST /api/harden/{scan_id} — 生成加固与回滚脚本

**用途**：基于扫描结果，由规则引擎推荐加固项并生成脚本。**R4 约束**：`confirm_ownership` 必须为真值（`true` / `"true"` / `"1"` / `"yes"` / `"on"`）。成功后会向 Session 写入 `harden_confirmed_at`，供脚本下载端点复用校验。请求体接受 JSON 或表单。

**请求示例**：

```bash
curl -i -b cookies.txt -X POST http://127.0.0.1:5000/api/harden/LS-20260615-153012-a1b2 \
  -H "Content-Type: application/json" \
  -H "X-CSRF-Token: $TOKEN" \
  -d '{"os_platform":"linux","confirm_ownership":true}'
```

**成功响应**（`200`，已生成）：

```json
{
  "success": true,
  "generated": true,
  "action_count": 5,
  "script_path": "reports/harden_192_168_1_10_20260615-153012.sh",
  "rollback_path": "reports/rollback_192_168_1_10_20260615-153012.sh",
  "script_filename": "harden_192_168_1_10_20260615-153012.sh",
  "rollback_filename": "rollback_192_168_1_10_20260615-153012.sh",
  "status": "success",
  "message": "已生成 5 条加固操作"
}
```

**成功响应**（`200`，无风险项）：

```json
{ "success": true, "generated": false, "message": "未发现需要加固的风险项", "code": 200 }
```

**错误码**：

| 状态码 | 说明 |
|:--:|------|
| 400 | `os_platform` 非 `linux`/`windows`；或 R4 未确认（消息以 `[R4]` 开头） |
| 401 | 未登录 |
| 403 | CSRF 校验失败 |
| 404 | 扫描记录不存在 |
| 500 | 仓库读取 / 脚本生成失败 |
| 429 | 触发速率限制 |

---

# 加固闭环

## 8. POST /api/harden/{scan_id}/verify — 触发加固闭环（v0.0.40+）

**用途**：触发 `core.run_harden_closed_loop()`，执行扫描→推荐→生成→执行→复扫→验证全链路。支持 DRY_RUN（预检，不改系统）和 APPLY（真机执行，改真实系统）两种模式。

**请求示例**：

```bash
# DRY_RUN 模式（预检，不改系统）
curl -i -b cookies.txt -X POST http://127.0.0.1:5000/api/harden/LS-20260615-153012-a1b2/verify \
  -H "Content-Type: application/json" \
  -H "X-CSRF-Token: $TOKEN" \
  -d '{"mode":"dry_run","os_platform":"linux"}'
```

```bash
# APPLY 模式（真机执行，需双确认）
curl -i -b cookies.txt -X POST http://127.0.0.1:5000/api/harden/LS-20260615-153012-a1b2/verify \
  -H "Content-Type: application/json" \
  -H "X-CSRF-Token: $TOKEN" \
  -d '{"mode":"apply","os_platform":"linux","confirm_ownership":true,"confirm_execute":true}'
```

**请求体**：

| 字段 | 类型 | 必填 | 默认 | 说明 |
|------|------|:--:|------|------|
| `mode` | string | 否 | `dry_run` | `dry_run`（预检）或 `apply`（真机执行） |
| `os_platform` | string | 否 | `linux` | `linux` 或 `windows` |
| `confirm_ownership` | bool | APPLY 必填 | `false` | R4 所有权确认（APPLY 模式必须 `true`） |
| `confirm_execute` | bool | APPLY 必填 | `false` | R4 执行确认（APPLY 模式必须 `true`） |

**成功响应**（`200`，DRY_RUN 完成）：

```json
{
  "target": "192.168.1.10",
  "os_platform": "linux",
  "mode": "dry_run",
  "overall": "generated_only",
  "audit_id": "CL-20260615-160000-a1b2c3",
  "before_scan": {"status": "completed", "findings": [...]},
  "harden": {"status": "generated", "action_count": 5, "script_path": "..."},
  "execution": {"status": "skipped", "sandbox": "dry_run"},
  "after_scan": null,
  "verification": null,
  "success": true,
  "scan_id": "LS-20260615-153012-a1b2"
}
```

**成功响应**（`200`，APPLY 验证通过）：

```json
{
  "target": "192.168.1.10",
  "os_platform": "linux",
  "mode": "apply",
  "overall": "verified",
  "audit_id": "CL-20260615-160500-d4e5f6",
  "before_scan": {"status": "completed", "findings": [...]},
  "harden": {"status": "executed", "action_count": 5},
  "execution": {"status": "success", "exit_code": 0, "duration_seconds": 12.3},
  "after_scan": {"status": "completed", "findings": []},
  "verification": {
    "verdict": "verified",
    "resolved": [{"vuln_type": "high_risk_port", "port": 23}],
    "remaining": [],
    "regressed": []
  },
  "success": true,
  "scan_id": "LS-20260615-153012-a1b2"
}
```

**错误响应**（`422`，APPLY 未通过护栏）：

```json
{
  "target": "192.168.1.10",
  "overall": "failed",
  "execution": {
    "status": "rejected",
    "sandbox": "host",
    "error": "APPLY 需要回滚脚本已就绪（rollback_path 不存在或为空）"
  },
  "success": false,
  "scan_id": "LS-20260615-153012-a1b2"
}
```

**错误码**：

| 状态码 | 说明 |
|:--:|------|
| 400 | `mode` 非 `dry_run`/`apply`；`os_platform` 非法；APPLY 模式缺双确认 |
| 401 | 未登录 |
| 403 | CSRF 校验失败 |
| 404 | 扫描记录不存在 |
| 422 | 闭环执行失败（护栏拒绝 / 执行异常 / 验证失败）—— `overall` 字段为 `failed` |
| 429 | 触发速率限制 |

**overall 字段取值**：

| 值 | 含义 | 适用模式 |
|------|------|:--:|
| `verified` | 复扫确认所有风险已消除 | APPLY |
| `partial` | 部分风险已修复，仍有残留或新增 | APPLY |
| `failed` | 加固未消除任何风险，或执行/护栏拒绝 | APPLY |
| `generated_only` | 仅生成脚本，未执行复扫 | DRY_RUN |

---

## 9. GET /api/script/{scan_id}/{filename} — 下载加固 / 回滚脚本

**用途**：下载之前由 `/api/harden` 生成的脚本文件。**三重校验**：

1. **文件名白名单**：必须匹配 `harden_*.sh`、`harden_*.ps1`、`rollback_*.sh`、`rollback_*.ps1`。
2. **CSRF**：通过 `X-CSRF-Token` 请求头，或查询参数 `?_csrf_token=` / `?csrf_token=` 传入（后者用于浏览器原生 `<a download>` 链接，无法设 header 时的回退）。
3. **R4**：`session.harden_confirmed_at` 必须存在（即先调用过 `/api/harden` 并通过 R4）。

文件以 `application/octet-stream` + `Content-Disposition: attachment` 形式返回。

**请求示例**：

```bash
# 方式 A：header 传 CSRF
curl -b cookies.txt -OJ \
  -H "X-CSRF-Token: $TOKEN" \
  http://127.0.0.1:5000/api/script/LS-20260615-153012-a1b2/harden_192_168_1_10_20260615-153012.sh

# 方式 B：查询参数传 CSRF（浏览器链接回退）
curl -b cookies.txt -OJ \
  "http://127.0.0.1:5000/api/script/LS-20260615-153012-a1b2/harden_192_168_1_10_20260615-153012.sh?_csrf_token=$TOKEN"
```

**成功响应**（`200`）：二进制脚本流，`Content-Type: application/octet-stream`。

**错误码**：

| 状态码 | 说明 |
|:--:|------|
| 400 | 文件名不在白名单内 |
| 401 | 未登录 |
| 403 | CSRF 校验失败 / R4 未确认 |
| 404 | 文件不存在 |
| 429 | 触发速率限制 |

---

## 页面路由说明

除上述 8 个 REST 端点外，LightShield 还提供 4 个**浏览器页面**（蓝图 `pages_bp`，渲染 HTML，**非 REST API**，不纳入本规范）：`GET /`、`GET /dashboard`、`GET /report/{scan_id}`、`GET /harden/{scan_id}`。它们用于图形界面操作，未登录时重定向到登录页。

---

## 核对说明

> 本节列出与源码逐条核对的结果。Ground truth 来自任务文件 `.cluster/tasks/pending/ZCODE-v039-openapi.md` 第四节，源码核对范围为 `lightshield/web/routes.py` / `auth.py` / `app.py` / `csrf.py` 以及 `lightshield/utils/constants.py`。

### 一致项（已逐行核对，无差异）

- ✅ **速率限制覆盖范围**：`app.py` 的 `_rate_limit` 钩子作用于 `request.endpoint.startswith("api.")`，即所有 8 个 `/api/*` 端点，超限返回 429——与清单一致。
- ✅ **login / logout CSRF 豁免**：两者均标注 `@csrf_exempt`，`csrf.py` 的 `is_csrf_exempt()` 据此放行——一致。
- ✅ **scan 的 R2 双层校验 + 202 返回**：`routes.py:128` 先做 `TargetValidator.validate`，core 内部再做一次；成功返回 `{task_id,status:"accepted",target}` + 202——一致。
- ✅ **report 409 条件**：仅 `completed` / `partial` 可生成报告，其余返回 409——一致。
- ✅ **report format 回退**：`markdown/text/pdf` 之外的值回退为 `markdown`——一致。
- ✅ **report PDF 附件头**：`Content-Type: application/pdf` + `Content-Disposition: attachment; filename="lightshield-<scan_id>.pdf"`——一致。
- ✅ **harden 请求体双通道**：`request.get_json(silent=True) or request.form.to_dict()` 同时支持 JSON 与表单——一致。
- ✅ **harden R4 失败返回 400**（消息 `[R4] 请先确认目标所有权或授权范围`）：`routes.py:310`——一致。
- ✅ **script 三重校验与白名单模式**：`harden_*.sh`、`harden_*.ps1`、`rollback_*.sh`、`rollback_*.ps1`，且拒绝路径分隔符 `/` `\`——一致。
- ✅ **script R4 / CSRF 失败返回 403**：`routes.py:377`（CSRF）、`routes.py:381`（R4）——一致。

### 与清单的细微出入（已据源码修正入册，无需裁决）

1. **ScanStatus 状态机多一个 `cancelled`**：
   - 清单第四节第 4 行只列 `pending/running/completed/partial/failed`；
   - 源码 `lightshield/utils/constants.py` 的 `ScanStatus` 枚举实际还含 `cancelled`。
   - **处理**：`openapi.json` 的 `ScanStatus.status` 枚举已补入 `cancelled`，`docs/API.md` 第 4 节文字同步说明。不影响接口契约，仅更完整。

2. **script 下载端点 CSRF 回退通道不止 `?_csrf_token=` 一个**：
   - 清单第四节第 8 行写「`X-CSRF-Token` 头 或 `?_csrf_token=` 查询参数」；
   - 源码 `routes.py:423` `_validate_download_csrf()` 实际接受 **4 个来源**：`X-CSRF-Token` 头、`?_csrf_token=`、`?csrf_token=`、表单字段 `_csrf_token`。
   - **处理**：`openapi.json` 与 `docs/API.md` 第 8 节已如实列全 4 个通道（其中查询参数两个、表单一个）。这是源码更宽松，对清单是**超集兼容**，不构成破坏性差异。

3. **harden 成功响应在「无风险项」分支额外携带 `code: 200`**：
   - 清单第 7 行的无风险项响应示例只有 `{success, generated:false, message}`；
   - 源码 `routes.py:330` 实际多返回一个 `"code": 200` 字段。
   - **处理**：`openapi.json` 的 `no_risk` 示例与 `docs/API.md` 已保留该 `code` 字段，与源码一致。`HardenResult` schema 未把 `code` 列为必填（因为它是可选附加字段）。

### 结论

除上述 3 处**源码更完整 / 更宽松**的细微出入（均已据源码修正入册，属超集兼容，无破坏性）外，**8 个端点的方法 / 路径 / 参数 / 响应码 / 鉴权要求与任务清单完全一致**。本任务未发现需要 Claude Code 裁决的冲突。

---

## 附录：合规要求速查

| 端点 | 涉及红线 | 实现要点 |
|------|:--:|------|
| `/api/scan` | R2, R6 | 单目标校验（API 层 + core 双层）；频率限制 |
| `/api/harden/{scan_id}` | R4 | `confirm_ownership` 必须真值；写入 `harden_confirmed_at` |
| `/api/harden/{scan_id}/verify` | R4, R6 | APPLY 模式双确认；DRY_RUN-first 前置；rollback 就绪检查 |
| `/api/script/{scan_id}/{filename}` | R4 | 文件名白名单 + CSRF + `harden_confirmed_at` 三重校验 |
| 全部 `/api/*` | R6 | 每 IP 每小时速率限制，默认 100 次 |

---

## 附录：完整错误码表

| HTTP 状态码 | 含义 | 触发场景 |
|:--:|------|------|
| **200** | 成功 | 所有 GET 端点 + 部分 POST 成功 |
| **202** | 已接受（异步处理） | `POST /api/scan` 提交扫描任务 |
| **400** | 请求格式错误 | 请求体为空 / 缺少必填字段 / 字段值非法 / R2 校验失败 / R4 未确认 |
| **401** | 未认证 | 未登录或 Session 过期 |
| **403** | 禁止访问 | CSRF 校验失败 / R4 未确认（脚本下载） |
| **404** | 资源不存在 | 任务 ID / 扫描 ID / 脚本文件不存在 |
| **409** | 冲突 | 扫描未完成无法生成报告 |
| **422** | 不可处理实体 | 加固闭环执行失败（护栏拒绝 / 执行异常 / 验证失败） |
| **429** | 请求过多 | 触发速率限制（每 IP 每小时 100 次） |
| **500** | 服务器内部错误 | 仓库初始化 / 数据解析 / 报告生成 / 脚本生成失败 |

### 错误信封统一格式

所有失败响应遵循：

```json
{
  "error": true,
  "message": "<中文错误说明>",
  "code": <HTTP 状态码>
}
```

**特殊情况**：`/api/harden/{scan_id}/verify` 的 `422` 响应额外包含闭环结果字段（`target` / `overall` / `execution` / `audit_id` 等），以便前端展示失败详情。`error` 字段仍为 `true`。

### 合规相关错误消息前缀

| 前缀 | 含义 | 示例 |
|------|------|------|
| `[R2 违规]` | 目标校验失败 | `[R2 违规] 拒绝 CIDR 网段` |
| `[R4]` | 所有权未确认 | `[R4] 请先确认目标所有权或授权范围` |

带有这些前缀的错误消息表示请求触发了合规红线拦截，需修正输入或完成所有权确认后重试。
