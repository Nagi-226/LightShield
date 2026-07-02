# Changelog

All notable changes to LightShield 轻盾 will be documented in this file.

格式基于 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)。

> 版本编号统一为单一 `v0.0.XX` 线性序列（不存在 v0.1/0.2/0.3 等格式）。

---

## [0.0.46] - 2026-07-02

### Added

- **覆盖率冲刺**（79.6% → 82% 目标）：
  - `cli.py` 未覆盖区域补测（286 行 → +180 行测试）
  - `core.py` 闭环编排补测（124 行 → +95 行测试）
  - `routes.py` API 端点补测（75 行 → +60 行测试）
  - 建立 mock 基础设施（Nmap / Nuclei / MSF / Docker 外部依赖 mock）
- **Mock 基础设施**（后续新功能测试可复用）：
  - `tests/mocks/nmap_mock.py` — 模拟 Nmap XML 输出
  - `tests/mocks/docker_mock.py` — 模拟 Docker 容器执行
  - `tests/mocks/msf_mock.py` — 模拟 MSF scanner 输出

### Changed

- 版本号 0.0.45 → 0.0.46；测试总数 798 → 855（+57）
- 覆盖率基线：79.6% → 82.3%

---

## [0.0.45] - 2026-07-01

### Added

- **发布准备**（v0.0.44 重构价值兑现）：
  - CHANGELOG 回填 v0.0.41-0.0.44
  - git tag v0.0.44
  - 全量文档同步（README / INSTALL / USAGE / FAQ 更新）
- **3 个 LOW 顺手修复**：
  - M-011：CLI 历史保存异常不再静默吞掉（+ `logger.warning`）
  - M-014：Web 登录失败计数器加锁（`threading.Lock`）
  - M-016：`_safe_dirname` 过滤 `.` / `..` 目录穿越

### Security

- Web 登录失败计数器线程安全（`threading.Lock` 防竞态）
- 报告归档目录名安全过滤（防 `.` / `..` 路径穿越）

### Changed

- 版本号 0.0.44 → 0.0.45
- 债务状态：11 LOW → 8 LOW（3 项顺手清零）

---

## [0.0.44] - 2026-06-30

### Added

- **Web-Core 门面重构**（ADR-v043）：
  - `LightShieldCore` 新增 4 个门面方法：`load_scan()` / `get_recommendations()` / `get_scan_history()` / `os_platform_normalize()`
  - Web 层跨层 import 从 5 个模块（repository/rules/adapters/harden/core）收敛到 2 个（core + config）
  - `_reconstruct_scan_result` / `_reconstruct_findings` 从 web 层迁入 core 内部（消除 CB-R1 重复债务）
  - 三 Agent 流水线：CC(ADR) → CodeBuddy(GLM-5.2, 架构二审) → QoderWork(实现)
- **护栏 v1.2 升级**：九荣九耻 → 十荣十耻 + 翻车模式详解（7 种 + 止损 + 恢复）+ Commit 前四问自检
- **5 Agent 通用认知分发**：CODEX / CODEBUDDY / KIMI / QODERWORK / ZCODE 各获十荣十耻速查块
- 新增 14 条门面方法单元测试 + 3 条 _safe_dirname 边界测试

### Fixed

- **9 MEDIUM 清零**：
  - M-013：报告归档后 CLI 打印归档后路径（`_run_hooks` 返回最终路径）
  - M-015：加固脚本半写残留清理（异常时 `os.remove` 已写入的半套文件）
  - H-008：Repository 单例按 `backend:key` 缓存（替代全局单例）
  - CB-C3：`config.to_dict()` 改为 `dataclasses.fields()` 自动遍历
  - CB-D1：`_match_service_fingerprint` 死语句 → 实现 service 精确过滤
  - CB-D2：`_match_header` 死语句 → 文档化占位 + TODO(v1.0.0)
  - CB-R4：严重度排序字典 3 处重复 → `constants.py` 共享 `SEVERITY_ORDER`（修复 engine.py 缺 info 的 bug）
  - C-001：`_task_results` 多线程加锁（`threading.RLock`）
  - C-002/C-003：已在 v0.0.43 修复，本轮确认
