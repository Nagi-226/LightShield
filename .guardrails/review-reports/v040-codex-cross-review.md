# 审查报告  v0.0.40 CC 自写代码交叉审查
> **审查者**：Codex (GPT-5.5) | **日期**：2026-06-27 | **范围**：4 commits (2420020..adb2c11)

## 发现总览
| 等级 | 数量 |
|------|:--:|
| 🔴 CRITICAL | 0 |
| 🟠 HIGH | 2 |
| 🟡 MEDIUM | 1 |
| 🔵 LOW | 2 |
| 💡 SUGGESTION | 1 |

## 逐项发现

### 🟠 HIGH H-001  APPLY 未强制 DRY_RUN-first 前置
- **位置**：`lightshield/core.py:952`
- **描述**：`run_harden_closed_loop(mode="apply")` 在 R4 双确认后直接委托 `_run_apply_and_verify()`，该 helper 只检查 rollback 是否存在和 R1 内容扫描，未先执行 `_run_dry_run_precheck()`，也未要求 Docker/DRY_RUN 预检成功证据。实际实现与提交契约“三重前置护栏：R4 双确认 + DRY_RUN-first + rollback 就绪”不吻合；APPLY 可在未完成隔离预检的情况下进入 HostExecutor 真机执行。
- **建议**：在 APPLY 分支中先执行 `_run_dry_run_precheck(script_path, audit_id)`，仅当预检明确成功（或按安全策略明确允许的受控状态）时才继续；预检 rejected/error/skipped 应返回结构化失败。补充测试：APPLY 时 Docker 预检未调用/失败必须拒绝，成功才允许 HostExecutor。

### 🟠 HIGH H-002  CLI APPLY 确认的脚本与实际执行脚本可能不是同一份
- **位置**：`lightshield/cli.py:675`
- **描述**：`run_harden_command()` 已经完成扫描、规则匹配、生成并打印加固/回滚脚本路径，随后 `_run_closed_loop()` 又调用 `core.run_harden_closed_loop()` 重新执行“扫描→推荐→生成→执行”。用户在 CLI 中确认“已审阅加固脚本”时看到的是第一次生成的脚本，但 APPLY 实际执行的是闭环内部第二次生成的脚本，存在审阅对象与执行对象不一致的问题，同时造成重复扫描/重复规则计算/重复脚本生成。
- **建议**：二选一收敛流程：要么 `--closed-loop` 直接进入核心闭环且在执行前展示闭环内生成的脚本并等待确认；要么让 `run_harden_closed_loop()` 接收已生成的 `scan_result/recommendations/harden_result`，确保被确认与被执行的是同一份脚本。补充测试断言 APPLY 不会生成第二份未审阅脚本。

### 🟡 MEDIUM M-001  Web APPLY 闸门 DOM id 不匹配，前端模式切换会抛错
- **位置**：`lightshield/web/templates/harden_verify.html:123`
- **描述**：模板中的闸门容器 id 是 `apply-gate`，但脚本查找 `cl-apply-gate`。点击 APPLY tab 后执行 `applyGate.hidden = ...` 会因 `applyGate === null` 抛出 TypeError，导致 APPLY 双确认区域无法正常显示，前端闸门失效/页面交互中断。后端 R4 校验仍在，但前端防线和用户流程不可用。
- **建议**：统一 DOM id（例如改为 `document.getElementById("apply-gate")`），并增加前端行为测试或至少在页面渲染测试中断言脚本引用的 id 与 DOM 实体一致。

### 🔵 LOW L-001  Bark 配置契约不完整：`config.bark_key` 未被 CLI 解析使用
- **位置**：`lightshield/cli.py:742`
- **描述**：配置类已新增 `bark_key` 且支持 `LS_BARK_KEY`，提交说明也写明“CLI / 环境变量 / config.bark_key”，但 `_resolve_bark_key()` 只读取 CLI 参数和环境变量，没有读取 `get_config().bark_key`。这会使配置文件中的 Bark Key 不生效。
- **建议**：在 CLI 参数和环境变量为空时读取 `get_config().bark_key`；测试覆盖三层优先级（CLI > env > config）。默认空字符串仍保持 disabled。

### 🔵 LOW L-002  对比表使用 `innerHTML` 渲染 API 数据，存在未来 XSS 回归面
- **位置**：`lightshield/web/templates/harden_verify.html:238`
- **描述**：当前字段主要来自内部扫描类型/枚举，风险较低；但“后端 API 数据”不应天然视为可信，未来若 finding 字段接入外部扫描器、历史仓库或插件输入，`vuln_type/severity/port` 进入 `innerHTML` 会形成 XSS sink。
- **建议**：改为 `document.createElement()` + `textContent` 构造单元格，或集中做 HTML escaping；补充一个包含 `<img onerror=...>` 的回归测试，确保页面只显示文本。

### 💡 SUGGESTION S-001  双模式语义已更新但仍有局部旧注释
- **位置**：`lightshield/utils/constants.py:147`
- **描述**：`sandbox/base.py` 顶部已更新为 DRY_RUN Docker 与 APPLY Host 双模式，HostExecutor 也把额外护栏放在编排层，整体方向正确；但 `constants.py` 仍写着“沙箱...绝不在宿主机直接运行”，`sandbox/base.py` 抽象方法注释仍有“隔离环境中运行”表述，容易误导后续审查。
- **建议**：修复实现问题后，同步注释为“Docker 后端隔离预检；Host 后端真机执行”，避免再次造成执行基座语义漂移。

## 合规检查
| R1 | R2 | R3 | R4 | R5 | R6 |
|:--:|:--:|:--:|:--:|:--:|:--:|
| ✅ | ✅ | ✅ | ⚠️ | ✅ | ✅ |

