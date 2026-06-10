# LightShield v0.0.16 加固生成器安全审查 — Codex

> 审查人：Codex（GPT-5.5 角色）  
> 审查日期：2026-06-10  
> 审查范围：`lightshield/harden/base.py`、`lightshield/harden/linux_harden.py`、`lightshield/core.py::generate_hardening()`、`lightshield/cli.py::run_harden_command()`  
> 审查定位：安全正确性、R1-R6 合规、接口可扩展性、异常安全、代码质量  
> Graphify：`graphify-out/graph.json` 不存在，按项目规则跳过 graphify query。

---

## 审查摘要

| 严重等级 | 数量 | 结论 |
|:--:|:--:|------|
| Blocker | 2 | 回滚正确性与脚本安全生成存在必须修复项 |
| High | 3 | 防御命令边界、iptables 语义回滚、SSH sed 覆盖率存在高风险 |
| Medium | 3 | 编排一致性、异常安全、文件权限语义需增强 |
| Low | 2 | 代码清理与结果元数据可改进 |

总体结论：**不建议 v0.0.16 无条件合入**。当前实现满足“生成脚本、不自动执行、不设置 +x、脚本内 R4 确认门、apt upgrade 回滚标注”等核心安全方向，但 Linux 回滚脚本无法可靠恢复 SSH 备份，且规则中的 `<service>` 占位符会被当作真实 shell 命令执行，属于加固脚本生成器的正确性与安全边界问题。

已执行验证：

- `rg -n "subprocess|os\.system|chmod|stat\.S_IX|Popen|run\(" lightshield\harden lightshield\core.py lightshield\cli.py`
- `python lightshield\harden\linux_harden.py`：项目根目录通过自检
- `python lightshield\core.py`：项目根目录通过自检
- `python lightshield\cli.py`：项目根目录通过自检

---

## 问题清单分级

### Blocker-B1：未替换的 `<service>` 占位符会被写成可执行 shell 命令

**位置**：`lightshield/harden/base.py:119`、`lightshield/harden/linux_harden.py:268`、`lightshield/harden/linux_harden.py:273`、`lightshield/rules/harden_rules.json:31`

**证据**：

- `HardenBase._substitute()` 只替换 `{port}` 与 `{target}`，docstring 声称 `<service>` 等未实现变量会“保留原样（注释引导操作员填写）”。
- `LinuxHardener._build_harden_script()` 对任何非 `#` 开头行都直接写入脚本执行。
- `harden_rules.json` 当前包含 `systemctl stop <service>` 与 `systemctl disable <service>`。

**影响**：生成的加固脚本运行时，`<service>` 在 shell 中会被解释为重定向语法，而不是占位提示；在 `set -euo pipefail` 下会导致脚本中断，且操作员可能误以为该动作已被正确处理。该问题直接破坏“生成可审阅、可执行的防御性加固脚本”的核心契约。

**建议**：

- 生成器发现 `<...>` 未填占位符时，必须将该行改写为注释或 `echo` 提示，不得作为命令执行。
- 更稳妥方案：为规则 schema 增加 `requires_manual_input: true` / `placeholder_fields`，生成脚本时强制进入人工编辑段。

---

### Blocker-B2：SSH `.bak` 回滚不可用，回滚脚本引用了另一个进程中的变量

**位置**：`lightshield/harden/linux_harden.py:242`、`lightshield/harden/linux_harden.py:244`、`lightshield/harden/linux_harden.py:320`、`lightshield/harden/linux_harden.py:324`

**证据**：

- 加固脚本运行时创建 `_SSHD_BACKUP=/etc/ssh/sshd_config.bak.$(date ...)`。
- 回滚脚本独立运行时检查 `${_SSHD_BACKUP:-}` 并尝试 `cp "$_SSHD_BACKUP" /etc/ssh/sshd_config`。
- `_SSHD_BACKUP` 没有写入回滚脚本、manifest 或固定路径文件；两个脚本不是同一 shell 进程，变量不会自动传递。

**影响**：用户按提示运行 `rollback_*.sh` 时，大概率只能得到“未找到 sshd_config 备份”的警告，无法自动恢复 SSH 配置。该问题直接违反“SSH 加固 sed .bak 备份恢复正确”的审查要求。

**建议**：

- 在生成加固脚本时确定固定备份路径，并把同一绝对路径硬编码进回滚脚本。
- 或生成 `harden_manifest_<ts>.json`，记录 `_SSHD_BACKUP`、`_IPT_BACKUP` 等运行时备份路径，回滚脚本读取 manifest。
- 当前规则中的固定备份 `cp /etc/ssh/sshd_config /etc/ssh/sshd_config.bak` 也应与自动备份统一，避免双备份路径竞争。

