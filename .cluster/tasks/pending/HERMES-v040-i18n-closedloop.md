# HERMES 任务 — v0.0.40 闭环页面 i18n 文案（closed_loop.*）

> **Agent**：Hermes（DeepSeek-V4-Flash，工具链 + 基础设施 + 样板）
> **版本**：v0.0.40 自动加固闭环｜**类型**：i18n locale 补全（中英对称）
> **依赖**：键名与 **Qoder 任务**（Web 对比页）对齐——以页面实际用到的键为准，缺则补齐。
> **冻结接口来源**：`docs/design-v040-closed-loop.md`（正式版）§8；延续 v0.0.39 i18n 体系

---

## 一、项目上下文（简短）

v0.0.39 已建中英双语体系：`lightshield/web/locales/{zh-CN,en-US}.json`（含 `_meta`，键集必须中英对称），运行期 `i18n.py` 加载、模板 `t()` / 前端 `window.t/tf` 消费。v0.0.40 新增「加固+复扫+对比」页面，需补 `closed_loop.*` 文案。

## 二、⚠️ 合规约束（R1-R6）

纯文案任务，不涉执行。注意：APPLY（真改系统）相关文案要**如实传达风险**——所有权确认、二次确认、回滚提示用语准确，不淡化（呼应 R4）。不得出现诱导用户扫描他人资产的措辞。

## 三、接口契约（严格按此）

### 3.1 文件

`lightshield/web/locales/zh-CN.json` 与 `en-US.json` 同步新增 `closed_loop` 命名空间，**两边键集完全对称**（v0.0.39 已有对称校验，勿破）。

### 3.2 必备键集（起步清单，最终以 Qoder 页面为准对齐）

```
closed_loop.title              加固闭环对比 / Hardening Closed-Loop
closed_loop.mode.dry_run       预检模式 / Dry-run
closed_loop.mode.apply         应用模式 / Apply
closed_loop.overall.verified   已验证 / Verified
closed_loop.overall.partial    部分修复 / Partial
closed_loop.overall.failed     未修复 / Failed
closed_loop.overall.generated_only  仅生成（未复扫） / Generated only
closed_loop.col.type           风险类型 / Type
closed_loop.col.port           端口 / Port
closed_loop.col.severity       严重度 / Severity
closed_loop.col.status         状态 / Status
closed_loop.status.resolved    已修复 / Resolved
closed_loop.status.remaining   仍存在 / Remaining
closed_loop.status.regressed   新增风险 / Regressed
closed_loop.exec.log           执行日志 / Execution log
closed_loop.exec.download      下载脚本 / Download script
closed_loop.confirm.ownership  我确认拥有该资产 / I confirm I own this asset
closed_loop.confirm.execute    确认在真机执行加固 / Confirm applying on the real host
closed_loop.warn.apply         应用模式将真实修改本机系统，请先预检并确认回滚脚本就绪 / Apply mode will really modify this host — run dry-run first and ensure the rollback script is ready
closed_loop.empty.dryrun       预检模式未复扫 / Dry-run: no re-scan performed
```

（数量/命名最终与 Qoder 对齐；Qoder 会回传页面实际键清单。）

## 四、代码要求

- 严格中英对称（缺一边即破 v0.0.39 校验）；`_meta` 按现有格式更新（如版本/键数）。
- 译文自然、准确；APPLY 警示文案不得弱化风险。
- JSON 合法（无尾逗号/重复键）；UTF-8。
- 跑现有 i18n 对称性测试（`tests/test_web_i18n.py` 体系）确保通过。
- `python -m pre_commit run --files <改动>` 过门禁。

## 五、验收

1. [ ] zh-CN.json / en-US.json 同步新增 closed_loop.* 且键集对称。
2. [ ] 必备键全覆盖，APPLY 风险文案如实。
3. [ ] i18n 对称性测试通过。
4. [ ] 键清单已与 Qoder 页面对齐（无悬空键/缺键）。
5. [ ] pre-commit 零违规。
