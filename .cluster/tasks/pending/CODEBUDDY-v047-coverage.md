# CODEBUDDY-v047-coverage：Kimi LOW-001~005 测试补充 + 覆盖率冲刺 85%

> **【CodeBuddy 模式：B · WorkBuddy CLI（批量模板化测试任务）】**
> **【模型切换：DeepSeek-V4-Pro】**
> **【下发 Agent：Claude Code】**
> **【依赖】🟢 不阻塞版本迭代 — 与 Kimi 审查并行执行**
> **【基线】996 tests / 0 fail / 1 skip / 覆盖率 ~82.7%**

---

## ⚠️ 核心约束摘要（≤5 条，不可被上下文稀释覆盖）

| # | 约束 | 违反后果 |
|---|------|---------|
| 1 | **只加测试，不改源码**（LOW-001~005 是测试覆盖缺口，不是代码缺陷） | 无意间引入回归 |
| 2 | 测试必须独立、可重复——不依赖前序测试的状态 | 跨测试状态污染（已知历史问题） |
| 3 | 现有 996 tests 基线不降——每加一个测试就跑一次全量确认零回归 | 覆盖率上升但回归测试被打破 |
| 4 | 禁止为凑覆盖率写空断言（如 `assert True`）——每个测试必须有明确的"验证什么"注释 | 假覆盖率，实际无防护价值 |
| 5 | 不要在测试中引入新的外部依赖（网络、Docker、文件系统特殊路径） | CI 环境不可运行 |

---

## ⚠️ 提问姿态约束

**Agent 自查**（每次输出前）：
- [ ] 我是在写"验证行为的测试"还是在写"复述实现的测试"？
- [ ] 我是否穷举了边界输入，而不是只写了 happy path？
- [ ] 如果未来有人重构了被测试的实现，我的测试会拦截退化吗？

---

## 一、项目上下文

LightShield v0.0.47，Kimi (K2.7-code) 在 v0.0.46 独立审查中发现了 5 个测试覆盖缺口（LOW-001~005），全部位于 `tests/test_v046_coverage.py`。这些是已知债务，不阻塞当前版本迭代。

**覆盖率现状**：~82.7%，目标 85%。剩余未覆盖代码主要在 `lightshield/cli.py`（286 行）和 `lightshield/core.py` 的 `closed_loop` 部分（124 行）。

**本任务不与 Kimi 审查串行**：Kimi 在审查 v0.0.47 的新代码，本任务是补 v0.0.46 已识别的测试缺口。二者可完全并行。

---

## 二、⚠️ 合规约束片段

| 红线 | 本任务相关？ | 具体要求 |
|:--:|:--:|------|
| R1 | 否 | 纯测试任务，不涉及攻击代码 |
| R2 | 否 | 不涉及扫描操作 |
| R3 | 否 | 不涉及远控/后门/木马 |
| R4 | 否 | 不涉及目标资产 |
| R5 | 否 | 不涉及 MSF 调用 |
| R6 | 否 | 不涉及扫描操作 |

---

## 三、任务详情

### 阶段 A：Kimi LOW-001~005 修复（优先，5 个独立测试补充）

#### LOW-001：`_merge_findings` 去重 key 未覆盖 `url/parameter/title`

- **文件**：`tests/test_v046_coverage.py`
- **问题**：当前 `test_dedup_by_key` 仅验证 `vuln_type + port` 相同即去重，未验证 `url/parameter/title` 差异时**不应去重**的场景
- **任务**：新增一个测试用例——`vuln_type` 和 `port` 相同，但 `url`/`parameter`/`title` 不同时，应保留为 2 条发现
- **验收**：该用例断言 `len(findings) == 2`，且如果未来有人误改 key 逻辑导致去重过度，该用例 FAIL

#### LOW-002：`_resolve_script_path` 子目录绕过用例强度不足

- **文件**：`tests/test_v046_coverage.py:479-488`
- **问题**：注释说"创建子目录 + 文件以尝试绕过"，但实际仅创建了子目录，未在子目录中创建文件。若未来实现调整判断顺序（先 `is_file()` 再检查 parent），此用例会退化为"文件不存在"测试
- **任务**：在 `subdir/` 下真实创建 `harden_test.sh` 文件，再断言 `_resolve_script_path(td, "subdir/harden_test.sh")` 返回 `None`
- **验收**：无论判断顺序如何调整，该用例都能验证 traversal/子目录防护

#### LOW-003：`_validate_download_csrf` 未覆盖 `request.form` token

- **文件**：`tests/test_v046_coverage.py:406-449`
- **问题**：`routes.py:507` 支持 `request.form.get("_csrf_token")`，但测试仅覆盖了 Header 和 Query Param
- **任务**：新增 `test_accepts_form_token` 用例，使用 `cov_app.test_request_context(..., data={"_csrf_token": "token-form"}, method="POST")`
- **验收**：form token 通过验证，三种来源（Header / Query / Form）全覆蓋

