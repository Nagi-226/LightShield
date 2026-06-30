# Web-Core 边界 ADR 架构二审报告

**审查模型**：GLM-5.2（ZCode 替补）| **被审决策作者**：Claude Code (DS V4-Pro)
**跨模型审查**：✅ GLM ≠ DS
**审查对象**：`docs/adr-v043-web-core-facade.md`
**审查日期**：2026-06-30
**审查范围**：架构决策全局一致性（非代码审查）

---

## 结论

**🟡 Changes Requested**

ADR 方向正确——建门面消除 Web 层穿透是正确的架构治理决策。但有 **3 个阻塞性问题** 需修改后才能合入：

1. **门面数量不一致**：ADR §2 声称"5 个门面方法"但 §2.1 只定义 4 个；且 `api_get_report` 端点的 ReportGenerator 穿透未被覆盖
2. **load_scan 返回类型不符合项目模式**：返回 dict 但嵌套 VulnFinding dataclass 是混合类型，与项目"core 返回 dataclass + web 调 to_dict()"的一致模式冲突
3. **异常语义未定义**：门面方法的异常处理契约缺失，可能导致 web 层仍需 try/except 包裹 core 调用

---

## 五维发现

### ① 分层语义自洽

**穿透点覆盖矩阵**（ADR 定义的 4 个方法 vs 6 项穿透点）：

| 穿透点 | 描述 | 被哪个门面覆盖 | 状态 |
|:--:|------|------|:--:|
| CB-R1 | `_reconstruct_findings` 重复 | `load_scan()` 内部重建 | ✅ |
| CB-R2 | `get_repository` fallback 重复 6 次 | `load_scan()` + `get_scan_history()` + `get_recommendations()` 内部调 repo | ✅ |
| CB-L1 | `repo.get()` 获取原始 dict 再解包 | `load_scan()` 封装 | ✅ |
| CB-L2 | 直接 `RuleEngine()` + `.load_rules()` | `get_recommendations()` 封装 | ✅ |
| CB-L3 | 从 dict 手动重建 VulnFinding | `load_scan()` 返回已重建的 findings | ✅ |
| CB-C1 | os_platform 类型不一致 | `os_platform_normalize()` | ✅ |

**已定义的 6 个穿透点全部覆盖**。但审查中发现 **2 个 ADR 未列入的穿透点**：

| # | 新发现穿透点 | 位置 | 当前 web 层代码 | ADR 是否覆盖 |
|:--:|------|------|------|:--:|
| NP-1 | **ReportGenerator 穿透** | `routes.py:28,307-309` | Web 层直接 `from lightshield.report.reporter import ReportGenerator` + `ReportGenerator().generate(scan_result, findings, fmt)` | ❌ |
| NP-2 | **脚本文件命名规则穿透** | `routes.py:43,503-530` | `SCRIPT_FILENAME_PATTERNS = ("harden_*.sh", ...)` 硬编码在 web 层 + `_resolve_script_path` 知道 harden 层文件命名约定 | ❌ |

**NP-1 是阻塞性问题**：`api_get_report` 端点（`routes.py:228-323`）的完整调用链是 `get_repository → _reconstruct_scan_result → _reconstruct_findings → ReportGenerator.generate()`。ADR 的 `load_scan()` 覆盖了前三步，但 **ReportGenerator 调用没有门面覆盖**——且 `load_scan` 返回 dict（非 ScanResult），而 `ReportGenerator.generate()` 需要 `ScanResult` 对象作为参数，**类型不兼容**。

**ADR 内部不一致**：ADR §2 正文声称"新增 5 个门面方法"，但 §2.1 只列出 4 个（`load_scan` / `get_recommendations` / `get_scan_history` / `os_platform_normalize`）。第 5 个方法很可能是为 NP-1 预留的报告生成门面，但未写出。

### ② ADR vs 实现对照

| 检查项 | 现有 core.py 状态 | ADR 要求 | 兼容性 |
|------|------|------|:--:|
| `VulnFinding` import | L36 `from lightshield.adapters.base import ... VulnFinding` ✅ 已有 | `load_scan` 需重建 VulnFinding | ✅ 兼容 |
| `repository` import | **无** —— core.py 当前不 import repository | `load_scan` / `get_scan_history` / `get_recommendations` 均需调 repository | 🟡 需新增依赖 |
| `RuleEngine` import | `generate_hardening` 内部惰性 import（L496） ✅ | `get_recommendations` 需调 RuleEngine | ✅ 可复用惰性 import 模式 |
| `OSPlatform` | L28-30 TYPE_CHECKING 块中有 | `os_platform_normalize` 需用 OSPlatform | ✅ 兼容 |
| `generate_hardening` 签名 | `os_platform: str | None = None`（L469） | ADR 说"统一 generate_hardening 签名"但未明确改成什么 | 🟡 不明确 |
| `generate_hardening` 内部规范化 | L518 `platform = (getattr(os_platform, "value", None) or os_platform or "").lower()` 已有 | ADR 新增 `os_platform_normalize` 但未说 generate_hardening 是否调它 | 🟡 不明确 |

