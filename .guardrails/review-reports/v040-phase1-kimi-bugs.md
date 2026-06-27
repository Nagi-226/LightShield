# 全项目 BUG 排查报告  Phase 1-A

> **审查者**：Kimi (K2.7-code) | **日期**：2026-06-27
> **审查范围**：`lightshield/` 下全部 Python 源文件，聚焦代码逻辑正确性、状态生命周期、异常路径与边界条件
> **方法论**：逐文件执行路径追踪 + 状态变量生命周期分析 + 异常路径覆盖 + 边界条件穷举

## 发现总览

| 等级 | 数量 |
|------|:--:|
|  CRITICAL（一定炸或数据损坏） | 4 |
|  HIGH（条件满足就炸/行为错误） | 6 |
|  MEDIUM（不良实践/隐蔽缺陷） | 8 |

总计 **18** 项发现。以下按文件/行号定位，所有结论均基于源码直接推导，不做架构评判。

---

## 逐项发现

### [CRITICAL] 001 `_task_results` 多线程读写无锁保护

- **位置**：`lightshield/core.py:87, 375, 401, 433`
- **触发条件**：Web API 或多个 CLI/异步任务并发调用 `submit_scan()` / `get_scan_status()` / `_run_scan_async()`
- **影响**：
  - `submit_scan` 写入 `self._task_results[task_id] = task` 与 `_run_scan_async` 读取/修改 `task.status` / `task.result` 之间无互斥。
  - Python dict 在 CPython 3.10+ 的写-写并发场景下仍可能触发 `RuntimeError: dictionary changed size during iteration` 或数据损坏；非 CPython 实现风险更高。
  - 任务状态（`PENDING → RUNNING → COMPLETED`）和 `task.result` 的赋值不是原子可见的，`get_scan_status()` 可能读到中间状态。
- **建议**：在 `LightShieldCore.__init__` 中增加 `self._lock = threading.RLock()`，对所有 `_task_results` 的读写、`task` 字段修改加锁；或在 `_TaskInfo` 字段更新处使用锁。

---

### [CRITICAL] 002 CLI 交互确认函数未处理 `EOFError`

- **位置**：`lightshield/cli.py:567, 584`
- **触发条件**：
  - 在 CI/自动化/管道中执行 `lightshield scan/harden` 但未传入 `--confirm-ownership`。
  - 在 SSH 非交互式会话或 `stdin` 被重定向时调用。
- **影响**：`input()` 遇到 EOF 会抛出 `EOFError`，外层的 `except Exception` 虽然能捕获，但 `_ensure_ownership` / `_ensure_execute` 自身没有兜底，导致堆栈泄露且返回码由外层 `exc` 决定；若未来重构去掉外层 try，将直接崩溃。更严重的是，自动化脚本可能在未确认的情况下无法优雅退出。
- **建议**：
  ```python
  try:
      answer = input(...)
  except EOFError:
      return False
  ```

---

### [CRITICAL] 003 Web 登录接口对非字符串凭证触发 `TypeError`

- **位置**：`lightshield/web/routes.py:73-74, 79`
- **触发条件**：攻击者/异常客户端发送 `{"username": null, "password": null}` 或整数类型的 JSON。
- **影响**：`secrets.compare_digest(username, valid_user)` 要求两个参数同为 `str` 或同为 `bytes`，传入 `None`/`int` 会抛出 `TypeError`，导致 500 错误；同时泄露后端异常类型（信息泄露）。
- **建议**：
  ```python
  username = str(data.get("username") or "")
  password = str(data.get("password") or "")
  ```

---

### [CRITICAL] 004 Web 提交扫描任务未校验 `scan_types` 类型

