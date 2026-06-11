# LightShield 轻盾 — 项目总览

> **阅读对象**：AI Agent / 新加入开发者 / 项目协作者
> **目的**：5 分钟内建立完整项目认知，明确边界、架构、约束与可扩展路径
> **维护规则**：架构变更、技术选型调整、合规边界变化时需同步更新本文档

---

## 一、项目身份证

| 属性 | 值 |
|------|-----|
| **项目名** | LightShield（轻盾） |
| **一句话定位** | 面向初创企业 & 个人站长的开源轻量化安全自检 + 防御加固工具 |
| **当前阶段** | v0.1.0 — MVP 已完成（14 模块，8 Agent 集群协作），v0.2.0 开发中 |
| **开源协议** | MIT |
| **主语言** | Python 3.10+ |
| **辅助语言** | Shell（部署脚本）、PowerShell（Windows 适配） |
| **最新更新** | 2026-06-09 — 进度追踪见 `.guardrails/PROGRESS.md` |

---

## 二、为什么做这个

```
痛点：初创企业/个人站长买不起 Nessus/Qualys，
      又不具备手操 Metasploit 的技术能力，
      但他们的服务器每天都在被自动化扫描攻击。
```

**目标场景**：
- 用户租了一台阿里云/腾讯云轻量服务器，部署了 WordPress/Nginx/MySQL
- 他想知道：我开了哪些危险端口？有没有弱口令？Web 应用有 SQL 注入吗？
- LightShield 一键告诉他答案，并帮他自动加固

---

## 三、技术路线（已决策）

### 3.1 底座选型

```
❌ 方案A：全量引入 hackingtool（185+ 工具）
   否决原因：
   - 75%+ 模块为纯攻击向（DDoS/RAT/钓鱼/后渗透），需要大量剔除
   - 依赖链爆炸（Hashcat/John/Bettercap 等重型工具）
   - 与"轻盾"定位冲突，实际部署包 5-10GB
   - 合规风险高（源码含攻击代码，GitHub 有被举报先例）

✅ 方案B（当前选择）：Nmap + 独立安全脚本 + 精简版 Metasploit scanner
   选择理由：
   - Nmap：网络扫描工业标准，无需赘述
   - 独立安全脚本：自研 Python 漏洞检测逻辑，轻量可控
   - Metasploit auxiliary/scanner 子集：仅引入扫描器模块，不引入 exploit/payload
   - 预计部署包 ≤ 500MB（含依赖）
```

### 3.2 技术栈清单

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

## 四、架构分层设计

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
│  - OWASP Top 10 检测规则                     │
│  - CVE 组件版本匹配规则                       │
│  - 弱口令特征规则                             │
│  - 加固策略映射规则                           │
├─────────────────────────────────────────────┤
│           日志 & 报告层 (Reporting)           │
│  - 操作日志本地留存                           │
│  - Markdown/纯文本 中文报告                   │
│  - 加固记录 & 复检验证                        │
└─────────────────────────────────────────────┘
```

---

## 五、合规红线（AI Agent 必须遵守）

> **这是原则，不是建议。任何违反的代码不得合入。**

| 编号 | 红线 | 实现方式 |
|:--:|------|------|
| R1 | 禁止对外主动攻击 | 仅调用扫描/检测能力，不调用任何 exploit/payload 模块 |
| R2 | 禁止批量扫描公网 IP 段 | 输入校验层：只接受单一 IP 或域名，拒绝 CIDR/网段/通配符 |
| R3 | 禁止远控/后门/木马 | 代码审查关键字：`bind_shell`、`reverse_shell`、`backdoor`、`trojan` |
| R4 | 仅允许自查自有资产 | 启动时弹窗确认"你拥有目标的所有权"，日志记录目标地址 |
| R5 | MSF 调用限制 | 仅允许 `auxiliary/scanner/` 路径下的模块，白名单机制 |
| R6 | 扫描频率限制 | 单目标扫描并发 ≤ 20，两次扫描间隔 ≥ 5 秒 |

### R5 补充：MSF 模块白名单设计

```
# 仅允许这些路径前缀的模块被调用
ALLOWED_MSF_PREFIXES = [
    "auxiliary/scanner/portscan/",
    "auxiliary/scanner/discovery/",
    "auxiliary/scanner/http/",
    "auxiliary/scanner/smb/",
    "auxiliary/scanner/ssh/",
    "auxiliary/scanner/mysql/",
    "auxiliary/scanner/ftp/",
    "auxiliary/scanner/ssl/",
    "auxiliary/scanner/dns/",
]

