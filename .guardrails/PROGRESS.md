# 📊 LightShield 开发进度追踪

> **最后更新**：2026-06-20 | **当前版本**：v0.0.39 ✅（本地交付，待推送 GitHub）| **下一目标**：v0.0.40
> **会话状态**：v0.0.39 OpenAPI + i18n 中英双语交付（ZCode→OpenAPI/Swagger，Hermes→locale，CC→i18n.py 桥接+6 页面接线+测试）。`/docs` Swagger UI、`/lang/<code>` 切换、Accept-Language 协商、JS i18n 桥（window.t/tf）。687 passed / 1 skip，五道门禁全绿（含 Gate A 合规）。阶段三 2/2 ✅。
> **下次启动**：v0.0.40 自动加固闭环（QoderWork VM + Qoder Web + CodeWhale 审查 + CC 架构/集成）

---

## v0.0.01 — v0.0.10（已完成 ✅）

| 版本 | Agent | 产出 | 验收 | 备注 |
|:--:|------|------|:--:|------|
| v0.0.01 | Hermes | 骨架 + constants.py | ✅ | 7 __init__.py + .gitignore |
| v0.0.02 | CC | config.py | ✅ | Reasonix 失败，CC 接管 |
| v0.0.03 | Codex | validator.py | ✅ | 黑名单优先、fallback 常量 |
| v0.0.03 | QoderWork | smoke test | ✅ | 20/20 通过 |
| v0.0.04 | CC | base.py + core.py | ✅ | Qoder 审查发现 8 问题，全部修复 |
| v0.0.04 | Qoder | 双审报告 | ✅ | 2B + 6S → CC 修复 |
| v0.0.05 | CC | nmap_adapter + port_scanner | ✅ | XML 解析 + 高危端口标记 |
| v0.0.06 | Codex | web_vuln_scanner.py | ✅ | SQLI/XSS payload 仅检测 |
| v0.0.07 | Reasonix | weak_password + component_checker | ✅ | 901+1240行，代码已读，有效模块 |
| v0.0.08 | Codex | msf_adapter.py | ✅ | 黑名单优先、timeout=60 |
| v0.0.09 | CC | engine + vuln/harden_rules | ✅ | 14+6 规则 |
| v0.0.10 | CC | reporter.py | ✅ | Markdown + Text 中文报告 |
| Phase1 | CodeBuddy | 骨架审查 | ✅ | 7 BUG 全部修复 |
| Phase1 | CodeWhale | 全量审查 | ✅ | Grade A |
| Phase1 | Reasonix | batch1 测试（constants/logger/config） | ✅ | 121项全部通过（2026-06-10） |

---

## v0.0.11 — v0.0.20 进度

