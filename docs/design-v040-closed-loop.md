# v0.0.40 自动加固闭环 — 接口契约（CC 架构设计）

> **状态**：✅ **正式版** — 基座决策已由 QoderWork 真机验证 + CC 安全终审定稿（见 ADR-v040 与 §9）。
> **作者**：Claude Code（架构 + 编排）｜**版本**：v0.0.40｜**日期**：2026-06-21（2026-06-22 回填定稿）
> **消费方**：Reasonix（verify 比对模块实现）、Qoder（Web 对比页面）、QoderWork（集群 E2E 夹具）、CodeWhale（审查基准）
> **关联**：ADR-v040 `docs/adr-v040-execution-substrate.md`、验证报告 `docs/e2e-v040-sandbox-verify-report.md`、验证门禁 `.cluster/tasks/pending/QODERWORK-v040-sandbox-verify.md`

---

## 1. 文档定位

本文是 v0.0.40「自动加固闭环」的**接口契约**，不是实现。它定义各模块之间的数据结构与方法签名，让 QoderWork / Reasonix / Qoder 能并行开发而接口不漂移。

✅ **基座决策已定稿（ADR-v040）**：APPLY = **宿主机本机执行**（新增 `backend="host"`），非 VM/特权容器；DRY_RUN 维持 v0.0.38 锁死容器。原 `【待验证】` 条目已按真机结论回填（§4/§6/§9），实现方可放行合入执行代码。

---

## 2. 现状盘点（已有的拼图，v0.0.38 止）

闭环 `扫描 → 推荐 → 生成脚本 → 执行 → 复扫 → 验证` 中，**前三环已就绪**，后两环缺位：

| 环节 | 现状 | 代码位置 |
|------|------|---------|
| 扫描 | ✅ `core.run_vuln_scan(target) -> ScanResult`（`.findings: list[VulnFinding]`） | `core.py:320` |
| 推荐 | ✅ `RuleEngine.recommend_hardening(findings) -> list[dict]` | `rules/engine.py:405` |
| 生成脚本 | ✅ `LinuxHardener/WinHardener.generate(target, recommendations, output_dir) -> HardenResult`（含 `script_path` + `rollback_path`） | `harden/linux_harden.py:122` / `win_harden.py:102` |
| 隔离执行 | 🟡 `SandboxExecutor.execute(script_path, confirm_execute=True) -> ExecutionResult`（Docker 后端）— **代码完成，真机未验证** | `sandbox/base.py` / `docker_executor.py` |
| 复扫 | ⬜ 缺（复用 `run_vuln_scan` 二次调用即可，无新接口） | — |
| **验证（比对）** | ⬜ **缺，v0.0.40 全新** | 待建 |
| **闭环编排** | ⬜ **缺，v0.0.40 全新** | 待建 |
| **Web 对比页面** | ⬜ **缺，v0.0.40 全新** | 待建 |

**既有数据结构（实现方按此对接，勿改字段名）：**
- `VulnFinding`（`adapters/base.py:58`）：`vuln_type: str`、`severity: RiskLevel`、`title: str`、`description: str`、`port: int | None`
- `HardenResult`（`harden/base.py:34`）：`status: HardenStatus`、`script_path`、`rollback_path`、`action_count`、`audit_id` …
- `ExecutionResult`（`sandbox/base.py:71`）：`status: ExecutionStatus`、`exit_code`、`stdout`、`stderr`、`duration_seconds`、`timed_out`、`audit_id` …

---

## 3. 闭环全景

```
run_harden_closed_loop(target, os_platform, confirm_ownership, mode, ...)
   │
   ├─① 基线扫描   core.run_vuln_scan(target)            → before: ScanResult
   ├─② 推荐       RuleEngine.recommend_hardening(...)   → recommendations: list[dict]
   ├─③ 生成       Hardener.generate(...)                → HardenResult(script_path, rollback_path)
   ├─④ 执行       SandboxExecutor.execute(script,...)   → ExecutionResult   ← 基座是 §4 的关键决策
   ├─⑤ 复扫       core.run_vuln_scan(target)            → after: ScanResult
   ├─⑥ 验证       verify_hardening(before, after)       → VerificationResult ← Reasonix 纯函数
   └─⑦ 汇总                                            → ClosedLoopResult（贯穿①-⑥ + 总判定）
```

---

## 4. 核心张力：DRY_RUN vs APPLY 基座【已定稿 · ADR-v040】

这是 v0.0.40 最关键的架构决策。QoderWork 真机验证（V1-V7 全证实）+ CC 安全终审后,**项目所有者拍板:APPLY = 宿主机本机执行**。详细论证见 `docs/adr-v040-execution-substrate.md`,以下为契约结论。