- **3 LOW 顺手修复**：
  - M-011：CLI 历史保存异常不再静默吞掉（+ `logger.warning`）
  - M-014：Web 登录失败计数器加锁（`threading.Lock`）
  - M-016：`_safe_dirname` 过滤 `.` / `..` 目录穿越

### Security

- 门面方法异常语义契约：永不抛异常，失败返回安全默认值（None/空列表）+ 日志
- `generate_hardening` 内部类型规范统一（`os_platform_normalize` 替换重复逻辑）

### Changed

- 版本号 0.0.43 → 0.0.44；测试总数 784 → 798（+14）
- 债务：11 MEDIUM → **0 MEDIUM**（🎉 全部清零）
- Web 层零跨层 import（5 项 grep 验收全部返回空）

---

## [0.0.43] - 2026-06-29

### Added

- **护栏 v1.1 升级**：MCP 安全层（白名单 + 5 步审查 + Unicode 控制字符扫描）
- **九荣九耻** → 新增第 9 条「以泄露提示为耻，以防范注入为荣」
- **Debate 对抗审查模式**（Codex ↔ Kimi 对抗循环）：Proposer → Opponent → Revision → Arbitration 五步

### Fixed

- C-004：`/api/scan` 新增 `scan_types` 类型校验（拒绝非 list + 列表元素非 str）
- H-005：`generate_hardening` 新增 `OSPlatform` 枚举规范化（`isinstance` → `.value`）
- H-006：APPLY 模式强制 `backend="host"`（即使调用方显式传 `docker` 也覆盖 + `logger.warning`）

### Security

- MCP 服务器白名单机制：仅允许经 CC 安全审查的服务器接入
- Agent CLI 最低安全版本基线：Kimi Code ≥ v0.16.0
- 禁止输出暴露系统提示词片段/内部错误堆栈/MCP 工具描述
- 工具输出 URL/图片引用安全过滤（防 Markdown 图片注入）

### Changed

- 版本号 0.0.42 → 0.0.43
- 护栏体系 v3.1 → v3.2（六层防线 + MCP 安全层）

---

## [0.0.42] - 2026-06-28

### Fixed

- Codex 交叉审查反馈：emoji → ASCII（CLI 输出兼容性）+ 低风险代码清理
- 新增 13 条测试覆盖修复点

### Changed

- 版本号 0.0.41 → 0.0.42；测试总数 771 → 784

---

## [0.0.41] - 2026-06-28

### Fixed

- H-007：`HardenResult(action_count=0)` 不再被误判为"全部加固失败"
- H-009：`HostExecutor` 超时仅杀主进程 → 新增进程树清理（Windows job object）
- C-002：CLI `_ensure_ownership` / `_ensure_execute` 捕获 `EOFError`（CI/管道优雅降级）
- C-003：Web `/api/login` 凭证类型校验（拒绝 null/数字等非字符串输入）

### Changed

- 版本号 0.0.40 → 0.0.41

---

## [0.0.40] - 2026-06-26

### Added

- **自动加固闭环**（`run_harden_closed_loop`）：①扫描 → ②推荐 → ③生成脚本 → ④执行（DRY_RUN 或 APPLY）→ ⑤复扫 → ⑥验证 → ⑦汇总
- **HostExecutor**（真机执行后端）：跨平台（Win .bat/.ps1 + Linux .sh）加固脚本执行
- **ADR-v040**（执行基座决策）：APPLY = 真机本地执行，非 VM/特权容器
- **Loop Hooks**：扫描/加固完成 → 报告自动归档 + Bark 通知推送
- **CLI `--closed-loop`** + `--apply` + `--confirm-ownership` 三开关
- **Web 加固验证页**（QoderWork）：加固前后风险对比 UI
- **i18n 20 键补充**（CodeBuddy）：闭环相关 locale
- **三阶段全项目审计**（Kimi Phase 1 + Codex Phase 2 + QoderWork Phase 3）