| 版本 | 目标 | Agent | 状态 | 验收 |
|:--:|------|------|:--:|:--:|
| v0.0.11 | CLI 入口 + setup.py | Codex | ✅ | ✅ R4 YES/NO + R2 validate |
| v0.0.11 | pyproject.toml + 依赖 | Hermes | ✅ | ✅ 3 项完成 |
| v0.0.12 | test_validator.py | Codex | ✅ | ✅ 225行/12函数 |
| v0.0.13 | test_msf_adapter.py | Codex | ✅ | ✅ 185行/白名单+黑名单+注入防护 |
| v0.0.18 | deploy_linux.sh + deploy_win.ps1 | Hermes | ✅ | ✅ 171+239行 |
| v0.0.20 | LICENSE + docs 骨架 | Hermes | 🟢 | ⬜ 已给提示词 |
| v0.0.12-14 | test_constants/log/config + batch2/3 | Reasonix | ✅ | ✅ batch1(121)+batch2(96)+batch3(129)=346项全部通过，1 skip合理(DNS绕过mock已等效覆盖) |
| v0.0.15 | 日志+异常加固 (3/14模块) | CC | ✅ | ✅ config:182 bare logging→get_logger, engine: +logger/_load_json容错/match逐规则try-except, reporter: +logger/save()异常安全。其余11模块已达标无需改动 |
| v0.0.16 | Linux 加固脚本生成器 | CC | ✅ | ✅ 6文件：base.py(HardenStatus/Result/Base)、linux_harden.py(R4阻断门+iptables-D回滚+零subprocess)、templates×2、core钩子、CLI harden子命令。脚本生成器模式，不自动执行 |
| v0.0.16 | 审查 linux_harden.py | Codex | ✅ | ✅ docs/review-v016-codex.md (17KB/10项发现)，5项核心修复已由CC应用 |
| v0.0.17 | Win 加固 | CC | ✅ | ✅ win_harden.py+win_firewall.ps1+__init__+core os_platform钩子。脚本生成器模式，零subprocess。自检9断言全过，回归346项全过 |
| v0.0.19 | E2E + 合规终审 | WSL2 Docker→CC | ✅ | ✅ WSL2 Ubuntu 24.04 替代 VM 执行：scan(61端口/7漏洞/CVE-2023-38408)→harden(11条建议+harden.sh+rollback.sh)→R2 拦截→R1-R6 全通过。报告：docs/e2e-v019-report.md |
| v0.0.20 | 文档骨架 | Hermes | ✅ | ✅ LICENSE+README.md(134行)+CHANGELOG.md(49行)+INSTALL(162行)+USAGE(173行)+FAQ(71行) 已落盘 |
| v0.0.20 | 文档填充（清TODO+补真实数据） | CC | ✅ | ✅ CHANGELOG 完整版(v0.0.10/v0.0.20)、FAQ 4条TODO全部填充(场景对比/加固执行示例/macOS/帮助渠道)、README 架构描述补细节 |

---

## v0.0.20 发布就绪 🎉

**全部 21 个版本 (v0.0.01-v0.0.20) 已完成。8/8 Agent 零任务。**

### v0.0.20 发布 + 架构预留（2026-06-11）

| 版本 | 目标 | Agent | 状态 |
|:--:|------|------|:--:|
| v0.0.20 | git tag + E2E 终审 | CC | ✅ |
| — | Repository 抽象 (JSON→SQLite→PG) | CC | ✅ `lightshield/repository/` |
| — | `submit_scan()` / `get_scan_status()` | CC | ✅ core.py 异步接口预留 |
| — | 未来扩展 config 字段 | CC | ✅ web/redis/db/queue/auth 预留 |
| — | CLAUDE.md 扩展表更新 | CC | ✅ 9 个扩展点全部标注预留状态 |

### 发布步骤
1. ✅ `git tag v0.0.20` 已创建
2. `git push origin main --tags`（需手动执行）
3. GitHub Release 附 CHANGELOG.md v0.0.20 条目

---

## v0.0.21 — v0.0.30 十版本迭代规划 🎯

> **总目标**：从 v0.0.20 CLI 工具 → v0.0.30 GUI 桌面客户端
> **三阶段推进**：质量深化 → 内容增长 → GUI 铺路
> **Agent 复用**：Codex(安全关键) / Reasonix(批量测试) / Hermes(基础设施) / CodeWhale(审查)

---

### 阶段一：质量深化（v0.0.21-0.0.23）—— 把基础打牢 ✅ 已完成

| 版本 | 目标 | Agent | 关键交付 | 状态 |
|:--:|------|:--:|------|:--:|
| **v0.0.21** | mypy 收紧 + 类型安全 | CC | `check_untyped_defs=true`、修复存量类型错误、新增 type hints 覆盖 | ✅ |
| **v0.0.22** | CLI + core 测试覆盖 | Reasonix | CLI arg 解析测试(0%→60%)、core._validate_request 测试(0%→70%) | ✅ |
| **v0.0.23** | C90 重构 + 测试补齐 | CC | `scan()` F(41)→A(4)、5 helper 提取、移除 C901 豁免、+92 测试（nmap 30 + win_harden 34 + component 28）、覆盖率 71→78% | ✅ |

