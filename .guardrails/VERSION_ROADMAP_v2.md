# LightShield v0.0.11 — v0.0.20 版本迭代路线图

> **起点**：v0.0.10 MVP（14 模块全部就绪，架构 Grade A）
> **终点**：v0.0.20 — 可发布的完整 CLI 工具
> **原则**：测试先行 → 加固补齐 → CLI 抛光 → 文档收尾

---

## 版本总览

```
v0.0.11  CLI 入口      → 一条命令完成全流程扫描
v0.0.12  测试 batch1    → utils 层全覆盖（validator/constants/logger/config）
v0.0.13  测试 batch2    → adapters + scanners 核心路径
v0.0.14  测试 batch3    → scanners 扩展 + rules + report
v0.0.15  日志+异常加固   → 全模块日志集成 + 异常处理一致性
v0.0.16  自动加固 Linux  → 高危端口关闭 + 服务禁用 + Web 防护
v0.0.17  自动加固 Win    → Windows 防火墙 + 账户策略 + 服务管理
v0.0.18  一键部署        → deploy_linux.sh + deploy_win.ps1
v0.0.19  E2E 集成测试    → QoderWork 全链路 + 靶机验证 + 合规终审
v0.0.20  文档 + 发布     → README/INSTALL/USAGE/FAQ + v0.0.20 tag
```

---

## 详细规划

### v0.0.11 — CLI 入口

| 属性 | 值 |
|------|-----|
| **目标** | 提供 `lightshield scan <target>` 一条命令完成资产扫描→漏洞检测→报告生成 |
| **Agent** | Claude Code |
| **产出** | `lightshield/cli.py`, `setup.py` 更新（console_scripts 入口） |
| **验证** | `lightshield scan 127.0.0.1` 输出完整中文报告 |

**关键子任务**：
- argparse 命令行解析（scan / quick-scan / report / version 子命令）
- `--output-format markdown|text` 参数
- `--confirm-ownership` 参数（R4 合规）
- 进度提示（扫描中... / 检测中... / 报告生成中...）
- `setup.py` / `pyproject.toml` 配置 `console_scripts` 入口

---

### v0.0.12 — 测试 batch1：utils 层

| 属性 | 值 |
|------|-----|
| **目标** | utils 层 4 个模块达到 80%+ 覆盖率 |
| **Agent** | Reasonix（批量测试生成，成本优化） |
| **产出** | `tests/test_validator.py`, `tests/test_constants.py`, `tests/test_logger.py`, `tests/test_config.py` |
| **验证** | `pytest tests/ -v --cov=lightshield/utils` |

**关键测试场景**：
- validator: 20+ 合法/非法 IP/域名/参数组合
- constants: MSF 白名单/黑名单不重叠、枚举值存在性
- logger: 日志写入/轮转/敏感信息过滤/线程安全
- config: YAML加载/JSON加载/环境变量覆盖/MSF校验

---

### v0.0.13 — 测试 batch2：adapters + scanners 核心

| 属性 | 值 |
|------|-----|
| **目标** | base/nmap/msf adapter + port_scanner 核心路径覆盖 |
| **Agent** | Reasonix |
| **产出** | `tests/test_base.py`, `tests/test_nmap_adapter.py`, `tests/test_msf_adapter.py`, `tests/test_port_scanner.py` |
| **验证** | `pytest tests/ -v` |

**关键测试场景**：
- base: ScanResult/VulnFinding to_dict、BaseAdapter 抽象方法存在性
- nmap: XML 解析正确性、高危端口标记、超时处理
- msf: 白名单/黑名单逻辑、SecurityViolationError 抛出、审计日志
- port_scanner: 端口分析统计、高危端口提取、摘要生成

---

### v0.0.14 — 测试 batch3：scanners + rules + report

| 属性 | 值 |
|------|-----|
| **目标** | 剩余模块测试 + 规则引擎匹配验证 |
| **Agent** | Reasonix |
| **产出** | `tests/test_web_vuln.py`, `tests/test_weak_password.py`, `tests/test_component.py`, `tests/test_engine.py`, `tests/test_reporter.py` |
| **验证** | `pytest tests/ -v --cov=lightshield` |

---

### v0.0.15 — 日志 + 异常加固

| 属性 | 值 |
|------|-----|
| **目标** | 所有模块统一使用 get_logger()，异常处理风格一致 |
| **Agent** | Claude Code |
| **产出** | 修改所有 14 个 .py 文件的日志调用和异常处理 |
| **验证** | 所有模块自检日志输出一致，异常场景覆盖 |

**检查清单**：
- [ ] 所有 scan() 方法调用 _log_scan_start/end
- [ ] 所有异常路径有友好的中文错误提示
- [ ] 敏感信息过滤在所有模块生效
- [ ] 审计日志覆盖所有扫描/加固/MSF 调用

---

### v0.0.16 — 自动加固：Linux

