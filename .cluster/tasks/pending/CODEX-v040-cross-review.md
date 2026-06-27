# CODEX 任务 — v0.0.40 CC 自写代码交叉审查（🔴 强制门禁）

> **Agent**：Codex（GPT-5.5，安全关键 + 精密审查）
> **版本**：v0.0.40 自动加固闭环｜**类型**：🔴 强制交叉审查（CC 自写代码，不可跳过）
> **触发规则**：`.cluster/CLUSTER.md` 规则 #4 — CC 自写代码由 Codex (GPT-5.5) 交叉审查
> **审查清单**：`.guardrails/REVIEW_CHECKLIST.md`（M8 五维扫描 + R1-R6 合规 + 八荣八耻）

---

## 一、审查范围

以下 4 个 CC 自写 commits（全部在 `2420020..adb2c11` 范围内，不含纯文档 commit `8d4303d`）：

| Commit | 描述 | 涉及文件 |
|--------|------|---------|
| `2420020` | HostExecutor + 闭环编排 | `core.py`, `cli.py`, `sandbox/host_executor.py`, `sandbox/base.py`, `sandbox/__init__.py`, `utils/constants.py`, `harden/__init__.py`, `harden/base.py`, `harden/closed_loop.py`, `harden/verify.py`, `tests/test_closed_loop.py`, `tests/test_host_executor.py`, `tests/test_verify_hardening.py` |
| `ac3536f` | Loop Hook — Bark 通知 + 报告归档 | `cli.py`, `utils/notifier.py`, `utils/report_archiver.py`, `config.py`, `tests/test_loop_hooks.py` |
| `18b915f` | Web 闭环路由 | `web/routes.py`, `tests/test_web_closed_loop.py` |
| `036b21e` | Web 对比页面 + 样式 | `web/pages.py`, `web/static/style.css`, `web/templates/harden_verify.html`, `tests/test_web_closed_loop.py` |

> ⚠️ `263566c`（八荣八耻文档）和 `8d4303d`（任务文件）是纯文档/配置更新，按 `.guardrails/REVIEW_CHECKLIST.md §六` 不触发交叉审查，可跳过。但若审查中涉及行为准则合规检查，可引用 `263566c` 作为审查依据。

---

## 二、审查指令

### 2.1 审查清单（逐项打勾）

按 `.guardrails/REVIEW_CHECKLIST.md` 完整执行以下五维扫描：

#### 维度 1：架构（Architecture）
- [ ] 模块是否正确分层（adapters/scanners/harden/rules/report/web/utils）？
- [ ] `HostExecutor` 是否正确继承 `SandboxExecutor` 模板方法模式？
- [ ] `run_harden_closed_loop` 编排是否在 `core.py`（核心调度层）而非 adapter/scanner 层？
- [ ] Web 路由/页面是否在 `web/` 层，有无跨层调用（如 web 直接调 sandbox 内部方法）？
- [ ] 新增依赖是否必要？是否在 `requirements.txt` 声明？（注：Bark 通知用的 `requests` 已在 deps 中）

#### 维度 2：安全（Security）—— 本任务重中之重
- [ ] **R1 禁攻击**：全量 grep `exploit|payload|attack|ddos|dos_attack|brute_force`，确认无误命中
- [ ] **R2 禁批量扫描**：`validate_target()` 调用链完整，CLI 入口拒绝 CIDR/网段/通配符
- [ ] **R3 禁远控后门**：grep `bind_shell|reverse_shell|backdoor|trojan|remote_admin`，确认无误命中
- [ ] **R4 仅自查自有**：APPLY 路径 `confirm_ownership=True` AND `confirm_execute=True` 双闸强制；DRY_RUN-first 前置检查生效
- [ ] **R5 MSF 白名单**：本次无 MSF 调用变更（确认即可）
- [ ] **R6 扫描频率**：并发 ≤20、间隔 ≥5s（`SCAN_CONCURRENCY_LIMIT` / `SCAN_INTERVAL_SECONDS`）
- [ ] **HostExecutor._run_script 安全审计**：subprocess 调用是否硬禁毒化 shell=True？是否有注入面？
- [ ] **Web 路由安全**：POST `/api/harden/<scan_id>/verify` 有无 CSRF 风险？输入校验是否完整？