**阶段一验收标准**：
- mypy `check_untyped_defs=true`，0 errors ✅
- 覆盖率 ≥70%（当前 **78%**）✅
- 无 C90 违规（圈复杂度全部 ≤20）✅

---

### 阶段二：内容增长（v0.0.24-0.0.26）—— 让产品有用

| 版本 | 目标 | Agent | 关键交付 | 状态 |
|:--:|------|:--:|------|:--:|
| **v0.0.24** | CVE 知识库扩充 | Codex | CVE 条目 28→69、覆盖组件 11→22、新增 6 组件（mongodb/django/laravel/magento/bind/exim） | ✅ |
| **v0.0.25** | Repository SQLite 实现 | CC | `SqliteRepository`、扫描历史查询、`lightshield history` 子命令、28 条测试 | ✅ |
| **v0.0.26** | 规则引擎增强 | CC | `import_rules_from_url/file`、`reload_rules()` 热加载、`rule_metadata` 版本指纹、`--rules-url` CLI、18 条新测试 | ✅ |
| **v0.0.27** | Flask API 骨架 | CC | `lightshield/web/` (app/auth/routes)、5 端点 (login/logout/scan/status/report)、Session 鉴权、`lightshield serve` CLI、25 条测试 | ✅ |

**阶段二验收标准**：
- CVE 知识库 ≥50 条（覆盖 OWASP Top 10 常见组件）✅ 70 条 / 22 组件
- SQLite 存储可用，`lightshield history` 可列出历史扫描 ✅
- 规则引擎支持 `--rules-url` 远程导入 ✅

---

### 阶段三：GUI 铺路（v0.0.27-0.0.29）—— 为桌面端搭骨架

| 版本 | 目标 | Agent | 关键交付 |
|:--:|------|:--:|------|
| **v0.0.27** | Flask API 骨架 | CC | REST API：`POST /api/scan`、`GET /api/scan/<id>`、`GET /api/report/<id>`、Session 鉴权 | ✅ |
| **v0.0.28** | Web 仪表板 | Codex | 扫描面板（输入目标→提交→查看进度）、报告查看器（Markdown 渲染）、历史记录列表 | ✅ |
| **v0.0.29** | 加固页面 + 安全加固 | Codex | 加固建议面板、一键生成脚本、Web 端 R4 所有权确认、CSRF 防护 | ✅ |

**阶段三验收标准**：
- Flask API 全部端点可用（curl 可调）
- Web 界面可完成 scan → view report → harden 全流程
- Session 鉴权 + CSRF 防护到位

---

### 收尾：集成发布（v0.0.30）

| 版本 | 目标 | Agent | 关键交付 |
|:--:|------|:--:|------|
| **v0.0.30** | Web Panel E2E + v0.0.30 就绪 | CC + Hermes + CodeWhale | Web E2E 测试、性能基线（<100ms API 响应）、文档更新（INSTALL/USAGE/FAQ 补充 Web 章节）、CodeWhale 全量审查 |

---

### Agent 任务分配总览

```
Agent        v0.0.21  v0.0.22  v0.0.23  v0.0.24  v0.0.25  v0.0.26  v0.0.27  v0.0.28  v0.0.29  v0.0.30
──────────────────────────────────────────────────────────────────────────────────────────────────
Claude Code    ✅       —        ✅        —       ✅       ✅       ✅        —        —       ✅
Codex           —       —        —       ✅        —        —        —       ✅       ✅        —
Reasonix        —      ✅       ✅        —        —        —        —        —        —        —
Hermes          —       —        —        —        —        —        —        —        —       ✅
CodeWhale       —       —        —        —        —        —        —        —        —       ✅
──────────────────────────────────────────────────────────────────────────────────────────────────
CC: 6 task    Codex: 3 task    Reasonix: 2 task    Hermes: 1 task    CodeWhale: 1 task
```

### 为什么是这个顺序