- **位置**：`lightshield/web/routes.py:132-141` → `lightshield/core.py:227`
- **触发条件**：API 请求体中 `scan_types` 为字符串 `"port_scan"`、整数、或 `null`，而非列表。
- **影响**：`core.run_scan` 中 `requested_count = len(scan_types)` 对非 `Sized` 类型抛出 `TypeError`，导致 500；自动化集成时容易触发。
- **建议**：在 `api_submit_scan` 中强制校验：
  ```python
  scan_types = data.get("scan_types")
  if scan_types is not None and not isinstance(scan_types, list):
      return jsonify({"error": True, "message": "scan_types 必须是字符串列表", "code": 400}), 400
  ```

---

### [HIGH] 005 `generate_hardening` 对 `OSPlatform` 枚举调用 `.lower()` 崩溃

- **位置**：`lightshield/core.py:503`
- **触发条件**：外部调用者直接传入 `os_platform=OSPlatform.LINUX`（函数签名允许 `str | None`，但 `LightShieldCore` 的 public API 暴露给上层时容易被误传枚举）。
- **影响**：`(os_platform or "").lower()` 在枚举对象上执行 `.lower()` 触发 `AttributeError`，加固流程中断。
- **建议**：统一处理枚举和字符串：
  ```python
  platform = str(os_platform or "").lower()
  ```
  或在类型签名中明确只接受字符串并对枚举做兼容。

---

### [HIGH] 006 加固闭环 `apply` 模式可被显式指定为 `docker` 后端

- **位置**：`lightshield/core.py:897-898, 781`
- **触发条件**：调用者显式传入 `mode="apply", backend="docker"`。
- **影响**：文档声称 APPLY 模式“backend 锁死 host/真机执行”，但代码仅在 `backend is None` 时自动选择；显式传入 `docker` 时，`HostExecutor()` 分支不会被命中，脚本在 Docker 容器中“应用”，既未真正修改宿主机，也消耗了 APPLY 的确认语义，闭环验证结果失真。
- **建议**：在 `run_harden_closed_loop` 开头强制覆盖：
  ```python
  if mode == "apply":
      backend = "host"
  elif mode == "dry_run":
      backend = "docker"
  ```

---

### [HIGH] 007 CLI 闭环前后扫描覆盖范围不一致导致验证失真

- **位置**：`lightshield/cli.py:236-238` 与 `cli.py:690`
- **触发条件**：执行 `lightshield harden <target> --closed-loop`。
- **影响**：
  - 基线扫描 `before_scan` 使用 `scan_types=["port_scan", "service_detect"]`。
  - 闭环内部 `_run_closed_loop` 调用 `run_harden_closed_loop(..., scan_types=None)`，其 `_do_scan` 在 `scan_types` 为空时执行 `run_vuln_scan`（包含 web_vuln、weak_password、component_check）。
  - 前后两次扫描能力不同，`after_scan.findings` 可能包含基线未发现的 web/弱口令/component 风险，被 `verify_hardening` 误判为“regressed（加固引入新风险）”。
- **建议**：`_run_closed_loop` 应传入与基线一致的 `scan_types`，或在闭环内部使用 `pre_generated` 中的 `scan_result` 作为 before，并保证 after 使用相同扫描类型集合。

---

### [HIGH] 008 `get_repository` 单例忽略后续 `backend` 参数

- **位置**：`lightshield/repository/base.py:210-225`
- **触发条件**：测试或代码先调用 `get_repository("json")`，之后调用 `get_repository("sqlite", db_url=...)`。
- **影响**：第二次调用返回的是 JsonFileRepository，导致 SQLite 路径不被使用，测试间相互污染；Web 层与 CLI 层若初始化顺序不同，可能拿到错误后端。
- **建议**：在工厂中增加 `force` 参数或按 `backend + 关键参数` 组合缓存；至少提供 `reset_repository()` 测试钩子。

---

### [HIGH] 009 HostExecutor 超时只杀主进程不杀进程树

