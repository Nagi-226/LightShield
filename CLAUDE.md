# CLAUDE.md — LightShield（轻盾）

> **用途**：给 Claude Code 的项目全局指令，每次会话自动加载。
> **维护**：架构变更、依赖路径变化、合规规则调整时同步更新。
> **集群模式**：本项目开启了多 Agent 开发集群，详见 `.cluster/CLUSTER.md`。
> **护栏体系**：基于 Nagi Dev Guardrails v3.0 的五层防御架构，详见 `.guardrails/`。
> **上次会话**：2026-06-14 19:00 — v0.3.5 CVE 105 条交付，阶段二 2/4 完成。
>   - 质量基线：**580 tests** / 0 fail / ruff + mypy 全零违规
>   - 阶段一 ✅✅✅ 安全加固 | 阶段二 ✅✅⬜⬜ 能力扩展 | 阶段三 ⬜⬜⬜ 自动化铺路
>   - 明天启动：v0.3.6 Nuclei 适配器（CC）+ v0.3.7 Web UI 增强（Codex）可并行
> **进度追踪**：`.guardrails/PROGRESS.md`

---

## 零-A、开发护栏体系（强制）

本项目集成了 Nagi ai-dev-guardrails 的五层防御架构。**所有 Agent 产出必须通过质量门禁才能合入**。

### 护栏文件索引

| 文件 | 内容 | 来源 |
|------|------|------|
| `.guardrails/PROJECT_CONTRACT.md` | 项目契约：范围/架构/红线/里程碑 | Nagi M1+M2 |
| `.guardrails/QUALITY_GATES.md` | CI/CD 五道门禁 + 审计模板 | Nagi M6+M8+M9 |
| `.guardrails/audit-log.md` | 门禁触发审计日志 | 跨层审计 |
| `.cluster/COORDINATION.md` | 多 Agent 冲突预防 + 知识缺口防护 | Nagi M5+M7 |
| `.githooks/pre-commit` | Gate A 自动合规扫描脚本 | 自动化执行 |

### 五大门禁（不可跳过）

```
Gate A: 合规扫描  → Pre-commit Hook 自动执行关键字/MSF/IP检查
Gate B: 范围忠实度 → SF-L1~L4 检测 + Anti-Grinding 表
Gate C: 质量审计   → M8 五维扫描（架构/安全/性能/质量/测试）
Gate D: 冲突检测   → 多 Agent 产出兼容性 + Graphify 一致性
Gate E: 回归验证   → QoderWork VM 中 smoke test
```

### 五大铁律（Nagi Five Iron Principles）

1. **不盲从**：用户指令有技术错误 → 纠正后再开工
2. **不脑补**：需求模糊 → 问清楚再写，不自行假设
3. **实事求是**：能力边界外的工作 → 明确告知局限
4. **可落地**：所有代码可运行，无占位符/TODO桩
5. **确认再开工**：非微调任务先确认方案 → 再写代码

### 范围漂移阀值

| 指标 | 阀值 | 动作 |
|------|------|------|
| 累积新增 vs 原始范围 | >30% | 🟡 提醒 |
| 无审查的连续新增 | >3 | 🔴 暂停 |
| 架构模式改变 | 任何 | 🟠 暂停 + ADR |

---

## 零-B、开发集群模式（重要）

本项目配置了一个 **8 Agent 开发集群**，Claude Code 担任架构师+编排器角色。

### 集群成员

| Agent | 角色 | 非交互调用 |
|-------|------|-----------|
| **Claude Code** | 🏛️ 架构师 + 编排器 | —（自身） |
| **Codex** | 💎 高级开发工程师 | `codex exec "$(cat task.md)"` |
| **Reasonix** | 🔧 开发工程师（DeepSeek） | `reasonix run "$(cat task.md)"` |
| **CodeWhale** | 🔍 代码审查专员 | `codewhale exec "$(cat task.md)"` |
| **Hermes** | 🛠️ 工具链 + 基础设施 | `hermes -z "$(cat task.md)"` |
| **CodeBuddy** | 💻 IDE 大规模开发 | 需人工在 IDE 中操作 |
| **Qoder** | 🖥️ IDE 精准修改 + AI补全 | 需人工在 IDE 中操作 |
| **QoderWork** | 🏭 后台任务 + VM 隔离 | 后台常驻服务 |

### 编排规则