1. **质量先行**（21-23）：mypy 收紧 + 覆盖率提升 → 后续任何新功能都有安全网
2. **内容跟上**（24-26）：CVE 库扩充 + 规则增强 → 扫描结果更有价值
3. **GUI 铺路**（27-29）：Flask API + Web UI → 为 v0.0.30 Tkinter 桌面端验证交互模式
4. **收尾发布**（30）：全量审查 + E2E → v0.0.30 发布

### 为什么是这个顺序（回顾）

1. **质量先行**（21-23）：mypy 收紧 + 覆盖率提升 → 后续任何新功能都有安全网
2. **内容跟上**（24-26）：CVE 库扩充 + 规则增强 → 扫描结果更有价值
3. **GUI 铺路**（27-29）：Flask API + Web UI → 为 v0.0.30 桌面端验证交互模式
4. **收尾发布**（30）：全量审查 + E2E → v0.0.30 发布

---

## v0.0.30 发布就绪 🎉

**全部 30 个版本 (v0.0.01-v0.0.30) 已完成。8/8 Agent 全部任务完成。git tag v0.0.30 已推送。**

---

## v0.0.31 — v0.0.40 十版本迭代规划 🎯

> **总目标**：从 v0.0.30 Web 仪表板 → v0.0.40 自动加固执行
> **三阶段推进**：安全加固 → 能力扩展 → 自动化铺路
> **Agent 复用**（v0.0.31-38 已完成段）：CC(架构+安全关键) / Codex(前端+数据质量) / Hermes(基础设施) / CodeWhale(审查)
> **🔄 v0.0.39-40 按 2026-06-16 模型优势对齐改派**：CC(编排+架构+集成) / ZCode(OpenAPI) / Hermes(i18n骨架) / Qoder(重前端) / QoderWork(VM闭环) / CodeWhale(强制审查)。详见 `.cluster/CLUSTER.md §三-bis`。

---

### 阶段一：安全加固（v0.0.31-0.0.33）—— Web 生产就绪

| 版本 | 目标 | Agent | 关键交付 | 状态 |
|:--:|------|:--:|------|:--:|
| **v0.0.31** | 异步扫描 + 速率限制 | CC | `threading.Thread` 异步 `submit_scan()`、Web API 速率限制（`rate_limit_per_hour` 落地）、登录暴力破解防护（失败计数+指数退避）、`get_scan_status()` 返回 RUNNING/PENDING 状态 | ✅ |
| **v0.0.32** | Web 安全加固 | CC | Secure cookie flags（HttpOnly/SameSite/8h超时）、CSP 头（script-src CDN白名单）、CORS 白名单收紧（LS_CORS_ORIGINS）、`X-Frame-Options`/`X-Content-Type-Options`/`Referrer-Policy`、403 handler | ✅ |
| **v0.0.33** | Docker 部署 | Hermes | `Dockerfile` + `docker-compose.yml`、一键 `docker compose up` 启动 Web 仪表板、数据卷持久化（SQLite + 报告） | ✅ |

**阶段一验收标准**：
- Web API 扫描不阻塞请求线程 ✅
- 速率限制生效（同一 IP 超过限制 → 429）✅
- Docker 一键启动，无需手动安装 Python/Nmap ✅

---

### 阶段二：能力扩展（v0.0.34-0.0.37）—— 新扫描器 + 新格式

| 版本 | 目标 | Agent | 关键交付 | 状态 |
|:--:|------|:--:|------|:--:|
| **v0.0.34** | PDF 报告导出 | Codex | `PdfReportWriter`（`fpdf2` + 中文字体自动发现）、Web 下载 PDF 按钮、CLI `--output-format pdf` | ✅ |
| **v0.0.35** | CVE 100+ + 自动更新 | Codex | CVE 70→105（26 组件）、新增 Jenkins/ES/K8s/HAProxy、`fetch_latest_cves()` NVD API 2.0 | ✅ |
| **v0.0.36** | Nuclei 适配器 | CC | `NucleiAdapter(BaseAdapter)`、标签白名单/黑名单（R1 防线）、JSONL 解析 → `VulnFinding`、路径/参数注入防护、`lightshield/nuclei-templates/` 模板目录、52 条新测试 | ✅ |
| **v0.0.37** | Web UI 增强 | Codex | 脚本下载按钮 + CSRF + R4确认、SSE 实时推送 + poll fallback、暗色/亮色主题切换 + localStorage、仪表板搜索筛选 + URL参数同步。6 文件，+793 / -73 行。42 个 web 测试全过 | ✅ |