- **位置**：`lightshield/sandbox/host_executor.py:182-188`
- **触发条件**：加固脚本启动子进程/后台服务（如 `systemctl`、`apt`），或 Windows 下 `.bat` 调用 `powershell.exe`。
- **影响**：`subprocess.run(timeout=...)` 仅向主进程发送 `SIGKILL`（POSIX）或 `TerminateProcess`（Windows），子进程可能成为孤儿进程/僵尸进程，继续占用资源或修改系统。注释中声称“超时强制终止进程树”，实现与注释不符。
- **建议**：
  - POSIX：使用 `subprocess.Popen` + `os.killpg`/`start_new_session=True` 在超时后杀进程组。
  - Windows：使用 `subprocess.Popen` + `taskkill /T /F /PID <pid>` 递归终止。

---

### [HIGH] 010 规则引擎版本回退比较使用字符串字典序

- **位置**：`lightshield/rules/engine.py:475-477`
- **触发条件**：服务版本字符串无法被 `_parse_semver` 解析（如只含非数字前缀），或 fallback 路径被命中。
- **影响**：字符串比较 `"10.0" <= "2.0"` 为 `True`，会把高版本误判为受影响，产生 CVE 误报；反之 `"1.10" <= "1.2"` 为 `False`，漏报。
- **建议**：回退路径改为分字段数值比较，或当解析失败时返回 `False` 并记录警告，不要依赖字符串字典序判断版本大小。

---

### [MEDIUM] 011 CLI 历史保存异常被静默吞掉

- **位置**：`lightshield/cli.py:181-182`
- **触发条件**：数据库文件不可写、磁盘满、JSON 序列化失败等。
- **影响**：`except Exception: pass` 导致历史保存失败完全不可见，用户以为扫描已保存，实际没有；排查困难。
- **建议**：至少打印警告：`print(f"[警告] 扫描历史保存失败：{exc}")`，或只在特定异常（如 `sqlite3.Error`）时静默并在 verbose 模式下输出。

---

### [MEDIUM] 012 CLI `--output-dir` 未做目录穿越校验

- **位置**：`lightshield/cli.py:539`
- **触发条件**：用户传入 `--output-dir ../reports` 或 `--output-dir /tmp/evil`。
- **影响**：报告、加固脚本、回滚脚本写入到指定目录，可能覆盖用户系统上的任意文件（如果该目录存在同名文件）。虽然这是本地 CLI 工具，但缺少护栏容易在脚本拼接时造成意外破坏。
- **建议**：对 `--output-dir` 做路径解析并限制在工作目录下，或要求显式 `--allow-outside-output-dir` 危险标志。

---

### [MEDIUM] 013 报告归档后 CLI 仍打印旧路径

- **位置**：`lightshield/cli.py:148, 188-198, 762-783`
- **触发条件**：扫描/加固成功后触发 `_run_hooks`，其中 `archive_report` 使用 `shutil.move` 将报告从 `./reports/report-xxx.md` 移动到 `./reports/2026-06/27/...`。
- **影响**：CLI 向用户展示的 `report_path` 是归档前的路径，归档后该文件已不存在；用户按提示路径找不到报告。
- **建议**：`archive_report` 返回新路径后，CLI 应使用返回的新路径更新 `report_path` 并打印实际位置。

---

### [MEDIUM] 014 Web 登录失败计数器无锁并发访问

- **位置**：`lightshield/web/auth.py:46, 52-107`
- **触发条件**：Flask 以多线程模式运行（默认 `threaded=True`），多个并发登录请求来自同一 IP。
- **影响**：`_login_failures[ip]["failures"]` 的 += 操作非原子，可能丢失失败次数，导致暴力破解锁止被绕过或延迟计算错误。
- **建议**：使用 `threading.Lock` 保护 `_login_failures` 的读写，或改用 `collections.Counter` + 原子更新模式。

---

### [MEDIUM] 015 加固脚本部分写入失败导致文件残留