1. **Claude Code 不直接写实现代码** — 只做架构设计、接口定义、任务拆分、最终集成和合规审查
2. **每个独立模块通过任务文件下发** — 任务文件在 `.cluster/tasks/pending/` 中，自包含上下文
3. **并行执行 + 集中集成** — 各 Agent 并行产出，Claude Code 审查后合并
4. **双审机制** — CodeWhale + Claude Code 双重审查所有代码

### 任务文件模板规范

每个任务文件必须包含：
- 项目上下文（简短）
- ⚠️ 合规约束片段（R1-R6）
- 接口契约（明确的输入/输出/异常）
- 代码要求（注释、异常处理、类型标注）

详见 `.cluster/CLUSTER.md` 和 `.cluster/tasks/pending/` 下的任务文件。

---

## 一、项目身份证

| 属性 | 值 |
|------|-----|
| **项目名** | LightShield（轻盾） |
| **一句话定位** | 面向初创企业 & 个人站长的开源轻量化安全自检 + 防御加固工具 |
| **当前阶段** | v0.1.0 — MVP 已完成（14 模块），v0.2.0 开发中 |
| **开源协议** | MIT |
| **主语言** | Python 3.10+ |
| **辅助语言** | Shell（部署脚本）、PowerShell（Windows 适配） |
| **项目总览文档** | `PROJECT_OVERVIEW.md` |
| **AI 提示词全集** | `LightShield_AI_Prompt_全集.txt` |

---

## 二、外部资源

LightShield 的技术底座是 **Nmap + 自研 Python 安全脚本 + Metasploit auxiliary/scanner 子集**（详见第三章方案 B）。以下两个外部项目以不同方式服务于开发：

### 2.1 hackingtool — 设计参考源码（非依赖）

> ⚠️ **定位澄清**（2026-06-09）：hackingtool **不是** LightShield 的运行时依赖。它不进入部署包、不被 import、不被调用。它的唯一角色是**设计参考**——为自研 Python 安全脚本提供检测逻辑的思路参照。

- **路径**：`E:\Open-Source Projects by others\hackingtool`
- **来源**：Z4nzu/hackingtool v2.0.0
- **与 LightShield 的关系**：我们**吸取思路，不引入代码**。自研脚本从零独立实现，hackingtool 仅用于理解"同类工具如何检测某项漏洞"。
- **方案 A（全量引入）已被否决**：原因见 `PROJECT_OVERVIEW.md` 第三章（75%+ 攻击模块、合规风险、5-10GB 膨胀）。

**可作为设计参考的模块（思路借鉴，非代码复用）**：

| 文件 | 参考内容 | 对应的自研模块 |
|------|------|------|
| `information_gathering.py` | 端口扫描、whois、DNS 枚举的思路 | `lightshield/scanners/port_scanner.py` |
| `forensics.py` | 日志分析的字段和处理流程 | 安全审计（未来 Phase） |
| `cloud_security.py` | 云配置检查项清单 | 云环境加固（未来 Phase） |
| `sql_injection.py` | SQL 注入检测 payload 构造逻辑 | `lightshield/scanners/web_vuln_scanner.py` |
| `xss_attack.py` | XSS 检测 payload 和匹配模式 | `lightshield/scanners/web_vuln_scanner.py` |
| `web_attack.py` | 目录枚举字典、CMS 指纹库 | `lightshield/scanners/web_vuln_scanner.py` |
| `wordlist_generator.py` | 弱口令字典生成规则 | `lightshield/scanners/weak_password.py` |

**严格禁止引入（连参考价值都没有，纯攻击工具）**：
`ddos.py`, `payload_creator.py`, `payload_injection.py`, `post_exploitation.py`,
`remote_administration.py`, `exploit_frameworks.py`, `phishing_attack.py`,
`wireless_attack.py`, `wifi_jamming.py`, `reverse_engineering.py`,
`steganography.py`, `anonsurf.py`, `homograph_attacks.py`, `socialmedia.py`,
`android_attack.py`, `mobile_security.py`

### 2.2 Metasploit Framework — 运行时依赖（通过 MSF Adapter 调用）

> ✅ **定位明确**：MSF 是 LightShield 架构中正式的一层（`lightshield/adapters/msf_adapter.py`）。部署包中包含 MSF 的 auxiliary/scanner 子集，通过白名单严格控制。
- **路径**：`E:\Open-Source Projects by others\metasploit-framework`
- **来源**：rapid7/metasploit-framework
- **结构**：Ruby 项目，核心模块在 `modules/` 目录下按类型分目录
- **在 LightShield 中的角色**：**仅调用 auxiliary/scanner 子集**，通过白名单机制筛选

