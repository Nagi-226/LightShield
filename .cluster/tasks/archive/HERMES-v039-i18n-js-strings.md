你是 LightShield 项目的工具链 + 基础设施专家，使用 **DeepSeek-V4-Flash** 模型。本任务为 **v0.0.39 — i18n JS 运行时字符串补库（第二批）**。

---

## 一、背景（一句话）

上一批（`HERMES-v039-i18n-locale.md`）已把**静态模板**字符串抽进 `zh-CN.json` / `en-US.json` 并通过验收。但仪表板等页面的 **JavaScript 运行时字符串**（状态提示、客户端校验、插值文案）还没入册。本任务把 CC 从源码提取好的这批 JS 字符串**翻译 + 格式化**成一个**追加片段文件**，由 CC 合并进正式 locale。

> 你**只产出 1 个片段 JSON 文件**。**不要改 `zh-CN.json` / `en-US.json` 本身**（合并由 CC 做，避免误删已有键）。**不改任何 .py / .html，不新增依赖。**

---

## 二、⚠️ 合规约束

R1 禁攻击 / R2 禁批量扫公网 / R3 禁远控后门 / R4 仅自查 / R5 MSF 白名单 / R6 频率限制。
纯数据文件，保持中性。**涉及 R4 的文案按第五节中文原文逐字保留**，英文译文务必保住"所有权 / 授权"语义。

---

## 三、产出文件（1 个新文件）

`lightshield/web/locales/_additions-v039.json`

顶层两个键 `"zh-CN"` 与 `"en-US"`，各自是**嵌套命名空间对象**（与正式 locale 同结构），只包含本批**新增**键：

```json
{
  "zh-CN": {
    "dashboard":{ "...": "..." },
    "report":   { "...": "..." },
    "harden":   { "...": "..." }
  },
  "en-US": {
    "dashboard":{ "...": "..." },
    "report":   { "...": "..." },
    "harden":   { "...": "..." }
  }
}
```

- `zh-CN` 各值 = 第五节的中文原文，**逐字复制，一个标点都不改**（含中文逗号 `，`、`...`、`或`/`和` 的区别、R4 字样）。
- `en-US` 各值 = 对应英文。第五节已给 EN 种子；你**校对 / 润色**，确认无误即采用；语义不确定（尤其 R4 那条）保留 EN 种子并加同级 `"<key>__review": true` 标记交 CC 复核。
- 2 空格缩进，UTF-8，中英文直接写字符（不要 `\uXXXX`）。

---

## 四、文件结构规范

- 嵌套对象（点号 → 嵌套）：`dashboard.err_no_target` → `{"dashboard":{"err_no_target":"..."}}`
- 不要 `_meta`（这是片段，不是完整 locale）。
- 只放第五节列出的键，**不要**添加其它键，**不要**重复已有静态键。

---

## 五、字符串清单（键 → 中文原文 → EN 种子）

> 中文逐字复制到 `zh-CN`；EN 种子校对后放 `en-US`。带 `{xxx}` 的是**插值占位符**，原样保留（前端用 `tf()` 替换），**不要翻译占位符名**。

```
dashboard.unknown_target          = "未知目标"
   en: "Unknown target"
dashboard.detail_progress         = "目标 {target}，端口 {ports}，发现 {findings}"
   en: "Target {target}, ports {ports}, findings {findings}"
dashboard.err_no_target           = "请输入目标地址"
   en: "Please enter a target address"
dashboard.err_target_space        = "目标地址不能包含空格"
   en: "Target address must not contain spaces"
dashboard.err_target_url          = "请填写域名或 IP，不要包含 URL 协议"
   en: "Enter a domain or IP, without a URL scheme"
dashboard.err_target_path         = "请填写单个 IP 或域名，不要包含路径、CIDR 或查询参数"
   en: "Enter a single IP or domain, without paths, CIDR, or query parameters"
dashboard.err_target_wildcard     = "不支持通配符域名"
   en: "Wildcard domains are not supported"
dashboard.err_target_range        = "不支持 IP 范围"
   en: "IP ranges are not supported"
dashboard.err_status_query        = "查询扫描状态失败"
   en: "Failed to query scan status"
dashboard.err_status_timeout      = "扫描状态查询超时，请稍后刷新仪表板。"
   en: "Scan status query timed out. Please refresh the dashboard later."
dashboard.timeout_title           = "进度监听超时"
   en: "Progress stream timed out"
dashboard.timeout_detail          = "扫描仍在后台运行，请稍后查看历史记录。"
   en: "The scan is still running in the background. Check the history later."
dashboard.err_sse_connect         = "扫描进度连接失败"
   en: "Scan progress connection failed"
dashboard.sse_interrupt_title     = "SSE 中断"
   en: "SSE interrupted"
dashboard.sse_interrupt_detail    = "自动切换为轮询查询。"
   en: "Falling back to polling."
dashboard.scan_fail_title         = "扫描失败"
   en: "Scan failed"
dashboard.records_count           = "{visible}/{total} 条记录"
   en: "{visible}/{total} records"
dashboard.err_r4                  = "R4 合规要求：请先确认目标所有权或授权范围。"   ← 注意是「或」，与 harden 的「和」不同；逐字复制
   en: "R4 compliance requirement: please confirm target ownership or authorization scope first."   ← R4 项，建议加 __review
dashboard.submitting              = "提交中..."
   en: "Submitting..."
dashboard.status_submitting_title = "正在提交"
   en: "Submitting"
dashboard.status_submitting_detail= "请求已发送到 LightShield API。"
   en: "Request sent to the LightShield API."
dashboard.err_submit_fail         = "扫描提交失败"
   en: "Scan submission failed"
dashboard.status_scanning_title   = "扫描中"
   en: "Scanning"
dashboard.status_scanning_detail  = "任务 {task_id} 已创建，正在接收实时进度。"
   en: "Task {task_id} created; receiving live progress."

report.err_load                   = "报告加载失败"
   en: "Failed to load report"

harden.err_generate               = "脚本生成失败"
   en: "Script generation failed"
```

---

## 六、约束（Flash 特化）

- 只做**翻译校对 + 格式化**，不抽象、不设计、不预留、不动其它文件。
- 键名严格用第五节给的（点号转嵌套）。
- zh-CN 值逐字复制；EN 不确定项保留种子 + `__review` 标记。
- 输出文件必须合法可 `json.load`，顶层恰好 `zh-CN` / `en-US` 两键，两边键集合完全一致。

---

## 七、验收标准

1. [ ] `_additions-v039.json` 合法 JSON，顶层 `zh-CN` / `en-US` 两键，两边嵌套键集合完全一致
2. [ ] 共 26 个数据键（dashboard 24 + report 1 + harden 1）
3. [ ] zh-CN 值与第五节逐字一致（含「或/和」、中文标点、`{占位符}`）
4. [ ] en-US 全部有译；R4 等不确定项带 `__review`
5. [ ] 未改动 `zh-CN.json` / `en-US.json` / 任何 .py / .html，未新增依赖

---

## 八、调用方式

```bash
hermes -m deepseek-v4-flash -z "$(cat .cluster/tasks/pending/HERMES-v039-i18n-js-strings.md)"
```