# 严格禁止的路径（即使误触也会拦截）
BLOCKED_MSF_PREFIXES = [
    "exploit/",
    "payload/",
    "post/",
    "auxiliary/scanner/backdoor/",
    "auxiliary/dos/",
    "auxiliary/admin/",
]
```

---

## 六、MVP 功能范围（v0.1.0）✅ 已完成

> 原则：做少做精，不做大而全。**v0.1.0 已全部交付，共 14 个 Python 模块。**

| 优先级 | 模块名 | 实际产出 | 状态 |
|:--:|------|------|:--:|
| P0 | **资产扫描** | `nmap_adapter.py` + `port_scanner.py` — Nmap 封装 + 端口分析 | ✅ |
| P0 | **漏洞检测** | `web_vuln_scanner.py` + `weak_password.py` + `component_checker.py` — SQL注入/XSS/弱口令/CVE | ✅ |
| P0 | **中文报告** | `reporter.py` — Markdown + 纯文本双格式 | ✅ |
| P1 | **自动加固** | 规则已就绪（`harden_rules.json`），执行模块 v0.0.16-17 | ⏳ |
| P1 | **规则引擎** | `engine.py` + `vuln_rules.json` (14条) + `harden_rules.json` (6条) | ✅ |
| P2 | Web 面板 | Flask 轻量管理界面 | v0.2.0 |
| P2 | 桌面客户端 | Tkinter 跨平台 GUI | v0.3.0 |

---

## 七、目录结构规划

```
LightShield/
├── PROJECT_OVERVIEW.md          # ← 本文档（项目总览）
├── LightShield_AI_Prompt_全集.txt # 原始设计文档
├── README.md                    # GitHub 开源首页（开发中）
├── LICENSE                      # 开源协议
│
├── lightshield/                 # 核心 Python 包
│   ├── __init__.py
│   ├── core.py                  # 主调度器
│   ├── config.py                # 配置管理
│   │
│   ├── adapters/                # 能力适配层
│   │   ├── __init__.py
│   │   ├── nmap_adapter.py      # Nmap 封装
│   │   ├── msf_adapter.py       # MSF scanner 安全调用封装
│   │   └── script_engine.py     # 自研检测脚本执行引擎
│   │
│   ├── scanners/                # 自研扫描脚本
│   │   ├── __init__.py
│   │   ├── port_scanner.py      # 端口扫描（基于 nmap_adapter）
│   │   ├── web_vuln_scanner.py  # Web 漏洞检测
│   │   ├── weak_password.py     # 弱口令检测
│   │   └── component_checker.py # 组件版本 & CVE 匹配
│   │
│   ├── rules/                   # 规则引擎 + 规则库
│   │   ├── __init__.py
│   │   ├── engine.py            # 规则引擎核心
│   │   ├── vuln_rules.json      # 漏洞特征规则库
│   │   └── harden_rules.json    # 加固策略规则库
│   │
│   ├── harden/                  # 自动加固模块
│   │   ├── __init__.py
│   │   ├── linux_harden.py      # Linux 加固
│   │   ├── win_harden.py        # Windows 加固
│   │   └── templates/           # 加固脚本模板
│   │       ├── linux_firewall.sh
│   │       ├── linux_service.sh
│   │       └── win_firewall.ps1
│   │
│   ├── report/                  # 报告生成
│   │   ├── __init__.py
│   │   └── reporter.py          # Markdown/文本 中文报告
│   │
│   └── utils/                   # 工具函数
│       ├── __init__.py
│       ├── validator.py          # 输入校验（IP/域名合法性 + 权限拦截）
│       ├── logger.py             # 日志记录
│       └── constants.py          # 常量和枚举
│
├── scripts/                     # 独立工具脚本
│   ├── deploy_linux.sh          # Linux 一键部署
│   ├── deploy_win.ps1           # Windows 环境适配
│   └── rule_importer.py         # 外部规则批量导入
│
├── tests/                       # 测试
│   ├── test_validator.py
│   ├── test_nmap_adapter.py
│   └── test_rules_engine.py
│
├── docs/                        # 用户文档
│   ├── INSTALL.md               # 部署教程
│   ├── USAGE.md                 # 使用手册
│   └── FAQ.md                   # 常见问题
│
├── requirements.txt             # Python 依赖
└── .gitignore
```

---

## 八、可扩展性设计（为未来"重盾"预留）

> **核心理念**：轻盾是基座，不锁死天花板。预留以下扩展点，未来可平滑升级为"重盾"企业版。

### 8.1 扩展点清单

| 扩展点 | 当前轻盾做法 | 未来重盾方向 | 切换机制 |
|--------|-------------|-------------|:--:|
| **扫描引擎** | Nmap + 自研脚本 | + hackingtool 精选模块 / OpenVAS | 适配器模式，新增 Adapter 即可 |
| **MSF 集成度** | 仅 auxiliary/scanner 子集 | 可扩展至 auxiliary/server/ 等审计模块 | 白名单配置文件控制 |
| **规则引擎** | 本地 JSON 文件 | + 远程规则订阅 / STIX/TAXII 威胁情报 | 数据源接口抽象 |
| **报告格式** | Markdown/纯文本 | + PDF/HTML/JSON API | 报告渲染器可插拔 |
| **用户界面** | CLI（v0.1.0） | Web 面板 → 桌面客户端 → SaaS 多租户 | 前后端分离架构预留 |
| **数据存储** | 本地日志文件 | + SQLite → PostgreSQL | Repository 模式抽象 |
| **分布式** | 单机运行 | 支持 Agent 模式（中心控 + 多节点扫描） | 消息队列接口预留 |
| **认证鉴权** | 无（单用户） | 多用户 + RBAC | 中间件层预留 |

### 8.2 适配器模式 — 核心可扩展机制

```python
# 所有扫描能力通过 Adapter 抽象，新增能力只需新增 Adapter