**关键发现**：core.py 当前**不依赖 repository**——core 只管扫描编排和加固生成，持久化由 CLI 和 Web 层各自调用 repository 完成。ADR 的门面方法会让 core **首次依赖 repository**，这是一个**职责扩展**。虽然合理（core 作为门面理应封装持久化），但 ADR 未明确指出这一依赖方向变化的影响——core 的单元测试现在需要 mock repository。

### ③ 跨模块接口契约

**`load_scan()` 返回 dict vs dataclass 分析**：

ADR §2.1 定义 `load_scan` 返回 `dict | None`，其中 `findings` 字段是 `list[VulnFinding]`（dataclass）。

| 对比维度 | ADR 方案（dict 混合 dataclass） | 项目现有模式（纯 dataclass） |
|------|------|------|
| 返回类型 | `dict` 含 `list[VulnFinding]` | `ScanResult`（dataclass） |
| 字段访问 | `scan["target"]` + `scan["findings"][0].vuln_type` 混合 | `result.target` + `result.findings[0].vuln_type` 统一 |
| 序列化 | 需手动处理 findings 的 to_dict | 调 `.to_dict()` 一步到位 |
| 与 ReportGenerator 兼容 | ❌ `ReportGenerator.generate()` 需要 `ScanResult` 参数 | ✅ 直接传入 |

**项目现有模式**（一致性参照）：
- `core.run_scan()` → `ScanResult`（dataclass）
- `core.generate_hardening()` → `HardenResult`（dataclass）
- `core.run_harden_closed_loop()` → `ClosedLoopResult`（dataclass）
- `core.verify_hardening()` → `VerificationResult`（dataclass）

**所有现有 core 方法都返回 dataclass**。ADR 的 `load_scan` 返回 dict 是唯一的例外——这破坏了接口契约一致性。

**建议**：`load_scan` 应返回 `ScanResult | None`。web 层需要 dict 时调 `result.to_dict()`；需要传给 ReportGenerator 时直接传 dataclass。这与 NP-1 的解决直接相关——如果 `load_scan` 返回 ScanResult，则 `api_get_report` 可以直接传入 ReportGenerator，无需额外门面。

**web 层改造后调用方代码自然度对比**：

```python
# ADR 方案（dict 混合 dataclass）—— 不自然
scan = core.load_scan(scan_id)  # dict
target = scan["target"]          # dict 访问
findings = scan["findings"]      # list[VulnFinding] —— 混合！
# 传给 ReportGenerator 需要重建 ScanResult —— 矛盾
reporter.generate(???, findings=findings, fmt=fmt)

# 建议方案（纯 dataclass）—— 自然
scan = core.load_scan(scan_id)   # ScanResult | None
target = scan.target             # 属性访问
findings = scan.findings         # list[VulnFinding]
reporter.generate(scan, findings=findings, fmt=fmt)  # 直接传入 ✅
```

### ④ 抽象层级合理性

**4 个方法数量评估**：合理偏少。应增加至 5 个（补报告生成门面或让 load_scan 返回 ScanResult 使报告生成无需门面）。

**薄包装分析**：

| 方法 | 是否薄包装 | 价值评估 |
|------|:--:|------|
| `load_scan` | 否——封装 repo.get + raw_result 解包 + findings 重建 | ✅ 高价值，消除 3 项穿透 |
| `get_recommendations` | 否——封装 repo.get + findings 重建 + RuleEngine 加载 + 推荐 | ✅ 高价值，消除 2 项穿透 |
| `get_scan_history` | **是**——仅 `repo.list_recent(limit)` 的透传 | 🟡 中价值——消除 db_url 穿透 + 异常封装（如果定义了异常语义） |
| `os_platform_normalize` | 是——纯类型转换工具函数 | 🟡 低价值——可用 `generate_hardening` 内部已有的 L518 逻辑替代 |

