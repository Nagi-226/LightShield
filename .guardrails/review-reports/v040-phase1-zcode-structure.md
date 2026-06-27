# 全项目结构审计报告 — Phase 1-B

> **审查者**：CodeBuddy (GLM-5.2 · ZCode 替补) | **日期**：2026-06-27
> **审查范围**：`lightshield/` 下全部 46 个 .py 文件（含 `__init__.py`）
> **审查方法**：全局扫描——逐文件读入构建依赖图，再按 6 维度交叉分析
> **基线**：v0.0.40 封版，771 tests
> **分层参照**：`CLAUDE.md §四`

---

## 发现总览

| 🗑️ 死代码 | 📋 重复逻辑 | 🔗 循环依赖 | 🚫 分层违规 | 💧 抽象泄露 | 🔀 契约不一致 |
|:--:|:--:|:--:|:--:|:--:|:--:|
| 3 | 8 | 0 | 6 | 6 | 7 |

**严重度分布**：🔴 高 4 ｜ 🟡 中 14 ｜ 🟢 低 12

---

## 一、死代码

| # | 位置 | 描述 | 严重度 | 建议 |
|:--:|------|------|:--:|------|
| D1 | `rules/engine.py:365-366` | `_match_service_fingerprint` 中 `rule.get("service","").lower()` 和 `rule.get("auth_result","")` 调用后返回值未赋给任何变量——纯死语句 | 🟡 中 | 删除这两行，或赋值后用于实际匹配逻辑 |
| D2 | `rules/engine.py:384-385` | `_match_header` 中 `rule.get("header","").lower()` 和 `rule.get("pattern","")` 同样是死语句 | 🟡 中 | 同上 |
| D3 | `repository/base.py:84-203` | `JsonFileRepository` 类（v0.0.20 实现）在当前代码中**无任何调用方**——CLI 和 Web 全部使用 `get_repository("sqlite", ...)`。`get_repository` 工厂中 `backend=="json"` 分支也无人触发 | 🟢 低 | 标注为 deprecated 或移除；若保留作教学示例，在 docstring 中注明"仅历史保留，不再使用" |

---

## 二、重复逻辑

| # | 位置 | 描述 | 严重度 | 建议 |
|:--:|------|------|:--:|------|
| R1 | `web/routes.py:567-599` 与 `web/pages.py:170-194` | `_reconstruct_findings` 函数在两个文件中**几乎逐行重复定义**（从 dict 重建 VulnFinding） | 🔴 高 | 提取为 `VulnFinding.from_dict(d)` classmethod 放到 `adapters/base.py`，两处共用 |
| R2 | `web/routes.py` ×3 + `web/pages.py` ×3 = **6 处** | `db_url = config.db_url or "data/lightshield.db"` + `repo = get_repository("sqlite", db_url=db_url)` 模式重复 6 次 | 🔴 高 | 提取为 `web/_helpers.py` 的 `_get_repo(config)` 函数；或由 core 暴露 `core.get_scan(scan_id)` 接口，web 层不直接碰 repository |
| R3 | `rules/engine.py:445-457` 与 `report/reporter.py:301-310` | `RuleEngine.summarize_risks()` 和 `ReportGenerator._risk_summary()` 做完全相同的事——统计 findings 各风险等级数量，实现几乎一致 | 🟡 中 | 提取为 `utils/risk_stats.py` 公共函数，两处调用 |
| R4 | 严重度排序字典 | `severity_order` / `SEVERITY_ORDER` 在 `rules/engine.py`（2 处：L435 字符串版 + L518 枚举版）、`report/pdf_writer.py:25`、`cli.py:728` 重复定义 4 次 | 🟡 中 | 统一定义到 `utils/constants.py`，如 `SEVERITY_RANK: dict[str, int]` |
| R5 | `sys.path.insert` 兜底 | 11 个文件开头有相同模式的 `sys.path.insert(0, ...)` 用于支持直接 `python file.py` 自检 | 🟡 中 | 移除运行时兜底（生产环境用 `pip install -e .` 安装包后无需）；自检改用 `python -m lightshield.module` 方式运行 |
| R6 | 适配器计时模式 | `started_at = time.monotonic()` → 执行 → `duration = time.monotonic() - started_at` 在 nmap/msf/nuclei/web_vuln 四个适配器中重复 | 🟢 低 | 可用装饰器 `@timed_scan` 提取，但优先级低（可读性影响小） |
| R7 | ScanResult 失败构造 | `return ScanResult(status=ScanStatus.FAILED, target=target, error=msg)` 在所有适配器中重复 10+ 次 | 🟢 低 | 加 `ScanResult.failed(target, error)` classmethod 工厂 |
| R8 | subprocess 调用样板 | 4 个适配器各自实现 `subprocess.run(capture_output, text, timeout)` + `TimeoutExpired/FileNotFoundError` 异常处理 | 🟢 低 | BaseAdapter 提供 `_run_command(cmd, timeout)` 辅助方法统一异常转 ScanResult |