#### LOW-004：`_is_truthy` 未覆盖 `None` 边界

- **文件**：`tests/test_v046_coverage.py:519-537`
- **问题**：`_is_truthy(None)` 会落入 `return bool(value)` 返回 `False`，但未显式覆盖
- **任务**：在现有 `test_falsy_strings` 或新增用例中加 `assert _is_truthy(None) is False`
- **验收**：None 边界被显式覆盖，文档化"None = falsy"的预期行为

#### LOW-005：`_print_execution_result` 未覆盖 stdout 截断边界

- **文件**：`tests/test_v046_coverage.py:148-165`
- **问题**：实现截取 stdout 末尾 20 行，当前测试仅 3 行输出，未验证 >20 行的截断行为
- **任务**：构造 25 行的 stdout，断言 `_print_execution_result` 只打印后 20 行
- **验收**：截断边界被验证，且前 5 行确认不出现在输出中

---

### 阶段 B：覆盖率冲刺 82.7% → 85%（LOW-001~005 完成后可选）

**剩余未覆盖重点**：
- `lightshield/cli.py`（~286 行）— CLI 命令处理逻辑
- `lightshield/core.py` `closed_loop`（~124 行）— 闭环编排
- `lightshield/web/routes.py`（~75 行）— Web API 端点

**策略**：
1. 先用 `python -m pytest tests/ --cov=lightshield --cov-report=term-missing` 定位精确的未覆盖行
2. 优先覆盖**纯函数**（无 I/O 依赖）→ 可以用 mock 隔离的 → 需要基础设施的（放最后）
3. 每 +2% 覆盖率 → 跑一次全量回归 → 确认零退化

---

## 四、接口契约

```python
# 被测试的函数签名（来自源码，仅用于确认测试对象）

# cli_helpers.py
def _merge_findings(findings: list) -> list: ...
def _print_execution_result(result) -> None: ...
def _resolve_script_path(base_dir: str, script_path: str) -> str | None: ...
def _is_truthy(value) -> bool: ...

# routes.py
def _validate_download_csrf() -> bool: ...
```

---

## 五、代码要求

- [ ] 测试文件使用 pytest 风格（函数以 `test_` 开头）
- [ ] 每个测试有中文注释说明"验证什么"
- [ ] 需要 mock 时使用 `unittest.mock.patch` 或 `pytest-mock`
- [ ] 不修改 `lightshield/` 下的任何源码（除非发现真正的 bug——此时暂停并上报 CC）
- [ ] ruff / mypy / bandit 零违规

---

## 六、测试要求

- [ ] LOW-001~005 完成后跑全量 `python -m pytest tests/ -q`，确认 996+ 通过
- [ ] 🔴 影响驱动测试：改完 `test_v046_coverage.py` 后，确认所有引用该文件的测试通过
- [ ] 🔴 注意：不要创建新的全局 mock 或 patch 对象——这会污染其他测试模块（已知历史问题）

---

## 七、验收清单

- [ ] LOW-001 已修复：`test_dedup_by_key` 新增 url/parameter/title 差异不应去重的用例
- [ ] LOW-002 已修复：`_resolve_script_path` 子目录文件绕过用例已补强
- [ ] LOW-003 已修复：`_validate_download_csrf` form token 用例已新增
- [ ] LOW-004 已修复：`_is_truthy(None)` 边界已覆盖
- [ ] LOW-005 已修复：`_print_execution_result` >20 行截断边界已覆盖
- [ ] 全量回归通过（`python -m pytest tests/ -q`）
- [ ] pre-commit 全部通过（ruff/mypy/bandit）
- [ ] 🆕 覆盖率报告已出（`--cov=lightshield --cov-report=term`）
- [ ] Goal Drift 自检通过（对照 AGENT_CODE_OF_CONDUCT.md §8.4）

---

## 八、不确定性声明

| 判断 | 置信度 | 替代方案 | 待确认点 |
|------|:--:|------|------|
| LOW-001~005 全部在 `test_v046_coverage.py` 中 | 🟢 高 | — | 已由 Kimi 审查确认 |
| 覆盖率 85% 可在阶段 B 达成 | 🟡 中 | 若 cli.py mock 过于复杂，可能只到 84% | `cli.py` 的 mock 基础设施需要多少工作量 |
| 阶段 B 不会引入跨测试状态污染 | 🟡 中 | 使用 pytest 的 `monkeypatch` fixture 替代全局 `mock.patch.object` | `test_web_pages.py` 与 coverage 测试的历史冲突需验证 |

---

## 九、关联资源

- Kimi 审查报告：`docs/review-v046-kimi.md`（LOW-001~005 原文）
- 被测源码：`lightshield/cli_helpers.py`（CLI 辅助函数）
- 被测源码：`lightshield/core.py`（闭环编排）
- 被测源码：`lightshield/web/routes.py`（Web API）
- 集群护栏：`.guardrails/AGENT_CODE_OF_CONDUCT.md`