#### 维度 3：性能（Performance）
- [ ] 网络请求有超时（notifier Bark HTTP、CLI 子进程 timeout）
- [ ] 无阻塞式文件 I/O 在热路径
- [ ] 闭环编排中的两次扫描（before/after）有无不必要的重复？

#### 维度 4：代码质量（Code Quality）
- [ ] 异常捕获完善（网络超时、subprocess 超时/kill、权限不足）
- [ ] 类型标注完整，mypy 零违规
- [ ] 中文注释清晰
- [ ] 无占位符/TODO 桩
- [ ] ruff 零违规（含 C90 圈复杂度 ≤20）

#### 维度 5：测试（Testing）
- [ ] 新增模块均有对应测试（`test_closed_loop.py`, `test_host_executor.py`, `test_loop_hooks.py`, `test_verify_hardening.py`, `test_web_closed_loop.py`）
- [ ] 测试覆盖 dry_run + apply 双路径
- [ ] 测试覆盖双确认闸门拒绝路径
- [ ] 测试覆盖异常路径（超时、权限不足、脚本不存在）
- [ ] Mock 使用恰当
- [ ] 771 tests 全量通过（baseline 不下降）

### 2.2 R1-R6 合规红线逐条检查表

| 编号 | 红线 | 检查动作 | 通过 |
|:--:|------|---------|:--:|
| R1 | 禁止对外主动攻击 | grep `exploit\|payload\|attack\|ddos\|dos_attack\|brute_force` | ⬜ |
| R2 | 禁止批量扫描公网 IP | 审查 `validate_target()` 调用链，确认拒 CIDR/网段/通配符 | ⬜ |
| R3 | 禁止远控/后门/木马 | grep `bind_shell\|reverse_shell\|backdoor\|trojan\|remote_admin` | ⬜ |
| R4 | 仅允许自查自有资产 | 确认 APPLY 路径 `confirm_ownership=True` + `confirm_execute=True` 双闸 | ⬜ |
| R5 | MSF 调用限制 | 确认本次变更无 MSF 调用修改（无新 exploit/payload 入口） | ⬜ |
| R6 | 扫描频率限制 | 确认 `SCAN_CONCURRENCY_LIMIT` ≤ 20、`SCAN_INTERVAL_SECONDS` ≥ 5 | ⬜ |

### 2.3 八荣八耻审查对照

| # | 准则 | 审查要点 | 通过 |
|:--:|------|------|:--:|
| 1 | 认真查询 | CC 是否查询了实际接口签名而非猜测？（如 `SandboxExecutor` 基类、`generate_hardening` 签名） | ⬜ |
| 2 | 寻求确认 | 不确定之处是否先问后写（无明显假设痕迹）？ | ⬜ |
| 3 | 人类确认 | CC 是否替用户做了业务决策？（如 Bark webhook URL、通知频率） | ⬜ |
| 4 | 复用现有 | 新增代码是否必要？HostExecutor 是否合理复用 `SandboxExecutor` 基类？Loop Hook 是否复用 `cli.py` 既有模式？ | ⬜ |
| 5 | 主动测试 | 每个改动是否配测试 + 全量回归 771 tests 通过？ | ⬜ |
| 6 | 遵循规范 | 文件位置/接口契约/架构分层是否正确？ | ⬜ |
| 7 | 诚实无知 | 产出中不确定性是否标注？（检查代码注释/commit message） | ⬜ |
| 8 | 谨慎重构 | 改动是否聚焦？是否混杂重构+行为变更？（检查 `sandbox/base.py` 语义注释更新是否为必要且聚焦） | ⬜ |

