# ADR-v043：Web-Core 分层边界 — 建立 core 门面，消除 Web 层穿透

> **状态**：✅ Accepted（经架构二审修订）
> **日期**：2026-06-30
> **决策者**：Claude Code（架构 + 安全终审）｜**二审**：CodeBuddy 切 GLM-5.2（ZCode 替补，1M 上下文）
> **二审报告**：`docs/review-v044-codebuddy-arch-review.md`（🟡 Changes Requested → 3 项修改后 Approved）
> **关联**：`.guardrails/review-reports/v040-phase2-codex-verification.md`（CB-R1/R2/L1/L2/L3/C1）
> **类型**：分层架构模式治理 → 范围漂移阀值「架构模式改变→🟠 暂停+ADR」强制立项

---

## 1. 背景（Context）

### 1.1 问题：Web 层绕过 core 直接穿透到下层

当前 `lightshield/web/pages.py` 和 `lightshield/web/routes.py` 中存在大量**跨层直接调用**，绕过了 `lightshield/core.py` 的门面：

```python
# pages.py — 直接从 web 层穿透到 repository + rules + adapters
from lightshield.adapters.base import VulnFinding      # ← 跨层
from lightshield.repository.base import get_repository  # ← 跨层
from lightshield.rules.engine import RuleEngine          # ← 跨层

# harden_page() 里的典型穿透链:
repo = get_repository("sqlite", db_url=db_url)           # web → repository
scan_data = repo.get(scan_id)                            # web → repository
raw = scan_data.get("raw_result", scan_data)             # web 直接操作 dict
findings = _reconstruct_findings(raw.get("findings", [])) # web → adapters
engine = RuleEngine()                                    # web → rules
engine.load_rules()                                      # web → rules
recommendations = engine.recommend_hardening(findings)    # web → rules
```

这种穿透导致 **6 项债务**：

| 编号 | 类型 | 问题 | 等级 |
|:--:|------|------|:--:|
| CB-R1 | 重复 | `_reconstruct_findings` 在 pages.py 和 routes.py 中各有一份几乎相同的实现 | 🟡 MEDIUM |
| CB-R2 | 重复 | `get_repository("sqlite", db_url=...)` 的 fallback 模式在 web 层重复 6 次 | 🟡 MEDIUM |
| CB-L1 | 分层穿透 | Web 层通过 `repo.get()` 获取原始 dict，再手动解包 `raw_result` | 🟡 MEDIUM |
| CB-L2 | 分层穿透 | Web 层直接 `RuleEngine()` + `.load_rules()` + `.recommend_hardening()` | 🔵 LOW |
| CB-L3 | 耦合 | Web 层从 dict 手动重建 `VulnFinding` 领域对象 | 🔵 LOW |
| CB-C1 | 契约 | `os_platform` 类型在 `str` / `OSPlatform` 枚举之间不一致 | 🔵 LOW |

### 1.2 为什么现在修

1. 已累积 6 项跨层债务（3 MEDIUM + 3 LOW），每次新增 Web 功能都会产生新穿透点
2. v0.0.43 前 CC 直接可修项已全部清零（8 MEDIUM），剩余 MEDIUM 全部集中在此
3. 不修 → 债务按 Web 端点数量线性增长

### 1.3 当前架构分层（问题视图）

```
CLI ─────────→ core ─────────→ adapters / rules / repository / harden
                                 ✅ 干净分层

Web ──→ core ──→ adapters / harden  ← 调 core.generate_hardening() ✅
  │
  ├──→ get_repository()              ← 绕过 core ❌
  ├──→ RuleEngine()                  ← 绕过 core ❌
  ├──→ VulnFinding(...)              ← 绕过 core ❌
  ├──→ ReportGenerator()             ← 绕过 core ❌
  └──→ raw dict 手动解包             ← 绕过 core ❌
```

---

## 2. 决策（Decision）

**在 `LightShieldCore` 上新增 4 个门面方法。Web 层仅调用 core 门面 + config，删除所有跨层 import。**

### 2.1 新增 core 门面接口

