# 📊 LightShield 开发进度追踪

> **最后更新**：2026-07-08 | **当前版本**：v0.0.51 | **护栏版本**：v1.3（六层防线 + 十荣十耻 + 翻车模式 + 四问自检 + Goal Drift 防护）
> **会话状态**：✅ v0.0.51 全部债务清零完成。1001 passed / 1 skip / 12 门禁全绿。
> **剩余债务**：**0C / 0H / 0M / 0L / 0I** 🎉 全部清零（详见 `docs/audit-v051-debt-resolution.md`）
> **今日交付**：v0.0.50–v0.0.60 十一版本规划 + 报告页前端设计刷新 + v0.0.51 债务清零

---

### 2026-06-29：C-004 / H-005 / H-006 三个 MEDIUM 清零

**交付**：
- `lightshield/web/routes.py`：C-004 — `/api/scan` 新增 scan_types 类型校验（拒绝非 list + 列表元素非 str）
- `lightshield/core.py` `generate_hardening()`：H-005 — 新增 OSPlatform 枚举规范化（`isinstance(os_platform, OSPlatformEnum)` → 取 `.value`）
- `lightshield/core.py` `run_harden_closed_loop()`：H-006 — APPLY 模式强制 `backend="host"`（即使调用方显式传 `docker` 也覆盖 + logger.warning）
- 784 passed / 1 skip / 0 fail — 零回归

---

### 2026-06-29：护栏体系 v1.1 升级（基于多Agent集群日报安全情报）

**交付**：
- `QUALITY_GATES.md`：新增 Gate A-5（MCP 服务器白名单验证 + 5 步审查流程）、Gate C 安全维度新增沙箱逃逸/MCP/提示词注入 3 项检查、新增 §九（沙箱逃逸防御清单 + gVisor/Firecracker 升级路径）、新增 §十（自动化调度：/goal+/schedule+Stop Hooks + Goal Mode 安全约束）
- `AGENT_CODE_OF_CONDUCT.md`：v1.0→v1.1，八荣八耻→九荣九耻，新增第 9 条「以泄露提示为耻，以防范注入为荣」+ 落地机制（MCP 白名单/版本基线/错误消息过滤/图片注入防护）+ 审查对照表更新 + 防线体系图更新（v3.1→v3.2，新增 MCP 安全层）
- `COORDINATION.md`：新增 §八（MCP 安全规则：白名单/注入防护/配置审计）、新增 §九（Agent CLI 最低安全版本基线表，Kimi Code ≥ v0.16.0）、新增 §十（Git Worktree 隔离规范：使用场景/规则/并发控制 3-5 甜点）
- `REVIEW_CHECKLIST.md`：§六新增跨模型审查量化数据（同模型自审缺陷检出率低 40-60%）+ 跨模型审查覆盖率要求表 + 同模型盲区警告 + §七审查对照表新增第 9 条
- `CLUSTER.md`：新增 §3.8 Debate 对抗审查模式（Proposer→Opponent→Revision→Arbitration 五步）+ 适用场景 + 对抗性提示词模板 + 与其他审查模式关系表
- `CLAUDE.md`：护栏版本 v3.0→v3.2，六层防线 + 九荣九耻 + MCP 安全层。编排规则 #4 新增 Debate 模式引用。
- `PROGRESS.md`：本记录。

**安全情报来源**：2026-06-29 多Agent集群日报（MCP 投毒 340+感染 / VM2 沙箱逃逸 CVSS 9.0-10.0 / 提示词侧信道 4 攻击向量 / Kimi Code v0.16.0 凭证修复 / 同模型自审 40-60% 缺陷漏检率 / 五大编排模式 / Goal Mode Token 黑洞案例）

---

### 2026-06-30：护栏体系 v1.2 升级 — 十荣十耻 + 翻车模式 + 四问自检

**来源**：ZEEKR ARK OS 2「十荣十耻」v3.7.2（吸收 Karpathy 内部 Claude.md 十条军规）→ 精华融合进 LightShield 防线体系。