**允许调用的 MSF 模块路径前缀（白名单）**：
```
auxiliary/scanner/portscan/
auxiliary/scanner/discovery/
auxiliary/scanner/http/
auxiliary/scanner/smb/
auxiliary/scanner/ssh/
auxiliary/scanner/mysql/
auxiliary/scanner/ftp/
auxiliary/scanner/ssl/
auxiliary/scanner/dns/
```

**严格禁止的 MSF 模块路径前缀（黑名单）**：
```
exploit/
payload/
post/
evasion/
nops/
auxiliary/scanner/backdoor/
auxiliary/dos/
auxiliary/admin/
```

### 2.3 agency-agents（开发辅助 Agent 角色库）

- **路径**：`E:\Open-Source Projects by others\agency-agents`
- **来源**：msitarzewski/agency-agents
- **本质**：~150 个 AI Agent 人格定义文件（markdown），供 Claude Code 等工具加载为专业角色
- **在 LightShield 中的角色**：**开发流程辅助**，不作为产品技术集成
- **评估结论**：✅ 适合开发流程

**可直接利用的关键 Agent**：

| Agent | 在 LightShield 开发中的用途 |
|-------|---------------------------|
| 🔒 Security Engineer | 合规红线审计（Phase 10）、安全架构审查、OWASP 检测逻辑验证 |
| 🎯 Threat Detection Engineer | 漏洞特征规则库设计、检测引擎逻辑验证 |
| 🏛️ Software Architect | 适配器模式架构落地、ADR 决策记录、分层设计审查 |
| 👁️ Code Reviewer | 每个 Phase 完成后的代码质量审查 |
| 🚀 DevOps Automator | 一键部署脚本设计与 CI/CD 流水线 |
| 📚 Technical Writer | 开源 README/INSTALL/USAGE/FAQ 文档撰写 |
| 🗄️ Database Optimizer | 未来重盾版本的 PostgreSQL schema 设计 |

**使用方式**：开发对应模块时，通过 Claude Code 的 Agent 工具激活对应角色进行专项审查。

### 2.4 MetaGPT（已评估，不采用）

- **路径**：`E:\Open-Source Projects by others\MetaGPT`
- **来源**：geekan/MetaGPT
- **本质**：LLM 多 Agent 框架，模拟软件公司 SOP，从一句话需求自动生成完整项目代码
- **评估结论**：❌ 不适合 LightShield

**不采用理由**：

1. **缺乏网安领域特异性**：MetaGPT 生成通用软件，不理解 MSF/hackingtool 的合规裁剪逻辑
2. **合规风险不可控**：LightShield 的 6 条合规红线（R1-R6）需要在每行代码中体现，自动生成无法保证
3. **代码质量不可控**：生成的代码可能引入攻击向逻辑、不安全依赖或不合理的架构
4. **领域错配**：更适合标准 CRUD/Web 应用，不适配安全工具的精细化需求
5. **依赖膨胀**：会引入 LLM 调用链（openai/gpt-4 等）、不必要的三方包，违背"轻盾 ≤500MB"的约束

### 2.5 开发 Agent 角色库（来自 agency-agents）

已从 `E:\Open-Source Projects by others\agency-agents` 引入 7 个专业 Agent 到 `.claude/agents/`，供开发各阶段调用。

| Agent | 文件 | 在 LightShield 中的使用场景 |
|-------|------|---------------------------|
| 🔒 Security Engineer | `security-engineer.md` | Phase 10 合规审计、R1-R6 红线校验、OWASP 检测逻辑审查 |
| 🎯 Threat Detection Engineer | `threat-detection-engineer.md` | 漏洞特征规则库设计、检测引擎逻辑验证、风险分级标准 |
| 🏛️ Software Architect | `software-architect.md` | 适配器模式落地、ADR 架构决策记录、分层设计审查 |
| 👁️ Code Reviewer | `code-reviewer.md` | 每个 Phase 完成后的代码质量审查 |
| 🏗️ Backend Architect | `backend-architect.md` | Python 核心调度层设计、API 设计、模块解耦 |
| 🚀 DevOps Automator | `devops-automator.md` | Phase 8 部署脚本、CI/CD 流水线、环境适配 |
| 📚 Technical Writer | `technical-writer.md` | README/INSTALL/USAGE/FAQ 开源文档撰写 |

