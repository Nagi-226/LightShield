你是 LightShield 项目的知识架构师（ZCode 3.0 + GLM-5.2）。本任务为 **v0.0.39 — OpenAPI 文档生成**。

---

## 一、项目上下文

LightShield（轻盾）是开源轻量化安全自检 + 防御加固工具，Python 3.10+，MIT 协议。
当前版本 v0.0.38，本版本 v0.0.39。完整项目信息在 `CLAUDE.md`。

Web API 基于 Flask，应用工厂在 `lightshield/web/app.py` 的 `create_app()`，
所有 REST 端点注册在 `lightshield/web/routes.py`（蓝图 `api_bp`，统一前缀 `/api`），
鉴权逻辑在 `lightshield/web/auth.py`，安全头/CSRF/限流在 `app.py`。

默认服务地址：`http://127.0.0.1:5000`（config.web_host / web_port）。

---

## 二、⚠️ 合规约束（不可违反）

- R1 禁止对外主动攻击　R2 禁止批量扫描公网 IP 段　R3 禁止远控/后门/木马
- R4 仅允许自查自有资产　R5 MSF 仅 auxiliary/scanner　R6 扫描频率限制
- **R7（GLM-5.2 专属）**：充分利用 1M 上下文，**一次性读取** `routes.py` / `auth.py` / `app.py` / `pages.py` 全文，不要分片读取。
- 本任务**只产出文档**，**严禁修改任何 `.py` 源码**，**严禁新增依赖**。Swagger UI 的路由接线和 CSP 调整由 Claude Code 负责，**不属于你的范围**。

---

## 三、任务目标

为 LightShield 的 8 个 REST 端点生成 **OpenAPI 3.0.3 规范**和**人类可读 API 参考文档**。

### 产出文件（仅 2 个，均为文档产物）

1. **`lightshield/web/static/openapi.json`** —— 机器可读的 OpenAPI 3.0.3 规范（合法 JSON）
2. **`docs/API.md`** —— 人类可读的中文 API 参考（与 openapi.json 内容一致）

> 放在 `static/` 下是为了让 Flask 自动以 `/static/openapi.json` 提供，CC 后续接 Swagger UI 时直接引用，你**不需要**写任何路由。

---

## 四、端点权威清单（Ground Truth — 以此为准，并与源码逐一核对）

> ⚠️ 下表是从源码提取的权威事实。请逐条与 `routes.py` / `auth.py` 核对。**若发现任何不一致，不要自行编造或猜测——在 `docs/API.md` 末尾的「核对说明」里列出差异，交 Claude Code 裁决。**

通用响应信封：
- 成功：各端点不同（见下）
- 失败：`{"error": true, "message": "<中文说明>", "code": <HTTP状态码>}`

通用约束：
- **所有 `/api/*` 端点**都受**速率限制**（每 IP 每小时 `config.rate_limit_per_hour`，默认 100 次），超限返回 `429`。
- 鉴权方式 = Flask **Session 签名 Cookie**（登录后下发）。需登录端点未登录时返回 `401`。
- 对**已登录用户**的**非安全方法（POST 等）**需携带 **CSRF Token**（请求头 `X-CSRF-Token`，值来自页面 `<meta name="csrf-token">`）。`/api/login`、`/api/logout` 为 CSRF 豁免。

| # | 方法 | 路径 | 鉴权 | 请求 | 成功响应 | 错误 |
|--|------|------|:--:|------|---------|------|
| 1 | POST | `/api/login` | 公开 | JSON `{username:string, password:string}` | `200 {success:true, message:"登录成功"}` | 400 请求体空/缺字段；401 用户名或密码错误；429 |
| 2 | POST | `/api/logout` | 公开 | 无 | `200 {success:true, message:"已登出"}` | 429 |
| 3 | POST | `/api/scan` | 需登录+CSRF | JSON `{target:string(必填), scan_types?:string[], confirm_ownership?:boolean}` | `202 {task_id:string, status:"accepted", target:string}` | 400 缺 target / R2 违规(`[R2 违规] ...`)；401；500 提交失败；429 |
| 4 | GET | `/api/scan/{task_id}` | 需登录 | 路径参数 task_id | `200 {task_id, status, target, ...}`（状态机：pending/running/completed/partial/failed） | 404 任务不存在；401；429 |
| 5 | GET | `/api/scan/{task_id}/stream` | 需登录 | 路径参数 task_id | `200 text/event-stream`（SSE）。事件：默认(进度快照 JSON)、`done`(完成)、`error`、`timeout`(20s 超时) | 401；429 |
| 6 | GET | `/api/report/{scan_id}` | 需登录 | 路径 scan_id + query `format=markdown\|text\|pdf`（默认 markdown） | `200` markdown/text→`text/plain; charset=utf-8`；pdf→`application/pdf`(attachment) | 404 记录不存在；409 扫描未完成；500；401；429 |
| 7 | POST | `/api/harden/{scan_id}` | 需登录+CSRF | JSON 或 form `{os_platform:"linux"\|"windows", confirm_ownership:boolean}` | `200 {success:true, generated:true, action_count:int, script_path, rollback_path, script_filename, rollback_filename, status, message}`；或无风险项 `200 {success:true, generated:false, message:"未发现需要加固的风险项"}` | 400 os 非法 / R4 未确认(`[R4] ...`)；404；500；401；429 |
| 8 | GET | `/api/script/{scan_id}/{filename}` | 需登录+CSRF+R4 | 路径 scan_id+filename；CSRF 经 `X-CSRF-Token` 头或 `?_csrf_token=` 查询参数 | `200 application/octet-stream`（脚本文件下载，attachment） | 400 文件名不在白名单(`harden_*.sh/.ps1`、`rollback_*.sh/.ps1`)；403 CSRF 失败 / R4 未确认；404 文件不存在；401；429 |