### 2.4 重点关注项（CC 已标记的高风险区域）

> 以下来自 CC 在开发期间的自我标注，Codex 审查时请重点验证：

1. **`sandbox/base.py` + `sandbox/host_executor.py` — 设计张力**：基类原注释"脚本只在隔离容器运行、绝不在宿主机直接执行"，HostExecutor 打破此不变量。验证：①基类语义已更新为两态；②额外护栏在编排层（非 executor 层）；③`core.execute_hardening` docstring 已更新。
2. **`core.py:run_harden_closed_loop` — APPLY 三重前置**：双确认 + DRY_RUN-first + rollback 就绪。验证：缺一即拒，返回结构化失败不抛异常。
3. **`utils/notifier.py` — Bark 通知**：webhook URL 从 `config.py` 读取（非硬编码），默认 disabled。验证：无敏感信息泄露。
4. **`web/routes.py:verify_hardening` — CSRF 风险**：POST 端点无 CSRF token。验证：是否为可接受风险（内部工具/单用户场景）或需标记为已知限制。

---

## 三、审查输出格式

按 `.guardrails/REVIEW_CHECKLIST.md §五` 模板：

```markdown
# 审查报告 — v0.0.40 CC 自写代码交叉审查

> **审查者**：Codex (GPT-5.5) | **日期**：YYYY-MM-DD | **范围**：v0.0.40 全部 CC 自写 commits（4 个）

## 发现总览
| 等级 | 数量 |
|------|:--:|
| 🔴 CRITICAL | N |
| 🟠 HIGH | N |
| 🟡 MEDIUM | N |
| 🔵 LOW | N |
| 💡 SUGGESTION | N |

## 逐项发现
### [等级] [编号] — [标题]
- **位置**：`文件:行号`
- **描述**：[问题描述]
- **建议**：[修复建议]
- **状态**：⬜ 待修复 / ✅ 已修复 / ⏸️ 已知悉不修（需理由）

## 合规检查
| 红线 | 结果 |
|:--:|:--:|
| R1 | ✅/❌ |
| R2 | ✅/❌ |
| R3 | ✅/❌ |
| R4 | ✅/❌ |
| R5 | ✅/❌ |
| R6 | ✅/❌ |

## 八荣八耻检查
| # | 准则 | 通过 |
|:--:|------|:--:|
| 1 | 认真查询 | ✅/❌ |
| 2 | 寻求确认 | ✅/❌ |
| 3 | 人类确认 | ✅/❌ |
| 4 | 复用现有 | ✅/❌ |
| 5 | 主动测试 | ✅/❌ |
| 6 | 遵循规范 | ✅/❌ |
| 7 | 诚实无知 | ✅/❌ |
| 8 | 谨慎重构 | ✅/❌ |

## 结论
- [ ] 通过，可合入 + tag v0.0.40
- [ ] 有条件通过（[N] 项需修复后合入）
- [ ] 驳回（需重新实现）
```

---

## 四、执行方式

Codex 审查完成后，将报告输出到 `.guardrails/audit-log.md` 末尾，格式：

```
YYYY-MM-DD | Gate C (Codex cross-review) | v0.0.40 (commits 2420020..adb2c11) | [findings summary] | [PASS/CONDITIONAL/REJECT]
```

然后将审查报告全文写入 `.guardrails/review-reports/v040-codex-cross-review.md`。

---

## 五、验收清单

- [ ] M8 五维扫描全部完成，每维度逐项打勾
- [ ] R1-R6 合规红线逐条检查通过（或标注例外+理由）
- [ ] 八荣八耻 8 项全部审查通过
- [ ] 4 个重点关注项均已验证
- [ ] 审查报告输出到 `review-reports/v040-codex-cross-review.md`
- [ ] 审计日志条目写入 `audit-log.md`
- [ ] 结论明确（通过/有条件通过/驳回）