---

## 三、循环依赖

| # | 位置 | 描述 | 严重度 | 建议 |
|:--:|------|------|:--:|------|
| — | — | **无循环依赖**。依赖图为严格分层的 DAG：`utils/constants` → `adapters/base` / `harden/base` / `config` → `scanners` / `rules` / `sandbox` → `core` → `cli` / `web`。`core.py` 用 `TYPE_CHECKING` import `ClosedLoopResult` 和 `OSPlatform` 是合理的类型标注实践，**非掩盖循环** | ✅ | — |

**附注**：`core.py:30` 的 `TYPE_CHECKING` 块中 `from lightshield.utils.constants import OSPlatform` 是**冗余**的——顶部 L40 已 `from lightshield.utils.constants import ScanStatus`，OSPlatform 完全可以合并到顶部 import。这不是循环依赖问题，属于轻微冗余。

---

## 四、分层违规（重点）

分层图：`web/ → core.py → {adapters/, scanners/, rules/, harden/, sandbox/, report/, utils/}`

| # | 位置 | 违规描述 | 严重度 | 建议 |
|:--:|------|------|:--:|------|
| L1 | `web/routes.py:26,28,29,30` + `web/pages.py:9,11` | **Web 层直接 import adapters/rules/report/repository**——跳过 core 编排。Web 层应只依赖 `core` + `utils`，由 core 暴露领域操作 | 🔴 高 | core 增加 `core.get_scan(scan_id)`, `core.recommend_harden(scan_id)`, `core.generate_report(scan_id, fmt)` 等门面方法；web 层只调这些 |
| L2 | `web/routes.py:326-328` + `web/pages.py:125-127` | **Web 层直接 `RuleEngine().load_rules()` + `engine.recommend_hardening()`**——规则匹配是 core 的职责，web 层不应触及 RuleEngine | 🔴 高 | core 暴露 `core.get_harden_recommendations(scan_id)` 方法，内部封装 RuleEngine 调用 |
| L3 | `web/routes.py:540-599` + `web/pages.py:170-194` | **Web 层从 dict 重建 VulnFinding/ScanResult**（`_reconstruct_findings` / `_reconstruct_scan_result`）——反序列化是 repository/core 的职责 | 🔴 高 | repository 层应返回领域对象而非裸 dict；或 core 提供 `core.load_scan(scan_id) -> ScanResult` |
| L4 | `scanners/port_scanner.py:13` | **Scanners 层直接依赖具体适配器** `from lightshield.adapters.nmap_adapter import NmapAdapter`——scanners 和 adapters 是同级，port_scanner 应通过 core 注入适配器，而非硬编码依赖 NmapAdapter | 🟡 中 | port_scanner 接受 `BaseAdapter` 注入，由 core 负责实例化并传入 NmapAdapter |
| L5 | `web/routes.py:246,313,412` + `web/pages.py:66,103,148` | **Web 层直接操作 repository**——`get_repository("sqlite", db_url=...)` 散落 6 处。Web 层不应感知存储后端类型和 db_url | 🟡 中 | core 持有 repository 实例，暴露 `core.get_scan(scan_id)`, `core.list_recent_scans(limit)` |
| L6 | `cli.py:18-25` | **CLI 直接 import adapters/rules/report/utils 多层**——CLI 直接串联 RuleEngine + ReportGenerator + core。虽然 CLI 作为最顶层入口有一定编排权，但 scan→match→report 全链路散在 CLI 中 | 🟢 低 | core 增加 `core.run_full_pipeline(target) -> report_path` 一站式方法，CLI 只负责参数解析 + R4 确认 |