**交付**：
- `AGENT_CODE_OF_CONDUCT.md`：v1.1→v1.2，九荣九耻→**十荣十耻**（新增 #10「以猜测试错为耻，以根因排错为荣」+ 落地机制 + 三次试错闸门）
- 增强现有条目：
  - #4「复用现有」→ 新增 **依赖守门** 三问闸门（stdlib→已有库→维护活跃度）+ commit 说理 + YAGNI 原则
  - #5「主动测试」→ 新增 **影响驱动测试** 流程（grep 所有引用测试文件→全跑，不限于自己模块）+ **异常三问**（参数边界/依赖失败/超时资源）
  - #8「谨慎重构」→ 新增 **改前影响分析**（Find References + Call Hierarchy + 逐调用方确认兼容）+ 七种翻车自检链接
- 🆕 **§三 翻车模式详解**（7 种模式，每种配识别信号+止损策略+恢复路径）：
  ① Kitchen Sink ② Wrong Abstraction ③ Optimistic Path ④ Runaway Refactor
  ⑤ 知识幻觉 ⑥ 风格漂移 ⑦ 隐式耦合破坏（LightShield 最高频翻车预警标注）
- 🆕 **§四 Commit 前四问自检**（破解自我监督盲区——事前自检 + 事后交叉审查互补）：
  ① 范围（diff --stat）② 影响（Find References）③ 覆盖（grep 测试 + 784 tests 基线不降）④ 差异（逐行理解）
  + 与现有五道门禁 + Codex/Kimi 交叉审查的衔接流程图
- 审查对照表更新：#1~#10 全部带 🆕 增强问点
- 防线体系图更新：清晰标注 v1.2 新增模块
- `CLAUDE.md`：护栏版本引用更新 + 文件索引表格更新
- `PROGRESS.md`：本记录 + 版本号更新
- 🆕 **集群 5 Agent 通用认知分发**：在 `CODEX.md`、`CODEBUDDY.md`、`KIMI.md`、`QODERWORK.md`、`ZCODE.md` 的护栏章节各插入统一的「十荣十耻 v1.2 速查表 + 翻车模式七种自检 + Commit 前四问自检」三合一速查块，指向完整准则文档。每个 Agent 会话启动时加载自身 .md 即建立通用行为认知。

**设计原则**：保留 LightShield 独有优势（#9 MCP 安全层 + 项目落地机制 + 置信度标注 + 集群审查体系），从十荣十耻汲取最需要的三块拼图（第 10 条 + 翻车模式 + 四问自检），不做简单替换。**分发策略**：每个 Agent .md 放紧凑速查表（维护轻量），详细落地机制集中在 `AGENT_CODE_OF_CONDUCT.md`（单一事实来源）。

---

### 2026-06-30：A 组 4 MEDIUM 清零

**交付**（全部 784 tests / 0 fail 确认）：

| 编号 | 修复 | 文件 | 改动 |
|:--:|------|------|------|
| **M-013** | 报告归档后 CLI 打印归档后路径 | `lightshield/cli.py` | `_run_hooks()` 返回最终路径（归档后或原始）；scan/harden 两个调用方改为先归档再打印 |
| **M-015** | 加固脚本部分写入失败残留文件清理 | `lightshield/harden/linux_harden.py` `win_harden.py` | 写入异常时清理已落盘的半套文件（防止用户误执行无回滚的加固脚本） |
| **H-008** | Repository 单例按 backend+db_url 缓存 | `lightshield/repository/base.py` | 全局单例 `_repository` → `_repositories: dict` 按 `backend:key` 缓存；同进程混用不同后端各自独立 |
| **CB-C3** | config.to_dict() 用 dataclasses 自动遍历 | `lightshield/config.py` | 手写 15 字段 → `dataclasses.fields()` 自动遍历（跳过 `_` 前缀内部字段）；零维护滞后 |

**债务变化**：11M → **7M**（-4）

---

### 2026-06-30：B 组 3 MEDIUM 清零（规则引擎）

**交付**（全部 784 tests / 0 fail 确认）：

| 编号 | 修复 | 文件 | 改动 |
|:--:|------|------|------|
| **CB-R4** | 严重度排序字典去重为共享常量 | `constants.py` `engine.py` `pdf_writer.py` | 新增 `SEVERITY_ORDER` 常量（含 info）；`recommend_hardening`/`_deduplicate`/`PdfReportWriter` 三处统一引用；修复 engine.py 原定义缺 info 的 bug |
| **CB-D1** | `_match_service_fingerprint` 死语句 → 精确匹配 | `engine.py` | 删除丢弃结果的 `rule.get("service")`/`rule.get("auth_result")` 死调用；实现 service 字段精确过滤（查找 finding 端口对应的服务名，仅匹配规则指定服务的 finding） |
| **CB-D2** | `_match_header` 死语句 → 文档化占位 | `engine.py` | 删除丢弃结果的 `rule.get("header")`/`rule.get("pattern")` 死调用；添加 TODO(v1.0.0) 注释说明待 HTTP 响应头采集就绪后实现精确匹配 |

