你是 LightShield 项目的工具链 + 基础设施专家，使用 **DeepSeek-V4-Flash** 模型。本任务为 **v0.0.39 — i18n locale 骨架**。

---

## 一、背景（一句话）

LightShield Web 仪表板目前所有界面文字硬编码为中文。v0.0.39 要做中英文切换，第一步是把界面文字抽进 locale 文件。**这一步就是你的任务**：把下面已经整理好的字符串清单，格式化成两个 JSON 文件。

> 你**只产出 2 个 JSON 数据文件**。i18n 接线（`t()` 函数、模板改造、语言选择）由 Claude Code 负责，**不是你的范围**。**不要改任何 .py 或 .html 文件，不要新增依赖。**

---

## 二、⚠️ 合规约束

R1 禁攻击 / R2 禁批量扫公网 / R3 禁远控后门 / R4 仅自查 / R5 MSF 白名单 / R6 频率限制。
本任务是纯数据文件，不涉及扫描逻辑，按上述红线保持中性即可。

---

## 三、产出文件（2 个新文件）

1. `lightshield/web/locales/zh-CN.json`
2. `lightshield/web/locales/en-US.json`

两个文件**键完全相同**，只是值不同：
- `zh-CN.json` 的值 = 第五节给你的中文原文（**逐字复制，不要改写**）
- `en-US.json` 的值 = 对应英文翻译（你来译；不确定的加 `"__review": true` 兄弟键标记，交 CC/Codex 复核）

---

## 四、文件结构规范

- 嵌套 JSON，按命名空间分组（`_meta` / `common` / `nav` / `footer` / `login` / `dashboard` / `report` / `harden`）
- 2 空格缩进，UTF-8，中文/英文直接写字符（不要 `\uXXXX` 转义）
- 每个文件顶部加 `_meta`：
  - zh-CN：`{"code":"zh-CN","name":"简体中文","dir":"ltr"}`
  - en-US：`{"code":"en-US","name":"English","dir":"ltr"}`

---

## 五、字符串清单（键 → 中文值；逐字复制到 zh-CN.json）

> 这些是从 5 个模板（base/login/dashboard/report/harden）抽取的**静态界面文字**。en-US 列给了部分种子翻译，其余你补全。