---

## 五、抽象泄露

| # | 位置 | 描述 | 严重度 | 建议 |
|:--:|------|------|:--:|------|
| A1 | `nmap_adapter.py`, `msf_adapter.py`, `nuclei_adapter.py`, `sandbox/*.py` | **subprocess 实现细节泄露到 5 个适配器**——每个适配器各自管理 `subprocess.run(capture_output, text, timeout)` + 超时/找不到异常处理。BaseAdapter 未提供统一的命令执行辅助 | 🟡 中 | BaseAdapter 增加 `_run_external(cmd, timeout) -> tuple[stdout, stderr, returncode]` 辅助方法，统一异常转 ScanResult |
| A2 | `web/routes.py:43` + `routes.py:503-530` | **加固脚本文件命名规则泄露到 Web 层**——`SCRIPT_FILENAME_PATTERNS = ("harden_*.sh", ...)` 和 `_resolve_script_path` 让 web 屄知道了 harden 层的文件命名约定 | 🟡 中 | harden 层暴露 `Hardener.list_scripts(scan_id)` 或 core 提供 `core.list_scripts(scan_id)`，web 层不硬编码模式 |
| A3 | `utils/constants.py` 中 `SANDBOX_DEFAULT_*` | **Docker 容器参数泄露到全局常量**——`SANDBOX_DEFAULT_IMAGE/MEMORY/CPUS/PIDS_LIMIT/NETWORK` 是 Docker 执行器的实现细节，却放在全局 constants 中 | 🟢 低 | 移到 `sandbox/docker_executor.py` 内部作为类常量或默认参数 |
| A4 | `adapters/base.py:47` | **ScanResult.to_dict() 硬编码 `"adapter_name": "merged"`**——合并结果的 adapter_name 永远是 "merged"，这是 core.run_scan 合并逻辑的实现细节泄露到数据结构 | 🟢 低 | ScanResult 增加可选 `adapter_name` 字段，由 core 合并时传入 |
| A5 | `web/routes.py:246` 等 6 处 | **db_url 硬编码 `"data/lightshield.db"` 泄露到 web 层**——数据库路径应完全由 config 管理 | 🟡 中 | config 的 `db_url` 字段设默认值为 `"data/lightshield.db"`，web 层直接用 `config.db_url` 不加 `or` 兜底 |
| A6 | `harden/base.py:121-131` | **`_substitute` 方法暴露了命令模板格式**——`{port}`, `{target}` 占位符是 harden 层内部约定，但放在基类中暗示所有子类都要遵循此模板格式 | 🟢 低 | 可接受（加固脚本模板确实需要占位符替换），但应在 docstring 中明确这是约定 |

---

## 六、接口契约一致性