**债务变化**：7M → **4M**（-3）

---

### 2026-06-30：C-001 多线程加锁（+ 确认 C-002/C-003 已修）

**交付**（784 tests / 0 fail）：

| 编号 | 状态 | 修复 | 文件 |
|:--:|:--:|------|------|
| **C-001** | 🆕 修复 | `_task_results` 新增 `threading.RLock`；`submit_scan`/`_run_scan_async`/`get_scan_status` 全部加锁保护 | `lightshield/core.py` |
| **C-002** | ✅ 已修 (v0.0.43) | `_ensure_ownership` / `_ensure_execute` 已捕获 `EOFError` | `lightshield/cli.py` |
| **C-003** | ✅ 已修 (v0.0.43) | `/api/login` 已加 `isinstance(username, str)` 类型校验 | `lightshield/web/routes.py` |

**债务变化**：4M → **3M**（-1）

**🟠 下一 Agent 交接**：CC 直接可修项已全部清零。剩余 3 MEDIUM 属于 **Web-Core 边界分层穿透**（CB-R1/R2/L1/L2/L3/C1 共 6 项跨层债务，3M+3L），需要下一 Agent 先出 ADR 定义 `core` 门面接口，再逐个治理。

---

### 2026-06-30：v0.0.44 Web-Core 门面重构（全集群流水线）

**流水线**：CC(ADR) → CodeBuddy(GLM-5.2, 架构二审 9 发现) → CC(ADR 修订 F-1~F-7) → QoderWork(实现) → CC(验收)

**交付**（798 tests / 0 fail，+14 新测试）：

| Agent | 产出 | 文件 |
|------|------|------|
| **CC** 🏛️ | ADR 初版 + 二审修订 | `docs/adr-v043-web-core-facade.md`（✅ Accepted） |
| **CodeBuddy** 🔑 (GLM-5.2) | 架构二审报告（9 项发现，F-1~F-7 全部采纳） | `docs/review-v044-codebuddy-arch-review.md` |
| **QoderWork** 🏗️ | 4 门面方法 + web 层改造 + 测试 | `lightshield/core.py` `web/pages.py` `web/routes.py` 等 |

**重构核心**：
- `core.load_scan()` → `ScanResult \| None`（统一项目 dataclass 返回模式）
- `core.get_recommendations()` → 封装 RuleEngine 加载+推荐
- `core.get_scan_history()` → 封装 repository 查询
- `core.os_platform_normalize()` → 统一类型契约，`generate_hardening` 内部调用
- `_reconstruct_scan_result` / `_reconstruct_findings` 从 web 层迁入 core 内部
- Web 层依赖从 5 模块 → 2 模块（core + config + reporter 渲染）

**验收（5 项 grep + 测试）**：
```
grep "from lightshield.repository" lightshield/web/ → 空
grep "from lightshield.rules" lightshield/web/      → 空
grep "from lightshield.adapters" lightshield/web/   → 空
grep "_reconstruct_findings" lightshield/web/       → 空
grep "_reconstruct_scan_result" lightshield/web/    → 空
798 passed / 0 fail / 1 skip
```

**债务清零**：最后 3 MEDIUM（CB-R1/R2/L1）+ 3 LOW（CB-L2/L3/C1）全部解决。**🎉 0C / 0H / 0M。**

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
| **v0.0.40** | 自动加固闭环 + 发布 | **CC**(核心实现) + **QoderWork**(Web页+VM验证) + **CodeBuddy**(i18n) | 🟡 2026-06-26 CC 交付：HostExecutor（真机执行）+ run_harden_closed_loop（7步闭环编排）+ CLi 接线 + 25 条新测试。待完成：QoderWork Web 对比页 + CodeBuddy closed_loop i18n locale + Codex 交叉审查 + CC 集成+tag | 🟡 |

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