**`get_scan_history` 薄包装的价值**：虽是透传，但消除了"web 层知道 backend='sqlite' 和 db_url"这个穿透点（CB-R2 的 6 处之一）。如果 core 定义了异常语义（repo 异常 → 返回空列表），则 web 层不需要 try/except，价值进一步提升。

**`os_platform_normalize` 的问题**：ADR 说"统一 generate_hardening 签名"但未明确：
- `generate_hardening` 的 `os_platform` 参数类型会改吗？（当前 `str | None`，ADR 未说改成什么）
- `generate_hardening` 内部会调 `os_platform_normalize` 吗？（当前 L518 已有自己的规范化逻辑）
- 如果 `generate_hardening` 内部已能处理 `str | OSPlatform`（L518 的 `getattr(os_platform, "value", None)` 已兼容枚举），那 `os_platform_normalize` 是否多余？

**建议**：要么删除 `os_platform_normalize`（让 `generate_hardening` 内部 L518 逻辑继续兜底），要么明确 `generate_hardening` 会调用它并删除 L518 的重复逻辑。不能两套逻辑并存。

### ⑤ 遗漏关注点

| # | 遗漏项 | 严重度 | 描述 |
|:--:|------|:--:|------|
| O-1 | **门面方法异常语义** | 🔴 高 | ADR 未定义：repo 异常时 `load_scan` 返回 None 还是抛异常？RuleEngine 失败时 `get_recommendations` 返回空列表还是抛异常？现有 web 层用 try/except 包裹所有 repo 调用（pages.py L68-72），如果 core 门面不定义异常语义，web 层仍需 try/except——穿透虽消除但异常处理仍分散 |
| O-2 | **`_reconstruct_scan_result` 迁移位置** | 🔴 高 | ADR §2.4 步骤4 说"迁入 core"但未说具体位置。这与 ③ 的 dict vs dataclass 决策直接耦合：若 `load_scan` 返回 ScanResult，则 `_reconstruct_scan_result` 自然迁入 `load_scan` 内部；若返回 dict，则需要独立存在或迁入 repository |
| O-3 | **报告生成门面缺失** | 🔴 高 | `api_get_report` 端点的 ReportGenerator 调用无门面覆盖（NP-1）。若 `load_scan` 返回 ScanResult 则可自然解决；若返回 dict 则需新增第 5 个门面 `generate_report(scan_id, fmt)` |
| O-4 | **core 依赖方向变化** | 🟡 中 | core.py 当前不 import repository。门面方法让 core 首次依赖 repository——core 的单元测试需要 mock repository。ADR 未提及此影响 |
| O-5 | **`os_platform_normalize` 与 `generate_hardening` 集成关系** | 🟡 中 | ADR 说"统一 generate_hardening 签名"但未明确 generate_hardening 是否调用 os_platform_normalize，也未说 L518 现有逻辑是否删除 |
| O-6 | **脚本下载门面缺失** | 🟢 低 | `api_download_script` 的 `SCRIPT_FILENAME_PATTERNS` 和 `_resolve_script_path` 是 harden 层文件命名规则泄露。非本次 ADR 范围但建议后续治理 |
| O-7 | **`load_scan` 返回的 findings 是 dataclass 还是 dict** | 🟡 中 | ADR §2.1 docstring 写 `"findings": list[VulnFinding]`（dataclass），但返回类型标注是 `dict`。dataclass 嵌套在 dict 中无法直接 JSON 序列化——web 层返回 JSON 响应时需要手动调 to_dict()。这与"web 层不需要知道 raw_result 结构"的目标矛盾 |

---

## 发现清单