| # | 位置 | 描述 | 严重度 | 建议 |
|:--:|------|------|:--:|------|
| C1 | `core.py:834` vs `core.py:456` | **os_platform 类型不一致**——`run_harden_closed_loop` 接受 `str | OSPlatform`，`generate_hardening` 接受 `str | None`，两者内部都要做 `OSPlatform(str.lower())` 转换 | 🟡 中 | 统一为 `os_platform: OSPlatform`，调用方负责转换 |
| C2 | `closed_loop.py:45` + `verify.py:48` | **mode/verdict/overall 用裸字符串而非枚举**——`mode = "dry_run"|"apply"`、`verdict = "verified"|"partial"|"failed"`、`overall = ...|"generated_only"` 都是裸字符串，而 `HardenStatus` 是 Enum。同概念两种风格 | 🟡 中 | 新增 `ClosedLoopMode(Enum)` 和 `VerificationVerdict(Enum)`，与 HardenStatus 风格统一 |
| C3 | `config.py:274-292` | **`to_dict()` 不完整**——缺少 v0.0.40 新增的 `bark_key` 和 `report_auto_archive` 字段。`_update_from_dict` 用 `dataclasses.fields()` 自动发现（完整），但 `to_dict` 是手写的（不完整） | 🟡 中 | `to_dict()` 也改用 `dataclasses.fields()` 自动遍历，或补全缺失字段 |
| C4 | `config.py:58` vs 其他 | **output_dir 命名不一致**——config 字段名 `report_output_dir`，但 `ReportGenerator.__init__` / `core.generate_hardening` / `Hardener.generate` 参数都叫 `output_dir` | 🟢 低 | 统一命名（建议 config 也叫 `output_dir`，或调用方都用 `report_output_dir`） |
| C5 | `rules/engine.py:445` vs `report/reporter.py:301` | **风险统计返回结构一致但实现独立**——两处都返回 `{"critical": N, "high": N, ...}`，但各自硬编码键名 | 🟢 低 | 提取公共函数（见 R3） |
| C6 | 全局 | **"findings" 语义三义**——`ScanResult.findings`（适配器原生）、`RuleEngine.match()` 返回值（规则匹配）、CLI `_merge_findings()` 结果（合并后）。三处都叫 findings 但语义不同 | 🟡 中 | 引入类型别名或子类区分：`ScannerFindings` / `RuleFindings` / `MergedFindings`，或至少在 docstring 中标注来源 |
| C7 | `adapters/base.py:37` | **ScanResult.findings 字段类型引用 `"VulnFinding"` 字符串**——`findings: list["VulnFinding"]` 用前向引用字符串，但 VulnFinding 在同文件 L58 紧随定义。这是合法的，但说明两个 dataclass 有隐式耦合顺序 | 🟢 低 | 可接受（Python dataclass 常见模式），无需修改 |

---

## 架构整体评价

LightShield v0.0.40 的代码库**整体架构健康度良好**，核心设计（适配器模式 + 分层 + 合规红线落地）扎实且一致。771 tests 零失败、ruff+mypy 全零违规说明工程纪律到位。

**核心优势**：
1. **依赖图无环**——DAG 分层严格，TYPE_CHECKING 使用规范，无循环依赖债务
2. **合规红线落地彻底**——R1-R6 在代码中有明确的 enforce 点（validator、msf 白名单、sandbox 闸门、R1 关键字扫描）
3. **v0.0.40 闭环设计前瞻**——ClosedLoopResult/VerificationResult 数据结构干净，纯函数 verify_hardening 可测性好
4. **异常安全文化一致**——所有适配器统一返回结构化结果而非抛异常

**主要债务集中在 Web 层与 Core 的边界**：
- Web 层（routes.py + pages.py）承担了过多本应由 Core 编排的职责——直接 import rules/repository/adapters，自己重建领域对象，自己调 RuleEngine。这是当前最突出的分层违规（L1-L3 + L5），共 4 条高级别问题。
- `_reconstruct_findings` 重复定义和 `db_url` 模式 6 处重复是这一边界问题的直接症状。

**次要债务**：
- rules/engine.py 有两处死代码（D1/D2）和两个半成品匹配方法（`_match_service_fingerprint` / `_match_header` 的规则字段读取后未使用）
- config.to_dict() 与字段自动发现不同步
- 严重度排序字典散落 4 处

**建议优先级**：
1. 🔴 **立即**：提取 `_reconstruct_findings` 到公共位置（R1）；提取 `_get_repo(config)` 辅助（R2）；core 增加门面方法让 web 层不直接碰 rules/repository（L1-L3）
2. 🟡 **下个迭代**：修复 rules/engine.py 死代码（D1/D2）；统一严重度排序常量（R4）；config.to_dict() 补全（C3）；引入 mode/verdict 枚举（C2）
3. 🟢 **择期**：清理 sys.path.insert 兜底（R5）；BaseAdapter 增加 `_run_command` 辅助（A1/R8）；废弃 JsonFileRepository（D3）

**结论**：代码库无"屎山"级问题，但 Web-Core 边界存在系统性分层泄漏，建议在 v0.0.41 专项治理。其余为常规维护性债务，不阻塞 v0.0.40 发布。

---

> **审查约束遵守**：本报告仅标注问题，未修改任何代码。分层图参照 `CLAUDE.md §四`。利用 GLM-5.2 大上下文窗口逐文件读入 46 个 .py 构建全局依赖视图后交叉分析，非孤立逐文件审查。
