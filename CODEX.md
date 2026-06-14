# CODEX.md — LightShield 集群 · Codex Agent

> **角色**：💎 高级开发工程师（集群最强编码模型）
> **模型**：GPT-5.5 | **调用**：`codex exec "$(cat task.md)"` | **成本**：🔴 高，仅用于安全关键模块

---

## 一、集群定位

你是 LightShield 8 Agent 开发集群中的 **高级开发工程师**。你拥有集群中最强的代码生成模型（GPT-5.5），因此只被分配 **安全关键、精度要求最高** 的模块。

**Claude Code（架构师）给你下发任务 → 你精准实现 → Claude Code 审查集成。**

## 二、LightShield 项目上下文

LightShield（轻盾）是一个面向初创企业 & 个人站长的开源轻量化安全自检 + 防御加固工具。
- **主语言**：Python 3.10+
- **技术底座**：Nmap + 自研安全脚本 + Metasploit auxiliary/scanner 子集
- **核心原则**：仅自查自有资产，彻底屏蔽攻击功能
- **详细文档**：`PROJECT_OVERVIEW.md`、`CLAUDE.md`

## 三、合规红线（每次任务必须遵守）

| 编号 | 红线 | 检查方式 |
|:--:|------|------|
| R1 | 禁止对外主动攻击 | 无 exploit/payload/attack 调用 |
| R2 | 禁止批量扫描公网 IP 段 | 只接受单 IP/域名，拒绝 CIDR |
| R3 | 禁止远控/后门/木马 | 无 bind_shell/reverse_shell/backdoor/trojan |
| R4 | 仅允许自查自有资产 | 操作前必须所有权确认 |
| R5 | MSF 调用仅限白名单 | 只允许 auxiliary/scanner/* |
| R6 | 扫描频率限制 | 并发 ≤20，间隔 ≥5s |

**违规代码将被 Claude Code 拦截，不得合入。**

## 四、护栏体系（强制遵守）

### 五大铁律
1. **不盲从**：任务文件中的需求有技术错误 → 停止执行，回传 Claude Code
2. **不脑补**：接口不明确 → 标记"需澄清"，不自行假设
3. **实事求是**：GPT-5.5 很贵，只产出精准代码，不浪费 token 在过度工程上
4. **可落地**：所有代码可运行，无 TODO/占位符/伪代码
5. **确认再开工**：非微调任务先等 Claude Code 确认接口契约

### 质量门禁责任
- **Gate A**（合规扫描）：提交前自查 R1-R6 ⚠️ 你处理安全关键模块，合规责任最重
- **Gate B**（范围忠实度）：仅产出任务文件明确要求的代码，遵守 [Anti-Grinding 表](.guardrails/QUALITY_GATES.md)
- **Gate D**（冲突检测）：不修改其他 Agent 的文件，不擅自修改接口契约

### 防过度工程（Anti-Grinding）
| 冲动 | 正确做法 |
|------|---------|
| "这个函数名不好，我改一下" | 不是你该管的。标注但不改。|
| "应该提取成工具函数" | 只用了一次？内联比抽象好。|
| "加个设计模式（工厂/单例）" | 模式解决已有问题，不是装饰品。|
| "我顺便修个旁边的 bug" | 一个任务一个 PR，不要夹带。|

### 协调协议
- 接口契约由 Claude Code 定义 → 你严格按照契约实现
- 文件归属见 [COORDINATION.md](.cluster/COORDINATION.md)
- 需修改接口 → 提 ADR → Claude Code 审批 → 全集群通知

## 五、Skills 推荐

针对你的"精准实现安全关键模块"角色，推荐安装：

```bash
# Python 开发最佳实践（314 installs）
npx skills add skillcreatorai/ai-agent-skills@python-development -g -y

# 安全代码审查（363 installs）—— 自审用
npx skills add hieutrtr/ai1-skills@code-review-security -g -y

# Graphify 知识图谱（已安装）
# graphify codex install
```

## 六、MCP 配置

在 Codex 的 MCP 配置中添加 context7 用于查询 Python 库文档：

```json
{
  "mcpServers": {
    "context7": {
      "type": "http",
      "url": "https://mcp.context7.com/sse"
    }
  }
}
```

配置方式：`codex mcp add context7 https://mcp.context7.com/sse`

## 七、Graphify 知识图谱

Graphify 已安装。每次任务前检查知识图谱了解模块依赖：
```bash
graphify query "validator.py 的依赖关系"
graphify affected "config.py"
```

## 八、Codex 版本任务总览（全 20 版本）

> v0.0.01-10 中你完成了 3 个安全关键模块（全部验收合格）。v0.0.11-20 中有一个实现任务 + 一个审查任务。

### v0.0.01-10（已完成）

| 版本 | 模块 | 状态 | Claude Code 验收 |
|:--:|------|:--:|:--:|
| v0.0.03 | `validator.py` | ✅ | 读码验证：validate() 拒绝 CIDR/IP范围/通配符/URL，fallback 常量 |
| v0.0.06 | `web_vuln_scanner.py` | ✅ | 读码验证：SQLI/XSS payload 仅检测，BS4 可选导入 |
| v0.0.08 | `msf_adapter.py` | ✅ | 读码验证：is_module_allowed() 黑名单优先，subprocess timeout=60 |

### v0.0.11-30

| 版本 | 模块 | 状态 | Claude Code 验收 |
|:--:|------|:--:|:--:|
| **v0.0.11** | `cli.py` + `setup.py` | ✅ | 读码验证：R4 YES/NO确认(行164)、R2 validate(行69) |
| **v0.0.12** | `test_validator.py` | ✅ | 225 行 / 12 测试函数 |
| **v0.0.13** | `test_msf_adapter.py` | ✅ | 185 行 / 白名单+黑名单+注入防护+审计日志 |
| **v0.0.16** | 审查 `linux_harden.py` | ✅ | 审查报告已产出（见 `docs/review-v016-codex.md`） |
| **v0.0.24** | CVE 知识库扩充 | ✅ | 28→70 条 CVE，11→22 组件，新增 mongodb/django/laravel/magento/bind/exim |
| **v0.0.28** | Web 仪表板 | ✅ | 7 文件 / 7 测试 / CC 验收通过 — 扫描面板 + 报告查看器 + 历史记录列表 |
| **v0.0.29** | 加固页面 + 安全加固 | 🟢 当前任务 | 加固建议面板 + 一键生成脚本 + Web R4 所有权确认 + CSRF 防护 |

---

### Codex 全任务完成统计

```
v0.0.03  validator.py           ✅  R2 防线
v0.0.06  web_vuln_scanner.py    ✅  SQL注入/XSS检测
v0.0.08  msf_adapter.py         ✅  R5 防线
v0.0.11  cli.py + setup.py      ✅  R4 防线
v0.0.12  test_validator.py      ✅  225行/12函数
v0.0.13  test_msf_adapter.py    ✅  185行/全覆盖
v0.0.16  审查 linux_harden.py   ✅  10 issues / 5 fixed
v0.0.24  CVE 知识库扩充         ✅  28→70 条 / 11→22 组件
v0.0.28  Web 仪表板              ✅  7 文件 / 7 测试 / CC 验收通过
v0.0.29  加固页面 + CSRF 防护      ✅  9 文件 / 9 测试 / CC 验收通过
──────────────────────────────────────
        10/10 全部完成 🎉
```

> 当前状态：**全部任务完成！等待 v0.0.30 集成发布（CC + Hermes + CodeWhale）**
> 上一任务：v0.0.29 加固页面 + CSRF 防护（已完成 ✅，CC 验收通过）

---

## 九、v0.0.16 审查任务 ✅ 已完成

### 审查结果

v0.0.16 审查已于 2026-06-10 完成。Codex 审查了 4 个核心文件（harden/base.py、harden/linux_harden.py、core.py generate_hardening()、cli.py run_harden_command()），发现 10 个问题：

| 级别 | 数量 | 处理 |
|------|:--:|------|
| BLOCKER | 1 | ✅ 已修复（B1: placeholder exec 路径） |
| HIGH | 2 | ✅ 已修复（B2: SSH 备份路径；H3: SSH sed 模式） |
| MEDIUM | 1 | ✅ 已修复（M1: 重复计算逻辑） |
| LOW | 1 | ✅ 已修复（L1: 死代码 import） |
| 误报/风格 | 5 | ✅ 已确认不需修复 |

详见审查报告：`docs/review-v016-codex.md`

### 任务背景

v0.0.15-16 已由 Claude Code（架构师）交付。v0.0.16 引入了全新的 `lightshield/harden/` 子包——加固脚本生成器。Claude Code 实现了 4 个核心文件，但作为架构师（不是 Codex），代码未经你这位集群最强的安全审查模型检验。

你是 **v0.0.16 的安全审查者**——只做审查，不做修改。

### 审查范围（4 个文件）

| 文件 | 行数 | 审查重点 |
|------|------|---------|
| `lightshield/harden/base.py` | 136 | HardenStatus/HardenResult/HardenBase 接口：与 BaseAdapter 分离的决策是否正确？`generate()` 抽象签名是否合理？ |
| `lightshield/harden/linux_harden.py` | ~300 | LinuxHardener 实现：iptables 回滚对称性、R4 门在脚本中的声明、零 subprocess 执行 |
| `lightshield/core.py:305-388` | 84 | `generate_hardening()` 钩子：R2 目标校验、RuleEngine → hardener 的调用链是否正确 |
| `lightshield/cli.py:67-130` | 64 | `run_harden_command()` 子命令：R4 交互确认、扫描→匹配→hardener 的全链路 |

### 审查维度

1. **安全（最高优先级）**
   - 确认全链无 `subprocess.run/os.system/Invoke-Expression` 执行加固命令
   - iptables `-A` 与 `-D` 回滚是否对称（加固脚本中的规则名是否与回滚脚本一致）
   - SSH 加固回滚路径是否正确（`sed` → `.bak` 备份恢复）
   - 不可逆操作（apt upgrade）是否在回滚脚本中标注

2. **合规（R1-R6）**
   - R1：脚本包含的命令是否仅有防御性操作（iptables DROP、systemctl stop、备份）
   - R4：脚本头是否有 `read -r -p "...所有权...yes/no"` 阻断门
   - R5：是否触碰到 MSF 调用（应该不触碰——harden 不使用 MSF）
   - 每条操作是否调用了 `logger.audit_harden_action()`

3. **接口设计**
   - `HardenBase` 与 `BaseAdapter` 分离是否合理？（答案：是的——scan 是只读，harden 修改系统，不同语义）
   - `HardenResult` 字段是否完备？（status/target/os_platform/script_path/rollback_path/action_count/audit_id/error）
   - 未来 `WinHardener` 能否复用同一个 `HardenBase`？（当前架构已预留对称扩展点）

4. **异常安全**
   - 文件写入失败 → 返回 `HardenResult(FAILED)` 而非 crash
   - 空 recommendations → 返回 `HardenResult(NO_ACTION)` 而非生成空脚本
   - 输出目录创建失败 → 友好错误 + 日志

5. **代码质量**
   - 中文注释完整性、type hints 覆盖率
   - 模板文件路径是否正确（`templates/` 下的 `.sh` 文件）
   - `__main__` 自检块是否可运行（mock recommendations → 生成脚本 → 断言）

### 输出要求

审查报告写入 `docs/review-v016-codex.md`，格式参考 `docs/review-v004-qoder.md`：
- **审查摘要**：结论（Approved / Changes Requested / Blocked）+ 发现总数
- **问题清单**：按严重度分级（BLOCKER / HIGH / MEDIUM / LOW），每条含文件:行号 + 问题描述 + 修复建议
- **R 线逐个核查**：R1-R6 每条线标记 PASS / FAIL + 证据引用
- **接口评价**：HardenBase 设计合理性判断 + 扩展性评估

### 启动提示词（直接复制到 Codex）

```
你是 LightShield 项目的高级开发工程师（GPT-5.5）。这不是代码实现任务，是安全审查任务。

## 背景
v0.0.16 由 Claude Code（架构师）交付了全新的 `lightshield/harden/` 加固脚本生成器子包。
你作为集群最强的安全审查模型，需要审计这 4 个核心文件的正确性、安全性与合规性。

LightShield 是开源安全自检工具，Python 3.10+，路径：E:/Github Project/LightShield/

## 审查范围

1. lightshield/harden/base.py — HardenStatus / HardenResult / HardenBase ABC
2. lightshield/harden/linux_harden.py — LinuxHardener（加固.sh + 回滚.sh 生成器）
3. lightshield/core.py 的 generate_hardening() 方法 — 编排钩子
4. lightshield/cli.py 的 run_harden_command() 函数 — CLI harden 子命令

## 审查维度

### 1. 安全（最高优先级）
- 确认全链无 subprocess / os.system 执行加固命令
- iptables -A 加固与 -D 回滚是否对称
- SSH 加固 sed → .bak 备份恢复是否正确
- 不可逆操作（apt upgrade）是否在回滚脚本中标注"无法自动回滚"
- 脚本是否以只读方式生成（不自动执行、不设置 +x）

### 2. 合规 R1-R6
- R1: 脚本命令是否仅有防御性操作？
- R4: 脚本头是否有所有权确认交互门？
- 每条操作是否调用了 logger.audit_harden_action()？

### 3. 接口设计
- HardenBase 与 BaseAdapter 分离是否合理？
- HardenResult 字段是否完备？
- WinHardener（v0.0.17）能否对称复用？

### 4. 异常安全
- 文件写入失败 / 空推荐 / 目录创建失败 → 是否优雅降级？

### 5. 代码质量
- 中文注释完整性、type hints 覆盖率
- __main__ 自检是否可运行

## R1-R6 逐个核查模板

| 红线 | 状态 | 证据 |
|------|:--:|------|
| R1 禁攻击 | | |
| R2 禁批量扫描 | | |
| R3 禁远控/后门 | | |
| R4 仅自查 | | |
| R5 MSF白名单 | | |
| R6 频率限制 | | |

## 输出
只输出一个文件：docs/review-v016-codex.md
格式参考 docs/review-v004-qoder.md（审查摘要 + 问题清单分级 + R线核查 + 接口评价）
```

```
你是 LightShield 项目的高级开发工程师，使用 GPT-5.5 模型。

## 背景
v0.1.0 MVP 已完成，v0.0.11 CLI 已交付。v0.0.12 开始测试阶段。
validator.py 是你自己在 v0.0.03 实现的——你最了解它的逻辑。

## 任务：实现 tests/test_validator.py

### 要求
基于 pytest 编写 TargetValidator 的完整单元测试，目标覆盖率 >90%。

### 必须覆盖的场景

**合法输入（assert validate() 返回 True）**：
- 单 IPv4: 192.168.1.1, 10.0.0.1, 172.16.0.1
- 单 IPv6: ::1, fe80::1, 2001:db8::1
- 域名: example.com, my-server.example.com, test.cn
- localhost

**非法输入（assert validate() 返回 False）**：
- 空字符串
- CIDR: 192.168.1.0/24, 10.0.0.0/8, 172.16.0.0/12
- IP 范围: 192.168.1.1-192.168.1.10
- IP 缩写范围: 192.168.1.1-10
- 通配符域名: *.example.com
- URL: http://example.com, https://example.com/path
- 带端口: example.com:443
- 纯路径: /admin
- 带查询参数: example.com?q=test

**边界情况**：
- None 输入（应处理为 False）
- 超长域名（>253 字符）
- 含空格的输入 " 192.168.1.1 "
- Unicode 域名（如中文域名）

**R4/R6 测试**：
- confirm_ownership() 返回非空提示文本
- validate_scan_params(20, 5.0) → True
- validate_scan_params(21, 5.0) → False
- validate_scan_params(10, 2.0) → False
- validate_scan_params(0, 5.0) → 边界

**is_private_ip 测试**：
- 10.0.0.1 → True
- 172.16.0.1 → True
- 192.168.1.1 → True
- 127.0.0.1 → True
- 8.8.8.8 → False

### 代码规范
- pytest 风格（函数名 test_ 开头）
- 中文注释每个测试类的用途
- 使用 parametrize 减少重复
- 每个测试函数断言明确，失败信息清晰

### 输出
只输出一个文件：tests/test_validator.py
内置 if __name__ == "__main__": pytest.main([__file__, "-v"])
```

### 依赖就绪状态（v0.0.08 — 最后一个任务）

```
v0.0.08 需要的依赖：
├── BaseAdapter ABC + ScanResult    ✅ v0.0.04
├── NmapAdapter（实现参考模板）      ✅ v0.0.05
├── ALLOWED/BLOCKED_MSF_PREFIXES    ✅ v0.0.02 constants.py
├── TargetValidator                 ✅ v0.0.03
├── get_logger() + audit_msf_call() ✅ Phase 1 logger.py
└── 全部就绪，零阻塞
```

**结论**：v0.0.08 可以立即开始——这是你在 LightShield 的最后一个任务。

## 九、各版本详细任务 + 启动提示词

### ⚠️ 使用方式

将下方的启动提示词保存为文件，然后执行：
```bash
codex exec "$(cat .cluster/tasks/pending/CODEX-v003-validator.md)"
```
或直接在 Codex 交互会话中输入提示词。

---

### v0.0.03 — validator.py（R2 防线）

**前置依赖**：v0.0.02 完成（`constants.py` 已定义合规常量）

**启动提示词**（保存为 `.cluster/tasks/pending/CODEX-v003-validator.md`）：

```
你是 LightShield 项目的高级开发工程师，使用 GPT-5.5 模型。

## 项目背景
LightShield（轻盾）是一个开源轻量化安全自检 + 防御加固工具，主语言 Python 3.10+。
当前版本 v0.0.03，需要实现输入校验模块。

## 任务：实现 lightshield/utils/validator.py

### 核心需求
实现 TargetValidator 类，这是合规红线 R2（禁止批量扫描公网 IP 段）和 R4（仅自查自有资产）的核心防线。

### 接口契约

```python
class TargetValidator:
    """目标输入校验器 —— 合规 R2/R4 的核心防线"""

    @staticmethod
    def is_valid_ip(target: str) -> bool:
        """验证是否为合法单 IPv4/IPv6 地址（拒绝 CIDR/网段）"""

    @staticmethod
    def is_private_ip(target: str) -> bool:
        """验证是否为内网 IP（10.x, 172.16-31.x, 192.168.x, 127.x）"""

    @staticmethod
    def is_cidr(target: str) -> bool:
        """检测是否为 CIDR 网段格式（需要拦截的格式）"""

    @staticmethod
    def is_valid_domain(target: str) -> bool:
        """验证是否为合法域名（拒绝通配符 *.example.com）"""

    @staticmethod
    def is_wildcard_domain(target: str) -> bool:
        """检测通配符域名"""

    @staticmethod
    def validate(target: str) -> tuple[bool, str]:
        """
        综合校验入口——所有对外操作的前置关口

        校验规则：
        1. 拒绝空字符串
        2. 拒绝 CIDR 网段 (192.168.1.0/24)
        3. 拒绝 IP 范围 (192.168.1.1-192.168.1.10)
        4. 拒绝通配符域名 (*.example.com)
        5. 拒绝 URL 格式 (http://xxx)
        6. 仅接受：单 IPv4、单 IPv6、单域名、localhost

        合法: "192.168.1.1", "example.com", "localhost", "::1"
        非法: "192.168.1.0/24", "*.example.com", "http://example.com"
        """

    @staticmethod
    def confirm_ownership(target: str) -> str:
        """生成所有权确认提示信息（合规 R4）"""

    @staticmethod
    def validate_scan_params(concurrency: int, interval: float) -> tuple[bool, str]:
        """校验扫描参数（合规 R6：并发 ≤20，间隔 ≥5s）"""
```

### 测试场景（实现代码中内置 __main__ 自检块）
- "192.168.1.1" → (True, "合法单 IPv4")
- "192.168.1.0/24" → (False, "拒绝 CIDR 网段")
- "::1" → (True, "合法单 IPv6")
- "*.example.com" → (False, "拒绝通配符域名")
- "http://example.com" → (False, "拒绝 URL")
- "" → (False, "拒绝空地址")

### ⚠️ 合规约束
1. 你的代码是防御代码，不得包含任何攻击向逻辑
2. 正则表达式必须精确——宁可误拒，不可漏过
3. IPv6 支持完整格式（包括 :: 缩写、fe80:: 等）

### 代码规范
- Python 3.10+，中文注释
- 零外部依赖（仅 re, ipaddress 标准库）
- type hints + docstring
- 异常安全：任何输入不应抛出未捕获异常

### 输出
只输出一个文件：lightshield/utils/validator.py
```

---

### v0.0.06 — web_vuln_scanner.py（Web 漏洞检测）🟢 已解锁

**当前就绪的依赖**：
```
lightshield/adapters/base.py     ✅ BaseAdapter + ScanResult + VulnFinding
lightshield/utils/constants.py   ✅ RiskLevel + ScanStatus
lightshield/utils/validator.py   ✅ TargetValidator
lightshield/utils/logger.py      ✅ get_logger()（Phase 1 刚完成）
```

**启动提示词**（保存为 `.cluster/tasks/pending/CODEX-v006-webvuln.md`，或直接复制下方到 Codex）：

```
你是 LightShield 项目的高级开发工程师，使用 GPT-5.5 模型。

## 项目背景
LightShield（轻盾）是开源轻量化安全自检 + 防御加固工具，Python 3.10+。
当前版本 v0.0.06。Phase 1 骨架已完成，所有依赖已就绪：

已有文件（你可以 import）：
  lightshield/adapters/base.py      → BaseAdapter, ScanResult, VulnFinding
  lightshield/utils/constants.py    → RiskLevel, ScanStatus, ScanType
  lightshield/utils/validator.py    → TargetValidator
  lightshield/utils/logger.py       → get_logger()

## 任务：实现 lightshield/scanners/web_vuln_scanner.py

### 核心需求
实现 WebVulnScanner 类，继承 BaseAdapter，自研实现：
1. SQL 注入检测（仅检测，不利用）
2. XSS 检测（反射型 + 存储型）
3. 敏感目录/文件枚举

### ⚠️ 关键边界（合规红线）
- 这是**检测**模块，不是**利用**模块
- SQL 注入：发送测试 payload → 观察响应差异 → 判断是否存在漏洞 → **不提取数据**
- XSS：发送测试 payload → 检查响应中是否未转义 → **不执行脚本**
- 目录枚举：基于内置字典 → **不做暴力破解**

### 接口契约

```python
class WebVulnScanner(BaseAdapter):
    """Web 漏洞检测扫描器 — 自研脚本引擎"""

    # === BaseAdapter 必须实现 ===
    def validate_target(self, target: str) -> bool: ...
    def scan(self, target: str, **kwargs) -> ScanResult: ...
    def capabilities(self) -> list[str]: ...

    # === SQL 注入检测 ===
    def detect_sqli(self, url: str, params: dict = None) -> list[VulnFinding]:
        """
        基于 OWASP Top 10 的 SQL 注入检测。
        方法：注入测试 payload → 分析响应（错误消息/响应时间/内容差异）
        不对数据库执行任何写操作或数据提取操作。
        """

    # === XSS 检测 ===
    def detect_xss(self, url: str, params: dict = None) -> list[VulnFinding]:
        """
        XSS 检测（反射型 + 存储型）。
        方法：注入测试 payload → 检查响应中是否未转义回显
        不执行任何脚本，不弹窗，不在浏览器中渲染。
        """

    # === 敏感目录枚举 ===
    def enumerate_directories(self, base_url: str) -> list[VulnFinding]:
        """
        基于内置字典猜解常见敏感路径。
        字典上限：200 条常见路径。
        不做暴力破解，不做递归深度遍历。
        """
```

### VulnFinding 数据结构
```python
@dataclass
class VulnFinding:
    vuln_type: str          # "sqli" | "xss_reflected" | "xss_stored" | "sensitive_dir"
    severity: RiskLevel     # CRITICAL / HIGH / MEDIUM / LOW
    url: str
    parameter: str          # 受影响的参数
    payload: str            # 测试 payload（用于复现验证）
    evidence: str           # 响应中证实漏洞存在的证据
    description: str        # 中文描述
    remediation: str        # 修复建议
```

### SQL 注入检测 Payload（仅检测用，不以利用为目的）
```python
SQLI_TEST_PAYLOADS = [
    ("'", "单引号闭合测试"),
    ('"', "双引号闭合测试"),
    ("' OR '1'='1", "OR 永真测试（仅检测，不提取数据）"),
    ("' AND '1'='2", "AND 永假测试"),
    ("'; WAITFOR DELAY '0:0:3'--", "时间盲注测试（3秒延迟）"),
]
# ⚠️ 所有 payload 仅用于区分正常/异常响应，不对数据库执行任何写操作
```

### XSS 检测 Payload
```python
XSS_TEST_PAYLOADS = [
    ("<script>alert(1)</script>", "基础 script 标签"),
    ('"><script>alert(1)</script>', "属性闭合注入"),
    ("<img src=x onerror=alert(1)>", "img onerror 事件"),
]
# ⚠️ payload 仅作为字符串发送——不渲染、不弹窗、不在浏览器中执行
```

### 代码规范
- Python 3.10+，中文注释
- 依赖：requests, beautifulsoup4（已在 requirements.txt 中）
- 网络超时 10s，异常友好提示
- Rate limiting：同一目标请求间隔 ≥1s

### 输出
只输出一个文件：lightshield/scanners/web_vuln_scanner.py
```

---

### v0.0.08 — msf_adapter.py（MSF 安全调用封装）🟢 已解锁

**当前就绪的依赖**：
```
lightshield/adapters/base.py           ✅ BaseAdapter（参考 nmap_adapter 的完整实现）
lightshield/adapters/nmap_adapter.py   ✅ BaseAdapter 实现模板
lightshield/utils/constants.py         ✅ ALLOWED_MSF_PREFIXES + BLOCKED_MSF_PREFIXES
lightshield/utils/validator.py         ✅ TargetValidator
lightshield/utils/logger.py            ✅ get_logger() + audit_msf_call()
```

**启动提示词**（保存为 `.cluster/tasks/pending/CODEX-v008-msf.md`，或直接复制下方到 Codex）：

```
你是 LightShield 项目的高级开发工程师，使用 GPT-5.5 模型。

## 项目背景
LightShield（轻盾）是开源轻量化安全自检 + 防御加固工具，Python 3.10+。
当前版本 v0.0.08。这是你在 10 个小版本中的最后一个任务。

已有文件（你可以 import 参考）：
  lightshield/adapters/base.py           → BaseAdapter, ScanResult, VulnFinding
  lightshield/adapters/nmap_adapter.py   → BaseAdapter 的完整实现参考
  lightshield/utils/constants.py         → ALLOWED_MSF_PREFIXES, BLOCKED_MSF_PREFIXES
  lightshield/utils/validator.py         → TargetValidator
  lightshield/utils/logger.py            → get_logger()（含 audit_msf_call()）

## 任务：实现 lightshield/adapters/msf_adapter.py

### 核心需求
实现 MsfScannerAdapter(BaseAdapter)，这是合规红线 R5（MSF 调用限制）的核心防线。
通过白名单机制安全封装 Metasploit auxiliary/scanner 子集。

### ⚠️ 关键边界（你最重要的责任）
- **仅允许**调用 auxiliary/scanner/ 路径下的模块
- **绝对禁止**调用 exploit/、payload/、post/、evasion/、nops/ 及 auxiliary/dos/、auxiliary/admin/
- 白名单/黑名单定义在 `lightshield/utils/constants.py` 中
- 你的代码是项目的 **R5 防线**——如果这里出错，整个合规体系失效

### 接口契约

```python
class MsfScannerAdapter(BaseAdapter):
    """MSF 扫描器适配器 — 合规 R5 白名单防线"""

    def __init__(self, msf_path: str = None):
        """初始化 MSF 适配器，加载白名单/黑名单"""

    # === BaseAdapter 必须实现 ===
    def validate_target(self, target: str) -> bool:
        """目标合法性校验（委托给 TargetValidator）"""

    def scan(self, target: str, **kwargs) -> ScanResult:
        """执行扫描，kwargs 指定 msf_module（必须在白名单内）"""

    def capabilities(self) -> list[str]:
        """返回可用的 MSF scanner 模块列表（仅白名单内）"""

    # === MSF 特有方法 ===
    def is_module_allowed(self, module_path: str) -> bool:
        """
        R5 白名单校验——任何模块调用前的强制检查。

        规则：
        1. module_path 必须以 ALLOWED_MSF_PREFIXES 中某一项为前缀
        2. module_path 不得以 BLOCKED_MSF_PREFIXES 中任一项为前缀
        3. 不匹配任何白名单 → 拒绝 + 日志告警
        """

    def list_allowed_modules(self) -> list[str]:
        """列出所有白名单内的可用模块"""

    def exec_msf_module(self, module_path: str, target: str,
                        options: dict = None) -> dict:
        """
        安全执行 MSF 模块——带完整审计日志。

        流程：
        1. is_module_allowed() → 不通过则抛 SecurityViolationError
        2. TargetValidator.validate() → 不通过则抛 InvalidTargetError
        3. 记录审计日志（模块名、目标、时间戳）
        4. 构造 msfconsole -q -x "use module; set RHOSTS target; run; exit"
        5. 解析输出为结构化数据
        6. 记录完成日志
        """

    def get_audit_log(self, limit: int = 50) -> list[dict]:
        """获取 MSF 调用审计日志"""
```

### 安全异常定义
```python
class SecurityViolationError(Exception):
    """合规违规异常——当尝试调用非白名单模块时抛出"""
    def __init__(self, module_path: str, reason: str):
        self.module_path = module_path
        self.reason = reason
        super().__init__(f"安全违规: {module_path} — {reason}")
```

### 审计日志格式
```python
# 每次 MSF 调用记录
{
    "timestamp": "2026-06-09T20:30:00",
    "module": "auxiliary/scanner/ssh/ssh_login",
    "target": "192.168.1.1",
    "options": {"RHOSTS": "192.168.1.1", "THREADS": "1"},
    "result": "completed",
    "duration_seconds": 12.5
}
```

### 代码规范
- Python 3.10+，中文注释
- 子进程调用使用 subprocess.run() + timeout=60
- 所有 MSF 调用前必须经过 is_module_allowed() 白名单检查（不可绕过！）
- 所有 MSF 调用记录完整审计日志
- 参考 `lightshield/adapters/nmap_adapter.py` 作为 BaseAdapter 实现模板

### 输出
只输出一个文件：lightshield/adapters/msf_adapter.py
```

---

## 十、任务执行协议

1. **接收任务**：从 `.cluster/tasks/pending/` 读取任务文件，或直接使用上述提示词
2. **理解接口**：提示词中定义了明确的接口契约（输入/输出/异常）
3. **实现代码**：严格按照接口契约实现，不越界
4. **自审合规**：对照 R1-R6 自查代码——你的任务是安全关键代码，违规零容忍
5. **输出文件**：将代码写入指定路径（每个任务只输出一个文件）
6. **标记完成**：通知 Claude Code 进行 Gate A→B→D 审查

## 十一、代码规范

- Python 3.10+，完整中文注释
- 所有公开方法带 type hints 和 docstring
- 异常安全：不抛出未捕获异常
- 零外部依赖优先（仅标准库，除非任务明确允许）
- 参考 `CLAUDE.md` 中的目录结构和架构分层
- 每个文件末尾内置 `if __name__ == "__main__":` 自检块，覆盖核心校验场景

---

## 十二、v0.0.11 详细任务 + 启动提示词 🟢 当前任务

### 背景

v0.1.0 MVP 已有 14 个模块，但只能在 Python 中通过 `from lightshield.core import ...` 调用。
v0.0.11 需要给用户一个命令行入口：`lightshield scan 192.168.1.1`

### 依赖就绪

```
lightshield/core.py              ✅ 主调度器（run_scan / run_asset_scan / run_full_scan）
lightshield/adapters/nmap_adapter.py ✅ Nmap 适配器
lightshield/rules/engine.py       ✅ 规则引擎
lightshield/report/reporter.py    ✅ 报告生成器
lightshield/utils/validator.py    ✅ TargetValidator
lightshield/config.py             ✅ 配置管理
```

### 启动提示词（直接复制到 Codex）

```
你是 LightShield 项目的高级开发工程师，使用 GPT-5.5 模型。

## 项目背景
LightShield（轻盾）是开源轻量化安全自检+防御加固工具，Python 3.10+。
v0.1.0 MVP 已完成（14 模块），v0.0.11 需要添加 CLI 命令行入口。

## 任务：实现 lightshield/cli.py + 更新 setup.py

### 核心需求
提供 `lightshield scan <target>` 命令行入口，让用户一条命令完成：
资产扫描 → 漏洞检测 → 规则匹配 → 报告生成

### 子命令设计

```
lightshield scan <target>          # 全量扫描（资产+漏洞+报告）
lightshield quick-scan <target>    # 快速扫描（Top 100 端口）
lightshield report <target>        # 仅生成报告（基于已有扫描结果）
lightshield version                # 显示版本号
```

### 参数设计

```
lightshield scan 192.168.1.1 \
    --output-format markdown|text \   # 报告格式，默认 markdown
    --output-dir ./reports \         # 报告输出目录
    --confirm-ownership \            # R4：确认目标所有权（必须！）
    --scan-types port_scan,web_vuln \ # 指定扫描类型，默认全部
    --timeout 60 \                   # 扫描超时
    --verbose                        # 详细日志输出
```

### 接口契约

```python
# lightshield/cli.py

def create_parser() -> argparse.ArgumentParser:
    """创建命令行参数解析器"""

def main():
    """CLI 主入口——由 console_scripts 调用"""

# 流程：
# 1. 解析参数
# 2. R2 输入校验（调用 TargetValidator.validate()）
# 3. R4 所有权确认（如未传 --confirm-ownership，打印警告并要求确认）
# 4. 注册适配器（NmapAdapter + 其他可用的）
# 5. 执行扫描（LightShieldCore.run_scan()）
# 6. 规则匹配（RuleEngine.match()）
# 7. 加固推荐（RuleEngine.recommend_hardening()）
# 8. 报告生成（ReportGenerator.generate_and_save()）
# 9. 输出报告路径到控制台
```

### ⚠️ 安全关键点

- `--confirm-ownership` 是 R4 防线：CLI 模式下默认要求用户传此参数
  未传时打印所有权警告并要求输入 YES 确认，不确认则退出
- 目标参数必须先过 TargetValidator.validate()，拒绝 CIDR/网段/通配符
- 错误信息用中文，面向非技术用户

### setup.py 更新

在 setup.py（或 pyproject.toml）中注册 console_scripts 入口：

```python
entry_points={
    "console_scripts": [
        "lightshield=lightshield.cli:main",
    ],
},
```

### 进度提示（面向用户友好）

```
LightShield 轻盾 v0.1.0
[1/4] 正在扫描端口... (NmapAdapter)
[2/4] 正在检测漏洞... (WebVulnScanner + WeakPassword + ComponentChecker)
[3/4] 正在匹配规则... (RuleEngine: 14 条漏洞规则)
[4/4] 正在生成报告... (ReportGenerator)
✅ 报告已保存: ./reports/report-20260609-215000.md
```

### 代码规范
- Python 3.10+，中文注释
- 仅标准库 + argparse（零新依赖）
- 异常安全：网络错误/超时/权限不足 → 中文错误提示 → 退出码 1
- 内置 __main__ 自检块（模拟 scan 流程但使用 mock 数据）

### 输出
- lightshield/cli.py（主文件）
- 更新 setup.py 或 pyproject.toml（console_scripts 入口）
```

---

### v0.0.16 预告（等 v0.0.15 完成后解锁）

Codex 将在 v0.0.16 作为 **安全审查者** 审查 `lightshield/harden/linux_harden.py`——确保自动加固脚本不会引入新的安全风险或误关关键服务。

---

## 十三、v0.0.24 详细任务 + 启动提示词 🟢 当前任务

### 背景

v0.0.23 刚完成 C90 重构（`component_checker.scan()` 从 F(41) 降到 A(4)）。阶段一质量深化已全部交付。
现在进入阶段二：**内容增长**——让扫描器真正有价值。

当前 CVE 知识库（`lightshield/scanners/component_checker.py` 的 `CVE_DATABASE`）仅有 **28 条记录**，覆盖 11 个组件。
许多常见组件的 CVE 覆盖面不足（如 nginx 仅 3 条、MySQL 仅 2 条、Redis 仅 2 条），且完全缺少 Laravel/Django/Magento/MongoDB 等广泛使用的组件。

### 目标

将 CVE 条目从 **28 → 50+**，覆盖 **Top 10 Web 组件**，每个组件至少 3 条 CVE 记录。

### 扩充优先级

| 优先级 | 组件 | 当前条目 | 目标条目 | 理由 |
|:--:|------|:--:|:--:|------|
| 🔴 | nginx | 3 | 5+ | 全球最广泛 Web 服务器 |
| 🔴 | apache_httpd | 3 | 5+ | 市场份额第二 |
| 🔴 | php | 3 | 5+ | 78% 网站使用 |
| 🔴 | mysql | 2 | 4+ | 最广泛开源数据库 |
| 🟡 | redis | 2 | 4+ | 常因配置不当暴露 |
| 🟡 | postgresql | 2 | 4+ | 企业首选数据库 |
| 🟡 | apache_tomcat | 2 | 4+ | Java 应用服务器 |
| 🟡 | nodejs | 2 | 4+ | 现代 Web 应用主流 |
| 🟢 | mariadb | 1 | 3+ | MySQL 替代品 |
| 🟢 | openssl | 2 | 3+ | 加密基础设施 |
| 🟢 | wordpress | 3 | 4+ | 43% 网站使用 CMS |
| 🟢 | drupal | 1 | 3+ | 企业 CMS |
| 🟢 | joomla | 1 | 3+ | 流行 CMS |
| 🟢 | phpmyadmin | 1 | 2+ | 常见管理面板 |
| ⚪ | MongoDB | 0 | 3+ | **新组件** — 广泛使用 |
| ⚪ | Django | 0 | 2+ | **新组件** — Python 首选框架 |
| ⚪ | Laravel | 0 | 2+ | **新组件** — PHP 首选框架 |
| ⚪ | Bind | 0 | 1+ | **新组件** — DNS 服务器 |
| ⚪ | Exim | 0 | 1+ | **新组件** — 邮件服务器 |

### 约束

1. **所有 CVE 必须来自公开 NVD 记录**（nvd.nist.gov），不得编造 CVE 编号
2. **版本范围必须精确**：`min_version` / `max_affected` 必须是实际受影响的版本号
3. **CVSS 分数必须准确**：使用 NVD 公开的 CVSS v3.x 评分
4. **中文描述准确**：标题、描述、修复建议全部中文化
5. **优先级**：2022-2025 年的高危/严重 CVE 优先（CVSS ≥ 7.5）
6. **格式严格遵守**：必须使用 `CveEntry` dataclass 的字段结构

### 依赖就绪

```
lightshield/scanners/component_checker.py  ✅ CVE_DATABASE 已定义 28 条
lightshield/utils/constants.py             ✅ RiskLevel enum (CRITICAL/HIGH/MEDIUM/LOW)
CveEntry dataclass                          ✅ 8 字段（cve_id/component/max_affected/min_version/severity/cvss_score/title_cn/description_cn/remediation_cn）
```

### 启动提示词（直接复制到 Codex）

```
你是 LightShield 项目的高级开发工程师，使用 GPT-5.5 模型。

## 项目背景
LightShield（轻盾）是开源轻量化安全自检 + 防御加固工具，Python 3.10+。
路径：E:/Github Project/LightShield/

## 任务：扩充 CVE 知识库

### 核心需求
在 `lightshield/scanners/component_checker.py` 的 `CVE_DATABASE` 列表中新增 ~25 条 CVE 记录，
将总量从 28 条提升到 50+ 条，覆盖至少 18 个组件。

### 你要修改的文件
`lightshield/scanners/component_checker.py`

只修改 `CVE_DATABASE` 列表（在现有 28 条记录后追加新条目）。不修改任何其他代码。

### CveEntry 格式（严格遵守）

```python
CveEntry(
    cve_id="CVE-YYYY-NNNNN",       # 精确 CVE 编号
    component="规范组件名",          # 必须匹配 _COMPONENT_ALIASES 中的 key
    max_affected="X.Y.Z",           # 最大受影响版本（不含），即 version < max_affected
    min_version="X.Y.Z",            # 起始受影响版本（含），'' 表示所有更早版本
    severity=RiskLevel.CRITICAL,    # CRITICAL / HIGH / MEDIUM / LOW
    cvss_score=9.8,                 # CVSS v3.x 浮点数
    title_cn="中文漏洞标题 (CVE-YYYY-NNNNN)",
    description_cn=("中文详细描述。影响范围：min ≤ version < max。"),
    remediation_cn="中文修复建议。",
)
```

### 版本范围规则
- `min_version=""` 表示所有低于 `max_affected` 的版本都受影响
- `min_version="X.Y.Z"` 表示从该版本起受影响（含）
- `max_affected="X.Y.Z"` 表示小于该版本的受影响（不含），即 [min, max) 半开区间
- OpenSSH 版本用 `p` 后缀（如 `9.8p1`），其他组件用标准语义化版本

### 必须扩充的组件（至少各新增 1-2 条）

**已有组件，需增加条目**：
- nginx: +2 条（建议 CVE-2024-7344 / CVE-2022-41741 等）
- apache_httpd: +2 条（建议 CVE-2024-4084 / CVE-2023-45802 等）
- php: +2 条（建议 CVE-2024-4577 已存在，补充 CVE-2023-3824 / CVE-2024-2961 等）
- mysql: +2 条（建议 CVE-2024-21096 / CVE-2023-22084 等）
- redis: +2 条（建议 CVE-2024-31449 / CVE-2022-24834 等）
- postgresql: +2 条
- apache_tomcat: +2 条
- nodejs: +2 条
- wordpress: +1 条
- drupal: +2 条
- joomla: +2 条
- mariadb: +2 条
- openssl: +1 条
- phpmyadmin: +1 条

**全新组件，需新增**：
- mongodb: +3 条
- django: +2 条
- laravel: +2 条
- magento: 此组件已在别名表但无 CVE → +2 条
- bind: +1 条
- exim: +1 条

### 数据来源约束

1. ⚠️ **CVE 编号必须真实存在**于 NVD 公开数据库（nvd.nist.gov）。不得编造。
2. **CVSS 分数必须准确**——使用 NVD 公开的 CVSS v3.x Base Score。
3. **版本范围必须精确**——核对 CVE 详情中的 `cpe:affected` 版本范围。
4. **优先收录**：CVSS ≥ 7.5、2022-2025 年、有公开 PoC 的高价值 CVE。
5. 如果某个组件找不到足够的高质量 CVE，标注原因并跳过——宁可少加，不加低质量记录。

### 合规约束

- R1（禁攻击）：CVE 描述中不包含 exploit 利用代码，仅描述漏洞影响和修复
- 描述语言：面向防御者，不是攻击者。强调"如何发现"和"如何修复"，不写"如何利用"
- 修复建议：具体、可操作（升级到哪个版本、改哪个配置）

### 代码规范
- 中文注释分组（如 `# === MongoDB ===`）
- 每个 CVE 条目前保留简短注释说明漏洞名称
- 条目按组件分组排列，组件按字母序，同组件内按 CVSS 降序
- 所有 CVE 描述使用中文

### 验收标准
1. CVE_DATABASE 总条目 ≥ 50
2. 覆盖组件 ≥ 18
3. 每个原有组件至少 +1 条
4. 至少 5 个新组件有 CVE 覆盖
5. CveEntry 格式无语法错误（可被 Python import）
6. 无编造 CVE 编号（抽查 5 条去 NVD 验证）

### 输出
只修改一个文件：lightshield/scanners/component_checker.py
仅修改 CVE_DATABASE 列表部分（追加新条目），不改动其他任何代码。
```

---

## 十四、v0.0.28 详细任务 + 启动提示词 🟢 当前任务

### 背景

v0.0.27 Flask API 骨架已由 Claude Code 交付。后端 5 个端点全部可用：

| 端点 | 功能 | 鉴权 |
|------|------|:--:|
| `POST /api/login` | 用户登录 | 否 |
| `POST /api/logout` | 用户登出 | 否 |
| `POST /api/scan` | 提交扫描任务（R2 校验） | 是 |
| `GET /api/scan/<id>` | 查询任务状态 | 是 |
| `GET /api/report/<id>` | 获取扫描报告（markdown/text） | 是 |

v0.0.28 需要你在此基础上构建 **Web 仪表板前端**——让用户通过浏览器完成 scan → view report 全流程。

### 依赖就绪

```
lightshield/web/app.py          ✅ create_app(config) Flask 工厂
lightshield/web/routes.py       ✅ api_bp Blueprint（/api/* 端点）
lightshield/web/auth.py         ✅ Session 鉴权（login_required 装饰器）
lightshield/core.py             ✅ submit_scan() / get_scan_status()
lightshield/repository/          ✅ SqliteRepository（list_recent / get / list_by_target）
```

### 核心需求

创建 Web 仪表板页面（Flask 模板 + 静态资源），实现：

1. **登录页面** (`GET /`) — 用户名密码登录表单
2. **仪表板主页** (`GET /dashboard`) — 扫描面板 + 历史列表
3. **报告查看器** (`GET /report/<scan_id>`) — Markdown 渲染报告

### 技术约束

- **Flask 原生模板**：使用 Jinja2 模板引擎（Flask 内置），不引入 React/Vue 等前端框架
- **CSS 框架**：推荐使用纯 CSS 或轻量级方案（如 Pico.css / Simple.css），不加构建工具链
- **Markdown 渲染**：使用 Python `markdown` 库（需新增可选依赖）或前端 JS 库（如 marked.js CDN）
- **零构建步骤**：`lightshield serve` 启动即可用，不需要 npm install / webpack / vite 等
- **Session 复用**：页面登录使用已有 `/api/login` 端点，Session cookie 自动由浏览器携带

### 页面设计

#### 1. 登录页面 (`GET /`)

```
┌──────────────────────────────────────────┐
│          LightShield 轻盾 Web 仪表板       │
│                                          │
│   ┌─────────────────────────────────┐    │
│   │  用户名: [_______________]      │    │
│   │  密码:   [_______________]      │    │
│   │  [登录]                         │    │
│   └─────────────────────────────────┘    │
│                                          │
│  默认凭证: admin / lightshield           │
└──────────────────────────────────────────┘
```

- 表单向 `POST /api/login` 提交（AJAX 或 form POST）
- 登录成功 → 重定向到 `/dashboard`
- 登录失败 → 显示红色错误提示
- 如已登录 → 直接重定向到 `/dashboard`

#### 2. 仪表板主页 (`GET /dashboard`)

```
┌──────────────────────────────────────────┐
│  LightShield 轻盾        [admin] [登出]   │
├──────────────────────────────────────────┤
│  ┌─ 新建扫描 ─────────────────────────┐  │
│  │  目标地址: [_______________]       │  │
│  │  扫描类型: [全量扫描 ▾]            │  │
│  │  ☐ 我确认拥有目标所有权            │  │
│  │  [开始扫描]                        │  │
│  │  状态: 扫描中... / 完成 / 失败     │  │
│  └────────────────────────────────────┘  │
│                                          │
│  ┌─ 扫描历史 ─────────────────────────┐  │
│  │  扫描ID     目标      状态   时间   │  │
│  │  LS-xxx  192.168.1  compl.. 12:00  │  │
│  │  LS-xxx  10.0.0.1   failed 11:30  │  │
│  │  [查看报告] [查看详情]              │  │
│  └────────────────────────────────────┘  │
└──────────────────────────────────────────┘
```

- 扫描提交：AJAX `POST /api/scan` → 显示 task_id → 轮询 `GET /api/scan/<id>` 直到 completed
- 历史列表：调用仓库 `list_recent(limit=20)` 展示
- 点击"查看报告" → 跳转 `/report/<scan_id>`
- 登出按钮 → `POST /api/logout` → 重定向到 `/`

#### 3. 报告查看器 (`GET /report/<scan_id>`)

```
┌──────────────────────────────────────────┐
│  LightShield 轻盾        [返回] [登出]    │
├──────────────────────────────────────────┤
│  扫描报告: LS-20260614-...               │
│  目标: 127.0.0.1  状态: completed        │
│  ─────────────────────────────────────── │
│  # LightShield 安全检测报告              │
│                                          │
│  ## 一、资产概览                         │
│  | 属性 | 值 |                           │
│  |------|----|                           │
│  | 目标 | 127.0.0.1 |                    │
│  ...                                     │
│                                          │
│  ## 二、风险摘要                         │
│  | 等级 | 数量 |                         │
│  ...                                     │
│                                          │
│  ## 三、漏洞详情                         │
│  ...                                     │
│                                          │
│  ## 四、加固操作建议                     │
│  ...                                     │
└──────────────────────────────────────────┘
```

- 调用 `GET /api/report/<scan_id>?format=markdown` 获取原始 markdown
- 使用 marked.js（CDN）或 Python markdown 库渲染为 HTML
- "返回"按钮 → `/dashboard`

### 文件结构

你需要创建以下文件：

```
lightshield/web/
├── templates/                  # Jinja2 模板目录
│   ├── base.html              # 基础布局（导航栏 + 页脚 + CSS 引入）
│   ├── login.html             # 登录页面
│   ├── dashboard.html         # 仪表板主页
│   └── report.html            # 报告查看页面
├── static/                    # 静态资源
│   └── style.css              # 全局样式表
└── pages.py                   # 页面路由蓝图（新文件 — 注册页面路由）

lightshield/web/app.py          # 修改：注册 pages 蓝图
```

### pages.py 页面路由（新增）

```python
# lightshield/web/pages.py
from flask import Blueprint, render_template, redirect, url_for, session

pages_bp = Blueprint("pages", __name__)  # 注意：无 url_prefix，直接挂载到 /

@pages_bp.route("/")
def index():
    """首页 — 已登录跳转到仪表板，否则显示登录页"""
    if "user" in session:
        return redirect(url_for("pages.dashboard"))
    return render_template("login.html")

@pages_bp.route("/dashboard")
def dashboard():
    """仪表板主页 — 需登录"""
    if "user" not in session:
        return redirect(url_for("pages.index"))
    # 获取扫描历史传给模板
    from lightshield.repository.base import get_repository
    try:
        repo = get_repository("sqlite", db_url="data/lightshield.db")
        history = repo.list_recent(limit=20)
    except Exception:
        history = []
    return render_template("dashboard.html", history=history)

@pages_bp.route("/report/<scan_id>")
def view_report(scan_id):
    """报告查看器 — 需登录"""
    if "user" not in session:
        return redirect(url_for("pages.index"))
    return render_template("report.html", scan_id=scan_id)
```

### app.py 修改

在 `create_app()` 中注册 pages 蓝图：

```python
from lightshield.web.pages import pages_bp
app.register_blueprint(pages_bp)  # 页面路由（无前缀，挂载在 /）
```

### Markdown 渲染方案

推荐使用 **marked.js CDN**（零后端依赖）：

```html
<!-- 在 report.html 中 -->
<script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
<script>
fetch('/api/report/{{ scan_id }}?format=markdown')
  .then(r => r.text())
  .then(md => { document.getElementById('report-content').innerHTML = marked.parse(md); });
</script>
```

备选方案：新增 Python `markdown` 可选依赖，在服务端渲染。

### 样式要求

- **专业安全工具风格**：深色主题（可选切换）、清晰的信息层级
- **响应式**：桌面端和移动端均可使用
- **中文友好**：合适的字体栈（`"PingFang SC", "Microsoft YaHei", sans-serif`）
- **状态色彩**：completed=绿色、failed=红色、partial=橙色、running=蓝色
- **风险等级色彩**：CRITICAL=深红、HIGH=红色、MEDIUM=橙色、LOW=黄色、INFO=灰色

### 合规约束

- **R2**：扫描面板的目标输入框应做前端校验（拒绝明显 CIDR/URL），但最终校验由 API 层完成
- **R4**：扫描面板的"确认所有权"复选框默认不勾选，提示文字说明合规要求
- 无攻击代码，无 exploit/payload/attack 相关内容
- Session cookie 由 Flask 自动管理，前端无需额外处理

### 验收标准

1. `lightshield serve` 启动后浏览器访问 `http://127.0.0.1:5000` 可看到登录页
2. 登录 → 仪表板 → 新建扫描 → 查看进度 → 查看报告 全流程可用
3. 未登录访问 `/dashboard` 自动跳转到登录页
4. 报告页面正确渲染 Markdown（表格、标题、代码块）
5. 扫描历史列表从 SQLite 加载并正确展示
6. 所有页面中文显示正常
7. 不引入超过 2 个新依赖（可选 markdown 库除外）
8. 现有 559 条测试全量通过（不修改现有测试）

### 启动提示词（直接复制到 Codex）

```
你是 LightShield 项目的高级开发工程师，使用 GPT-5.5 模型。

## 项目背景
LightShield（轻盾）是开源轻量化安全自检 + 防御加固工具，Python 3.10+。
路径：E:/Github Project/LightShield/

## 任务：实现 Web 仪表板前端（v0.0.28）

### 前置条件
v0.0.27 Flask API 骨架已就绪。后端 5 个端点全部可用：
- POST /api/login — 用户登录（Session 鉴权）
- POST /api/logout — 用户登出
- POST /api/scan — 提交扫描任务（需登录，R2 校验）
- GET /api/scan/<id> — 查询任务状态（需登录）
- GET /api/report/<id>?format=markdown — 获取扫描报告（需登录）

现有文件（你可参考/修改）：
  lightshield/web/app.py           → create_app(config) Flask 工厂
  lightshield/web/routes.py        → api_bp（/api/* 端点）
  lightshield/web/auth.py          → Session 鉴权（login_required / login / logout）
  lightshield/core.py              → submit_scan() / get_scan_status()
  lightshield/repository/           → SqliteRepository（list_recent / get / list_by_target）

### 核心需求

创建 Web 仪表板，让用户通过浏览器完成 scan → view report 全流程。

### 你要创建/修改的文件

**新建：**
1. lightshield/web/pages.py — 页面路由蓝图（GET /, /dashboard, /report/<scan_id>）
2. lightshield/web/templates/base.html — Jinja2 基础布局
3. lightshield/web/templates/login.html — 登录页面
4. lightshield/web/templates/dashboard.html — 仪表板（扫描面板 + 历史列表）
5. lightshield/web/templates/report.html — 报告查看器
6. lightshield/web/static/style.css — 全局样式表

**修改：**
7. lightshield/web/app.py — 注册 pages_bp 蓝图 + 配置模板/静态目录

### 页面功能要求

**1. 登录页面 (GET /)**
- 用户名密码表单，提交到 POST /api/login（AJAX fetch）
- 登录成功 → window.location = "/dashboard"
- 登录失败 → 显示红色错误提示
- 已登录（session 存在）→ 直接重定向到 /dashboard

**2. 仪表板主页 (GET /dashboard)**
- 顶部导航栏：标题 "LightShield 轻盾" + 当前用户名 + 登出按钮
- 扫描面板：
  - 目标地址输入框（前端校验：拒绝空值和明显 CIDR/URL，但最终由 API 校验）
  - 扫描类型下拉框：全量扫描 / 资产扫描 / 漏洞扫描
  - "我确认拥有目标所有权"复选框（未勾选时显示 R4 合规提示）
  - "开始扫描"按钮 → AJAX POST /api/scan → 显示 task_id → 轮询 GET /api/scan/<id> 直到 completed/partial/failed
  - 扫描进度条或状态文字（蓝色=running, 绿色=completed, 红色=failed, 橙色=partial）
  - 扫描完成后显示"查看报告"链接
- 扫描历史列表（从后端加载）：
  - 调用仓库 list_recent(limit=20) 获取数据 → 通过后端接口或直接在 pages.py 中调用
  - 表格列：扫描ID（截断显示）、目标、状态（彩色标签）、端口数、漏洞数、时间
  - 每行有"查看报告"按钮 → 跳转 /report/<scan_id>
- 登出按钮 → fetch POST /api/logout → window.location = "/"

**3. 报告查看器 (GET /report/<scan_id>)**
- 顶部导航栏 + 返回按钮
- 扫描元信息：scan_id、目标、状态、时间
- 报告内容区：
  - 使用 fetch GET /api/report/<scan_id>?format=markdown 获取原始 markdown
  - 使用 marked.js CDN 渲染为 HTML
  - 加载时显示加载动画
  - 错误时显示错误提示

### 技术约束

1. **Flask 原生模板**：Jinja2，不引入 React/Vue
2. **CSS**：纯 CSS 或 Pico.css CDN（推荐），不加构建工具链
3. **Markdown 渲染**：marked.js CDN（<script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>）
4. **零构建步骤**：lightshield serve 启动即可用
5. **Session 复用**：页面登录使用已有 /api/login，Session cookie 浏览器自动携带
6. **不引入新 Python 依赖**（marked.js 是前端 CDN，不需要 pip install）

### 样式要求

- **安全工具风格**：深色主题（推荐 #1a1a2e 底色 + #e94560 强调色 或自行设计）
- **中文友好**：字体栈 "PingFang SC", "Microsoft YaHei", sans-serif
- **状态色彩**：completed=#2ecc71, failed=#e74c3c, partial=#f39c12, running=#3498db
- **风险等级色彩**：critical=#8e44ad, high=#e74c3c, medium=#f39c12, low=#f1c40f, info=#95a5a6
- **响应式**：桌面端和移动端均可使用

### pages.py 接口契约

```python
from flask import Blueprint, render_template, redirect, session

pages_bp = Blueprint("pages", __name__)  # 无 url_prefix

@pages_bp.route("/")
def index():
    """首页：已登录→仪表板，否则→登录页"""
    if "user" in session:
        return redirect("/dashboard")
    return render_template("login.html")

@pages_bp.route("/dashboard")
def dashboard():
    """仪表板：需登录，否则跳转首页"""
    if "user" not in session:
        return redirect("/")
    from lightshield.repository.base import get_repository
    try:
        repo = get_repository("sqlite", db_url="data/lightshield.db")
        history = repo.list_recent(limit=20)
    except Exception:
        history = []
    return render_template("dashboard.html", history=history, username=session.get("user", "?"))

@pages_bp.route("/report/<scan_id>")
def view_report(scan_id):
    """报告查看器：需登录"""
    if "user" not in session:
        return redirect("/")
    return render_template("report.html", scan_id=scan_id)
```

### app.py 修改

在 create_app() 中注册 pages 蓝图（添加到 api_bp 注册之后）：
```python
from lightshield.web.pages import pages_bp
app.register_blueprint(pages_bp)
```

### 合规约束
- R4：扫描面板的"确认所有权"复选框默认不勾选，勾选后才允许提交
- 无攻击代码，无 exploit/payload/attack 相关内容
- 所有中文文本正确显示

### 验收标准
1. lightshield serve 启动后浏览器访问 http://127.0.0.1:5000 看到登录页
2. 登录→仪表板→新建扫描→查看进度→查看报告 全流程可用
3. 未登录访问 /dashboard 自动跳转到登录页
4. 报告页面正确渲染 Markdown（表格、标题、代码块、颜色标签）
5. 扫描历史列表从 SQLite 加载并正确展示
6. 所有页面中文显示正常（UTF-8）
7. 现有 559 条测试不受影响（不修改 tests/ 目录下任何文件）

### 输出文件清单
1. lightshield/web/pages.py
2. lightshield/web/templates/base.html
3. lightshield/web/templates/login.html
4. lightshield/web/templates/dashboard.html
5. lightshield/web/templates/report.html
6. lightshield/web/static/style.css
7. 修改 lightshield/web/app.py（注册 pages_bp）
```

---

## 十五、v0.0.29 详细任务 + 启动提示词 🟢 当前任务

### 背景

v0.0.27 Flask API + v0.0.28 Web 仪表板已就绪。用户现在可以通过浏览器完成 scan → view report 全流程。
v0.0.29 需要在此基础上添加 **加固页面**——让用户在 Web 端查看加固建议、一键生成加固/回滚脚本。

### 依赖就绪

```
lightshield/web/pages.py          ✅ 页面路由（/、/dashboard、/report/<scan_id>）
lightshield/web/templates/         ✅ base.html + login + dashboard + report
lightshield/web/static/style.css   ✅ 深色安全工具主题
lightshield/core.py                ✅ generate_hardening(target, findings, recommendations, output_dir, os_platform)
lightshield/harden/linux_harden.py ✅ LinuxHardener（生成 .sh + rollback.sh）
lightshield/harden/win_harden.py   ✅ WinHardener（生成 .ps1 + rollback.ps1）
lightshield/rules/engine.py        ✅ recommend_hardening(findings) → list[dict]
lightshield/web/routes.py          ✅ API 端点（/api/scan、/api/report）
```

### 核心需求

1. **加固建议面板** — 扫描完成后展示加固建议列表（从 `RuleEngine.recommend_hardening()` 获取）
2. **一键生成脚本** — 选择操作系统 → 调用 `core.generate_hardening()` → 下载加固+回滚脚本
3. **Web R4 所有权确认** — 加固脚本生成前再次确认（Web 表单 + Session 记录）
4. **CSRF 防护** — 为所有 POST 端点添加 CSRF token 校验

### 文件计划

**新建：**
1. `lightshield/web/csrf.py` — CSRF 保护模块（token 生成/校验/装饰器）
2. `lightshield/web/templates/harden.html` — 加固建议页面

**修改：**
3. `lightshield/web/pages.py` — 新增 `/harden/<scan_id>` 路由
4. `lightshield/web/app.py` — CSRF `before_request` 钩子 + 注入 `csrf_token()` 到模板上下文
5. `lightshield/web/templates/dashboard.html` — 扫描完成/历史列表添加"加固"按钮
6. `lightshield/web/templates/report.html` — 报告底部添加"加固建议"操作入口
7. `lightshield/web/static/style.css` — 加固页面样式
8. `lightshield/web/templates/base.html` — 所有 POST 表单添加 CSRF hidden input

### 页面设计

#### 加固建议页面 (`GET /harden/<scan_id>`)

```
┌──────────────────────────────────────────────────────────┐
│  LightShield 轻盾                    [admin] [退出]       │
│  ← 返回报告                                                 │
├──────────────────────────────────────────────────────────┤
│  加固操作建议                                               │
│  扫描: LS-20260614-...  目标: 192.168.1.1                  │
│                                                          │
│  ┌─ 加固建议列表 ──────────────────────────────────────┐  │
│  │  #  严重度  操作          目标        原因           │  │
│  │  1  HIGH    关闭高危端口   23/telnet   Telnet 明文传输 │  │
│  │  2  MEDIUM  禁用不必要服务 旧式 telnet  无需远程管理    │  │
│  │  3  HIGH    升级老旧组件   OpenSSH     CVE-2023-38408 │  │
│  │  ...                                                │  │
│  └─────────────────────────────────────────────────────┘  │
│                                                          │
│  ┌─ 生成加固脚本 ──────────────────────────────────────┐  │
│  │  目标操作系统: [Linux ▾]                              │  │
│  │  ☐ 我确认拥有目标所有权并授权执行加固操作 （R4）       │  │
│  │  ⚠️ 加固脚本仅生成不自动执行，请审阅后手动运行         │  │
│  │  [生成加固脚本] [生成回滚脚本]                         │  │
│  └─────────────────────────────────────────────────────┘  │
│                                                          │
│  ┌─ 生成结果 ─────────────────────────────────────────┐  │
│  │  ✅ 加固脚本已生成                                    │  │
│  │  加固脚本: harden-20260614-xxx.sh (3.2 KB)            │  │
│  │  回滚脚本: rollback-20260614-xxx.sh (1.8 KB)          │  │
│  │  [下载加固脚本] [下载回滚脚本]                         │  │
│  └─────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────┘
```

### CSRF 防护设计

```python
# lightshield/web/csrf.py

import secrets
from functools import wraps
from flask import session, request, jsonify, current_app

def generate_csrf_token():
    """生成 CSRF token 并存入 session。"""
    if "_csrf_token" not in session:
        session["_csrf_token"] = secrets.token_hex(32)
    return session["_csrf_token"]

def validate_csrf():
    """校验请求中的 CSRF token。"""
    token = request.headers.get("X-CSRF-Token") or request.form.get("_csrf_token")
    if not token or token != session.get("_csrf_token"):
        return False
    return True

def csrf_protect(f):
    """装饰器：为 POST/PUT/DELETE 请求校验 CSRF token。"""
    @wraps(f)
    def decorated(*args, **kwargs):
        if request.method in ("POST", "PUT", "DELETE", "PATCH"):
            if not validate_csrf():
                return jsonify({"error": True, "message": "CSRF 校验失败，请刷新页面后重试", "code": 403}), 403
        return f(*args, **kwargs)
    return decorated
```

**app.py 集成：**
- `before_request` 钩子：对 POST/PUT/DELETE API 请求校验 CSRF（AJAX 请求通过 `X-CSRF-Token` header）
- 模板全局注入：`@app.context_processor` 注入 `csrf_token()` 函数，所有模板可用 `{{ csrf_token() }}`
- 页面表单：所有 `<form method="POST">` 添加 `<input type="hidden" name="_csrf_token" value="{{ csrf_token() }}">`

### pages.py 新增路由

```python
@pages_bp.route("/harden/<scan_id>")
def harden_page(scan_id: str):
    """加固建议页面：需登录"""
    if "user" not in session:
        return redirect(url_for("pages.index"))

    from lightshield.repository.base import get_repository

    config = current_app.config.get("LIGHTSHIELD_CONFIG")
    db_url = getattr(config, "db_url", "") or "data/lightshield.db"

    try:
        repo = get_repository("sqlite", db_url=db_url)
        scan_data = repo.get(scan_id)
    except Exception:
        scan_data = None

    if scan_data is None:
        return render_template("harden.html", scan_id=scan_id, error="扫描记录不存在", show_nav=True, username=session.get("user", "?"))

    raw = scan_data.get("raw_result", scan_data)
    findings_data = raw.get("findings", [])

    # 调用规则引擎获取加固建议（基于扫描结果中的 findings）
    from lightshield.rules.engine import RuleEngine
    from lightshield.adapters.base import VulnFinding
    from lightshield.utils.constants import RiskLevel

    findings = []
    for f in findings_data:
        try:
            severity = RiskLevel(f.get("severity", "info"))
        except ValueError:
            severity = RiskLevel.INFO
        findings.append(VulnFinding(
            vuln_type=f.get("vuln_type", "unknown"),
            severity=severity,
            title=f.get("title", ""),
            description=f.get("description", ""),
            remediation=f.get("remediation", ""),
            port=f.get("port"),
            cve_id=f.get("cve_id"),
            cvss_score=f.get("cvss_score"),
            evidence=f.get("evidence"),
        ))

    engine = RuleEngine()
    engine.load_rules()
    recommendations = engine.recommend_hardening(findings)

    return render_template(
        "harden.html",
        scan_id=scan_id,
        scan_data=scan_data,
        recommendations=recommendations,
        findings_count=len(findings),
        show_nav=True,
        username=session.get("user", "?"),
    )
```

### API 端点需求（新增或修改）

你需要在 `lightshield/web/routes.py` 中新增一个 API 端点：

```python
# POST /api/harden/<scan_id> — 生成加固脚本（需登录 + CSRF）
@api_bp.route("/harden/<scan_id>", methods=["POST"])
@login_required
def api_generate_harden(scan_id: str):
    """生成加固和回滚脚本，返回下载链接。"""
    data = request.get_json(silent=True) or {}
    os_platform = data.get("os_platform", "linux")
    if os_platform not in ("linux", "windows"):
        return jsonify({"error": True, "message": "不支持的操作系统，请选择 linux 或 windows", "code": 400}), 400

    core = current_app.config["LIGHTSHIELD_CORE"]
    config = current_app.config["LIGHTSHIELD_CONFIG"]

    # 从仓库加载扫描数据，重建 findings
    from lightshield.repository.base import get_repository
    db_url = getattr(config, "db_url", "") or "data/lightshield.db"
    repo = get_repository("sqlite", db_url=db_url)
    scan_data = repo.get(scan_id)
    if scan_data is None:
        return jsonify({"error": True, "message": f"扫描记录不存在: {scan_id}", "code": 404}), 404

    raw = scan_data.get("raw_result", scan_data)
    findings_data = raw.get("findings", [])

    from lightshield.adapters.base import VulnFinding
    from lightshield.utils.constants import RiskLevel

    findings = []
    for f in findings_data:
        try:
            severity = RiskLevel(f.get("severity", "info"))
        except ValueError:
            severity = RiskLevel.INFO
        findings.append(VulnFinding(
            vuln_type=f.get("vuln_type", "unknown"),
            severity=severity,
            title=f.get("title", ""),
            description=f.get("description", ""),
            remediation=f.get("remediation", ""),
            port=f.get("port"),
            cve_id=f.get("cve_id"),
            cvss_score=f.get("cvss_score"),
            evidence=f.get("evidence"),
        ))

    # 获取加固建议
    from lightshield.rules.engine import RuleEngine
    engine = RuleEngine()
    engine.load_rules()
    recommendations = engine.recommend_hardening(findings)

    if not recommendations:
        return jsonify({"error": True, "message": "未发现需要加固的风险项", "code": 200, "generated": False}), 200

    # 生成加固脚本
    try:
        result = core.generate_hardening(
            scan_data.get("target", "unknown"),
            findings=findings,
            recommendations=recommendations,
            output_dir=config.report_output_dir,
            os_platform=os_platform,
        )
    except Exception as exc:
        return jsonify({"error": True, "message": f"脚本生成失败：{exc}", "code": 500}), 500

    return jsonify({
        "success": True,
        "generated": True,
        "action_count": result.action_count,
        "script_path": result.script_path,
        "rollback_path": result.rollback_path,
        "status": result.status.value if hasattr(result.status, "value") else str(result.status),
        "message": f"已生成 {result.action_count} 条加固操作",
    }), 200
```

### 合规约束

- **R4**：加固脚本生成前必须再次确认所有权（Web 表单复选框 + Session 记录确认时间）
- **CSRF**：所有 POST 端点（/api/scan、/api/harden/<id>）必须校验 CSRF token
- 加固脚本**仅生成不执行**——与 CLI harden 命令行为一致
- 下载的脚本包含 R4 所有权确认交互门（脚本内 `read -r -p` / `Read-Host`）
- 前端提示："请审阅脚本后手动执行，LightShield 不会自动运行加固命令"

### 验收标准

1. 从报告页面点击"加固建议"→ 进入 `/harden/<scan_id>` 页面
2. 加固建议列表正确展示（行动、目标、严重度、原因）
3. 选择操作系统 + 确认所有权 → 点击生成 → 获取脚本路径
4. CSRF token 在所有 POST 请求中校验（缺少 token → 403）
5. CSRF token 通过模板 `{{ csrf_token() }}` 和 AJAX header `X-CSRF-Token` 两种方式传递
6. 所有页面（login/dashboard/report/harden）的 POST 表单携带 CSRF hidden input
7. 未登录访问 `/harden/<scan_id>` → 重定向到登录页
8. `ruff check lightshield/web/` 零违规
9. `mypy lightshield/web/` 零错误
10. 现有 566 条测试全量通过

### 启动提示词（直接复制到 Codex）

```
你是 LightShield 项目的高级开发工程师，使用 GPT-5.5 模型。

## 项目背景
LightShield（轻盾）是开源轻量化安全自检 + 防御加固工具，Python 3.10+。
路径：E:/Github Project/LightShield/

## 任务：实现加固页面 + CSRF 防护（v0.0.29）

### 前置条件
v0.0.27 Flask API + v0.0.28 Web 仪表板已就绪。用户可以通过浏览器完成 scan → view report 全流程。

现有文件（你可参考/修改）：
  lightshield/web/app.py            → create_app(config)，已注册 api_bp + pages_bp
  lightshield/web/routes.py         → API 端点（/api/scan、/api/report/<id>、/api/scan/<id>）
  lightshield/web/pages.py          → 页面路由（/、/dashboard、/report/<scan_id>）
  lightshield/web/auth.py           → Session 鉴权
  lightshield/web/templates/         → base.html + login.html + dashboard.html + report.html
  lightshield/web/static/style.css   → 深色安全工具主题（673行）
  lightshield/core.py                → generate_hardening(target, findings, recommendations, output_dir, os_platform)
  lightshield/harden/linux_harden.py → LinuxHardener（生成 .sh + rollback.sh）
  lightshield/harden/win_harden.py   → WinHardener（生成 .ps1 + rollback.ps1）
  lightshield/rules/engine.py        → RuleEngine.recommend_hardening(findings) → list[dict]

### 核心需求

1. **加固建议面板** — 扫描完成后展示加固建议列表（从 RuleEngine 获取）
2. **一键生成脚本** — 选择操作系统 → 调用 core.generate_hardening() → 返回脚本路径
3. **Web R4 所有权确认** — 加固生成前再次确认（复选框）
4. **CSRF 防护** — 所有 POST 端点添加 CSRF token 校验

### 你要创建/修改的文件

**新建：**
1. lightshield/web/csrf.py — CSRF 保护模块（token 生成/校验/装饰器）
2. lightshield/web/templates/harden.html — 加固建议页面

**修改：**
3. lightshield/web/routes.py — 新增 POST /api/harden/<scan_id> 端点
4. lightshield/web/pages.py — 新增 GET /harden/<scan_id> 路由
5. lightshield/web/app.py — CSRF before_request 钩子 + context_processor
6. lightshield/web/templates/dashboard.html — 扫描完成/历史列表添加"加固"按钮
7. lightshield/web/templates/report.html — 报告底部添加"加固建议"入口
8. lightshield/web/templates/base.html — POST 表单添加 CSRF hidden input
9. lightshield/web/static/style.css — 加固页面样式

### CSRF 防护设计

csrf.py 接口契约：
```python
import secrets
from functools import wraps
from flask import session, request, jsonify

def generate_csrf_token() -> str:
    """生成 CSRF token 并存入 session（每个 session 一个 token）。"""

def validate_csrf() -> bool:
    """校验请求中的 CSRF token（支持 X-CSRF-Token header 和 _csrf_token form 字段）。"""

def csrf_protect(f):
    """装饰器：POST/PUT/DELETE/PATCH 请求校验 CSRF token，失败返回 403 JSON。"""
```

app.py 集成：
- `@app.before_request`：对 `/api/` 路径的 POST/PUT/DELETE 请求调用 `validate_csrf()`，失败返回 403 JSON
- `@app.context_processor`：注入 `csrf_token` 函数，模板中 `{{ csrf_token() }}` 可用

base.html 修改：
- 全局 JS 逻辑：读取 CSRF token 注入到所有 fetch 请求的 `X-CSRF-Token` header
- 所有 `<form method="POST">` 添加 hidden input：`<input type="hidden" name="_csrf_token" value="{{ csrf_token() }}">`

CSRF 豁免（公开端点不校验）：
- POST /api/login
- POST /api/logout
- GET 请求（所有）

### POST /api/harden/<scan_id> 端点设计

请求体：
```json
{
    "os_platform": "linux"  // "linux" 或 "windows"
}
```

响应 200（生成成功）：
```json
{
    "success": true,
    "generated": true,
    "action_count": 3,
    "script_path": "./reports/harden-20260614-xxx.sh",
    "rollback_path": "./reports/rollback-20260614-xxx.sh",
    "status": "generated",
    "message": "已生成 3 条加固操作"
}
```

响应 200（无需加固）：
```json
{
    "error": true,
    "message": "未发现需要加固的风险项",
    "code": 200,
    "generated": false
}
```

### 加固页面 (`GET /harden/<scan_id>`) 功能要求

1. 从仓库加载扫描数据 → 重建 VulnFinding 列表 → 调用 RuleEngine.recommend_hardening()
2. 展示加固建议列表（表格：序号、严重度彩色标签、操作、目标、原因）
3. 操作系统选择下拉框：Linux / Windows
4. R4 所有权确认复选框（未勾选时"生成加固脚本"按钮禁用）
5. "生成加固脚本"按钮 → AJAX POST /api/harden/<scan_id>（携带 CSRF token）
6. 生成结果显示：脚本路径、操作数量、"请审阅后手动执行"提示
7. 空建议时显示"目标当前状态良好，无需加固"

### dashboard.html 修改

- 扫描完成后（status=completed/partial）：结果区增加"加固建议"按钮 → 跳转 `/harden/<task_id>`
- 历史记录表：每行增加"加固"操作链接 → `/harden/<scan_id>`

### report.html 修改

- 报告底部（"四、加固操作建议"区域后）增加操作按钮："生成加固脚本" → 跳转 `/harden/<scan_id>`
- 如果报告已包含加固建议段（"四、加固操作建议"），按钮文案为"执行加固 →"

### 合规约束
- R4：加固生成前必须确认所有权（前端复选框 + 提示文字）
- 加固脚本仅生成不执行（与 CLI harden 行为一致）
- 生成的脚本包含 R4 所有权确认交互门（脚本本身有 read/Read-Host 确认）
- CSRF token 在登录前不生成（避免 session 固定攻击）
- 无攻击代码，无 exploit/payload/attack

### 验收标准
1. 从报告页点击"加固建议"→ 进入 /harden/<scan_id> 页面
2. 加固建议列表正确展示（行动、目标、严重度、原因）
3. 选择操作系统 + 确认所有权 → 点击生成 → 获取脚本路径 JSON
4. 未登录访问 /harden/<scan_id> → 重定向到登录页
5. POST 请求缺少 CSRF token → 403 JSON 错误
6. POST 请求携带正确 CSRF token → 正常处理
7. CSRF token 通过模板 {{ csrf_token() }} 和 AJAX X-CSRF-Token header 双通道
8. dashboard 和 report 页面有通往 harden 页面的入口
9. ruff check lightshield/web/ 零违规
10. mypy lightshield/web/ 零错误
11. 现有 566 条测试全量通过（不修改 tests/ 目录下任何文件）

### 输出文件清单
1. lightshield/web/csrf.py（新建）
2. lightshield/web/templates/harden.html（新建）
3. lightshield/web/routes.py（修改：+ POST /api/harden/<scan_id>）
4. lightshield/web/pages.py（修改：+ GET /harden/<scan_id>）
5. lightshield/web/app.py（修改：+ CSRF before_request + context_processor）
6. lightshield/web/templates/dashboard.html（修改：+ 加固按钮）
7. lightshield/web/templates/report.html（修改：+ 加固入口）
8. lightshield/web/templates/base.html（修改：+ CSRF hidden input + JS header 注入）
9. lightshield/web/static/style.css（修改：+ 加固页面样式）
```