| # | 维度 | 严重度 | 描述 | 建议 |
|---|------|:--:|------|------|
| F-1 | ① 自洽 | 🔴 高 | ADR §2 声称"5 个门面方法"但 §2.1 只定义 4 个——内部不一致 | 补齐第 5 个方法（报告生成门面）或修正 §2 措辞为 4 个 |
| F-2 | ① 自洽 | 🔴 高 | `api_get_report` 的 ReportGenerator 穿透未被覆盖（NP-1）——load_scan 返回 dict 无法传给 ReportGenerator | 让 load_scan 返回 ScanResult，或新增 `generate_report(scan_id, fmt)` 门面 |
| F-3 | ③ 契约 | 🔴 高 | load_scan 返回 dict 混合 dataclass 不符合项目"core 返回 dataclass"的一致模式 | 改为返回 `ScanResult | None` |
| F-4 | ⑤ 遗漏 | 🔴 高 | 门面方法异常语义未定义（O-1） | ADR 补充：repo 异常 → 返回 None/空列表；RuleEngine 异常 → 返回空列表 + 日志 |
| F-5 | ⑤ 遗漏 | 🔴 高 | `_reconstruct_scan_result` 迁移位置未明确（O-2），与 F-3 耦合 | 若采纳 F-3（返回 ScanResult），则自然迁入 load_scan 内部 |
| F-6 | ② 对照 | 🟡 中 | core.py 当前不 import repository，门面方法引入新依赖方向（O-4） | ADR 补充影响说明 + core 测试需 mock repository |
| F-7 | ④ 抽象 | 🟡 中 | `os_platform_normalize` 与 generate_hardening L518 现有逻辑关系不明确（O-5） | 明确 generate_hardening 调用 os_platform_normalize 并删除 L518 重复逻辑 |
| F-8 | ③ 契约 | 🟡 中 | load_scan 返回 dict 中嵌套 VulnFinding dataclass 无法直接 JSON 序列化（O-7） | 若改为返回 ScanResult 则 to_dict() 自动处理 |
| F-9 | ① 自洽 | 🟢 低 | `api_download_script` 的脚本文件命名规则穿透未覆盖（NP-2/O-6） | 非本次范围，建议后续 ADR 治理 |
| F-10 | ④ 抽象 | 🟢 低 | `get_scan_history` 是薄包装但有价值（消除 db_url 穿透） | 保留，但需定义异常语义（F-4） |

---

## 翻车自检记录

按 `AGENTS十荣十耻通用准则.md §翻车模式` 七种自检：

| # | 翻车模式 | 是否触发 | 说明 |
|:--:|------|:--:|------|
| ① | Kitchen Sink | ❌ 未触发 | 审查任务，未改代码，无 diff 膨胀 |
| ② | Wrong Abstraction | ⚠️ **识别到** | ADR 的 `load_scan` 返回 dict 混合 dataclass 是潜在错误抽象——为只有一个调用方的问题建了不匹配的返回类型。止损建议：改为返回 ScanResult dataclass（F-3） |
| ③ | Optimistic Path | ⚠️ **识别到** | ADR 未定义门面方法的异常语义——假设 repository/RuleEngine 不会失败。止损建议：补充异常契约（F-4） |
| ④ | Runaway Refactor | ❌ 未触发 | 审查任务，无连锁修改 |
| ⑤ | 知识幻觉 | ❌ 未触发 | 所有发现基于实际代码读入，无凭记忆猜测 |
| ⑥ | 风格漂移 | ⚠️ **识别到** | `load_scan` 返回 dict 与项目现有 core 方法返回 dataclass 的风格不一致。止损建议：统一为 dataclass（F-3） |
| ⑦ | 隐式耦合破坏 | ⚠️ **识别到** | 若按 ADR 原方案实施，`api_get_report` 端点会因 load_scan 返回 dict 而无法传给 ReportGenerator——签名兼容但行为不兼容。止损建议：F-2/F-3 联动解决 |

**自检结论**：识别到 4 种翻车模式信号（②③⑥⑦），均已在发现清单中标注止损建议。未触发 STOP——本次为审查任务（不修改代码），翻车信号指向被审 ADR 而非本次审查行为本身。

---

## 修改建议汇总（给 CC）

若 CC 采纳以下 3 项修改，本审查可转为 **Approved**：

1. **F-3 + F-5 + F-8 联动**：`load_scan` 改为返回 `ScanResult | None`。`_reconstruct_scan_result` 自然迁入 load_scan 内部。web 层需要 dict 时调 `.to_dict()`。此修改同时解决 F-2（ReportGenerator 兼容）和 F-8（JSON 序列化）。

2. **F-4**：ADR 补充异常语义章节——所有门面方法在 repository/RuleEngine 异常时返回 None 或空列表（不向上抛异常），与 web 层现有 try/except → 空值兜底的模式一致。

3. **F-1 + F-7**：修正门面数量表述（4 个 or 补第 5 个）；明确 `generate_hardening` 内部调用 `os_platform_normalize` 并删除 L518 重复逻辑。

---

> **审查约束遵守**：本报告仅审查架构决策，未修改任何代码。R1-R6 合规红线无关联（纯架构审查）。六大铁律 #6「理解再改」+ 十荣十耻 #6「遵循规范·分层不跨层」+ #8「谨慎重构」已落实。翻车模式七种自检已完成。
