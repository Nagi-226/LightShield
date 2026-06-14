# Changelog

All notable changes to LightShield 轻盾 will be documented in this file.

格式基于 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)。

---

## [0.3.0] - 2026-06-14

### Added

- **Web 仪表板**：`lightshield serve` 启动 Flask Web 服务，浏览器图形界面操作 LightShield
- **Flask REST API**：6 个端点（`POST /api/login`、`/api/logout`、`/api/scan`、`GET /api/scan/<id>`、`/api/report/<id>`、`POST /api/harden/<id>`）
- **Session 鉴权**：Flask 原生 session（签名 cookie），凭证通过环境变量 `LS_WEB_USERNAME` / `LS_WEB_PASSWORD` 配置
- **CSRF 防护**：自研 csrf.py 模块（`secrets.compare_digest` 时序安全 + X-CSRF-Token header + form hidden input 双通道）
- **4 个 Web 页面**：登录页、仪表板（扫描面板+历史列表）、报告查看器（marked.js Markdown 渲染+SRI hash）、加固建议页（RuleEngine 建议+脚本生成）
- **`lightshield serve`** CLI 子命令：支持 `--host` / `--port` / `--debug` 参数
- `pip install lightshield[web]` 可选依赖（Flask>=3.0）
- **CodeWhale v0.3.0 全量终审**：0 Blocker，5 Suggestion，全部修复（`docs/review-v030-codewhale.md`）
- **Nagi 五大铁律 × 六大合规红线**：全量 R1-R6 逐条核查通过

### Changed

- 版本号 0.0.27 → 0.3.0
- 测试总数 534 → 575
- `lightshield/web/` 子包（6 个 Python 模块 + 5 个 Jinja2 模板 + 1 个 CSS）
- 文档更新：INSTALL/USAGE/FAQ 补充 Web 仪表板章节

---

## [0.2.0] - 开发中

### Added

- `lightshield harden` 子命令：扫描 → 规则匹配 → 加固脚本生成 → 中文报告（含加固建议段）
- Linux 加固脚本生成器（`lightshield/harden/linux_harden.py`）：生成 iptables/SSH/服务管理加固脚本 + 对称回滚脚本，R4 所有权阻断门
- Windows 加固脚本生成器（`lightshield/harden/win_harden.py`）：生成 netsh/Set-Service 加固脚本 + 回滚脚本，PowerShell 模板
- `lightshield/harden/base.py`：HardenBase ABC + HardenResult/HardenStatus（与 BaseAdapter 分离——scan 只读，harden 修改系统）
- `core.generate_hardening()` 编排钩子：R2 校验 → 规则引擎推荐 → Linux/Windows hardener 分派 → 审计
- 346 项单元测试（Reasonix v0.0.12-14，覆盖 utils/adapters/scanners/rules/report/harden）

### Changed

- **日志与异常一致性加固**（v0.0.15）：`config.py` 环境变量覆盖走项目统一日志（审计+脱敏）；`rules/engine.py` JSON 加载不再静默失败、规则匹配逐条容错不中断；`report/reporter.py` save() 异常安全、写文件失败抛 IOError
- **harden_rules.json**：SSH sed 规则改为覆盖注释行与非注释行（`^#\?`），增加 `grep -q || echo` 兜底
- `core.py`：`generate_hardening()` 接收可选 `recommendations` 参数、增加 `os_platform` 参数分派 Win/Linux hardener
- 加固脚本备份路径统一为 `/tmp/lightshield-harden-backup/`（固定路径，加固+回滚脚本跨进程共享）

### Fixed

- **Codex 审查 B1**：`<service>` 等未替换占位符禁止作为 shell 命令执行，改为注释引导
- **Codex 审查 B2**：SSH/iptables 备份路径从运行时变量改为固定路径，回滚脚本可独立运行
- **Codex 审查 M1**：CLI 与 Core 重复计算 recommendations 问题，改为统一复用
- **Codex 审查 L1**：清理 linux_harden.py 死 import(`Path`) 和过期注释

---

## [0.1.0] - 2026-06-09

### Added

- MVP 14 核心模块：core.py / config.py / cli.py / base.py / nmap_adapter.py / msf_adapter.py / port_scanner.py / web_vuln_scanner.py / weak_password.py / component_checker.py / engine.py / vuln_rules.json / harden_rules.json / reporter.py
- 8-Agent 开发集群（Claude Code / Codex / Reasonix / CodeWhale / Hermes / CodeBuddy / Qoder / QoderWork）
- Nagi Dev Guardrails v3.0 五层防御护栏体系（Gate A-E）
- 合规红线 R1-R6：禁攻击 / 禁批量公网段 / 禁远控 / 仅自查 / MSF白名单 / 限频
- `lightshield scan` 全量扫描命令
- `lightshield quick-scan` 快速扫描命令
- `lightshield version` 版本查询命令
- 95 项单元测试（Codex：validator 62项 + msf_adapter 33项）
- 一键部署脚本 `scripts/deploy_linux.sh` + `scripts/deploy_win.ps1`
- 121 项单元测试（Reasonix batch1：constants 45项 + logger 29项 + config 47项）

[0.3.0]: https://github.com/LightShield/lightshield/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/LightShield/lightshield/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/LightShield/lightshield/releases/tag/v0.1.0