## Agent 完成统计（累计 · 2026-06-25 集群精简后）

| Agent | 已完成 | 待完成 | 备注 |
|------|:--:|:--:|------|
| Claude Code | 18 | 1 | v0.0.40 架构/集成；已切回 DeepSeek-V4-Pro；吸收 Hermes 样板职责 + CodeWhale 审查方法论 |
| Codex | 11 | 1 | v0.0.40 HostExecutor+编排（安全关键）；新增 CC 胶水代码交叉审查 |
| CodeBuddy | 2 | 2 | v0.0.40 verify+i18n（两任务）；吸收 Reasonix+Hermes |
| Kimi 🆕 | 0 | 3 | 双模式：模式A(K2.7-code) v0.0.40 闭环全量独立审查 + 安全关键路径复查；模式B(K2.6) v0.0.40 Web E2E 自动化测试 + 部署验证 + 文档截图 |
| QoderWork | 10 | 2 | 🆙 角色升级：从"VM+前端"→"🏗️ 高级开发主力（Code Arena #2 1541 超 GPT-5.5）+ 35h 长程自主 Agent"。v0.0.40 Web 对比页 + Gate E 夹具 |
| ZCode 3.0 | 1 | 0 | 🆙 角色升级：从"文档自动化"→"🎯 高级开发·特种部队（与 Codex 同级，关键时刻动用）"。GLM-5.2 Code Arena #2（1595）、FrontierSWE 与 Opus 差距<1%、Design Arena #1。配额消耗高+速度慢 → 一般任务不轻易使用 |
| ~~Reasonix~~ | ~~6~~ | — | 🪦 2026-06-25 退役 → CodeBuddy (DS V4-Pro) |
| ~~CodeWhale~~ | ~~3~~ | — | 🪦 2026-06-25 退役 → CC + 审查清单 + Codex 交叉审 |
| ~~Hermes~~ | ~~8~~ | — | 🪦 2026-06-25 退役 → CodeBuddy (DS Flash) |
| ~~Qoder IDE~~ | ~~1~~ | — | 🪦 2026-06-25 退役 → QoderWork 模式 A（同模型 Qwen-3.7-Max + 同付费体系） |

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
| 2026-06-21 | v0.0.39 推送 GitHub：commit `aebaeee`（27 文件/+2988-149）+ 带注释 tag `v0.0.39`，origin/main 对齐。**决策点收尾**：自托管 Swagger UI 的 `swagger-ui-bundle.js`（≈1.49MB）超 `check-added-large-files` 500KB 门禁 → 用户决策「入库 + 门禁加白名单」；落地为 pre-commit **顶层全局 `exclude: ^lightshield/web/static/vendor/`**（vendored 资产豁免所有 hook，保持与上游字节一致；**自研源码仍受 500KB + 全部卫生约束**；Gate A 走独立 bash 不受 exclude 影响）。附带接受 ruff 安全修复 `lru_cache(maxsize=None)`→`functools.cache`（i18n.py，语义等价）。687 passed / 1 skip / 五门禁全绿 |
| **2026-06-25** | **集群精简 9→5 Agent**：Reasonix→CodeBuddy(DS V4-Pro)；CodeWhale→CC(审查清单)+Codex(交叉审)；Hermes→CodeBuddy(DS Flash)；Qoder IDE→QoderWork(同模型 Qwen-3.7-Max + 双模式)。CC 切回 DeepSeek-V4-Pro。落盘：全部治理文件更新、4 退役 Agent .md 删除、CODEBUDDY.md/QODERWORK.md 重写、`.guardrails/REVIEW_CHECKLIST.md` 新建。v0.0.40 派工书已改派 |
| **2026-06-25** | **🆕 Kimi 统一 Agent 加入为第 6 Agent**：双模式合入同一 `KIMI.md`——模式 A：Kimi Code (K2.7-code · CLI) 深度调试+独立模型审查+MCP 工具链；模式 B：Kimi Work (K2.6 · 桌面端) 桌面自动化+Web E2E+300 子 Agent 并行+13h 长程执行。模型不同（K2.7-code 代码更强，K2.6 通用旗舰），角色完全不重叠（代码 vs 桌面）。Kimi 是集群唯一不同模型审查者 + 唯一桌面自动化层 |
| **2026-06-25** | **🆙 ZCode 角色重大升级**：从"文档自动化（去留待议）"→"🏗️ 长程主力实现 + 全量代码审查"→"🎯 高级开发·特种部队（与 Codex 同级）"。基于 GLM-5.2 实测（Code Arena #2 1595 超 GPT-5.5、FrontierSWE 差距<1%、Design Arena #1、AIME 99.2 超 Opus、1M 上下文实际可用、"御三家"共识、"无法与 Opus 区分"）。配额消耗高/速度慢 → 一般任务不轻易使用——关键时刻的杀手锏。新建 `ZCODE.md`（项目根），旧 `.cluster/agents/ZCODE.md` 删除 |
| **2026-06-26** | **v0.0.40 全部实现交付（session-end）**：CC 集成 QoderWork Web 对比页（+pages.py + harden_verify.html 348行 + style.css +5 测试）+ CodeBuddy i18n 20键。6 commits 全部门禁通过。771 passed / 1 skip。待 Codex 交叉审查 + tag |
| **2026-06-26** | **八荣八耻防线落地**：新建 `.guardrails/AGENT_CODE_OF_CONDUCT.md`（8 条 Agent 行为准则 + 置信度标注规范 + 审查对照表）；CLAUDE.md 五大铁律→六大铁律（#6 理解再改）；任务文件模板新增「不确定性声明」段；REVIEW_CHECKLIST 新增 §七 八荣八耻审查检查表 |
| **2026-06-26** | **v0.0.40 核心实现**：HostExecutor（跨平台真机执行，Win .bat/.ps1 + Linux .sh）+ run_harden_closed_loop（①-⑦ 7步编排：扫描→推荐→生成→DRY_RUN预检/APPLY真机执行→复扫→验证→汇总）+ CLI --closed-loop/--apply/--confirm-ownership 接线 + _run_dry_run_precheck/_run_apply_and_verify 助理解耦。Gate A 更新：R1_ATTACK_KEYWORDS 新增至 constants.py + 过滤规则。25 条新测试（test_host_executor 15 + test_closed_loop 10）。735 passed / 1 skip / 五门禁全绿 |
| **2026-06-25** | **🆙 QoderWork 角色重大升级**：从"VM 执行+前端 UI"→"🏗️ 高级开发主力（Code Arena #2 1541 超 GPT-5.5）+ 35h 长程自主 Agent"。基于 Qwen-3.7-Max 实测（Code Arena #2 1541 超 GPT-5.5、SWE-Multilingual 78.4 全球纪录、IFBench 81.2 指令遵循新高、35h 无人值守 1158 次工具调用 10x 性能提升）。此为集群 2026-06-25 最大认知偏差修正——Qwen-3.7-Max 是被严重低估的顶级编程模型 |
| **2026-07-08** | **v0.0.51 全部债务清零**：13 LOW + 12 INFO → 0。I-01（VULN-015 描述）+ INFO-001/002（test 注释）+ INFO-003/004（确认已修）+ I-02/I-03（已知悉不修）。历史 LOW-001~006 和 INFO-005~012 确认已在 v0.0.31–v0.0.49 期间解决。1001 tests 基线保持。详见 `docs/audit-v051-debt-resolution.md` |
| **2026-07-08** | **v0.0.50–v0.0.60 迭代规划（修订版 v2）定稿**：三阶段框架 + 六项硬约束修正（R2 ADR / 离线定义 / Nuclei 过滤 / WSGI 先于调优 / Kimi 改审不改编 / QoderWork 负载均衡）。写入 `.guardrails/PROGRESS.md` + `CLAUDE.md`。**报告页前端设计刷新**（severity bar + risk badge 增强 + 双主题同步）同步合入本次会话 |