**Agent 与开发 Phase 的对应关系**：

```
Phase 1  (骨架):   Backend Architect + Software Architect
Phase 2  (Nmap):   Backend Architect + Code Reviewer
Phase 3  (脚本):   Code Reviewer + Security Engineer（确保无攻击代码）
Phase 4  (MSF):    Security Engineer（白名单机制审查）
Phase 5  (规则):   Threat Detection Engineer + Security Engineer
Phase 6  (报告):   Technical Writer
Phase 7  (加固):   Security Engineer + DevOps Automator
Phase 8  (部署):   DevOps Automator
Phase 9  (界面):   Backend Architect + Code Reviewer
Phase 10 (审计):   Security Engineer + Threat Detection Engineer
全阶段文档:         Technical Writer
```

---

## 三、技术底座选型（已决策，不可回退）

```
❌ 方案A：全量引入 hackingtool（185+ 工具）
   否决原因：
   - 75%+ 模块为纯攻击向（DDoS/RAT/钓鱼/后渗透），需要大量剔除
   - 依赖链爆炸（Hashcat/John/Bettercap 等重型工具）
   - 与"轻盾"定位冲突，实际部署包 5-10GB
   - 合规风险高（源码含攻击代码，GitHub 有被举报先例）

✅ 方案B（当前选择）：Nmap + 独立安全脚本 + 精简版 Metasploit auxiliary/scanner 子集
   选择理由：
   - Nmap：网络扫描工业标准
   - 独立安全脚本：自研 Python 漏洞检测逻辑，轻量可控
   - Metasploit auxiliary/scanner 子集：仅引入扫描器模块，不引入 exploit/payload
   - 预计部署包 ≤ 500MB（含依赖）
```

| 层级 | 技术 | 用途 |
|------|------|------|
| 核心调度 | Python 3.10+ | 主控逻辑、模块编排 |
| 网络扫描 | Nmap 7.x (python-nmap 封装) | 端口扫描、服务识别、OS 探测 |
| Web 扫描 | 自研 Python 脚本 | SQL 注入检测、XSS 检测、目录枚举 |
| MSF 扫描器 | Metasploit auxiliary/scanner 子集 | 补充扫描能力（SMB/SSH/MySQL 弱口令等） |
| 规则引擎 | JSON Schema | 漏洞特征库、加固策略匹配 |
| 报告输出 | Python Markdown 生成 | 中文报告 |
| Web 界面 | Flask + 原生 HTML/CSS | 轻量管理面板（v0.2.0+） |
| 桌面界面 | Tkinter | 跨平台客户端（v0.3.0+） |

---

## 四、架构分层

```
┌─────────────────────────────────────────────┐
│              交互层 (Interface)              │
│  Flask Web Panel / Tkinter GUI / CLI        │
│  - 仅允许输入自有 IP/域名                    │
│  - 前端拦截 IP 段、公网随机地址              │
├─────────────────────────────────────────────┤
│           核心调度层 (Orchestrator)           │
│  lightshield_core.py                        │
│  - 扫描任务调度、模块编排                     │
│  - 参数安全校验（双层拦截）                   │
│  - 日志记录 & 行为审计                        │
├─────────────────────────────────────────────┤
│           能力适配层 (Adapters)               │
│  ┌──────────┬──────────────┬──────────────┐ │
│  │Nmap适配器│ 自研脚本引擎  │ MSF扫描适配器 │ │
│  │端口/服务/│ SQL注入/XSS/ │ 补充弱口令/   │ │
│  │OS探测    │ 目录/组件漏洞 │ 服务扫描      │ │
│  └──────────┴──────────────┴──────────────┘ │
├─────────────────────────────────────────────┤
│           规则引擎层 (Rule Engine)            │
│  JSON 规则库 + 风险分级（高/中/低）           │
├─────────────────────────────────────────────┤
│           日志 & 报告层 (Reporting)           │
│  - 操作日志本地留存                           │
│  - Markdown/纯文本 中文报告                   │
└─────────────────────────────────────────────┘
```

核心设计模式：**适配器模式（Adapter Pattern）**。所有扫描能力通过 `BaseAdapter` 抽象基类统一接口，新增能力只需新增 Adapter，不修改核心调度逻辑。

---

## 五、合规红线（强制遵守）

> **这是原则，不是建议。任何违反的代码不得合入。**