- **R1**：已执行 `rg -n -i "exploit|payload|attack|ddos|dos_attack|brute_force"`。审查范围内命中仅为 `core.py` 的 R1 黑名单常量/扫描逻辑；全仓命中还包含测试、MSF/Nuclei 黑名单、Web 漏扫检测 payload 与 vendored Swagger 变量名，未发现 v0.0.40 新增主动攻击逻辑。
- **R2**：CLI `scan/harden` 入口先调用 `TargetValidator.validate()`；core `_validate_request()` 与 `generate_hardening()` 复用同一校验，拒绝 CIDR、IP range、通配符、URL/path/port。Web verify 从历史 scan target 进入 core 后仍会被 core 校验。
- **R3**：已执行 `rg -n -i "bind_shell|reverse_shell|backdoor|trojan|remote_admin"`。审查范围内命中仅为 R1/R3 黑名单常量；全仓命中为 MSF 黑名单/测试/护栏文档，未发现远控/后门实现。
- **R4**：APPLY 双确认在 CLI、Web 路由和 core 层均存在；rollback 就绪检查存在；但 DRY_RUN-first 未在 APPLY 路径强制执行，因此标记 ⚠️。
- **R5**：本次 4 个代码提交无 MSF 调用链变更；既有 MSF 白名单/黑名单未被放宽。
- **R6**：常量为 `MAX_CONCURRENT_SCANS=20`、`MIN_SCAN_INTERVAL=5.0`，core 执行扫描时按 `max_concurrent_scans` 拒绝超量并在 adapter 间 sleep `scan_interval`；本次变更未放宽默认值。

## M8 五维扫描
| 维度 | 结果 | 说明 |
|------|:--:|------|
| 架构 | ⚠️ | HostExecutor 继承模板方法且编排在 core 层；但 APPLY 的 DRY_RUN-first 契约未落地，CLI 闭环有重复编排/脚本不一致问题。 |
| 安全 | ⚠️ | R1/R2/R3/R5/R6 基本通过；R4 的双确认通过，DRY_RUN-first 缺失需修复；Web verify 有 CSRF。 |
| 性能 | ⚠️ | CLI `--closed-loop` 当前重复扫描、重复推荐、重复生成；Bark HTTP 请求有 5s timeout。 |
| 代码质量 | ⚠️ | 异常多为结构化返回，类型标注较完整；Web JS id mismatch 属运行时缺陷，局部注释与双模式语义不一致。 |
| 测试 | ⚠️ | 新增 5 个测试文件覆盖多条路径；但缺少 APPLY 必须调用/通过 DRY_RUN-first 的负向测试，页面测试未捕获 DOM id mismatch。 |

## 重点关注项验证
1. **HostExecutor 设计张力**：基类总体已从单一“隔离沙箱”扩展为 DRY_RUN Docker / APPLY Host 双模式；HostExecutor 只实现 `is_available()` 与 `_run_script()`，未在 executor 内重复做 R4/DRY_RUN/rollback，符合“护栏在编排层”的方向。但编排层未真正执行 DRY_RUN-first，是阻塞项。
2. **APPLY 三重前置**：双确认强制 ✅；rollback 就绪检查 ✅；R1 最终扫描 ✅；DRY_RUN-first ❌。缺一即拒的结构化失败只覆盖双确认、rollback、R1，不覆盖 DRY_RUN-first。
3. **Bark 通知安全**：固定 HTTPS Bark endpoint，默认无 key 即 disabled，失败静默且请求 timeout=5s；通知内容只包含目标、计数、耗时/模式，不含脚本内容或 stdout/stderr。问题是 `config.bark_key` fallback 未实现，且 `NotifyResult` 会携带 key，当前未见日志输出但应避免未来打印。
4. **Web CSRF 风险**：`POST /api/harden/<scan_id>/verify` 有 `@login_required` + `@csrf_protect`，应用全局 before_request 也会保护已登录 unsafe methods；前端 fetch 带 `X-CSRF-Token`。CSRF 检查通过。

## 八荣八耻审查
| 1认真查询 | 2寻求确认 | 3人类确认 | 4复用现有 | 5主动测试 | 6遵循规范 | 7诚实无知 | 8谨慎重构 |
|:--:|:--:|:--:|:--:|:--:|:--:|:--:|:--:|
| ✅ | ⚠️ | ⚠️ | ✅ | ⚠️ | ⚠️ | ✅ | ⚠️ |

- **主要扣分点**：APPLY 确认与实际执行脚本可能不一致，影响“人类确认”；DRY_RUN-first 契约未实现，影响“遵循规范”；测试未覆盖该阻塞契约和前端运行时 id mismatch。

## 验证记录
- 已阅读全文：`core.py`、`cli.py`、`sandbox/base.py`、`sandbox/host_executor.py`、`sandbox/__init__.py`、`harden/closed_loop.py`、`harden/verify.py`、`utils/notifier.py`、`utils/report_archiver.py`、`config.py`、`web/routes.py`、`web/pages.py`、`web/templates/harden_verify.html`、`web/static/style.css`，并审阅新增测试文件。
- 已执行 Graphify 查询：`graphify query "v0.0.40 HostExecutor closed loop harden verify web routes csrf bark notifier"`。
- 已执行 targeted regression：`python -m pytest tests/test_host_executor.py tests/test_closed_loop.py tests/test_verify_hardening.py tests/test_loop_hooks.py tests/test_web_closed_loop.py` → 84 passed；pytest cache 写入出现 WinError 5 警告，不影响测试结论。

## 结论
- [ ] 通过，可合入 + tag v0.0.40 + push
- [x] 有条件通过（5 项需修复后合入；其中 H-001/H-002 为合入前阻塞）
- [ ] 驳回