| 属性 | 值 |
|------|-----|
| **目标** | 根据规则引擎推荐，自动执行 Linux 加固操作 |
| **Agent** | Claude Code |
| **产出** | `lightshield/harden/linux_harden.py`, `lightshield/harden/templates/linux_firewall.sh`, `lightshield/harden/templates/linux_service.sh` |
| **验证** | QoderWork VM 中执行加固脚本，验证端口关闭/服务禁用生效 |

**加固能力**：
- 高危端口关闭（iptables 规则）
- 不必要服务禁用（systemctl）
- SSH 加固（禁用密码登录、禁用 root 登录）
- Nginx/Apache 基础安全头配置
- 内核参数安全优化

---

### v0.0.17 — 自动加固：Windows

| 属性 | 值 |
|------|-----|
| **目标** | Windows Server 加固 |
| **Agent** | Claude Code |
| **产出** | `lightshield/harden/win_harden.py`, `lightshield/harden/templates/win_firewall.ps1` |
| **验证** | QoderWork Windows VM 中执行 |

---

### v0.0.18 — 一键部署脚本

| 属性 | 值 |
|------|-----|
| **目标** | 在干净 Linux/Windows 上一键完成环境安装 |
| **Agent** | Hermes（Shell 模板） + Claude Code（集成） |
| **产出** | `scripts/deploy_linux.sh`, `scripts/deploy_win.ps1` |
| **验证** | QoderWork 干净 VM 中执行部署 → 安装依赖 → `lightshield scan 127.0.0.1` 成功 |

---

### v0.0.19 — E2E 集成测试 + 合规终审

| 属性 | 值 |
|------|-----|
| **目标** | 在 QoderWork VM 中搭建含已知漏洞的靶机，全链路验证 |
| **Agent** | QoderWork（执行） + CodeWhale + Qoder（双审） |
| **产出** | `docs/e2e-test-report.md`, `docs/compliance-final-audit.md` |
| **验证** | 靶机上预置 5 个漏洞 → 扫描发现 ≥4 个 → 加固后复扫 = 0 个 |

**靶机漏洞清单**：
1. 开放 Telnet (23)
2. MySQL 弱口令 (root/admin)
3. 老旧 OpenSSH 版本
4. 开放 Redis 无密码 (6379)
5. 敏感目录可访问 (/.git, /phpmyadmin)

---

### v0.0.20 — 文档 + 正式发布

| 属性 | 值 |
|------|-----|
| **目标** | 完整的开源项目文档 + v0.0.20 发布 |
| **Agent** | Claude Code + Qoder（中文审查） + Technical Writer agent |
| **产出** | `README.md`, `docs/INSTALL.md`, `docs/USAGE.md`, `docs/FAQ.md`, `CHANGELOG.md` |
| **验证** | 新人按文档可在 10 分钟内完成安装→首次扫描→查看报告 |

---

## 集群任务分配

| 版本 | Claude Code | Codex | Reasonix | Hermes | CodeWhale | Qoder | QoderWork |
|:--:|:--:|:--:|:--:|:--:|:--:|:--:|:--:|
| v0.0.11 | CLI 入口 | — | — | — | — | — | smoke |
| v0.0.12 | — | — | 测试生成 | — | — | — | — |
| v0.0.13 | — | — | 测试生成 | — | — | — | — |
| v0.0.14 | — | — | 测试生成 | — | — | — | — |
| v0.0.15 | 日志加固 | — | — | — | — | — | — |
| v0.0.16 | Linux 加固 | — | — | — | 审查 | — | VM 验证 |
| v0.0.17 | Win 加固 | — | — | — | — | — | VM 验证 |
| v0.0.18 | 集成 | — | — | Shell 脚本 | — | — | VM 验证 |
| v0.0.19 | 协调 | — | — | — | 审查 | 审查 | E2E 执行 |
| v0.0.20 | README/文档 | — | — | — | — | 中文审查 | — |

---

## 里程碑

| Gate | 触发版本 | 检查内容 |
|:--:|:--:|------|
| Gate 3 | v0.0.11 | CLI 可执行、一条命令产出报告 |
| Gate 4 | v0.0.15 | 测试覆盖率 ≥80%、日志审计全覆盖 |
| Gate 5 | v0.0.19 | E2E 靶机验证通过、合规终审零违规 |
| 🚀 发布 | v0.0.20 | GitHub Release + 完整文档 |

---

## Codex 在 v0.0.11-v0.0.20 中的角色

> Codex 的 3 个安全关键模块（validator/web_vuln/msf）已在 v0.0.01-v0.0.10 全部完成。在 v0.0.11-v0.0.20 中 **无新增 Codex 任务**——后续 10 个版本以测试、加固、部署、文档为主，这些任务更适合 Reasonix（批量测试）、Hermes（Shell 模板）、Claude Code（架构集成）。

如果后续 v0.0.16 的自动加固模块需要安全关键代码审查，Codex 可作为审查者参与。
