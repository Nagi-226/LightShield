# CodeBuddy 任务 — v0.0.40 closed_loop i18n 文案补全

> **Agent**：CodeBuddy · **模型切换：DeepSeek-V4-Flash**（零推理量样板任务）
> **状态**：🟢 可开工 — 后端路由已就绪（`POST /api/harden/<scan_id>/verify`），Web 对比页并行开发中
> **类型**：纯文案，零代码逻辑
> **文件**：`lightshield/web/locales/zh-CN.json` + `lightshield/web/locales/en-US.json`

---

## 当前状态

closed_loop 命名空间已有 **20 个键**，均为空占位，需要填充中英文案：

```
col_port, col_severity, col_status, col_type,
confirm_execute, confirm_ownership, empty_dryrun,
exec_download, exec_log, mode_apply, mode_dry_run,
overall_failed, overall_generated_only, overall_partial, overall_verified,
status_regressed, status_remaining, status_resolved,
title, warn_apply
```

---

## 你的任务

为以上 20 个键填充**中英对称**文案。要求：

1. **中英键集严格对称**——zh-CN 有的 en-US 必须有，反之亦然（v0.0.39 已有自动校验）
2. **APPLY 风险文案如实传达**——`confirm_execute` / `confirm_ownership` / `warn_apply` 不得淡化风险
3. **JSON 合法**——无尾逗号、无重复键、UTF-8

### 参考译文

| 键 | zh-CN | en-US |
|---|------|------|
| `title` | 加固闭环对比 | Hardening Closed-Loop |
| `mode_dry_run` | 预检模式 | Dry Run |
| `mode_apply` | 应用模式 | Apply |
| `overall_verified` | 已验证 | Verified |
| `overall_partial` | 部分修复 | Partial |
| `overall_failed` | 未修复 | Failed |
| `overall_generated_only` | 仅生成（未复扫） | Generated Only |
| `col_type` | 风险类型 | Type |
| `col_port` | 端口 | Port |
| `col_severity` | 严重度 | Severity |
| `col_status` | 状态 | Status |
| `status_resolved` | 已修复 | Resolved |
| `status_remaining` | 仍存在 | Remaining |
| `status_regressed` | 新增风险 | Regressed |
| `exec_log` | 执行日志 | Execution Log |
| `exec_download` | 下载脚本 | Download Script |
| `confirm_ownership` | 我确认拥有该资产 | I confirm I own this asset |
| `confirm_execute` | 确认在真机执行加固 | Confirm applying on the real host |
| `warn_apply` | 应用模式将真实修改本机系统，请先预检并确认回滚脚本就绪 | Apply mode will really modify this host — run dry-run first and ensure the rollback script is ready |
| `empty_dryrun` | 预检模式未复扫 | Dry-run: no re-scan performed |

---

## 验收

1. [ ] zh-CN.json / en-US.json 的 closed_loop.* 全部 20 键已填充，中英对称
2. [ ] APPLY 风险文案如实（confirm_execute / warn_apply 不含弱化措辞）
3. [ ] `python -m pytest tests/test_web_i18n.py` 通过
4. [ ] `python -m pre_commit run --files lightshield/web/locales/zh-CN.json lightshield/web/locales/en-US.json` 零违规