---

### High-H1：加固命令缺少防御性 allowlist / schema 校验，R1 依赖规则文件可信

**位置**：`lightshield/harden/linux_harden.py:268`、`lightshield/harden/linux_harden.py:273`、`lightshield/rules/engine.py:276`、`lightshield/rules/engine.py:280`

**证据**：

- `RuleEngine.recommend_hardening()` 将规则 JSON 的 `commands` 原样放入 recommendation。
- `LinuxHardener` 对 recommendation 中的每条 command 只做字符串替换，然后直接写入脚本。
- 当前仓库规则内容基本为防御性操作，但生成器自身没有阻止非防御命令进入脚本。

**影响**：一旦规则文件被误改、污染或未来支持外部规则订阅，生成器可产出任意 shell 命令。虽然不会自动执行，但 LightShield 输出的“官方加固脚本”会带来明显供应链与合规风险。

**建议**：

- 对 Linux 命令建立最小 allowlist：`iptables -A/-C/-D`、`iptables-save`、限定配置文件的 `sed`、限定服务名的 `systemctl` 等。
- 对 `{port}` 运行时校验为 `1..65535` 的整数；对 `<service>` 等占位符禁止执行。
- 对不可逆命令增加 `manual_review_required`，默认以注释形式输出，除非用户显式启用。

---

### High-H2：iptables `-A` / `-D` 仅文本对称，遇到已有相同规则会误删原规则

**位置**：`lightshield/harden/linux_harden.py:42`、`lightshield/harden/linux_harden.py:44`、`lightshield/harden/linux_harden.py:335`、`lightshield/harden/linux_harden.py:337`

**证据**：

- 当前回滚规则将 `iptables -A INPUT -p tcp --dport ... -j DROP` 替换为 `iptables -D INPUT -p tcp --dport ... -j DROP`。
- 这是文本级对称；iptables 对 rule-spec 删除会删除第一条匹配规则。
- 如果加固前已有相同 DROP 规则，加固脚本追加重复规则，回滚时可能删除旧规则而保留新追加规则。

**影响**：回滚不是严格还原系统前态，可能破坏管理员原有防火墙策略。全量恢复提示也引用 `_IPT_BACKUP`，但该变量同样只存在于加固脚本进程中，回滚脚本无法可靠使用。

**建议**：

- 加固脚本改为 `iptables -C ... || iptables -A ...`，并在 manifest 中记录“本次是否新增”。
- 回滚只删除本次新增规则；如未新增则不删除。
- 或优先支持 `iptables-save` 快照 + manifest 路径，回滚使用确定的备份文件 `iptables-restore < fixed_path`。

---

### High-H3：SSH sed 规则只匹配注释行，不覆盖已显式开启的危险配置

**位置**：`lightshield/rules/harden_rules.json:80`、`lightshield/rules/harden_rules.json:82`

**证据**：

- 当前规则为 `sed -i 's/^#PermitRootLogin.*/PermitRootLogin no/' ...`。
- 若配置中已有 `PermitRootLogin yes` 或 `PasswordAuthentication yes`，该 sed 不会命中。

**影响**：脚本显示执行了 SSH 加固，但对最危险的“已显式开启”状态无效，造成加固成功的误导。

**建议**：

- 使用同时覆盖注释与非注释的模式，例如 `s/^#\?PermitRootLogin.*/PermitRootLogin no/`。
- 若目标项不存在，应追加安全配置行，并在回滚 manifest 中记录原始状态。

---

### Medium-M1：CLI 先计算 recommendations，Core 又重新计算一次，报告与脚本可能不一致

**位置**：`lightshield/cli.py:173`、`lightshield/cli.py:177`、`lightshield/cli.py:186`、`lightshield/core.py:357`、`lightshield/core.py:359`

**证据**：

- CLI 为展示与报告生成先调用 `recommend_hardening(all_findings)`。
- `core.generate_hardening()` 内部再次创建 `RuleEngine()` 并重新计算 recommendations。
- CLI 打印的是第一次 recommendations，实际脚本来自第二次 recommendations。

**影响**：当前规则本地且确定性较强，通常不会暴露；但未来规则热加载、远程规则或测试注入时，CLI 输出、报告和脚本可能不一致。

**建议**：让 `generate_hardening()` 接收可选 `recommendations` 参数；CLI 已计算时直接传入，Core 只负责校验和分派 hardener。

---

### Medium-M2：日志目录不可写时，自检/生成路径会在返回 HardenResult 前失败

**位置**：`lightshield/harden/linux_harden.py:116`、`lightshield/utils/logger.py:96`、`lightshield/utils/logger.py:263`

**证据**：