class BaseAdapter(ABC):
    """所有扫描适配器的基类"""
    @abstractmethod
    def validate_target(self, target: str) -> bool:
        """目标合法性校验"""
        ...

    @abstractmethod
    def scan(self, target: str, **kwargs) -> ScanResult:
        """执行扫描，返回结构化结果"""
        ...

    @abstractmethod
    def capabilities(self) -> list[str]:
        """返回该适配器支持的能力列表"""
        ...

# 轻盾已有适配器
class NmapAdapter(BaseAdapter):      ...
class SelfScriptAdapter(BaseAdapter): ...
class MsfScannerAdapter(BaseAdapter): ...

# 重盾未来新增（只需实现 BaseAdapter）
class OpenVASAdapter(BaseAdapter):    ...  # 集成 OpenVAS
class ZAPAdapter(BaseAdapter):        ...  # 集成 OWASP ZAP
class HackingToolAdapter(BaseAdapter):...  # 精选 hackingtool 防御模块
class NucleiAdapter(BaseAdapter):     ...  # 集成 Nuclei 模板引擎
```

### 8.3 规则引擎可扩展性

```json
// 当前规则格式（v0.1.0 本地 JSON）
{
  "rule_id": "VULN-001",
  "name": "MySQL 弱口令检测",
  "severity": "high",
  "match_type": "service_version",
  "pattern": {"service": "mysql", "auth_result": "weak"}
}

