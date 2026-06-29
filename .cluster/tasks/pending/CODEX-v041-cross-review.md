# CODEX 任务 — v0.0.41 CC 自写代码交叉审查（🔴 强制门禁）

> **Agent**：Codex（GPT-5.5，安全关键 + 精密审查）
> **版本**：v0.0.41 债务清偿｜**类型**：🔴 强制交叉审查（CC 自写代码，不可跳过）
> **触发规则**：`.cluster/CLUSTER.md` 规则 #4 — CC 自写代码由 Codex (GPT-5.5) 交叉审查
> **审查清单**：`.guardrails/REVIEW_CHECKLIST.md`（M8 五维扫描 + R1-R6 合规 + 八荣八耻）

---

## 一、审查范围

**单 commit**：`e4210ca`（`fc8557a` v0.0.40 基线 → `e4210ca` v0.0.41）

| 文件 | +/- | 涉及修复 |
|------|-----|---------|
| `lightshield/core.py` | +45/- | H-007: scan_types 一致化（pre_generated 携带 scan_types，effective_scan_types 决策） |
| `lightshield/cli.py` | +33/- | H-007: harden_scan_types 变量提取 + 参数传递；C-002: EOFError 处理 |
| `lightshield/sandbox/host_executor.py` | +140/- | H-009: Popen+killpg/taskkill 进程树清理；mypy/SIM105 修复 |
| `tests/test_host_executor.py` | +50/- | Mock 从 subprocess.run 迁移到 subprocess.Popen |
| `lightshield/web/routes.py` | +4/- | C-003: login 端点 isinstance(str) 类型校验 |
| `.cluster/CLUSTER.md` | +166/- | 🔭 观察名单 + WorkBuddy 文档（纯文档） |
| `CLAUDE.md` | +16/- | 上次会话更新（纯文档） |
| `CODEBUDDY.md` | +277/- | CodeBuddy A/B 双模式文档（纯文档） |

> ⚠️ `.cluster/CLUSTER.md`、`CLAUDE.md`、`CODEBUDDY.md` 是纯文档更新。按 `.guardrails/REVIEW_CHECKLIST.md §六` 不强制逐行审查，但若有架构/安全相关声明可在审查中引用。

---

## 二、修复背景（CC 提供，供 Codex 理解上下文）

### H-007：scan_types 一致化
- **问题**：闭环 `run_harden_closed_loop` 中 before-scan 和 after-scan 可能使用不同 scan_types（如 CLI 预扫描用 `["port_scan", "service_detect"]`，闭环 after-scan 用全量扫描），导致复扫前后结果不可比。
- **修复**：预生成数据 `pre_generated` 携带 `scan_types` 字段；`_resolve_pre_generated()` 返回 `pg_scan_types`；闭环中 `effective_scan_types = pg_scan_types if pg_scan_types is not None else scan_types`。
- **注意**：CLI 发现 `harden_scan_types` 跨函数作用域 bug（定义在 `run_harden_command`、使用在 `_run_closed_loop`），本次一并修复——作为参数传入。

### H-009：进程树清理
- **问题**：`subprocess.run(timeout=...)` 超时仅杀主进程，子进程（fork 出的 shell 子进程）继续运行成为孤儿进程。
- **修复**：改用 `subprocess.Popen` + `communicate(timeout=...)`；超时后跨平台清理——Linux 用 `start_new_session + killpg(SIGKILL)` 杀进程组；Windows 用 `taskkill /F /T /PID` 杀进程树。
- **回归 bug**（CC 在测试中发现并修复）：`communicate()` 成功后误用 `proc.stdout`（TextIOWrapper 文件对象）覆盖了字符串变量，导致 `len(stdout)` TypeError。已修复为直接使用 communicate() 返回的字符串。

### C-002：EOFError
- **问题**：CLI `input()` 在 CI/管道等非交互环境抛 EOFError，未捕获，堆栈退出。
- **修复**：`_ensure_ownership()` 和 `_ensure_execute()` 各加 `except EOFError`，打印错误信息并返回 False。

### C-003：登录类型校验
- **问题**：`POST /api/login` 接受 `{"username": null}` 或 `{"username": 42}` 等非字符串 JSON，传入 `login()` 导致 TypeError。
- **修复**：路由层增加 `isinstance(username, str) and isinstance(password, str)` 校验，不合法返回 400。

---

## 三、审查指令

### 3.1 审查清单（逐项打勾）

按 `.guardrails/REVIEW_CHECKLIST.md` 执行五维扫描：