- `LinuxHardener.__init__()` 立即调用 `get_logger()`。
- `get_logger()` 初始化时直接 `os.makedirs("./logs", exist_ok=True)`。
- 审查时在非项目根的不可写工作目录运行 `python ...\linux_harden.py`，触发 `PermissionError: './logs'`，未能进入 `generate()` 的优雅失败路径。

**影响**：文件写入失败、目录创建失败在 `generate()` 中处理得较好，但 logger 初始化失败会绕过 `HardenResult(status=FAILED)`，影响异常安全与自检可移植性。

**建议**：

- logger 初始化失败时降级到 console-only logger，或允许通过 config/env 指定日志目录。
- `LinuxHardener` 延迟初始化 logger，或捕获 logger 构造异常并返回结构化错误。

---

### Medium-M3：生成文件未设置执行位是正确的，但也未显式设置只读权限

**位置**：`lightshield/harden/linux_harden.py:171`、`lightshield/harden/linux_harden.py:174`

**证据**：

- 文件通过 `open(..., "w")` 写入；未调用 `chmod +x`，符合“不自动执行、不设置 +x”。
- 但也没有显式设置只读权限，文件权限依赖当前 umask / Windows ACL。

**影响**：如果“只读方式生成”严格解释为生成后只读，则当前实现不满足；如果解释为“不自动执行、不赋予执行权限”，当前实现满足。

**建议**：在设计文档中澄清语义。若确需只读，可写入后设置 `0o444` 或 `0o644`，但需权衡用户编辑审阅脚本的便利性。

---

### Low-L1：`Path` 未使用，注释提到的 `_collect_backup_files` 不存在

**位置**：`lightshield/harden/linux_harden.py:24`、`lightshield/harden/linux_harden.py:50`

**影响**：不影响运行，但降低代码可信度。建议清理未使用 import，并修正文档注释。

---

### Low-L2：`HardenResult` 缺少生成时间、脚本哈希和规则版本元数据

**位置**：`lightshield/harden/base.py:35`、`lightshield/harden/base.py:60`

**影响**：当前字段可满足 MVP，但安全审计和工单追踪时无法证明脚本内容未被修改，也无法关联规则版本。

**建议**：增加 `generated_at`、`script_sha256`、`rollback_sha256`、`rule_version` 或 `recommendation_count_by_severity` 等可选字段。

---

## 安全审查逐项结论

### 1. 全链无 subprocess / os.system 执行加固命令

**状态：通过。** 目标范围内未发现 `subprocess` / `os.system` 用于执行加固命令；`cli harden` 会调用扫描适配器执行扫描，这是 harden 子命令的“扫描 → 推荐 → 生成脚本”流程，不是执行加固命令。生成器未调用 `chmod +x`。

### 2. iptables `-A` 与 `-D` 回滚对称性

**状态：部分通过。** 当前文本映射能把现有规则 `iptables -A INPUT -p tcp --dport {port} -j DROP` 转为 `iptables -D INPUT -p tcp --dport {port} -j DROP`。但语义上无法区分本次新增规则与加固前已有相同规则，且 `_IPT_BACKUP` 未持久化，严格回滚不可靠。

### 3. SSH sed `.bak` 备份恢复

**状态：失败。** 加固脚本生成运行时变量 `_SSHD_BACKUP`，回滚脚本独立执行时无法获得该变量；同时 sed 只覆盖注释行，不能修复已显式开启的危险项。

### 4. 不可逆操作标注

**状态：通过。** `_IRREVERSIBLE_PATTERNS` 覆盖 `apt update`、`apt upgrade`、`yum update`、`yum upgrade`、`apt install`，回滚脚本会输出“无法自动回滚”。

### 5. 脚本只生成、不自动执行、不设置 +x

**状态：通过。** `LinuxHardener.generate()` 仅写入 `.sh` 文件，未执行脚本，未设置执行位。CLI 也提示用户审阅后手动执行。

### 6. 每条操作审计

**状态：基本通过。** `LinuxHardener.generate()` 在脚本写入成功后对每条 recommendation 调用 `_audit_action(..., "script_generated")`，最终落到 `logger.audit_harden_action()`。注意当前审计粒度是“每条加固建议”，不是“每条 shell command”。

---

## R1-R6 红线核查