> 备注：页面路由（`/`、`/dashboard`、`/report/<id>`、`/harden/<id>`，蓝图 `pages_bp`）渲染 HTML，**不是 REST API**，**不纳入** openapi.json，可在 `docs/API.md` 末尾用一句话说明它们是浏览器页面。

---

## 五、openapi.json 结构要求（OpenAPI 3.0.3）

请按以下分步生成（**每步都要做，勿跳过**）：

1. `openapi: "3.0.3"`
2. `info`: `title:"LightShield 轻盾 API"`、`version:"0.0.39"`、`description`（中文，一段：说明这是本地/内网安全自检 API，仅用于已授权资产）、`license:{name:"MIT"}`
3. `servers`: `[{"url":"http://127.0.0.1:5000","description":"本地默认"}]`
4. `tags`: `鉴权`、`扫描`、`报告`、`加固`（中文 name + description）
5. `components.securitySchemes`:
   - `sessionCookie`: `{type:"apiKey", in:"cookie", name:"session", description:"Flask 签名 Session Cookie，登录后下发"}`
   - `csrfToken`: `{type:"apiKey", in:"header", name:"X-CSRF-Token", description:"已登录用户的非安全方法需携带"}`
6. `components.schemas`：至少定义
   - `ErrorEnvelope` `{error:boolean, message:string, code:integer}`
   - `LoginRequest`、`LoginResponse`
   - `ScanRequest`（target 必填；scan_types 数组可空；confirm_ownership 布尔默认 false）、`ScanAccepted`、`ScanStatus`
   - `HardenRequest`、`HardenResult`
   每个 schema 字段都要有中文 `description` 和 `example`。
7. `paths`：逐一写入第四节的 8 个端点。每个端点必须包含：
   - `tags`、`summary`（中文）、`description`（中文，说明用途和合规点，如 R2/R4）
   - `parameters`（路径/查询参数，含类型与 example）
   - `requestBody`（POST，引用 schema）
   - `responses`：列出该端点**所有**状态码（含 401/429 等通用错误，引用 `ErrorEnvelope`）
   - `security`：公开端点为 `[]`；需登录端点 `[{sessionCookie:[]}]`；需 CSRF 的再加 `csrfToken`
8. 全文必须是**合法可解析 JSON**（你的强项：100% JSON 合法率），2 空格缩进，UTF-8，中文不转义（直接写中文字符）。

---

## 六、docs/API.md 结构要求

中文 Markdown，人类可读，与 openapi.json 同源：
1. 标题 + 一段总览（基址、鉴权方式、CSRF、限流、错误信封格式）
2. 「鉴权流程」小节：登录→拿 Session Cookie→非安全请求带 X-CSRF-Token
3. 按 4 个 tag 分组，每个端点一个小节：方法+路径、用途、请求示例（`curl` 命令）、响应示例（JSON）、错误码表
4. 末尾「页面路由说明」一句话 + 「核对说明」（列出与源码的任何差异，没有则写"已逐条核对，无差异"）

---

## 七、代码/产出规范

- 中文注释/描述，面向非英语用户
- **不修改任何 .py 文件**，**不新增依赖**，**不写路由**（接线是 CC 的事）
- 不编造端点/字段：一切以第四节 + 源码核对为准，存疑列入「核对说明」
- 产出经 Claude Code 验收后合入

---

## 八、验收标准

1. [ ] `lightshield/web/static/openapi.json` 是合法 OpenAPI 3.0.3，可被 swagger 解析器/`json.load` 无错加载
2. [ ] 8 个端点**全部**入册，路径/方法/参数/响应码与第四节一致
3. [ ] securitySchemes（sessionCookie + csrfToken）+ ErrorEnvelope 等 schema 完整，字段含中文 description
4. [ ] `docs/API.md` 覆盖 8 端点，每个含 curl 示例 + 响应示例 + 错误码
5. [ ] 未修改任何 .py 源码、未新增依赖
6. [ ] 「核对说明」列出与源码的差异（或声明无差异）

---

## 九、调用方式

```bash
zcode exec "$(cat .cluster/tasks/pending/ZCODE-v039-openapi.md)"
```