| 编号 | 红线 | 实现方式 |
|:--:|------|------|
| R1 | 禁止对外主动攻击 | 仅调用扫描/检测能力，不调用任何 exploit/payload 模块 |
| R2 | 禁止批量扫描公网 IP 段 | 输入校验层：只接受单一 IP 或域名，拒绝 CIDR/网段/通配符 |
| R3 | 禁止远控/后门/木马 | 代码审查关键字：`bind_shell`、`reverse_shell`、`backdoor`、`trojan` |
| R4 | 仅允许自查自有资产 | 启动时弹窗确认"你拥有目标的所有权"，日志记录目标地址 |
| R5 | MSF 调用限制 | 仅允许 `auxiliary/scanner/` 路径下的模块，白名单机制 |
| R6 | 扫描频率限制 | 单目标扫描并发 ≤ 20，两次扫描间隔 ≥ 5 秒 |

---

## 六、目录结构规划

```
LightShield/
├── CLAUDE.md                     # ← 本文件（项目指令）
├── PROJECT_OVERVIEW.md           # 项目总览（给人读）
├── LightShield_AI_Prompt_全集.txt # 原始设计文档 + 分模块提示词
├── README.md                     # GitHub 开源首页（开发中）
├── LICENSE                       # 开源协议
│
├── lightshield/                  # 核心 Python 包
│   ├── __init__.py
│   ├── core.py                   # 主调度器
│   ├── config.py                 # 配置管理
│   │
│   ├── adapters/                 # 能力适配层
│   │   ├── __init__.py
│   │   ├── base.py               # BaseAdapter 抽象基类
│   │   ├── nmap_adapter.py       # Nmap 封装
│   │   ├── msf_adapter.py        # MSF scanner 安全调用封装
│   │   └── script_engine.py      # 自研检测脚本执行引擎
│   │
│   ├── scanners/                 # 自研扫描脚本
│   │   ├── __init__.py
│   │   ├── port_scanner.py       # 端口扫描（基于 nmap_adapter）
│   │   ├── web_vuln_scanner.py   # Web 漏洞检测
│   │   ├── weak_password.py      # 弱口令检测
│   │   └── component_checker.py  # 组件版本 & CVE 匹配
│   │
│   ├── rules/                    # 规则引擎 + 规则库
│   │   ├── __init__.py
│   │   ├── engine.py             # 规则引擎核心
│   │   ├── vuln_rules.json       # 漏洞特征规则库
│   │   └── harden_rules.json     # 加固策略规则库
│   │
│   ├── harden/                   # 自动加固模块
│   │   ├── __init__.py
│   │   ├── linux_harden.py       # Linux 加固
│   │   ├── win_harden.py         # Windows 加固
│   │   └── templates/            # 加固脚本模板
│   │       ├── linux_firewall.sh
│   │       ├── linux_service.sh
│   │       └── win_firewall.ps1
│   │
│   ├── report/                   # 报告生成
│   │   ├── __init__.py
│   │   └── reporter.py           # Markdown/文本 中文报告
│   │
│   └── utils/                    # 工具函数
│       ├── __init__.py
│       ├── validator.py          # 输入校验（IP/域名合法性 + 权限拦截）
│       ├── logger.py             # 日志记录
│       └── constants.py          # 常量和枚举
│
├── scripts/                      # 独立工具脚本
│   ├── deploy_linux.sh           # Linux 一键部署
│   ├── deploy_win.ps1            # Windows 环境适配
│   └── rule_importer.py          # 外部规则批量导入
│
├── tests/                        # 测试
│   ├── test_validator.py
│   ├── test_nmap_adapter.py
│   └── test_rules_engine.py
│
├── docs/                         # 用户文档
│   ├── INSTALL.md
│   ├── USAGE.md
│   └── FAQ.md
│
├── requirements.txt              # Python 依赖
└── .gitignore
```

---

## 七、开发路线图

### 版本里程碑

| 版本 | 里程碑 | 核心交付 |
|------|--------|---------|
| v0.1.0 | MVP | 资产扫描 + 漏洞检测 + 中文报告（CLI） |
| v0.2.0 | Web 面板 | Flask 管理界面 + 在线报告预览 |
| v0.3.0 | 桌面客户端 | Tkinter 跨平台 GUI + 一键打包 |
| v0.4.0 | 自动加固 | Linux/Windows 加固脚本 + 复检验证 |
| v1.0.0 | 正式版 | 完整功能 + 开源文档 + 合规审计报告 |
| v2.0.0 | 重盾 | 适配器扩展 + 远程规则订阅 + 企业特性 |

