# v0.0.46 独立审查报告 — Kimi (K2.7-code)

> **审查者**：Kimi Code CLI（模式 A）
> **模型**：K2.7-code
> **下发 Agent**：Claude Code
> **审查范围**：v0.0.46 新增/变更 — `tests/test_v046_coverage.py`、`tests/test_msf_extra.py`、护栏文档 v1.3
> **审查日期**：2026-07-02
> **关联 commit**：`2d41a15`
> **Inherited Drift 防火墙**：本报告基于「任务文件核心约束 + 代码 diff」独立完成，未先读取 CC/被审查者的推理过程

---

## 执行摘要

| 维度 | 结论 |
|------|------|
| 全量回归 | ✅ 991 passed / 0 failed / 1 skipped（与任务文件一致） |
| R1-R6 红线 | ✅ 无新增违反（MSF 攻击字符串仅作为测试输入验证白名单拒绝） |
| 硬编码密钥 | ⚠️ 测试代码存在 2 处测试用凭据，非生产密钥，属 LOW/INFO |
| Mock 正确性 | ✅ 路径、对象、restore 均正确 |
| 状态隔离 | ⚠️ 1 处测试访问默认磁盘数据库（非内存），1 处临时目录未显式清理，均不影响功能 |
| 护栏文档一致性 | ⚠️ 2 处文档格式/路径不一致（LOW/INFO） |
| 测试覆盖充分性 | ⚠️ 4 处边界/分支覆盖遗漏（LOW） |

**整体结论**：v0.0.46 变更**无 CRITICAL / 无 HIGH / 无 MEDIUM 真 bug**，可合入。剩余发现均为测试覆盖遗漏或文档格式问题，建议作为技术债务在后续版本补齐。

---

## 发现总览

| 等级 | 数量 | 说明 |
|------|:--:|------|
| 🔴 CRITICAL | 0 | — |
| 🟠 HIGH | 0 | — |
| 🟡 MEDIUM | 0 | — |
| 🟢 LOW | 5 | 测试覆盖遗漏 / 文档格式 / 状态隔离可优化 |
| 💡 INFO | 3 | 测试用硬编码凭据 / 文档示例路径 |

---

## 独立发现（Phase 1-2 产出，未受被审查者影响）

### 🟢 LOW-001 — `_merge_findings` 去重 key 未覆盖 `url/parameter/title`

- **位置**：`tests/test_v046_coverage.py:126-133`
- **描述**：`_merge_findings` 的去重 key 为 `(vuln_type, port, url, parameter, title)`。当前 `test_dedup_by_key` 仅验证了 `vuln_type + port` 相同即去重，未验证 `url/parameter/title` 差异时**不应去重**的场景。如果未来有人误改 key 逻辑，测试无法拦截。
- **置信度**：🟢 确定
- **修复建议**：补充一个测试用例：vuln_type 和 port 相同，但 `url`/`parameter`/`title` 不同，应保留为 2 条发现。
- **状态**：⬜ 建议补齐

### 🟢 LOW-002 — `_resolve_script_path` 子目录绕过用例强度不足

- **位置**：`tests/test_v046_coverage.py:479-488`
- **描述**：注释描述为「创建子目录 + 文件以尝试绕过」，但实际代码仅创建了子目录，并未在子目录中创建文件。当前实现先判断 `script_path.parent != base_dir` 再判断 `is_file()`，因此该断言能覆盖 parent 检查；若未来实现调整判断顺序，此用例将退化为「文件不存在」测试，无法验证 traversal/子目录防护。
- **置信度**：🟢 确定
- **修复建议**：在 `subdir/` 下真实创建 `harden_test.sh`，再断言 `_resolve_script_path(td, "subdir/harden_test.sh")` 返回 `None`。
- **状态**：⬜ 建议补齐

### 🟢 LOW-003 — `_validate_download_csrf` 未覆盖 `request.form` token

- **位置**：`tests/test_v046_coverage.py:406-449`
- **描述**：`routes.py:507` 支持从 `request.form.get("_csrf_token")` 获取 token，但测试仅覆盖了 Header (`X-CSRF-Token`) 和 Query Param (`_csrf_token`)，未覆盖 form 场景。
- **置信度**：🟢 确定
- **修复建议**：补充一个 `test_accepts_form_token` 用例，使用 `cov_app.test_request_context(..., data={"_csrf_token": "token-form"}, method="POST")` 验证 form token 通过。
- **状态**：⬜ 建议补齐

### 🟢 LOW-004 — `_is_truthy` 未覆盖 `None` 边界

- **位置**：`tests/test_v046_coverage.py:519-537`
- **描述**：`_is_truthy(None)` 会落入 `return bool(value)`，返回 `False`。该边界未在测试中显式覆盖。
- **置信度**：🟢 确定
- **修复建议**：在 `test_falsy_strings` 或新增用例中增加 `assert _is_truthy(None) is False`。
- **状态**：⬜ 建议补齐

### 🟢 LOW-005 — `_print_execution_result` 未覆盖 stdout 截断边界

- **位置**：`tests/test_v046_coverage.py:148-165`
- **描述**：实现会截取 stdout 末尾 20 行。当前测试只有 3 行，未验证 >20 行时只打印后 20 行的行为。
- **置信度**：🟢 确定
- **修复建议**：补充一个生成 25 行 stdout 的用例，断言输出中只包含最后 20 行、不包含前 5 行。
- **状态**：⬜ 建议补齐

### 🟢 LOW-006 — `QUALITY_GATES.md` Gate B 章节标题缺失