---

## v0.0.50 — v0.0.60 十一版本迭代规划 🎯

> **总目标**：从 v0.0.49 质量基线 → v0.0.60 (v1.0.0-rc1) 生产就绪候选版本
> **三阶段推进**：质量收尾+ADR → 功能补全 → 生产就绪
> **设计原则**：长期项目不急着封版，合规红线（R1/R2/R5）/ 产品身份定义（离线）/ 技术顺序（WSGI 先于调优）三类约束与版本节奏无关，任何版本都不能跳过。
> **规划定稿日期**：2026-07-08

---

### 阶段一：质量收尾 + 前置决策（v0.0.50–v0.0.52）

> **核心理念**：在加新功能之前把地基扫干净。13 LOW + 12 INFO 带着进 v1.0.0 不像话。三份 ADR 是后续 53-57 的关键路径——不急着写代码，先让决策到位。

| 版本 | 目标 | 关键交付 | Agent | 状态 |
|:--:|------|------|:--:|:--:|
| **v0.0.50** | 覆盖率 85% + 发版 | CodeBuddy 覆盖率交付审查 → CC 验收 → `git tag v0.0.50`。前端设计刷新（severity bar + risk badge）合入 | CC + CodeBuddy | 🟡 |
| **v0.0.51** | LOW + INFO 债务清零 | 13 LOW → 0 + 12 INFO → 0。8 已修复 + 15 前序版本已修 + 2 已知悉不修（I-02/I-03）。全量回归（1001 tests 基线不降） | CC | ✅ |
| **v0.0.52** | ADR 冲刺 | 三份架构决策：① `adr-v052-offline-definition.md`（LightShield "离线"语义选型：纯离线 vs 无需持续联网授权）✅ ② `adr-v052-r2-multi-target-redesign.md`（R2 多目标边界重定义）✅ ③ `adr-v052-wsgi-migration.md`（gunicorn/waitress 生产 WSGI 方案）✅。🆕 **顺序调整**（2026-07-09）：offline 先行→R2 在 offline 约束框架下设计→WSGI 独立收尾 | CC | ✅ |