```python
# lightshield/core.py — 新增方法

class LightShieldCore:

    # =========================================================================
    # 🆕 v0.0.44 Web-Core 门面（Web 层唯一入口）
    # =========================================================================

    def load_scan(self, scan_id: str) -> ScanResult | None:
        """从仓库加载一次扫描，返回完整 ScanResult（含结构化 findings）。

        内部完成：repo.get → raw_result 解包 → _reconstruct_scan_result → _reconstruct_findings。
        Web 层不需要知道 repository backend / raw_result 结构。

        返回 None 表示 scan_id 不存在。仓库异常 → 日志 + 返回 None。

        **返回 ScanResult（非 dict）的理由**：
        - 与 core 所有方法的返回类型一致（run_scan/generate_hardening/run_harden_closed_loop
          全部返回 dataclass）
        - Web 层需要 dict 时调 result.to_dict()；传给 ReportGenerator 时直接传 dataclass
        - _reconstruct_scan_result 自然迁入此方法内部
        """

    def get_recommendations(self, scan_id: str) -> list[dict]:
        """获取加固建议。

        内部完成：load_scan → RuleEngine 加载 → recommend_hardening。
        Web 层不需要知道 RuleEngine / load_rules / recommend_hardening。

        返回空列表表示：扫描不存在 / 无 findings / 无匹配规则 / 仓库/RuleEngine 异常。
        """

    def get_scan_history(self, limit: int = 20) -> list[dict]:
        """获取最近扫描历史列表。

        Web 层不需要知道 repository backend / db_url。
        仓库异常 → 返回空列表。
        """

    @staticmethod
    def os_platform_normalize(raw: str | OSPlatform | None) -> str:
        """将 os_platform 输入规范化为字符串值。

        接受：OSPlatform 枚举 / 字符串 / None → 返回标准化的字符串值。
        generate_hardening() 内部调用此方法（替换当前 L518 的 getattr/f-string 逻辑）。
        """
```

### 2.2 `generate_hardening` 集成变更

```python
def generate_hardening(self, target, ..., os_platform: str | OSPlatform | None = None):
    # 旧：platform = (getattr(os_platform, "value", None) or os_platform or "").lower()
    # 新：统一调用 normalize
    platform = self.os_platform_normalize(os_platform)
```

### 2.3 异常语义（强制契约）

| 方法 | repository 异常 | RuleEngine 异常 | 返回值 |
|------|:--:|:--:|------|
| `load_scan` | 日志 + `None` | — | `ScanResult \| None` |
| `get_recommendations` | — | 日志 + `[]` | `list[dict]`（永不抛异常） |
| `get_scan_history` | 日志 + `[]` | — | `list[dict]`（永不抛异常） |
| `os_platform_normalize` | — | — | `str`（永不抛异常） |

> **设计原则**：与 web 层现有 `try/except → 空值兜底` 的容错模式一致。门面方法永不向上抛异常——失败时返回安全默认值（None / 空列表）+ 日志记录。

### 2.4 依赖方向变化

core.py 当前不依赖 repository（持久化由 CLI/Web 层各自调用）。门面方法让 core **首次 import repository**——这是合理的职责集中：

- 旧：`CLI → repository`、`Web → repository`（各自调用，重复 6+ 处）
- 新：`CLI → repository`（CLI 保留直接调用）、`Web → core → repository`（Web 走门面）

core 的单元测试需要 mock repository。核心逻辑测试不受影响。

### 2.5 Web 层改造后效果

```python
# pages.py — 改造后（仅 import core + config，零跨层）
def harden_page(scan_id: str):
    core = current_app.config["LIGHTSHIELD_CORE"]
    scan = core.load_scan(scan_id)                    # ScanResult | None
    if scan is None:                                   # dataclass 属性访问
        return render_template(..., error="...")
    recommendations = core.get_recommendations(scan_id)
    return render_template(..., target=scan.target,
                           findings_count=len(scan.findings),
                           recommendations=recommendations)

# routes.py — 改造后（报告生成直接用 dataclass）
def api_get_report(scan_id: str):
    scan = core.load_scan(scan_id)                    # ScanResult
    if scan is None:
        return jsonify(...), 404
    report = reporter.generate(scan, findings=scan.findings, fmt=fmt)
    # ↑ scan 是 ScanResult dataclass，直接兼容 ReportGenerator
```

### 2.6 分层契约（不可违反）

| Web 层允许的 import | Web 层禁止的 import |
|------|------|
| `lightshield.core`（门面） | `lightshield.repository.*` |
| `lightshield.config`（配置） | `lightshield.rules.*` |
| `lightshield.web.*`（自身子模块） | `lightshield.adapters.*`（VulnFinding/ScanResult 等） |
| `lightshield.utils.constants`（枚举，如 RiskLevel） | `lightshield.harden.*` |
| `lightshield.report.reporter`（仅 api_get_report 生成报告用，传入 ScanResult） | `lightshield.sandbox.*` |

> **注**：`lightshield.report.reporter` 保留在允许列表——`ReportGenerator.generate(ScanResult)` 是报告**渲染**职责，不是数据获取。Web 层通过 `core.load_scan()` 获取 ScanResult 后，传入 Reporter 做渲染是合理的数据流（非穿透）。

### 2.7 治理范围