**v0.0.38 沙箱（`--network none` + `no-new-privileges` + 默认丢弃 caps + 无 init）跑不动真实加固(真机已证实):** `systemctl`(无 init→失败)、`iptables`(未安装且无网装不上)、`apt`(`--network none`→无网) 三杀;`--network none` + `--rm` 无可复扫目标。**它只适合做 DRY_RUN 预检层。**

闭环**区分两种执行模式**:

| 模式 | 基座 | 作用 | 改变目标? | 复扫目标 | R 红线 |
|------|------|------|:---:|------|------|
| `DRY_RUN`（默认） | v0.0.38 锁死容器（`backend="docker"`）+ `bash -n` | `bash -n` 语法 + R1 关键字内容扫描 + 锁死容器烟测(不卡死/可放行/超时干净 kill)。**不预演加固成败** | ❌ 否 | 不复扫 | 天然安全（`--network none` 物理隔离保留） |
| `APPLY` | **宿主机本机**（新增 `backend="host"`,`HostExecutor`） | 在真机 localhost 原样执行加固脚本(不改写命令) | ✅ 是 | **同一台真机** localhost | 仅自有主机(R4 双确认)、防御命令(R1)、单目标(R2/R6) |

> **契约**：`SandboxExecutor` 抽象已支持多后端（`get_executor(backend)` 工厂）。**APPLY 作为新后端 `HostExecutor` 接入(`get_executor("host")`),在宿主机直接 `subprocess` 执行,不套容器/不开特权/不动网络模型,不破坏 v0.0.38 既有 Docker 后端。**
>
> **❌ 已否决**：特权容器(NET_ADMIN+bridge)+`systemctl→pkill` 改写——保真度陷阱(容器≠用户环境,pkill≠持久 disable→假验证) + R1 网络姿态退化。详见 ADR-v040 §3。该特权容器脚本**正名为集群 E2E 测试夹具**(QoderWork Gate E 用),不进产品包。
>
> **APPLY 真机执行强制护栏**(R 红线落地):① R4 双确认 `confirm_ownership=confirm_execute=True`;② DRY_RUN-first(APPLY 前必过一次 DRY_RUN);③ rollback 强制先行;④ 生成阶段 R1 关键字扫描,执行不调 exploit/payload;⑤ 单目标、并发≤20、间隔≥5s;⑥ 全程 `audit_id` 审计。**自动 `yes` 应答仅限测试夹具,严禁作产品默认。**

---

## 5. 数据结构契约（新增 / 扩展）

### 5.1 扩展 `HardenStatus`（`harden/base.py`）

```python
class HardenStatus(Enum):
    GENERATED = "generated"   # 已有：生成脚本未执行
    NO_ACTION = "no_action"   # 已有
    FAILED = "failed"         # 已有
    EXECUTED = "executed"     # 🆕 脚本已在沙箱/VM 执行（不代表已验证）
    VERIFIED = "verified"     # 🆕 复扫确认风险项已消除
    REGRESSED = "regressed"   # 🆕 复扫发现仍存在 / 引入新风险
```

### 5.2 新增 `VerificationResult`（建议置于 `harden/verify.py`）

```python
@dataclass
class VerificationResult:
    target: str
    resolved: list[dict]      # 加固前有、加固后消失的风险（修复成功）
    remaining: list[dict]     # 加固前后都在（未修复）
    regressed: list[dict]     # 加固后新增的风险（加固引入回归）
    before_count: int
    after_count: int
    verdict: str              # "verified" | "partial" | "failed"
    audit_id: str = ""
    def to_dict(self) -> dict: ...
```

**verdict 判定规则（契约）**：
- `verified`：`resolved` 非空且 `remaining` 为空且 `regressed` 为空。
- `partial`：`resolved` 非空但 `remaining` 或 `regressed` 非空。
- `failed`：`resolved` 为空（加固未消除任何风险），或 `regressed` 非空且 `resolved` 为空。

### 5.3 新增 `ClosedLoopResult`（建议置于 `harden/closed_loop.py`）

```python
@dataclass
class ClosedLoopResult:
    target: str
    os_platform: OSPlatform
    mode: str                          # "dry_run" | "apply"
    before_scan: dict                  # ScanResult.to_dict()
    harden: dict                       # HardenResult.to_dict()
    execution: dict | None             # ExecutionResult.to_dict()（DRY_RUN 跳过执行则可为 None）
    after_scan: dict | None            # ScanResult.to_dict()（DRY_RUN 无复扫则 None）
    verification: dict | None          # VerificationResult.to_dict()
    overall: str                       # "verified" | "partial" | "failed" | "generated_only"
    audit_id: str
    def to_dict(self) -> dict: ...     # Web/报告直接消费
```

---

## 6. 编排接口契约（`core.py` 新增）