**阶段一验收标准**：
- 0C / 0H / 0M / **0L / 0I**（全部债务清零）
- 覆盖率 ≥85%
- 三份 ADR **Accepted**（离线 / R2 / WSGI）

---

### 阶段二：功能补全（v0.0.53–v0.0.57）

> **核心理念**：用户最直接感知的价值——报告好看、检测准确。QoderWork（Code Arena #2 1541）从闲置中激活，承接 HTML 报告 + 规则引擎两大实现密集型任务。

| 版本 | 目标 | 关键交付 | Agent | 状态 |
|:--:|------|------|:--:|:--:|
| **v0.0.53** | HTML 报告 | 漏洞分布饼图 + 风险趋势线 + 打印友好 CSS。Markdown 保留共存（2 版本迁移通知期后切换默认格式） | **QoderWork**（实现） + Codex（前端审查） | ⬜ |
| **v0.0.54** | 规则引擎 + Nuclei 过滤 | ① 规则库 30+ → 50+ ② **Nuclei 模板白名单过滤器**（passive/detect 放行，exploit/brute 拒绝 + 来源审计日志）——过滤机制必须先行，再开放同步 | **QoderWork**（实现） + CC（合规审查） | ⬜ |
| **v0.0.55** | CVE 扩充 | CVE 105 → 150+ / 组件 26 → 35。NVD 同步行为**取决于 v0.0.52 ADR-B**：纯离线 → `fetch_latest_cves()` 仅手动触发；非持续授权 → 可选 `--auto-sync-cve` | **Codex** | ⬜ |
| **v0.0.56** | WSGI + 性能 | **前半**：gunicorn（Linux）/ waitress（Windows）生产 WSGI + SQLite WAL 模式 + 查询索引。**后半**：API p95 调优（基于真实 WSGI，目标 <100ms）——顺序不能反 | CC | ⬜ |
| **v0.0.57** | 资产清单 | 资产持久化（`AssetRegistry`）+ 多次扫描对比报告（同一资产历次 scan 变化 diff）。**批量多目标扫描不在此版本**——需等待 v0.0.52 ADR-A（R2 重设计）通过后 v0.0.61+ 实现 | **CodeBuddy** + CC | ⬜ |

**阶段二验收标准**：
- HTML 报告可查看（Markdown 仍可用，二者共存）
- 规则 ≥50 条 + Nuclei 白名单过滤器生效
- CVE ≥150 / WSGI 生产可用 / API p95 <100ms
- 资产清单可持久化 + 对比报告可用

---

### 阶段三：生产就绪（v0.0.58–v0.0.60）

> **核心理念**：E2E 验证 → 文档完备 → 合规审计 → RC。Kimi 的不可替代价值是跨模型独立审查——让它审测试覆盖率，不是写测试。