**阶段二验收标准**：
- PDF 报告可下载 ✅
- CVE 覆盖 ≥100 条、≥25 组件 ✅
- Nuclei 模板可扩展（社区贡献友好）✅
- Web UX 完整（下载/进度/主题/搜索）✅

---

### 阶段三：自动化铺路（v0.0.38-0.0.39）—— 为自动加固做准备

| 版本 | 目标 | Agent | 关键交付 | 状态 |
|:--:|------|:--:|------|:--:|
| **v0.0.38** | 沙箱执行器 | CC | `lightshield/sandbox/` 子包、`SandboxExecutor` 抽象（Docker 容器隔离）、`--execute` 危险标志（需额外 EXECUTE 确认）、执行超时+输出捕获+审计日志、32 条测试 | ✅ |
| **v0.0.39** | OpenAPI 文档 + i18n | **ZCode**(OpenAPI) + **Hermes**(i18n骨架) + **CC**(集成) | ZCode：手写 OpenAPI 3.0.3 JSON（8 端点）+ 自托管 Swagger UI（`/docs`）+ `docs/API.md`；Hermes：`zh-CN`/`en-US` locale（含 `_meta`、中英键集对称）；CC：`i18n.py` 桥接（协商 session→cookie→Accept-Language→默认 + JS 桥扁平字典）+ 6 页面接线（base/login/dashboard/report/harden/docs）+ `/lang/<code>` 切换 + `harden_page` 服务端 translate + 23 条 i18n/docs/双语测试。687 passed / 1 skip / 五门禁全绿 | ✅ |

**阶段三验收标准**：
- 沙箱中可安全执行加固脚本（docker exec → 超时 → 输出捕获 → 审计）✅
- API 文档在线浏览 ✅
- 中英文界面切换可用 ✅

---

### 收尾：v0.0.40 自动加固

| 版本 | 目标 | Agent | 关键交付 | 状态 |
|:--:|------|:--:|------|:--:|
| **v0.0.40** | 自动加固闭环 + 发布 | **QoderWork**(VM闭环) + **Qoder**(Web页) + **CodeWhale**(审查) + **CC**(架构/集成) | QoderWork：隔离 VM 中跑 `harden → execute → re-scan → verify` 全自动闭环 + 回滚验证；Qoder：Web 端一键加固+复扫+对比报告页面；CodeWhale：全量强制审查；CC：架构 + 集成 + git tag v0.0.40 | ⬜ |

---

### Agent 任务分配总览

```
Agent        v0.0.31  v0.0.32  v0.0.33  v0.0.34  v0.0.35  v0.0.36  v0.0.37  v0.0.38  v0.0.39  v0.0.40
──────────────────────────────────────────────────────────────────────────────────────────────
Claude Code    ✅       ✅       —       —       —       ✅       —      ✅      ✅†     ✅†
Codex           —       —       —       ✅      ✅       —       ✅       —       —       —
Hermes          —       —       ✅       —       —       —       —       —      ✅†     —
CodeWhale       —       —       —       —       —       —       —       —       —      ✅†
Qoder           —       —       —       —       —       —       —       —       —      ✅†
QoderWork       —       —       —       —       —       —       —       —       —      ✅†
ZCode           —       —       —       —       —       —       —       —      ✅†     —
──────────────────────────────────────────────────────────────────────────────────────────────
CC: 6    Codex: 3    Hermes: 2    CodeWhale: 1    Qoder: 1    QoderWork: 1    ZCode: 1
（† = v0.0.39/40 规划归属，按 2026-06-16 模型优势对齐分派；完成状态见上方阶段三表 ⬜）
```

