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

### v0.0.11-20（新任务）

| 版本 | 模块 | 状态 | Claude Code 验收 |
|:--:|------|:--:|:--:|
| **v0.0.11** | `cli.py` + `setup.py` | ✅ | 读码验证：R4 YES/NO确认(行164)、R2 validate(行69) |
| **v0.0.12** | `test_validator.py` | ✅ | 225 行 / 12 测试函数 |
| **v0.0.13** | `test_msf_adapter.py` | ✅ | 185 行 / 白名单+黑名单+注入防护+审计日志 |
| **v0.0.16** | 审查 `linux_harden.py` | ✅ | 审查报告已产出（见 `docs/review-v016-codex.md`） |

---

### Codex 全任务完成统计

```
v0.0.03  validator.py           ✅  R2 防线
v0.0.06  web_vuln_scanner.py    ✅  SQL注入/XSS检测
v0.0.08  msf_adapter.py         ✅  R5 防线
v0.0.11  cli.py + setup.py      ✅  R4 防线
v0.0.12  test_validator.py      ✅  225行/12函数
v0.0.13  test_msf_adapter.py    ✅  185行/全覆盖
v0.0.16  审查 linux_harden.py   ✅  10 issues / 5 fixed (B1/B2/H3/M1/L1)
──────────────────────────────────────
         7/7 完成，0 个待执行 ✅
```

> 当前状态：**全部任务完成，零剩余。** 等待 v0.3.0 新任务分配。
> 审查报告：`docs/review-v016-codex.md`

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
