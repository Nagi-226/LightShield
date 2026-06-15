# LightShield v0.0.01 — v0.0.10 版本迭代路线图

> **迭代原则**：每个小版本 = 1-2 个可独立验证的模块产出，遵循"骨架→基础设施→核心能力→集成"的渐进路径。
> **护栏**：每个版本完成后必须通过 Gate A（合规）+ Gate B（范围忠实度），里程碑版本追加 Gate C（质量审计）。

---

## 版本总览

```
v0.0.01  骨架        → 壳子先搭好，能看到项目结构
v0.0.02  常量+配置    → 全局定义可用，配置系统就位
v0.0.03  校验+日志    → 安全防线(validator) + 审计基础(logger)
v0.0.04  架构核心    → Adapter基类 + 主调度器，骨架成型
────────────────────────── Gate 1: 架构→编码 里程碑 ──
v0.0.05  Nmap适配    → 第一个完整扫描能力
v0.0.06  Web漏洞检测 → SQL注入/XSS检测（安全关键）
v0.0.07  弱口令+组件  → 补充检测能力
v0.0.08  MSF适配     → 外部扫描能力接入
────────────────────────── Gate 2: 核心完成 里程碑 ──
v0.0.09  规则引擎    → 规则库 + 匹配引擎
v0.0.10  报告生成    → 中文Markdown报告
────────────────────────── Gate 3: MVP v0.0.10 ──
```

---

## 详细规划

### v0.0.01 — 项目骨架

| 属性 | 值 |
|------|-----|
| **目标** | 项目目录结构完整，依赖定义，`.gitignore` 就位 |
| **Agent** | Hermes（DeepSeek-V4-flash） |
| **产出** | `requirements.txt`, `.gitignore`, 7 个 `__init__.py`, 目录结构 |
| **依赖** | 无 |
| **验证** | `pip install -r requirements.txt` 成功 |

### v0.0.02 — 常量 + 配置

| 属性 | 值 |
|------|-----|
| **目标** | MSF 白名单/黑名单常量，配置管理类 |
| **Agent** | Hermes（`constants.py`） + Reasonix（`config.py`） |
| **产出** | `lightshield/utils/constants.py`, `lightshield/config.py` |
| **依赖** | v0.0.01 |
| **验证** | `from lightshield.utils.constants import ALLOWED_MSF_PREFIXES` |

### v0.0.03 — 校验 + 日志 ⚠️ Codex

| 属性 | 值 |
|------|-----|
| **目标** | IP/域名输入校验（R2 防线）+ 结构化日志系统 |
| **Agent** | **Codex**（`validator.py`） + Reasonix（`logger.py`） |
| **产出** | `lightshield/utils/validator.py`, `lightshield/utils/logger.py` |
| **依赖** | v0.0.02（常量定义） |
| **验证** | `TargetValidator.validate("192.168.1.0/24")[0] == False` |

### v0.0.04 — 架构核心

| 属性 | 值 |
|------|-----|
| **目标** | BaseAdapter 抽象基类 + 主调度器 |
| **Agent** | Claude Code |
| **产出** | `lightshield/adapters/base.py`, `lightshield/core.py` |
| **依赖** | v0.0.03 |
| **验证** | Qoder（双审）审查接口一致性 |

### v0.0.05 — Nmap 适配器

| 属性 | 值 |
|------|-----|
| **目标** | Nmap 封装适配器 + 端口扫描器 |
| **Agent** | Claude Code（adapter）+ Reasonix（scanner） |
| **产出** | `lightshield/adapters/nmap_adapter.py`, `lightshield/scanners/port_scanner.py` |
| **依赖** | v0.0.04 |
| **验证** | QoderWork（VM 沙箱）测试扫描输出格式 |

### v0.0.06 — Web 漏洞检测 ⚠️ Codex

| 属性 | 值 |
|------|-----|
| **目标** | SQL 注入检测、XSS 检测、目录枚举（自研脚本） |
| **Agent** | **Codex（GPT-5.5）** |
| **产出** | `lightshield/scanners/web_vuln_scanner.py` |
| **依赖** | v0.0.05（端口扫描结果作为输入） |
| **审查** | Qoder（双审 — Qwen 独立视角验证检测≠利用边界） |
| **验证** | QoderWork（VM 沙箱）验证 HTTP 检测逻辑 |

### v0.0.07 — 弱口令 + 组件检测

| 属性 | 值 |
|------|-----|
| **目标** | SSH/MySQL/Web 弱口令检测 + CVE 组件版本匹配 |
| **Agent** | Reasonix |
| **产出** | `lightshield/scanners/weak_password.py`, `lightshield/scanners/component_checker.py` |
| **依赖** | v0.0.06 |
| **验证** | QoderWork（VM 内搭建 SSH/MySQL 靶机测试） |

### v0.0.08 — MSF 适配器 ⚠️ Codex

| 属性 | 值 |
|------|-----|
| **目标** | Metasploit auxiliary/scanner 安全调用封装（白名单机制，R5） |
| **Agent** | **Codex（GPT-5.5）** |
| **产出** | `lightshield/adapters/msf_adapter.py` |
| **依赖** | v0.0.05（Nmap 适配器作为模板） |
| **审查** | Qoder（双审 — 逐条验证白名单不可绕过） |
| **验证** | 🔴 QoderWork（VM 沙箱 — 尝试调用 exploit 模块，必须被拦截） |

### v0.0.09 — 规则引擎

| 属性 | 值 |
|------|-----|
| **目标** | JSON 规则库 + 匹配引擎 + 风险分级 |
| **Agent** | Claude Code（engine）+ Reasonix（JSON 规则库） |
| **产出** | `lightshield/rules/engine.py`, `lightshield/rules/vuln_rules.json`, `lightshield/rules/harden_rules.json` |
| **依赖** | v0.0.06 + v0.0.07（检测逻辑作为规则输入） |
| **审查** | Qoder（审查 JSON 规则文件的中文描述质量） |
| **验证** | QoderWork（VM 内批量导入 CVE 数据测试） |

### v0.0.10 — 报告生成 + MVP 集成

| 属性 | 值 |
|------|-----|
| **目标** | Markdown/纯文本中文安全报告 + 端到端 MVP 联调 |
| **Agent** | Reasonix（reporter）+ Qoder（中文语言审查） |
| **产出** | `lightshield/report/reporter.py` |
| **依赖** | v0.0.09（规则引擎输出作为报告输入） |
| **审查** | Qoder（Qwen 中文能力审查措辞专业性） |
| **验证** | 🔴 QoderWork（Gate E — 完整 MVP 端到端回归测试） |