- **位置**：`lightshield/harden/linux_harden.py:185-197`；`lightshield/harden/win_harden.py:165-177`
- **触发条件**：磁盘空间不足、权限问题，导致加固脚本写入成功但回滚脚本写入失败。
- **影响**：函数返回 `HardenStatus.FAILED`，但硬盘中已存在一个不完整的 `harden_*.sh`；用户可能误执行该脚本，而对应的回滚脚本不存在，无法恢复。
- **建议**：在写入任一文件失败时，删除已生成的另一个脚本，或在返回 FAILED 前清理。

---

### [MEDIUM] 016 `_safe_dirname` 未过滤 `.` / `..` / NUL

- **位置**：`lightshield/utils/report_archiver.py:126-135`
- **触发条件**：目标为 `.`、`..`、或包含 `\x00` 的异常字符串（虽然 R2 校验会拦截大部分，但 `archive_report` 是独立工具函数，可能被其他模块调用）。
- **影响**：可能创建名为 `.` 或 `..` 的归档子目录，造成路径混乱；NUL 字符会导致 Windows 创建截断文件名。
- **建议**：
  ```python
  safe = safe.strip().replace(".", "_")  # 或拒绝空/保留名
  if not safe or safe in {".", ".."}:
      safe = "unknown"
  safe = safe.replace("\x00", "")
  ```

---

### [MEDIUM] 017 MSF `-x` 脚本中选项值含空格可能被错误解析

- **位置**：`lightshield/adapters/msf_adapter.py:270-276`
- **触发条件**：`options` 中的值包含空格（例如 `RHOSTS` 被提前过滤，但其他自定义 option 值可能带空格）。
- **影响**：`_build_msf_command` 用 `"; ".join` 生成单条命令字符串，再传给 `msfconsole -x`；值中的空格会被 msfconsole 按参数边界拆分，导致 set 失败或执行意外命令。
- **建议**：对 option 值做 shell-safe 引号包裹，或改用 `-x` 多命令分号+引号格式；更彻底的是使用 msfconsole 的 resource 文件而非 `-x` 单字符串。

---

### [MEDIUM] 018 `_cleanup_old` 按目录 mtime 而非创建时间清理

- **位置**：`lightshield/utils/report_archiver.py:159-182`
- **触发条件**：启用 `max_age_days > 0` 并跨多日复用同一日期目录。
- **影响**：只要某天目录内有新文件写入，目录的 `mtime` 就会刷新，导致该日期下所有旧报告都被保留，超过保留期限的报告不会被清理。
- **建议**：按目录名 `YYYY-MM/DD` 解析日期判断，或递归检查目录内最旧/最新文件时间并取最早者。

---

## 模型独立性声明

- **审查模型**：Kimi-K2.7-code (Moonshot)
- **被审查代码作者模型**：DeepSeek-V4-Pro / Claude Code（根据项目上下文）
- **跨模型审查**：Kimi 独立执行路径追踪与边界条件分析，未参考其他 Agent 的审计结论；所有发现均基于源码直接推导。

---

## 附：重点维度扫描结论

| 检查维度 | 结论 |
|----------|------|
| 并发/竞态 | `core._task_results` 与 `web/auth._login_failures` 存在无锁访问；`RateLimiter` 为单进程内存实现，多 worker 不共享。 |
| 资源泄漏 | `HostExecutor` 超时未清理子进程树；`DockerSandboxExecutor` 在 `subprocess.run` 非 `TimeoutExpired` 异常时不会主动 kill 容器；`WeakPasswordAdapter` 在 HTTP 检测 finally 中正确关闭 session。 |
| None/空值安全 | 大部分 `.get()` 有 fallback；`web/routes` 登录与提交扫描任务存在类型假设错误；`core.generate_hardening` 对枚举参数处理不安全。 |
| 异常吞噬 | `cli.py:182` 历史保存失败完全静默；`report_archiver` 多处静默跳过；其他模块基本做到记录或返回结构化失败。 |
| CLI 路径/输入安全 | `--output-dir` 未做穿越校验；`_ensure_ownership` 在 EOF 场景下行为不稳定；参数默认值整体安全。 |

---

*本报告仅做缺陷标注，未修改任何源码。*