- **位置**：`.guardrails/QUALITY_GATES.md:209-212`
- **描述**：A-6 章节结束后直接进入引用块和 SF-L1~L4 表格，缺少 `## 三、Gate B：范围忠实度` 标题。与文档其他 Gate 章节的结构不一致。
- **置信度**：🟢 确定
- **修复建议**：在引用块前增加 `## 三、Gate B：范围忠实度` 标题。
- **状态**：⬜ 建议补齐

### 💡 INFO-001 — 测试 fixture 中硬编码 JWT secret

- **位置**：`tests/test_v046_coverage.py:38`
- **描述**：`config.jwt_secret = "test-secret-key-for-session-signing"` 为测试用密钥，仅作用于 `:memory:` 内存数据库的测试应用，不进入生产配置。
- **置信度**：🟢 确定（非安全漏洞）
- **修复建议**：如 bandit 扫描测试文件，可标记 `# nosec B105` 或改用 `secrets.token_urlsafe()` 动态生成，避免工具误报。
- **状态**：⏸️ 已知悉不修（测试用、无泄漏面）

### 💡 INFO-002 — 测试登录凭据硬编码

- **位置**：`tests/test_v046_coverage.py:54`
- **描述**：`cov_client.post("/api/login", json={"username": "admin", "password": "lightshield"})` 使用固定测试凭据登录。这是复用 `test_web.py` 模式的测试账号。
- **置信度**：🟢 确定（非安全漏洞）
- **修复建议**：可接受；如追求极致，可从 fixture 或环境变量读取测试凭据。
- **状态**：⏸️ 已知悉不修

### 💡 INFO-003 — Goal Drift 持久化目标文档路径与当前目录结构不一致

- **位置**：`.guardrails/AGENT_CODE_OF_CONDUCT.md:385`
- **描述**：反制措施 ❶ 提到目标文档路径为 `.cluster/tasks/active/goal-XXX.md`，但当前仓库仅有 `.cluster/tasks/pending/`，不存在 `active/` 目录。
- **置信度**：🟡 大概率（可能是未来待创建的流程目录）
- **修复建议**：如 `active/` 为规划中的流程目录，建议在 `.cluster/tasks/` 下添加 `active/.gitkeep` 或补充说明；如为笔误，应修正为 `pending/`。
- **状态**：⬜ 待确认

### 💡 INFO-004 — `TestScanPersistence` 使用默认磁盘数据库而非内存库

- **位置**：`tests/test_v046_coverage.py:315-336`
- **描述**：`LightShieldCore()` 使用默认 `LightShieldConfig()`，`db_url` 为空，会被 `load_scan` 回退为 `data/lightshield.db`。测试仅读取不存在的 `scan_id`，不影响结果，但状态隔离不如内存数据库理想。
- **置信度**：🟢 确定
- **修复建议**：为 `core` fixture 传入 `LightShieldConfig(db_url=":memory:")` 以增强隔离性。
- **状态**：⏸️ 已知悉不修（当前不影响功能）

---

## 确认已有发现（与 CC 自评/任务文件一致）

无。v0.0.45 遗留债务为 8 LOW / 9 INFO，本次审查未发现新增 MEDIUM 及以上问题，与任务文件「新增主要是测试代码，发现重大问题的概率低」的不确定性声明一致。

---

## 🆕 Inherited Drift 告警

无。被审查者（CC）在 commit message 中明确声明了变更范围（覆盖率冲刺 + 护栏 v1.3），与代码 diff 完全一致，未发现目标偏离。

---

## 合规检查（R1-R6）

| 红线 | 结果 | 说明 |
|:--:|:--:|------|
| R1 | ✅ | 测试代码不含主动攻击逻辑 |
| R2 | ✅ | `generate_hardening` 测试使用 CIDR 仅用于验证拒绝路径 |
| R3 | ✅ | 无 bind_shell/reverse_shell/backdoor/trojan |
| R4 | ✅ | 脚本下载测试正确验证 `harden_confirmed_at` 确认门 |
| R5 | ✅ | MSF 攻击字符串仅作为白名单拒绝测试输入 |
| R6 | ✅ | 无新增扫描并发/间隔相关代码 |

---

## 测试验证记录

```text
$ py -m pytest tests/test_v046_coverage.py tests/test_msf_extra.py -v
74 passed in 1.21s

$ py -m pytest tests/ --tb=short -q
991 passed, 1 skipped, 2 warnings in 99.03s

$ py -m ruff check tests/test_v046_coverage.py tests/test_msf_extra.py
All checks passed!
```

---

## Goal Drift 自检（AGENT_CODE_OF_CONDUCT.md §8.4）

| # | 检查点 | 结果 |
|---|--------|:--:|
| ① | 当前操作是否在原始任务文件的「验收清单」中？ | ✅ 是，执行审查并输出报告 |
| ② | 是否超过 10 轮交互仍未重新阅读目标文档？ | ✅ 否，首步即读取任务文件 |
| ③ | 输出是否出现原始任务未提及的新目标/新文件/新抽象？ | ✅ 否，仅输出审查报告 |
| ④ | 是否在「优化」一个已经可以交付的结果？ | ✅ 否，按任务要求完成审查即止 |

---

## 结论

- [ ] 通过，可合入
- [x] 通过，可合入（建议顺手修复 LOW-006 文档标题，其余 INFO/LOW 可债务化）
- [ ] 有条件通过
- [ ] 驳回

**v0.0.46 变更质量良好**：新增 61 个测试有效覆盖了 cli helpers、core generate_hardening、routes helpers 及 SSE/下载端点；mock 路径正确、状态隔离整体可控；护栏 v1.3 文档内容自洽。未发现 CRITICAL/HIGH/MEDIUM 级别问题，可安全合入。