#### 维度 1：架构（Architecture）
- [ ] `_resolve_pre_generated()` 返回 7-tuple（新增 `pg_scan_types`）是否破坏了所有调用方？
- [ ] `effective_scan_types` 三层回退逻辑（pg_scan_types → scan_types 参数 → run_vuln_scan 默认）是否正确且无歧义？
- [ ] `_run_closed_loop` 新增 `harden_scan_types` 参数：其他调用方（如有）是否已更新？

#### 维度 2：安全（Security）—— 本任务重中之重
- [ ] **R1 禁攻击**：host_executor.py 中新增 subprocess 调用（Popen/taskkill）是否可被注入？
- [ ] **R3 禁远控**：`_kill_process_tree` 中的 `taskkill` 和 `killpg` 调用是否仅作用于脚本子进程，不会越权杀系统进程？
- [ ] **R4 所有权确认**：C-002 EOFError 修复后，非交互环境是否仍有路径不经确认执行？（验证：EOFError 返回 False → 调用方检查 → 拒绝执行）
- [ ] **HostExecutor 安全审计**：`Popen(start_new_session=True)` 创建新进程组——权限边界是否正确？新进程组是否继承了不该有的权限？
- [ ] **Web 安全**：C-003 isinstance 校验是否在所有用户输入路径上都生效（username AND password 都必须 str，非空检查在类型检查之后）？

#### 维度 3：性能（Performance）
- [ ] `_kill_process_tree` 中 `taskkill` timeout=10s 是否合理？会否阻塞主流程过长？
- [ ] `proc.communicate(timeout=1)` 收集部分输出——1s 是否足够获取有意义的输出？

#### 维度 4：质量（Quality）
- [ ] `host_executor.py` 超时分支中 `partial_out` 的 `[:self._MAX_OUTPUT_BYTES]` 切片是否在 timeout 和非 timeout 两条路径上都生效？
- [ ] C-002 EOFError：`_ensure_ownership` 和 `_ensure_execute` 两个函数是否都有对称的 try/except 处理？
- [ ] C-003 类型校验：错误消息是否与现有 i18n 体系一致？
- [ ] `host_executor.py` 中 `stdout = stdout or ""` 是否为 communicate() 返回 None 的情况提供了正确兜底？
- [ ] mypy `# type: ignore[attr-defined]` 注释是否准确标注了平台特定符号（不掩盖真实类型错误）？

#### 维度 5：测试（Testing）
- [ ] Mock 测试从 `subprocess.run` 迁移到 `Popen` 后是否正确模拟了 `communicate()` 的返回值类型？
- [ ] `test_run_script_mocked_timeout` 的 `communicate.side_effect`（先抛 TimeoutExpired 再返回部分输出）是否正确反映了真实超时流程？
- [ ] C-002 和 C-003 是否有对应测试？（若无，标注为测试覆盖缺口）

### 3.2 合规扫描

- [ ] R1: 无 `exploit|payload|attack|ddos` 新增引用
- [ ] R2: 无 CIDR/网段扫描入口变更
- [ ] R3: 无 `bind_shell|reverse_shell|backdoor|trojan|remote_admin`
- [ ] R4: `_ensure_ownership` / `_ensure_execute` 调用链完整
- [ ] R5: 无 MSF 相关变更（本次不涉及）
- [ ] R6: 无扫描频率配置变更

---

## 四、输出要求

1. **分级报告**：按 CRITICAL / HIGH / MEDIUM / LOW / INFO 五级输出所有发现
2. **判定标准**：每个发现标注"真 bug" / "刻意设计" / "无害异味"
3. **最终结论**：是否阻止 tag？是否有必须 v0.0.42 修复的项？
4. **置信度声明**：低置信度判断标注替代解释

---

## 五、不确定性声明（CC 提供）

| 判断 | 置信度 | 说明 |
|------|:--:|------|
| H-009 Popen 迁移无注入面 | 🟢 高 | cmd 全部由 `_build_command` 内部构造，不接受外部输入 |
| C-002 EOFError 覆盖所有交互路径 | 🟢 高 | CLI 仅两处 `input()`，均在本次修复范围内 |
| effective_scan_types 回退逻辑正确 | 🟡 中 | 三层回退（pg_scan_types → scan_types 参数 → run_vuln_scan）需验证所有组合 |
| `assert proc.pid is not None` 安全 | 🟢 高 | typeshed 中 Popen.pid 为 int，运行时仅为极端情况兜底 |