### 为什么是这个顺序

1. **安全先行**（3.1-3.3）：异步扫描消除 Web 阻塞 → 速率限制防暴力破解 → Docker 降低部署门槛
2. **能力跟上**（3.4-3.7）：PDF 满足企业合规 → CVE 100+ 扩大检测面 → Nuclei 社区生态 → Web UX 打磨
3. **自动化收尾**（3.8-4.0）：沙箱是自动加固的前提——先有安全执行环境，再有全自动闭环

---

## Agent 完成统计（累计）

> 待完成列按 2026-06-16 模型优势对齐分工的 v0.0.39/40 归属重算。

| Agent | 已完成 | 待完成 | 待办（升级后） |
|------|:--:|:--:|------|
| Claude Code | 17 | 2 | v0.0.39 集成 + v0.0.40 架构/集成（不再当默认实现者） |
| Codex | 11 | 0 | — （安全关键模块按需触发） |
| Hermes | 6 | 1 | v0.0.39 i18n locale 骨架 |
| Reasonix | 4 | 0 | — （后续标准模块/测试默认派此） |
| CodeWhale | 3 | 1 | v0.0.40 强制全量审查（每版本强制审查升级） |
| Qoder | 1 | 1 | v0.0.40 Web 加固页面（重前端主力升级） |
| QoderWork | 1 | 1 | v0.0.40 VM 自动加固闭环 + v0.0.38 真机验证 |
| CodeBuddy | 1 | 0 | — （多文件大模块按需触发） |
| **ZCode 3.0** 🆕 | 0 | 1 | v0.0.39 OpenAPI 文档（+ 持续文档同步） |

---

## 审计日志