| 步骤 | 内容 | 涉及文件 |
|:--:|------|------|
| 1 | core 新增 `load_scan` / `get_recommendations` / `get_scan_history` / `os_platform_normalize` | `lightshield/core.py` |
| 2 | `generate_hardening` 内部改用 `os_platform_normalize` 替换 L518 重复逻辑 | `lightshield/core.py` |
| 3 | web/pages.py 删除跨层 import + `_reconstruct_findings`，改调 core 门面 | `lightshield/web/pages.py` |
| 4 | web/routes.py 删除跨层 import + `_reconstruct_findings` + `_reconstruct_scan_result`，改调 core 门面 | `lightshield/web/routes.py` |
| 5 | core 单元测试补 mock repository | `tests/test_core.py` |
| 6 | 全量回归 784 tests | `tests/` |

---

## 3. 被否决的备选（Alternatives Considered）

| 方案 | 内容 | 否决理由 |
|------|------|---------|
| **B：保持现状，逐个修重复** | 不建门面，只提取 `_reconstruct_findings` 到共享模块 | 每次新增 Web 端点必然产生新穿透点——门面缺失是根因 |
| **C：Web 层通过 CLI subprocess 调用 core** | Web 请求→`subprocess lightshield scan ...` | 进程边界开销 + shell 注入风险，与本地工具定位不符 |
| **D：`load_scan` 返回 dict**（ADR 初版方案） | 返回 `dict` 含 `list[VulnFinding]` 的混合类型 | 二审发现与项目"core 返回 dataclass"模式不一致；无法直接传给 ReportGenerator；JSON 序列化需手动处理。改为返回 ScanResult（本版） |

---

## 4. 后果（Consequences）

### 4.1 正面

- **分层清晰**：Web 依赖从 5 个模块（adapters/repository/rules/harden/core）收敛到 2 个（core/config + reporter 渲染）
- **类型一致**：`load_scan` 返回 ScanResult，与 core 全部方法风格一致
- **ReportGenerator 兼容**：ScanResult 可直接传入，无需额外门面
- **单一职责**：`_reconstruct_findings` 和 `_reconstruct_scan_result` 从两处重复收敛到 core 内部
- **可测试性**：core 门面方法可独立测试（mock repository）
- **扩展安全**：未来新增 Web 端点不会自动产生穿透

### 4.2 代价

- core.py 增加约 **80-100 行**（4 个门面方法 + `_reconstruct_*` 迁入）
- core 首次 import repository（依赖方向变化，合理）
- web/pages.py 约 **-25 行**（删除 `_reconstruct_findings` + 简化路由）
- web/routes.py 约 **-45 行**（删除 `_reconstruct_*`×2 + 简化 6 处 repo/RuleEngine 调用）
- core 单元测试需补 mock repository（约 +15 行）
- 净代码变化：约 **+15~30 行**（删重复 70 行 + 增门面 100 行）

### 4.3 验收标准

1. `grep -r "from lightshield.repository" lightshield/web/` 返回空
2. `grep -r "from lightshield.rules" lightshield/web/` 返回空
3. `grep -r "from lightshield.adapters" lightshield/web/` 返回空
4. `grep -r "_reconstruct_findings" lightshield/web/` 返回空
5. `grep -r "_reconstruct_scan_result" lightshield/web/` 返回空
6. 784 tests 全量通过，0 回归

---

## 5. 二审修订记录（CodeBuddy GLM-5.2）

| 发现 | ADR 初版 | 修订后 |
|:--:|------|------|
| F-1 | "5 个门面方法"但只定义 4 个 | 修正为 4 个（ReportGenerator 穿透由 ScanResult 返回类型解决，无需额外门面） |
| F-2 | api_get_report 的 ReportGenerator 调用无门面覆盖 | `load_scan` 返回 ScanResult → 直接兼容 ReportGenerator |
| F-3 | load_scan 返回 dict 混合 dataclass | 改为返回 `ScanResult \| None` — 与项目模式一致 |
| F-4 | 未定义门面方法异常语义 | §2.3 新增异常语义契约 |
| F-5 | `_reconstruct_scan_result` 迁移位置未明确 | 随 F-3 解决 → 自然迁入 load_scan 内部 |
| F-7 | `os_platform_normalize` 与 generate_hardening 关系不明 | §2.2 明确 generate_hardening 调用它并删除 L518 重复逻辑 |

---

## 6. 与现有防线体系的关系

```
六大铁律 #6「理解再改」→ 十荣十耻 #6「遵循规范·分层不跨层」
    │
    └── 本次 ADR：明确 Web → core 分层契约，消除 6 项跨层穿透
         │
         ├── Gate C（质量审计·M8 架构维度）：分层违规 → grep 自动化检测
         └── 范围漂移阀值：架构模式改变 → 🟠 ADR（本次）
```
