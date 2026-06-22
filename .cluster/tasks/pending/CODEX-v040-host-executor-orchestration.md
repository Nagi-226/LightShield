# CODEX 任务 — v0.0.40 HostExecutor + 闭环编排（安全关键）

> **Agent**：Codex（GPT-5.5，安全关键 + 精密实现）
> **版本**：v0.0.40 自动加固闭环｜**类型**：🔴 安全关键（在用户真机执行加固脚本）
> **依赖**：⛓️ **被 Reasonix 任务阻塞**——需先合入 `HardenStatus` 扩展 + `VerificationResult` + `ClosedLoopResult` + `verify_hardening`（可先 stub-import 并行开发，合并在 Reasonix 之后）。
> **冻结接口来源**：`docs/design-v040-closed-loop.md`（正式版）§4/§6；**决策与红线见 `docs/adr-v040-execution-substrate.md`（必读，尤其 §2.1 护栏）**

---

## 一、项目上下文（简短）

LightShield 自动加固闭环的「执行(④)+编排」环节。ADR-v040 已拍板：**APPLY = 在用户真实主机本机执行加固脚本**（非容器/VM）；DRY_RUN 维持 v0.0.38 锁死容器预检。你实现真机执行后端 + 整条闭环编排。**这是全项目风险最高的模块——它会真的改用户的 iptables/服务/配置。**

## 二、⚠️ 合规约束（R1-R6，本任务重中之重）

- **R1 禁攻击**：只执行 `Hardener.generate` 产出的防御命令；执行前复用/触发 R1 关键字扫描，命中 exploit/payload/反弹 shell 一律拒绝执行。真机 APPLY **不引入任何网络下载**（不 apt install），DRY_RUN 维持 `--network none`。
- **R4 仅自查自有**：APPLY 必须 `confirm_ownership=True` **且** `confirm_execute=True` 双闸；CLI 须 `--confirm-ownership --apply` 双显式标志。**严禁把自动 `yes` 应答作为产品默认**（那只是集群测试夹具用法）。
- **R2/R6**：单目标、并发≤20、间隔≥5s。
- 全程 `audit_id` 审计每条执行 + 所有权确认。

## 三、接口契约（严格按此）

### 3.1 `HostExecutor`（新建 `lightshield/sandbox/host_executor.py`）

继承 `SandboxExecutor`（`sandbox/base.py:120`，**模板方法模式**）：公共 `execute()` 已做 `confirm_execute` 闸门 + 脚本校验 + 审计，你只实现两个抽象方法：
```python
def is_available(self) -> bool: ...          # 真机执行：在支持的 OS 上返回 True
def _run_script(self, abs_script_path, *, timeout) -> ExecutionResult: ...  # 在【宿主机】subprocess 执行，捕获 stdout/stderr/exit_code/超时
```
在 `get_executor()` 工厂（`sandbox/__init__.py:32`）注册 `backend="host"`。

> 🔴 **必须处理的设计张力（CC 已标记）**：`SandboxExecutor` 基类与 `core.execute_hardening` 的注释当前写死「脚本只在隔离容器运行、**绝不在宿主机直接执行**」。HostExecutor 打破此不变量。要求：
> 1. **更新基类语义注释**为两态：「隔离预检执行(Docker) vs 真机应用执行(Host)」，说明 Host 后端用于 APPLY；
> 2. 真机执行的**额外护栏不放在 executor 层**（executor 只复用 confirm_execute 闸门+校验+审计），而放在编排层（见 3.2）；
> 3. 更新 `core.execute_hardening`（`core.py:520`）docstring，去掉"绝不在宿主机"绝对表述，改为"按 backend 选择隔离/真机"。

### 3.2 编排 `run_harden_closed_loop`（`core.py` 新增，签名见契约 §6）

```python
def run_harden_closed_loop(self, target, *, os_platform, confirm_ownership=False,
    mode="dry_run", confirm_execute=False, backend=None, scan_types=None) -> ClosedLoopResult:
```
- `backend=None` → 按 mode 自动选：`dry_run`→`"docker"`（锁死容器预检，不复扫、不改系统、overall=`generated_only`）；`apply`→`"host"`（真机执行④ + 复扫⑤ + verify⑥）。
- 编排顺序：① `run_vuln_scan`(before) → ② `RuleEngine.recommend_hardening` → ③ `generate_hardening`(得 script_path+rollback_path) → ④ `execute_hardening`(传对应 executor) → ⑤ `run_vuln_scan`(after) → ⑥ `verify_hardening`(before.findings, after.findings, target) → ⑦ 汇总 `ClosedLoopResult`。
- **APPLY 强制前置（缺一即拒，返回结构化失败不抛异常）**：`confirm_ownership and confirm_execute` 为真；**DRY_RUN-first**（APPLY 前必须先成功跑过一次 dry_run 的 `bash -n`+R1 扫描，未过则拒绝执行真机）；rollback 脚本已就绪。
- `overall` 取值：`verified`/`partial`/`failed`/`generated_only`，映射 verification.verdict（dry_run 恒为 `generated_only`）。
- 异常一律转 `ClosedLoopResult`（带错误态），不向上抛。

### 3.3 CLI（契约 §6）

`lightshield harden <scan_id> --closed-loop [--apply]`：默认 `--closed-loop`=dry_run；`--apply` 需配 `--confirm-ownership`，否则报错退出并提示双确认。

### 3.4 DRY_RUN 预检形态（契约 §9.5）

`bash -n`（语法）+ R1 攻击关键字内容扫描 + 锁死容器烟测（不卡死/可放行/超时被干净 kill）。**不预演加固成败**（锁死容器里加固命令必然全失败，属设计非缺陷）。

## 四、代码要求

- 全中文注释；类型标注完整；任何失败转结构化结果。
- `_run_script` 真机执行：subprocess 带 timeout，超时 kill 子进程；捕获完整输出；绝不 `shell=True` 拼接未净化输入。
- 复用既有 `generate_hardening`(`core.py:442`)、`execute_hardening`(`core.py:520`,已支持 `executor=` 入参)、`run_vuln_scan`(`core.py:320`)，勿重写。
- 单测：mock 真机 subprocess（参考 v0.0.38 docker_executor 测试风格）；覆盖 dry_run/apply 两路径、双确认闸门、DRY_RUN-first 拒绝、异常转结果。
- `python -m pre_commit run --files <改动>` 过 ruff+mypy+bandit（bandit 会盯 subprocess，确保无 shell 注入面）。

## 五、验收

1. [ ] HostExecutor 真机执行落地 + get_executor("host") 注册 + 基类/execute_hardening 语义注释更新。
2. [ ] run_harden_closed_loop 编排①-⑦，dry_run/apply 双路径正确，overall 映射正确。
3. [ ] APPLY 三重前置（双确认 + DRY_RUN-first + rollback 就绪）强制生效，缺一被拒。
4. [ ] CLI `--closed-loop`/`--apply`/`--confirm-ownership` 接线 + 缺确认报错。
5. [ ] 单测覆盖两路径 + 闸门 + 异常；pre-commit（ruff+mypy+bandit）零违规。
6. [ ] ⚠️ CC + CodeWhale 双审（安全关键，强制）。