```python
def run_harden_closed_loop(
    self,
    target: str,
    *,
    os_platform: OSPlatform,
    confirm_ownership: bool = False,     # R4：必须显式 True
    mode: str = "dry_run",               # "dry_run"(默认安全) | "apply"
    confirm_execute: bool = False,       # R4 双确认：mode="apply" 时必须 True
    backend: str | None = None,          # None→按 mode 自动选：dry_run="docker"(锁死容器) / apply="host"(真机)
    scan_types: list[str] | None = None,
) -> ClosedLoopResult:
    """扫描→推荐→生成→（执行）→（复扫）→（验证）一体编排。

    - mode="dry_run"：执行①②③ + 锁死容器/`bash -n` 预检（④，backend="docker"），不复扫不改系统。overall="generated_only"。
    - mode="apply"：执行①-⑦完整闭环，④在宿主机本机执行（backend="host"），⑤复扫同一台真机。
      要求 confirm_ownership=confirm_execute=True、target 为本机自有资产、且**已先过一次 DRY_RUN**（DRY_RUN-first 前置，未过则拒绝）。
    异常一律转结构化结果，不向上抛。
    """
```

**调用方**：CLI 新增 `lightshield harden <scan_id> --closed-loop [--apply]`；Web `POST /api/harden/<scan_id>/verify`（Qoder 页面）。

---

## 7. verify 比对逻辑契约（Reasonix 纯函数，可单测）

```python
def verify_hardening(
    before: list[VulnFinding],
    after: list[VulnFinding],
    target: str,
) -> VerificationResult:
    """对比加固前后两次扫描结果，分类 resolved / remaining / regressed。"""
```

**比对键（契约）**：两个 finding 视为"同一风险"当且仅当 `(vuln_type, port)` 相等。
- `resolved` = before 有、after 无的键。
- `remaining` = before、after 都有的键。
- `regressed` = after 有、before 无的键（加固引入的新风险）。

**纯函数要求**：无 I/O、无副作用、不联网；输入两个 list 输出一个 `VerificationResult`。**这是 Reasonix 的理想单测目标**（构造 before/after 列表断言三类分桶）。

---

## 8. Web 对比页面数据契约（Qoder）

页面"一键加固 + 复扫 + 对比"消费 `ClosedLoopResult.to_dict()`，**不直接碰 Python 对象**：
- 顶部：target / mode / overall 徽章（verified=绿 / partial=黄 / failed=红 / generated_only=灰）。
- before/after 对比表：每行一个风险，列 = 类型 / 端口 / 严重度 / 状态（已修复✅ / 仍存在⚠️ / 新增🔴）。
- 折叠区：`execution.stdout/stderr`（执行日志）+ 脚本下载（复用 v0.0.37 `/api/script/...` 白名单下载）。
- i18n：所有文案走 v0.0.39 `t()`（键前缀 `closed_loop.*`，中英对称，Hermes 补 locale）。

---

## 9. 已决问题（QoderWork 真机验证 + CC 安全终审定稿）

5 个原未决问题均已回答,基座决策成文于 ADR-v040。摘要:

1. **【基座】** v0.0.38 锁死容器**不能**承载 `APPLY`(V1-V5 真机证实:systemctl/iptables/apt 三杀 + 无复扫目标)。但**也不用独立 VM/特权容器**——**APPLY = 宿主机本机执行**(LightShield 装在被加固的自有机器上),目标即真机,无需另造基座。
2. **【特权边界】** 真机 APPLY **不需要容器特权**(以调用者权限直接执行,如同管理员手跑加固脚本)。R1 并存:加固脚本仅防御命令 + 生成阶段 R1 关键字扫描 + 不调 exploit/payload;**不引入 bridge 出网,DRY_RUN 维持 `--network none`**。(否决了原"特权容器+bridge"——会使 R1 从物理隔离退化为口头承诺,详见 ADR-v040 §1.2。)
3. **【复扫目标】** **被加固的那台真机本身**——APPLY 后 `run_vuln_scan` 复扫 localhost。复扫的就是真机 → 验证保真度满分,杜绝"容器里假修复"。
4. **【stdin 应答】** `yes\n*16` 自动应答经 `subprocess.run(input=)` 真机放行 R4 门(V6 证实)——但**仅作集群 E2E 测试夹具用**。产品 APPLY 的 R4 是真交互门(`--confirm-ownership --apply` 双显式标志),**严禁自动 `yes`**。
5. **【DRY_RUN 形态】** `bash -n`(语法) + R1 攻击关键字内容扫描 + 锁死容器烟测(脚本不卡死 / 交互门可放行 / 超时被干净 kill)。**DRY_RUN 不预演加固成败**(锁死容器里加固命令必然全失败,这是设计而非缺陷;真机有效性靠 APPLY 后的真机复扫验证)。

> 完整证据见 `docs/e2e-v040-sandbox-verify-report.md`;决策论证(含否决备选 B/C)见 `docs/adr-v040-execution-substrate.md`。**契约已转正式版,实现阶段放行。**
