# REASONIX 任务 — v0.0.40 数据结构 + verify 比对纯函数

> **Agent**：Reasonix（DeepSeek-V4-Pro，主力实现 + 测试生成）
> **版本**：v0.0.40 自动加固闭环｜**类型**：纯逻辑 + 数据类 + 单测（无 I/O、无副作用）
> **依赖**：无（本任务是闭环实现的地基，Codex/Qoder 都 import 你的产出）
> **冻结接口来源**：`docs/design-v040-closed-loop.md`（正式版）§5 / §7；决策背景见 `docs/adr-v040-execution-substrate.md`

---

## 一、项目上下文（简短）

LightShield（轻盾）是开源轻量化安全自检 + 加固工具，Python 3.10+。v0.0.40 做自动加固闭环 `扫描→推荐→生成→执行→复扫→验证`。**你负责"验证(⑥)"环节的纯函数 + 全闭环要用的数据结构**。这是整个闭环最适合单测的部分（构造 before/after 列表断言分桶），交给你。

## 二、⚠️ 合规约束（R1-R6）

本任务是纯函数，不联网、不执行命令、不碰系统，**天然满足 R1/R2/R6**。唯一注意：`verify_hardening` 是单目标比对（R2），不得引入��何批量/网络逻辑。

## 三、接口契约（严格按此，字段名勿改）

### 3.1 扩展 `HardenStatus`（`lightshield/harden/base.py:26`，现有 Enum）

新增 3 个成员（保留现有 GENERATED/NO_ACTION/FAILED）：
```python
EXECUTED = "executed"     # 脚本已执行（不代表已验证）
VERIFIED = "verified"     # 复扫确认风险已消除
REGRESSED = "regressed"   # 复扫发现仍存在 / 引入新风险
```

### 3.2 新增 `VerificationResult`（新建 `lightshield/harden/verify.py`）

```python
@dataclass
class VerificationResult:
    target: str
    resolved: list[dict]      # 加固前有、后无（修复成功）
    remaining: list[dict]     # 前后都在（未修复）
    regressed: list[dict]     # 后有、前无（加固引入新风险）
    before_count: int
    after_count: int
    verdict: str              # "verified" | "partial" | "failed"
    audit_id: str = ""
    def to_dict(self) -> dict: ...
```

### 3.3 新增 `ClosedLoopResult`（新建 `lightshield/harden/closed_loop.py`，**仅定义数据类 + to_dict**，编排逻辑归 Codex）

```python
@dataclass
class ClosedLoopResult:
    target: str
    os_platform: OSPlatform          # lightshield/utils/constants.py:61
    mode: str                        # "dry_run" | "apply"
    before_scan: dict
    harden: dict
    execution: dict | None
    after_scan: dict | None
    verification: dict | None
    overall: str                     # "verified"|"partial"|"failed"|"generated_only"
    audit_id: str
    def to_dict(self) -> dict: ...
```

### 3.4 核心纯函数 `verify_hardening`（`lightshield/harden/verify.py`）

```python
def verify_hardening(before: list[VulnFinding], after: list[VulnFinding], target: str) -> VerificationResult:
    """对比加固前后两次扫描，分类 resolved / remaining / regressed。纯函数：无 I/O、无副作用、不联网。"""
```
- **比对键**：两 finding 视为"同一风险" ⟺ `(vuln_type, port)` 相等。
- `resolved` = before 有、after 无；`remaining` = 都有；`regressed` = after 有、before 无。
- **verdict 规则**：`verified`= resolved 非空 且 remaining 空 且 regressed 空；`partial`= resolved 非空但 remaining 或 regressed 非空；`failed`= resolved 为空（未消除任何风险），或 regressed 非空且 resolved 为空。
- `VulnFinding` 字段见 `lightshield/adapters/base.py:58`：`vuln_type/severity/title/description/port`。

## 四、代码要求

- 全中文注释；类型标注完整；`to_dict()` 产出可直接 JSON 序列化（Web/报告消费，Enum 转 `.value`）。
- `verify_hardening` 必须纯：不读文件、不调 core、不联网。
- **单测**（`tests/test_verify_hardening.py`）：①三类分桶各造样例断言；②三种 verdict 边界；③空输入；④`(vuln_type,port)` 同类型不同端口算两条；⑤to_dict 往返。目标覆盖率对齐项目基线。
- 跑 `python -m pre_commit run --files <改动文件>` 过 ruff+mypy（**勿裸跑 mypy**，缺存根会误报）。

## 五、验收

1. [ ] HardenStatus 三新成员；VerificationResult/ClosedLoopResult 两数据类 + to_dict。
2. [ ] verify_hardening 纯函数，比对键/分桶/verdict 完全符合契约。
3. [ ] 单测全绿，覆盖三分桶+三 verdict+边界。
4. [ ] pre-commit（ruff+mypy）零违规。
5. [ ] **未碰 core 编排 / executor / Web**（那些是 Codex/Qoder 的）。