### 开发 Phase（严格按顺序）

```
Phase 1:  项目骨架          → core.py, config.py, validator.py, logger.py, base.py
Phase 2:  Nmap 适配器        → nmap_adapter.py → port_scanner.py
Phase 3:  自研检测脚本       → web_vuln_scanner.py, weak_password.py, component_checker.py
Phase 4:  MSF 扫描适配器     → msf_adapter.py（白名单机制）
Phase 5:  规则引擎           → engine.py + vuln_rules.json + harden_rules.json
Phase 6:  报告生成           → reporter.py
Phase 7:  自动加固           → linux_harden.py + 脚本模板
Phase 8:  部署脚本           → deploy_linux.sh, deploy_win.ps1
Phase 9:  界面（v0.2.0+）   → Flask Web Panel, Tkinter GUI
Phase 10: 合规审计           → 全量代码审查
```

---

## 八、关键开发规范

1. **所有代码中文注释**，方便非专业用户理解
2. **异常捕获完善**：网络超时、权限不足、工具调用失败等场景友好提示
3. **输入校验双层防护**：前端拦截 + 后端 validate_target() 校验，禁止批量扫描公网 IP 段
4. **操作日志本地留存**：记录每次扫描的目标地址、执行时间、操作类型
5. **模块解耦**：每个模块独立，通过 Adapter 抽象接口交互，方便后续替换和扩展
6. **适配器模式统一接口**：所有扫描能力通过 `BaseAdapter` 子类实现，核心调度器不直接依赖具体工具

---

## 九、可扩展性（为"重盾"预留）

| 扩展点 | 当前轻盾做法 (v0.2.0) | 未来重盾方向 | 切换机制 | 预留状态 |
|--------|------------------------|-------------|:--:|:--:|
| 扫描引擎 | Nmap + 自研脚本 | + OpenVAS / Nuclei / ZAP | 新增 Adapter 即可 | ✅ BaseAdapter 抽象 |
| MSF 集成度 | 仅 auxiliary/scanner | 可扩展至 auxiliary/server/ | 白名单配置文件控制 | ✅ 常量定义已就绪 |
| 规则引擎 | 本地 JSON | + 远程规则订阅 / STIX/TAXII | 数据源接口抽象 | ✅ engine.py 可插拔 |
| 报告格式 | Markdown/纯文本 | + PDF/HTML/JSON API | 报告渲染器可插拔 | ✅ reporter 可扩展 |
| 用户界面 | CLI | Web → 桌面 → SaaS 多租户 | 前后端分离 | ✅ CLI 与 core 解耦 |
| 数据存储 | JSON 文件 | + SQLite → PostgreSQL | Repository 模式 | ✅ `lightshield/repository/` |
| 任务调度 | 同步 `run_scan()` | + 线程池 → Celery 队列 | `submit_scan()` 接口 | ✅ `core.submit_scan()` |
| 缓存 & 限流 | R6 本地常量 | + Redis 缓存 + API 限流 | config 扩展字段 | ✅ config 预留字段 |
| 鉴权 | 无（单用户） | Session → JWT + OAuth2 | config.auth_enabled | ✅ config 预留字段 |

---

## 十、术语表

| 术语 | 含义 |
|------|------|
| 轻盾 (LightShield) | 当前项目，轻量化防御自检工具 |
| 重盾 (HeavyShield) | 未来企业版，可替换扫描引擎的完整方案 |
| 适配器 (Adapter) | 对第三方工具的统一封装层，继承 BaseAdapter |
| 规则引擎 (Rule Engine) | 漏洞特征匹配 + 风险分级 + 加固策略映射核心 |
| 合规红线 | 不可逾越的代码安全边界（第五章 6 条） |
| MSF | Metasploit Framework 缩写 |

## graphify

This project has a knowledge graph at graphify-out/ with god nodes, community structure, and cross-file relationships.

Rules:
- For codebase questions, first run `graphify query "<question>"` when graphify-out/graph.json exists. Use `graphify path "<A>" "<B>"` for relationships and `graphify explain "<concept>"` for focused concepts. These return a scoped subgraph, usually much smaller than GRAPH_REPORT.md or raw grep output.
- If graphify-out/wiki/index.md exists, use it for broad navigation instead of raw source browsing.
- Read graphify-out/GRAPH_REPORT.md only for broad architecture review or when query/path/explain do not surface enough context.
- After modifying code, run `graphify update .` to keep the graph current (AST-only, no API cost).