| 时间 | 事件 |
|------|------|
| 2026-06-09 20:00 | 护栏体系建立 |
| 2026-06-09 21:00 | Phase 1 骨架完成 |
| 2026-06-09 22:10 | v0.0.09-10 规则引擎+报告生成 → MVP 完成 |
| 2026-06-10 22:15 | 收尾——PROGRESS.md/CLAUDE.md 同步，4/8 Agent 全部任务完成 |
| 2026-06-11 22:45 | v0.0.20 发布：E2E 终审通过，pre-commit 9组hook，覆盖率71% |
| 2026-06-12 22:15 | v0.0.26 规则引擎增强，阶段二全部完成 |
| 2026-06-14 15:15 | v0.0.28 Web 仪表板交付（Codex），CC 验收通过 |
| 2026-06-14 16:05 | v0.0.29 加固页面 + CSRF 交付（Codex），CC 验收通过 |
| 2026-06-14 16:20 | v0.0.30 CodeWhale 全量终审（0 Blocker）+ Hermes 文档更新，CC E2E → git tag v0.0.30 → push GitHub |
| 2026-06-14 17:00 | v0.0.31 异步扫描+速率限制+登录防护 交付（CC）：core.py threading.Thread 异步化 + ratelimit.py 滑动窗口 + auth.py 指数退避锁定期 + app.py 429 handler。575 passed / ruff+mypy 全零 / smoke 通过 |
| 2026-06-15 19:15 | v0.0.36 Nuclei 适配器 交付（CC）：NucleiAdapter(BaseAdapter) + 标签白名单/黑名单（R1 防线） + JSONL 解析 + 路径/参数注入防护 + 52 条新测试。632 passed / ruff+mypy 全零 |
| 2026-06-15 22:30 | 集群扩展：ZCode 3.0 + GLM-5.2 作为 Agent 9（知识架构师）加入集群。创建 `.cluster/agents/ZCODE.md`，更新 CLUSTER.md + COORDINATION.md。Kimi K2.7 Code 作为 Agent 10 技术储备存入记忆 |
| 2026-06-15 23:30 | v0.0.37 Web UI 增强 交付验收（Codex）：脚本下载 + SSE + 主题切换 + 搜索筛选。42 web tests 全过。版本编号体系统一为 v0.0.XX，git tag v0.0.20-0.0.37 全部就位。阶段二 4/4 全部完成 🎉 |
| 2026-06-15 (续) | 源码版本号补齐：__init__/pyproject/setup 从 0.0.36 → 0.0.37（v0.0.37 交付时漏 bump，与已推送 tag 自相矛盾），独立提交建立干净基准。CHANGELOG 回填 v0.0.31-38 + 旧 [0.3.0]/[0.2.0]/[0.1.0] 头规范化为 v0.0.XX |
| 2026-06-15 (续) | v0.0.38 沙箱执行器 交付（CC）：`lightshield/sandbox/`（SandboxExecutor 抽象 + DockerSandboxExecutor）、Docker 隔离（--network none + 资源限制 + 只读挂载 + no-new-privileges）、`harden --execute` EXECUTE 二次确认、core.execute_hardening 钩子、超时强制终止 + 审计。32 条新测试，664 passed / 1 skip / ruff+mypy 全零。阶段三 1/2 |
| 2026-06-17 | **集群分工升级（模型优势对齐）**：CC 切 Opus 4.8 回归"编排+架构+安全终审"，卸下默认实现者。Reasonix 升默认实现+测试主力；CodeWhale 升每版本强制独立审查；Qoder 升重前端 UI 主力；QoderWork 接管 v0.0.40 VM 自动加固闭环 + v0.0.38 真机 Docker 验证；ZCode 承接 OpenAPI/审计文档；Hermes 加 i18n locale 骨架；CodeBuddy 主动承接多文件大模块。同步：8 个 `<AGENT>.md` + CLUSTER.md（新增 §三-bis 权威分工表 + 订正"集群模型实际配置"CC=Opus4.8 + 清理 §四 孤立残表 + Phase1 标历史存档）+ COORDINATION.md（归属表 v0.0.36→v0.0.38 + 集群治理文件归属 + CLAUDE.md 双重归属脚注）。**v0.0.39 改派** CC→ZCode(OpenAPI)+Hermes(i18n)+CC(集成)；**v0.0.40 改派** CC+CodeWhale→QoderWork(VM)+Qoder(Web)+CodeWhale(审查)+CC(架构) |
| 2026-06-16 | v0.0.38 推送 GitHub：commit `8b8ae1c`（14 文件/+1311）+ 带注释 tag `v0.0.38`，origin/main 对齐（顺带补推 a3a1ea9 版本基准提交）。纠正一处误判：单跑 `mypy lightshield/`（缺 types-requests 存根）误报 `web_vuln_scanner.py:496` 的 `# type: ignore[override]` 多余，删后被 pre-commit 拦下；该 ignore 在真实门禁（pre-commit mypy + types-requests）中**必需**，已还原，PROGRESS「mypy 全零」本就成立。附带清理 `nuclei_adapter.py` 无效 `# noqa: R1/R3` → 普通注释。pre-commit 全门禁通过 |
| 2026-06-20 | v0.0.39 OpenAPI + i18n 交付（ZCode + Hermes + CC 集成）：ZCode→`static/openapi.json`(8 端点)+自托管 Swagger UI(`/docs`)+`docs/API.md`；Hermes→`zh-CN`/`en-US` locale（中英对称）；CC→`i18n.py`（locale 加载/翻译/语言协商/JS 桥扁平字典）+ 6 个 Web 模板接入 `t()`/`window.t`/`window.tf` + `/lang/<code>` 切换（白名单+同源重定向防护）+ `harden_page` 服务端 translate + 版本 0.0.38→0.0.39 三处。新增 `tests/test_web_i18n.py`（23 条）。687 passed / 1 skip / ruff+mypy+bandit+Gate A 全过。阶段三 2/2 ✅ |