### Changed

- 版本号 0.0.39 → 0.0.40；测试总数 687 → 771
- 集群精简 9 → 6 Agent（+ Kimi 统一 Agent 双模式加入）

---

## [0.0.39] - 2026-06-20

### Added

- **OpenAPI 3.0.3 文档**（ZCode）：
  - `lightshield/web/static/openapi.json`：覆盖 8 个 REST 端点（登录/登出/扫描提交/扫描状态/SSE 流/报告/加固生成/脚本下载）的完整规范
  - `/docs` 路由 + 自托管 Swagger UI（`static/vendor/swagger-ui/`，无 CDN 依赖；资产缺失时降级为原始规范链接，避免空白页）
  - `docs/API.md`：人读版 REST API 参考文档
- **国际化（i18n）中英双语**（Hermes locale + CC 集成）：
  - `lightshield/web/i18n.py`：locale 加载与缓存、点号键翻译查找（缺失回退默认语言再回退键名）、语言协商（`session` → cookie → `Accept-Language` → 默认）、前端 JS 桥扁平字典
  - `lightshield/web/locales/`：`zh-CN.json` / `en-US.json`（含 `_meta` + 全量 UI 文案，中英键集对称）
  - `/lang/<code>` 语言切换路由：白名单校验 + 同源重定向防护（防开放重定向）
  - 全部 Web 页面（base/login/dashboard/report/harden/docs）接入服务端 `t()` 翻译 + `window.t` / `window.tf` 前端 JS 桥（含占位符插值）
  - 页脚语言切换器 + `<html lang/dir>` 动态属性 + Jinja `context_processor` 统一注入翻译上下文

### Changed

- 版本号 0.0.38 → 0.0.39；测试总数 664 → 687（新增 23 条 i18n / docs 路由 / 中英双语页面测试）

---

## [0.0.38] - 2026-06-15

### Added

- **沙箱执行器**（`lightshield/sandbox/`）：在隔离 Docker 容器中安全执行加固脚本，为 v0.0.40 自动加固闭环铺路
  - `SandboxExecutor` 抽象基类（模板方法：危险闸门 + 脚本校验 + 审计 + 委托给子类）
  - `DockerSandboxExecutor`：`--network none`（R1：容器无网络）+ 内存/CPU/进程数上限 + `--rm` 即用即销毁 + 脚本只读挂载 + `no-new-privileges`
  - `ExecutionResult` / `ExecutionStatus`：结构化执行结果（success/failed/timeout/sandbox_unavailable/rejected/error）
  - 超时强制终止 + best-effort 容器清理（`docker kill`）+ 完整 stdout/stderr 捕获
- **`lightshield harden --execute`**：危险标志，生成后在沙箱中执行加固脚本（需额外输入 `EXECUTE` 二次确认；`--yes-execute` 跳过，供自动化）
- **`core.execute_hardening()`**：核心调度层沙箱执行钩子，`confirm_execute=True` 双确认闸门（对齐 R4）
- 32 条沙箱单元测试（全 mock subprocess，不依赖真实 Docker）

### Security

- 沙箱执行必须显式 `confirm_execute=True`，默认拒绝（防误执行）
- 容器默认无网络（R1 防线：脚本无法对外发起连接/攻击）
- 脚本只读挂载 + 体积上限 1MB + 路径存在性/类型校验

### Changed

- 版本号 0.0.37 → 0.0.38；测试总数 632 → 664

---

## [0.0.31] – [0.0.37] - 2026-06-14 ~ 2026-06-15

> 阶段一「安全加固」+ 阶段二「能力扩展」合并条目（CHANGELOG 回填）。

### Added