// 未来可扩展格式（v1.0.0 支持远程订阅）
{
  "rule_id": "VULN-001",
  "source": "remote://threat-feed.example.com/rules/v1",
  "ttl_hours": 24,
  "signature_hash": "sha256:abcd1234..."
}
```

---

## 九、给 AI Agent 的开发指引

### 9.1 每个 Agent 开发前必读

1. **先读本文档**，建立项目全局认知
2. **再读 `合规红线（第五章）`**，确认你的产出不越界
3. **最后读对应模块的详细提示词**（在 `LightShield_AI_Prompt_全集.txt` 中）
4. 如果你的代码涉及 MSF 调用，必须检查 `ALLOWED_MSF_PREFIXES` 白名单
5. 所有对外网络操作的代码必须包含 `validate_target()` 校验

### 9.2 开发顺序（已执行到 Phase 6，Phase 7-10 规划中）

```
Phase 1: 项目骨架          → core.py, config.py, validator.py, logger.py  ✅ 已完成
Phase 2: Nmap 适配器        → nmap_adapter.py → port_scanner.py              ✅ 已完成
Phase 3: 自研检测脚本       → web_vuln_scanner.py, weak_password.py, component_checker.py  ✅ 已完成
Phase 4: MSF 扫描适配器     → msf_adapter.py（白名单机制）                   ✅ 已完成
Phase 5: 规则引擎           → engine.py + vuln_rules.json + harden_rules.json  ✅ 已完成
Phase 6: 报告生成           → reporter.py                                    ✅ 已完成
Phase 7: 自动加固           → linux_harden.py + 脚本模板                     ⏳ v0.0.16-17
Phase 8: 部署脚本           → deploy_linux.sh, deploy_win.ps1                ⏳ v0.0.18
Phase 9: CLI + 测试         → cli.py + pytest 全覆盖                         🟢 v0.0.11-14
Phase 10: 合规审计          → 全量代码审查 + Gate E                           ⏳ v0.0.19
```

> 详细进度追踪见 `.guardrails/PROGRESS.md`。

### 9.3 AI 模型分工

| 任务类型 | 推荐模型 | 理由 |
|----------|---------|------|
| 架构设计、多模块开发、界面开发 | Claude Code | 复杂上下文处理能力强 |
| 独立脚本、Shell/PowerShell 工具 | Codex | 脚本生成效率高 |
| 代码审查、合规审计 | 任意 | 规则明确，按清单检查 |

---

## 十、版本路线图

| 版本 | 里程碑 | 核心交付 | 状态 |
|------|--------|---------|:--:|
| v0.1.0 | MVP | 资产扫描 + 漏洞检测 + 中文报告（CLI） | ✅ 已完成 |
| v0.2.0 | 完整 CLI 工具 | CLI 入口 + 自动加固 + 测试覆盖 + 开源文档 | 🟢 开发中 |
| v0.3.0 | Web 面板 | Flask 管理界面 + 在线报告预览 | ⏳ |
| v0.4.0 | 桌面客户端 | Tkinter 跨平台 GUI + 一键打包 | ⏳ |
| v1.0.0 | 正式版 | 完整功能 + 开源文档 + 合规审计报告 | ⏳ |
| v2.0.0 | 重盾 | 适配器扩展 + 远程规则订阅 + 企业特性 | ⏳ |

> 详细小版本规划见 `.guardrails/VERSION_ROADMAP.md`（v0.0.01-10）和 `.guardrails/VERSION_ROADMAP_v2.md`（v0.0.11-20）。实时进度见 `.guardrails/PROGRESS.md`。

---

## 附录：术语表

| 术语 | 含义 |
|------|------|
| 轻盾 (LightShield) | 当前项目，轻量化防御自检工具 |
| 重盾 (HeavyShield) | 未来企业版，可替换扫描引擎的完整方案 |
| 适配器 (Adapter) | 对第三方工具的统一封装层 |
| 规则引擎 (Rule Engine) | 漏洞特征匹配 + 风险分级 + 加固策略映射的核心 |
| 合规红线 | 不可逾越的代码安全边界 |
| MSF | Metasploit Framework 缩写 |
