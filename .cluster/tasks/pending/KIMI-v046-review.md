# KIMI-v046-review：v0.0.46 独立审查

> **【Agent：Kimi Code CLI（模式 A）】**
> **【模型：K2.7-code】**
> **【下发 Agent：Claude Code】**
> **【关联版本：v0.0.46】**

---

## ⚠️ 核心约束摘要（≤5 条，不可被上下文稀释覆盖）

> **目的**：Kimi 是集群中唯一与所有其他 Agent 模型不同的审查者（K2.7-code ≠ DS ≠ GPT ≠ Qwen ≠ GLM），你的独立视角消除同源盲区。

| # | 约束 | 违反后果 |
|---|------|---------|
| 1 | 审查 v0.0.46 的**新增/变更代码**，不是全项目（v0.0.46 是覆盖率版本，变更集中在测试代码） | 浪费时间审查无关代码 |
| 2 | 按严重度分级输出（CRITICAL/HIGH/MEDIUM/LOW/INFO），区分"真问题" vs "无害异味" | 开发者无法区分修复优先级 |
| 3 | 审查发现必须提供**具体的文件+行号+修复建议**，不做泛泛评论 | 开发者无法复现/定位 |
| 4 | 不重复已修复的审查发现（v0.0.45 前已清零 0C/0H/0M，仅剩 8L/9I） | 制造噪音、浪费开发者时间 |
| 5 | 对每个发现给出置信度标注（🟢确定/🟡大概率/🔴疑似），🔴 项必须附"如何验证"步骤 | 开发者误修非 bug 代码 |

---

## ⚠️ 提问姿态约束（来自注意力机制原理）

**本任务禁止的审查方式**：

| ❌ 禁止 | ✅ 必须 |
|--------|--------|
| "代码看起来没问题" | "逐段审查，确认没有遗漏的边界情况" |
| "这个测试覆盖了该函数" | "对照源码逐行检查，是否所有分支/异常路径都有测试覆盖" |
| "没有安全漏洞" | "遍历 R1-R6 红线，逐条检查变更代码中是否存在违反" |

**自查**（每次输出前）：
- [ ] 我是否因为审查的是"测试代码"而降低了审查标准？
- [ ] 我是否只看了新增测试的正确路径，忽略了错误路径/边界值？
- [ ] 如果这是生产代码而非测试代码，我的审查结论会有实质不同吗？

---

## 一、项目上下文（简短）

LightShield 轻盾 — 开源轻量化安全自检 + 防御加固工具，基于 Python 3.10+。当前 v0.0.46，质量基线 991 tests / 0 fail / 覆盖率 82.72% / 债务 0C/0H/0M/8L/9I。

v0.0.46 是**覆盖率冲刺版本**（79.6% → 82.72%），变更集中在：
- 新增 `tests/test_v046_coverage.py`（61 个新测试）
- 修复 `tests/test_msf_extra.py`（1 行异常类型补充）
- 护栏文档升级（AGENT_CODE_OF_CONDUCT/QUALITY_GATES/REVIEW_CHECKLIST/CLAUDE.md）

本版本**无生产代码变更**——仅测试代码 + 护栏文档。你的审查重点：新增测试是否有遗漏、是否引入回归风险、护栏文档一致性。

---

## 二、⚠️ 合规约束片段（必读）

> 本次变更不涉及生产代码，但审查时仍需保持合规意识。

| 红线 | 本任务相关？ | 具体要求 |
|:--:|:--:|------|
| R1 | 否 | 测试代码不含攻击关键字 |
| R2 | 否 | — |
| R3 | 否 | — |
| R4 | 否 | — |
| R5 | 否 | — |
| R6 | 否 | — |

---

## 三、审查范围

### 变更文件清单

```text
tests/test_v046_coverage.py      # 新增 61 tests（cli helpers / core generate_hardening / routes helpers）
tests/test_msf_extra.py          # 修改 1 行（InvalidTargetError 加入预期异常列表）
.guardrails/AGENT_CODE_OF_CONDUCT.md  # 护栏 v1.3（Goal Drift 防护 §八）
.guardrails/QUALITY_GATES.md          # Gate A-6 + §十二 CI/CD Secret 隔离
.guardrails/REVIEW_CHECKLIST.md       # 审查更新
CLAUDE.md                             # 护栏 v3.3 + 进度更新
```

### 审查维度

| 维度 | 重点 |
|------|------|
| **测试质量** | test_v046_coverage.py 是否真正覆盖了宣称的函数？是否有"只调用了函数但不验证结果"的虚假覆盖？ |
| **回归风险** | 新增测试是否可能改变全局状态（tempfile/mock/session）影响其他测试？ |
| **Mock 正确性** | mock 的对象路径是否正确？mock 后是否正确 restore？ |
| **护栏文档** | AGENT_CODE_OF_CONDUCT §八 的 Goal Drift 防护逻辑是否自洽？与 QUALITY_GATES 是否一致？ |
| **安全** | 测试代码中是否有硬编码密钥/密码？是否有引入不安全的测试依赖？ |

---

## 四、任务详情

### 4.1 现状

v0.0.46 是覆盖率冲刺版本。CC（DeepSeek-V4-Pro）编写了 61 个新测试，覆盖：
- cli.py 纯函数（parse_scan_types、merge_findings、print_execution_result、self_check、print_history_table、print_scan_detail）
- core.py generate_hardening 直接调用
- routes.py 辅助函数（format_sse、is_allowed_script_filename、validate_download_csrf 等）
- routes.py API 端点（SSE 扫描流、脚本下载）

所有测试通过，pre-commit 全部门禁通过。

### 4.2 目标

完成 Kimi 独立模型审查，确认 v0.0.46 变更无回归、无安全风险。输出分级审查报告。

### 4.3 要求

1. 逐文件审查，重点关注测试代码的 mock 正确性和状态隔离
2. 护栏文档 Go-Goal Drift 防护逻辑检查
3. 对每个发现标注严重度 + 置信度 + 修复建议
4. 若未发现问题，说明"审查通过"并简述审查过程

---

## 五、验收清单

> **Agent 注意**：此清单即子目标列表。每完成一项打勾，完成前不扩展新目标（防 Subgoal Displacement）。

- [ ] test_v046_coverage.py 审查完成（mock 正确性、状态隔离、断言充分性）
- [ ] test_msf_extra.py 修改审查完成
- [ ] 护栏文档一致性检查完成（AGENT_CODE_OF_CONDUCT ↔ QUALITY_GATES ↔ REVIEW_CHECKLIST ↔ CLAUDE.md）
- [ ] 安全扫描（硬编码密钥/不安全依赖/攻击关键字）
- [ ] 分级审查报告输出（含文件+行号+严重度+置信度+修复建议）
- [ ] 🆕 Goal Drift 自检通过（对照 AGENT_CODE_OF_CONDUCT.md §8.4）

---

## 六、不确定性声明

| 判断 | 置信度 | 替代方案 | 待确认点 |
|------|:--:|------|------|
| v0.0.46 新增主要是测试代码，发现重大问题的概率低 | 🟢 | — | — |
| 跨测试文件状态隔离（cov_app vs app fixture 命名冲突）已通过 pytest 验证 | 🟢 | — | 需全量跑确认 |

---

## 七、关联资源

- 关联版本：v0.0.46（commit: `2d41a15`）
- 关联模块：tests/test_v046_coverage.py, tests/test_msf_extra.py
- 护栏文档：.guardrails/AGENT_CODE_OF_CONDUCT.md, .guardrails/QUALITY_GATES.md