| 版本 | 目标 | 关键交付 | Agent | 状态 |
|:--:|------|------|:--:|:--:|
| **v0.0.58** | E2E 测试 | **编写**：CodeBuddy Mode B（批量 Web/CLI/闭环 E2E 测试生成）→ **审查**：**Kimi**（E2E 覆盖率审查——审核心用户流程是否被测试覆盖，不是审代码） | CodeBuddy → **Kimi**（审查） | ⬜ |
| **v0.0.59** | 双语文档完整 | README 重写 + 开发者指南 + API 参考 + 部署手册 + FAQ（中英双语同步更新） | **Technical Writer** | ⬜ |
| **v0.0.60** | 安全审计 + RC | 全量合规审计（R1-R6）+ **三阶段排查**（Kimi 深度 BUG + ZCode 架构二审 + Codex 可行性验证）+ 依赖漏洞扫描（pip-audit / safety）+ `git tag v1.0.0-rc1` | CC + **全集群** | ⬜ |

**阶段三验收标准**：
- E2E 覆盖全部核心用户流程（经 Kimi 独立审查确认）
- 文档中英双语完整可用
- 合规审计报告通过（0C / 0H / 0M）
- v0.0.60 = v1.0.0-rc1

---

### 集群任务分配总览

```
Agent        v0.0.50  v0.0.51  v0.0.52  v0.0.53  v0.0.54  v0.0.55  v0.0.56  v0.0.57  v0.0.58  v0.0.59  v0.0.60
────────────────────────────────────────────────────────────────────────────────────────────────────────────
Claude Code   验收      ✅      ADR×3    —       合规审     —       ✅      集成      —        —       审计+RC
Codex           —       —        —      前端审     —       ✅       —        —        —        —       交叉审
CodeBuddy     ✅B       —        —        —        —       —        —       ✅B      ✅B(编)    —        —
Kimi            —       —        —        —        —       —        —        —       ✅(审)    —       BUG审
ZCode           —       —        —        —        —       —        —        —        —        —       二审
QoderWork       —       —        —       ✅       ✅        —        —        —        —        —        —
TechWriter      —       —        —        —        —       —        —        —        —       ✅        —
```

---

### 关键约束表（不可跳过的前置条件）

| # | 约束 | 类型 | 触发条件 | 阻塞 |
|---|------|:--:|------|------|
| 1 | **离线定义需要 ADR** | 产品身份 | v0.0.55 之前 | NVD 自动同步行为待定 |
| 2 | **R2 多目标需要 ADR** | 合规 | v0.0.57 之前 | 批量扫描延后至 v0.0.61+ |
| 3 | **Nuclei 过滤机制先行** | 合规 R1/R5 | v0.0.54 内置 | 同步功能排在过滤之后 |
| 4 | **WSGI 切换先于 API 调优** | 技术顺序 | v0.0.56 内部 | 前半不完成不进后半 |
| 5 | **Kimi 改审不改编** | 角色匹配 | v0.0.58 | E2E 编写 → CodeBuddy；Kimi 审覆盖率 |
| 6 | **QoderWork 均衡负载** | 集群效率 | v0.0.53-54 | HTML + 规则引擎分给 QW |

---

### 为什么是这个顺序

1. **债务先清零**（50-52）：在加新功能前把地基扫干净——13 LOW + 12 INFO 带着进 v1.0.0 不像话。三份 ADR 是整个阶段二的关键路径
2. **报告和规则跟上**（53-55）：用户最直接感知的价值——报告好看、检测准确
3. **性能和资产**（56-57）：WSGI 生产化 + 资产清单持久化——为 v1.0.0 的多资产管理奠基
4. **审计和文档收尾**（58-60）：E2E 验证 → 文档完备 → 合规审计 → RC。全集群在 v0.0.60 集结

### 里程碑速查

```
v0.0.10 MVP ──→ v0.0.20 CLI ──→ v0.0.30 Web ──→ v0.0.40 自动加固 ──→ v0.0.49 质量基线
                                                                              │
                                         v0.0.50 覆盖率85% ← 现在在这里        │
                                              │                               │
                                         v0.0.52 ADR×3                        │
                                              │                               │
                                         v0.0.53-57 功能补全                   │
                                              │                               │
                                         v0.0.58-60 生产就绪 ──→ v1.0.0-rc1   │
```