| 红线 | 状态 | 证据 |
|------|:--:|------|
| R1 禁攻击 | ⚠️ 部分通过 | 当前 `harden_rules.json` 主要为防御性操作；但 `linux_harden.py:268-275` 对 recommendation 命令无 allowlist/schema 校验，R1 依赖规则文件可信。 |
| R2 禁批量扫描 | ✅ 通过 | `cli.py:141-145` 先调用 `TargetValidator.validate()`；`core.py:342-345` 在生成加固前复用 R2 校验。 |
| R3 禁远控/后门 | ✅ 通过 | 审查范围内未发现 reverse shell、bind shell、后门、远控持久化等逻辑；生成脚本也未包含此类模板。 |
| R4 仅自查 | ✅ 通过 | CLI 层 `_ensure_ownership()` 要求 `YES` 或 `--confirm-ownership`；生成脚本头部 `linux_harden.py:227-235` 再次阻断确认。 |
| R5 MSF白名单 | N/A | 本次 harden 生成器不调用 MSF；未扩大 MSF 能力边界。 |
| R6 频率限制 | ✅ 通过 | `run_harden_command()` 通过 `core.run_scan(... confirm_ownership=True, timeout=...)` 复用扫描编排；R6 属于扫描阶段，生成脚本阶段无批量/并发执行。 |

---

## 接口评价

### HardenBase 与 BaseAdapter 分离

评价：**合理。** `BaseAdapter` 表达“检测/扫描能力”，`HardenBase` 表达“脚本生成能力”，安全边界清晰，避免把“扫描执行”和“系统变更脚本生成”混在同一抽象中。该设计也有利于 R1-R6 分层审计。

建议：不要在 `HardenBase` 预留会执行系统变更的 `execute()` 默认路径；如果未来必须支持执行，应另建 `Executor` 层，并强制二次确认、dry-run、最小权限和审计锁。

### HardenResult 字段完备性

评价：**MVP 基本完备。** `status`、`target`、`os_platform`、`recommendations`、`script_path`、`rollback_path`、`action_count`、`audit_id`、`error` 能支持 CLI 和报告输出。

建议增强：增加生成时间、脚本哈希、规则版本、文件权限、是否含手工步骤、不可逆操作列表，以满足开源安全工具的可追溯性。

### WinHardener 对称复用

评价：**可复用。** `WinHardener.generate()` 与 `LinuxHardener.generate()` 使用相同签名并返回同一 `HardenResult`，`core.generate_hardening()` 已可按 `os_platform == "windows"` 分派。

风险：`core.generate_hardening()` 默认 Linux，CLI harden 当前没有暴露 `--os-platform` 参数；用户在 Windows 目标上可能得到 Linux 脚本。建议 CLI 增加 `--os-platform {linux,windows}` 或从扫描结果 OS 探测自动推断并允许用户确认。

---

## 异常安全评价

| 场景 | 状态 | 证据 / 说明 |
|------|:--:|-------------|
| 空推荐 | ✅ 通过 | `linux_harden.py:138-145` 返回 `HardenStatus.NO_ACTION`，CLI 在 `cli.py:179-182` 直接成功退出。 |
| 输出目录创建失败 | ✅ 通过 | `linux_harden.py:150-159` 捕获 `OSError` 并返回 `HardenStatus.FAILED`。 |
| 脚本写入失败 | ✅ 通过 | `linux_harden.py:171-183` 捕获 `OSError` 并返回 `HardenStatus.FAILED`。 |
| logger 初始化失败 | ⚠️ 需增强 | `linux_harden.py:116` 构造期调用 `get_logger()`，可能在进入 `generate()` 前抛异常。 |
| CLI 总体失败 | ✅ 通过 | `cli.py:218-225` 捕获 `KeyboardInterrupt` 与普通异常，非 verbose 模式友好返回。 |

---

## 代码质量评价

优点：

- 中文注释和 docstring 覆盖较完整，安全设计意图清楚。
- type hints 覆盖核心入口和数据结构。
- `__main__` 自检在项目根目录可运行，且覆盖脚本生成、回滚生成、空推荐和变量替换。
- CLI R4 交互与脚本 R4 交互形成双确认门。

不足：

- 回滚逻辑依赖运行时 shell 变量，未形成跨脚本持久状态。
- recommendation 使用 `dict` 裸结构，缺少 schema/dataclass 校验。
- `generate_hardening()` 的 `findings is None` 分支存在无效变量 `last_adapter`，意图未完成。
- Linux 与 Windows hardener 的共同行为可抽到基类或 helper，减少未来不一致。

---

## 合入建议

必须修复后再合入：

1. 禁止未填 `<...>` 占位符作为命令执行。
2. 修复 SSH 与 iptables 备份路径持久化，确保回滚脚本独立运行时可恢复。
3. 为加固命令增加防御性 allowlist/schema，至少阻断明显非防御命令和非数字端口。

建议 v0.0.17 前修复：

1. CLI 增加 `--os-platform`，并避免 CLI/Core 重复计算 recommendations。
2. 改进 SSH sed 规则，覆盖注释与非注释两种状态。
3. logger 初始化失败时优雅降级，保证自检在非项目根目录也可运行。