```
common.brand                = "LightShield 轻盾"          (en: "LightShield")
common.console              = "安全自检控制台"            (en: "Security Self-Check Console")
common.target               = "目标"                      (en: "Target")
common.status               = "状态"                      (en: "Status")
common.ports                = "端口"                      (en: "Ports")
common.findings             = "发现"                      (en: "Findings")
common.time                 = "时间"                      (en: "Time")
common.loading              = "加载中"                    (en: "Loading")
common.unknown              = "未知"                      (en: "Unknown")
common.back                 = "返回"                      (en: "Back")
common.all                  = "全部"                      (en: "All")

nav.logout                  = "退出"                      (en: "Log out")
nav.theme_dark              = "深色"                      (en: "Dark")
nav.theme_light             = "亮色"                      (en: "Light")
nav.toggle_dark             = "切换深色主题"              (en: "Switch to dark theme")
nav.toggle_light            = "切换亮色主题"              (en: "Switch to light theme")

footer.notice               = "仅用于已授权资产的安全自检" (en: "For security self-check of authorized assets only")

login.title                 = "轻盾安全自检控制台"        (en: 待译)
login.lead                  = "提交授权目标、跟踪扫描状态，并在浏览器中阅读 Markdown 报告。" (en: 待译)
login.kicker                = "Session 登录"              (en: "Session login")
login.heading               = "进入仪表板"                (en: "Enter dashboard")
login.username              = "用户名"                    (en: "Username")
login.password              = "密码"                      (en: "Password")
login.submit                = "登录"                      (en: "Log in")
login.submitting            = "登录中..."                 (en: "Logging in...")
login.hint                  = "默认凭证：admin / lightshield。生产环境请通过环境变量覆盖。" (en: 待译)
login.error                 = "登录失败，请检查用户名和密码" (en: 待译)

dashboard.title             = "扫描面板"                  (en: "Scan panel")
dashboard.head_note         = "前端执行基础 R2/R4 提示，最终校验仍由 API 层完成。" (en: 待译)
dashboard.new_scan          = "新建扫描"                  (en: "New scan")
dashboard.target_label      = "目标地址"                  (en: "Target address")
dashboard.target_ph         = "127.0.0.1 或 example.com"  (en: "127.0.0.1 or example.com")
dashboard.scan_type         = "扫描类型"                  (en: "Scan type")
dashboard.type_full         = "全量扫描"                  (en: "Full scan")
dashboard.type_asset        = "资产扫描"                  (en: "Asset scan")
dashboard.type_vuln         = "漏洞扫描"                  (en: "Vulnerability scan")
dashboard.confirm_own       = "我确认拥有目标所有权或已获得明确授权" (en: 待译)
dashboard.start             = "开始扫描"                  (en: "Start scan")
dashboard.status_wait       = "等待提交"                  (en: "Awaiting submission")
dashboard.status_detail     = "输入单个 IP 或域名，并完成 R4 授权确认。" (en: 待译)
dashboard.view_report       = "查看报告"                  (en: "View report")
dashboard.harden            = "加固建议"                  (en: "Hardening advice")
dashboard.history           = "扫描历史"                  (en: "Scan history")
dashboard.search            = "搜索"                      (en: "Search")
dashboard.search_ph         = "搜索目标或扫描 ID..."      (en: "Search target or scan ID...")
dashboard.th_scan_id        = "扫描 ID"                   (en: "Scan ID")
dashboard.th_report         = "报告"                      (en: "Report")
dashboard.th_harden         = "加固"                      (en: "Harden")
dashboard.no_match          = "没有匹配的记录"            (en: "No matching records")
dashboard.empty             = "暂无扫描历史"              (en: "No scan history yet")
dashboard.empty_hint        = "完成第一次授权扫描后，最近 20 条记录会显示在这里。" (en: 待译)

report.page_title           = "报告"                      (en: "Report")
report.title                = "扫描报告"                  (en: "Scan report")
report.download_pdf         = "下载 PDF"                  (en: "Download PDF")
report.download_pdf_full    = "下载 PDF 报告"             (en: "Download PDF report")
report.view_harden          = "查看加固建议"              (en: "View hardening advice")
report.loading_md           = "正在加载 Markdown 报告..." (en: "Loading Markdown report...")
report.download_script      = "下载加固脚本"              (en: "Download hardening script")
report.download_rollback    = "下载回滚脚本"              (en: "Download rollback script")
report.load_fail_body       = "无法加载报告，请返回仪表板确认扫描状态。" (en: 待译)

harden.page_title           = "加固建议"                  (en: "Hardening")
harden.title                = "加固操作建议"              (en: "Hardening recommendations")
harden.back_report          = "返回报告"                  (en: "Back to report")
harden.rec_title            = "加固建议列表"              (en: "Recommendation list")
harden.rec_note             = "基于扫描 findings 和规则引擎生成，仅用于脚本生成前审阅。" (en: 待译)
harden.th_severity          = "严重度"                    (en: "Severity")
harden.th_action            = "操作"                      (en: "Action")
harden.th_reason            = "原因"                      (en: "Reason")
harden.none                 = "暂无可生成的加固建议"      (en: 待译)
harden.none_body            = "当前扫描未命中需要生成脚本的风险项。" (en: 待译)
harden.gen_title            = "生成加固脚本"              (en: "Generate hardening script")
harden.os_label             = "目标操作系统"              (en: "Target OS")
harden.confirm_own          = "我确认拥有目标所有权，并授权生成加固脚本（R4）" (en: 待译)
harden.warn_manual          = "LightShield 只生成加固和回滚脚本，不会自动执行命令。请审阅脚本后手动运行。" (en: 待译)
harden.gen_btn              = "生成加固脚本"              (en: "Generate hardening script")
harden.generating           = "生成中..."                (en: "Generating...")
harden.result_gen           = "脚本已生成"                (en: "Script generated")
harden.result_nogen         = "无需生成脚本"              (en: "No script needed")
harden.err_r4               = "R4 合规要求：请先确认目标所有权和授权范围。" (en: 待译)
```

---

## 六、约束（Flash 特化）

- **只做格式化 + 翻译**，不抽象、不设计、不预留。键名严格用第五节给的（点号在 JSON 里转成嵌套对象：`login.title` → `{"login":{"title":...}}`）。
- zh-CN 值**逐字复制**，一个标点都不要改（R4、`...`、中文括号都要保留原样）。
- en-US：能确定的直接译；语义不确定的，把英文写成你的最佳猜测，并在该键加同级 `"<key>__review": true` 标记（例：`"lead":"...","lead__review":true`），方便 CC/Codex 复核。
- 不改任何 .py / .html，不动 pyproject，不新增依赖。
- 两个 JSON 必须合法可 `json.load`。

---

## 七、验收标准

1. [ ] `zh-CN.json` + `en-US.json` 均为合法 JSON，键集合完全一致
2. [ ] 两文件都含正确的 `_meta`
3. [ ] zh-CN 值与第五节逐字一致（含标点）
4. [ ] en-US 全部键有英文值；不确定项带 `__review` 标记
5. [ ] 未改动任何 .py / .html / pyproject，未新增依赖

---

## 八、调用方式

```bash
hermes -m deepseek-v4-flash -z "$(cat .cluster/tasks/pending/HERMES-v039-i18n-locale.md)"
```