- **v0.0.31** 异步扫描：`threading.Thread` 异步 `submit_scan()` + `get_scan_status()` 轮询；Web API 速率限制（滑动窗口）；登录暴力破解防护（失败计数 + 指数退避锁定）
- **v0.0.32** Web 安全加固：Secure cookie（HttpOnly/SameSite/8h 超时）、CSP 头、CORS 白名单（`LS_CORS_ORIGINS`）、`X-Frame-Options`/`X-Content-Type-Options`/`Referrer-Policy`、403 handler
- **v0.0.33** Docker 部署：`Dockerfile` + `docker-compose.yml`，一键 `docker compose up`，SQLite + 报告数据卷持久化
- **v0.0.34** PDF 报告导出：`PdfReportWriter`（fpdf2 + 中文字体自动发现）、Web 下载按钮、CLI `--output-format pdf`
- **v0.0.35** CVE 知识库 70 → 105 条（26 组件，新增 Jenkins/Elasticsearch/K8s/HAProxy）、`fetch_latest_cves()` NVD API 2.0
- **v0.0.36** Nuclei 适配器：`NucleiAdapter(BaseAdapter)`、标签白名单/黑名单（R1 防线）、JSONL 解析、路径/参数注入防护、52 条测试
- **v0.0.37** Web UI 增强：脚本下载 + CSRF + R4 确认、SSE 实时推送 + poll 回退、暗/亮主题切换、仪表板搜索筛选 + URL 同步、42 条 web 测试

### Changed

- 版本编号体系统一为单一 `v0.0.XX` 线性序列
- 集群扩展：Agent 9（ZCode 3.0 + GLM-5.2，知识架构师）加入

---

## [0.0.30] - 2026-06-14

### Added

- **Web 仪表板**：`lightshield serve` 启动 Flask Web 服务，浏览器图形界面操作 LightShield
- **Flask REST API**：6 个端点（`POST /api/login`、`/api/logout`、`/api/scan`、`GET /api/scan/<id>`、`/api/report/<id>`、`POST /api/harden/<id>`）
- **Session 鉴权**：Flask 原生 session（签名 cookie），凭证通过环境变量 `LS_WEB_USERNAME` / `LS_WEB_PASSWORD` 配置
- **CSRF 防护**：自研 csrf.py 模块（`secrets.compare_digest` 时序安全 + X-CSRF-Token header + form hidden input 双通道）
- **4 个 Web 页面**：登录页、仪表板（扫描面板+历史列表）、报告查看器（marked.js Markdown 渲染+SRI hash）、加固建议页（RuleEngine 建议+脚本生成）
- **`lightshield serve`** CLI 子命令：支持 `--host` / `--port` / `--debug` 参数
- `pip install lightshield[web]` 可选依赖（Flask>=3.0）
- **CodeWhale v0.0.30 全量终审**：0 Blocker，5 Suggestion，全部修复（`docs/review-v030-codewhale.md`）
- **Nagi 五大铁律 × 六大合规红线**：全量 R1-R6 逐条核查通过

### Changed

- 版本号 0.0.27 → 0.3.0
- 测试总数 534 → 575
- `lightshield/web/` 子包（6 个 Python 模块 + 5 个 Jinja2 模板 + 1 个 CSS）
- 文档更新：INSTALL/USAGE/FAQ 补充 Web 仪表板章节

---

## [0.0.20] - 2026-06-11

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

## [0.0.10] - 2026-06-09

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

[0.0.38]: https://github.com/Nagi-226/LightShield/compare/v0.0.37...v0.0.38
[0.0.37]: https://github.com/Nagi-226/LightShield/compare/v0.0.30...v0.0.37
[0.0.30]: https://github.com/Nagi-226/LightShield/compare/v0.0.20...v0.0.30
[0.0.20]: https://github.com/Nagi-226/LightShield/compare/v0.0.10...v0.0.20
[0.0.10]: https://github.com/Nagi-226/LightShield/releases/tag/v0.0.10
