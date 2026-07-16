# LightShield 决策日志（Decision Log）

> **用途**：集中记录项目从 v0.0.01 至今的所有重大技术与架构决策，便于追溯遗留问题、审计决策链路、理解"为什么当时这么做"。
> **维护规则**：每次做出影响架构/Agent 分工/合规/外部依赖的决策后，在此文件追加一条 + 更新速查表。
> **最后更新**：2026-07-16 | **条目数**：29

---

## 速查表

| # | 日期 | 版本 | 决策 | 类型 | 状态 |
|:--:|------|:--:|------|:--:|:--:|
| 1 | 2026-06-08 | pre-v0.0.01 | 项目定位：轻量安全自检+加固工具 | 产品 | ✅ |
| 2 | 2026-06-08 | pre-v0.0.01 | 方案 B：Nmap + 自研脚本 + MSF scanner 子集 | 架构 | ✅ |
| 3 | 2026-06-08 | pre-v0.0.01 | 合规红线 R1-R6 | 合规 | ✅ |
| 4 | 2026-06-08 | pre-v0.0.01 | 适配器模式架构 | 架构 | ✅ |
| 5 | 2026-06-08 | pre-v0.0.01 | 版本编号铁律 v0.0.XX | 流程 | ✅ |
| 6 | 2026-06-08 | pre-v0.0.01 | 外部资源评估（hackingtool/MSF/agency-agents/MetaGPT） | 依赖 | ✅ |
| 7 | 2026-06-09 | v0.0.01 | 6 Agent 开发集群建立 | 集群 | ✅ |
| 8 | 2026-06-09 | v0.0.01 | 护栏体系 v1.0（五道门禁+六大铁律） | 流程 | ✅ |
| 9 | 2026-06-16 | v0.0.37 | 模型优势对齐——CC 切 Opus 4.8，9 Agent 按底层模型重排 | 集群 | 🔄 已演进 |
| 10 | 2026-06-17 | v0.0.38 | 沙箱执行器：Docker 隔离（--network none + 只读 + no-new-privileges） | 架构 | ✅ |
| 11 | 2026-06-20 | v0.0.39 | Swagger UI 大文件白名单（vendored 资产豁免 pre-commit） | 流程 | ✅ |
| 12 | 2026-06-25 | v0.0.40 | 集群精简 9→6 Agent（Reasonix/CodeWhale/Hermes/Qoder IDE 退役） | 集群 | ✅ |
| 13 | 2026-06-25 | v0.0.40 | Kimi 加入为第 6 Agent（双模式·K2.7-code+K2.6） | 集群 | ✅ |
| 14 | 2026-06-25 | v0.0.40 | ZCode 角色升级：文档→长程主力+全量审查→特种部队 | 集群 | ✅ |
| 15 | 2026-06-25 | v0.0.40 | QoderWork 角色升级：VM+前端→高级开发主力（Code Arena #2） | 集群 | ✅ |
| 16 | 2026-06-25 | v0.0.40 | CC 切回 DeepSeek-V4-Pro | 集群 | 🔄 #29 推翻 |
| 17 | 2026-06-26 | v0.0.40 | ADR-v040：加固执行基底——真机 HostExecutor（非 Docker） | 架构 | ✅ |
| 18 | 2026-06-26 | v0.0.40 | 八荣八耻→十荣十耻 Agent 行为准则（翻车模式+四问自检） | 流程 | 🔄 v1.3 |
| 19 | 2026-06-26 | v0.0.40 | 三阶段全项目组合排查审查体系（Kimi+ZCode→Codex→CC+QW） | 流程 | ✅ |
| 20 | 2026-06-27 | v0.0.40 | Agent 替补体系建立（三级递补：同模型→同能力→CC 兜底） | 集群 | ✅ |
| 21 | 2026-06-27 | v0.0.40 | ZCode 架构二审制度（每里程碑·GLM-5.2 审 CC 架构决策全局一致性） | 流程 | ✅ |
| 22 | 2026-06-28 | v0.0.42 | CodeBuddy A/B 双模式（Mode B: WorkBuddy CLI 加入集群） | 集群 | ✅ |
| 23 | 2026-06-29 | v0.0.43 | Debate 对抗审查模式（Codex↔Kimi 五步循环·安全关键模块） | 流程 | 🔄 |
| 24 | 2026-06-30 | v0.0.44 | ADR-v043：Web-Core 门面重构（解耦 Flask 依赖） | 架构 | ✅ |
| 25 | 2026-07-08 | v0.0.50 | Firecrawl 拒绝引入（AGPL-3.0 冲突+场景不匹配+合规红线） | 依赖 | ✅ |
| 26 | 2026-07-08 | v0.0.50 | v0.0.50–v0.0.60 十一版本迭代规划（三阶段+六项硬约束） | 规划 | ✅ |
| 27 | 2026-07-08 | v0.0.52 | ADR×3：离线定义 + R2 多目标重设计 + WSGI 迁移方案 | 架构 | ⚠️ 部分退回/阻断 |
| 28 | 2026-07-11 | v0.0.52 | Codex GPT-5.6-Sol 升级 + 分级派遣体系（🔪 手术刀定位） | 集群 | ✅ |
| 29 | 2026-07-16 | v0.0.52+ | CC 切回 Opus 4.8（原生模型）+ 扩权直做（推翻 #16） | 集群 | ✅ |

---

## 详细记录

### #1 · 2026-06-08 · pre-v0.0.01 · 项目定位

**决策**：LightShield = 面向初创企业 & 个人站长的开源轻量化安全自检 + 防御加固工具（MIT 协议）

**背景**：评估 hackingtool（185+ 工具）作为技术底座时发现 75%+ 模块为纯攻击向，部署包 5-10GB，与"轻盾"定位冲突。

**后果**：
- 部署包目标 ≤ 500MB
- 禁止引入攻击/漏洞利用/DDoS/后门类代码
- 合规红线 R1-R6 成为不可逾越的底线

**参阅**：`CLAUDE.md §一`、`PROJECT_OVERVIEW.md`

---

### #2 · 2026-06-08 · pre-v0.0.01 · 方案 B 技术底座

**决策**：选择方案 B（Nmap + 自研 Python 安全脚本 + MSF auxiliary/scanner 子集），否决方案 A（全量引入 hackingtool）

**方案对比**：

| 维度 | 方案 A（hackingtool 全量） | 方案 B（Nmap+自研+MSF scanner） |
|------|------|------|
| 攻击模块占比 | 75%+ 需剔除 | 0%（仅扫描/检测） |
| 部署包大小 | 5-10GB | ≤500MB |
| 合规风险 | 高（源码含攻击代码） | 低（白名单受控） |
| 可维护性 | 低（依赖爆炸） | 高（适配器模式统一接口） |

**后果**：自研脚本从零独立实现，hackingtool 仅作设计参考（检测逻辑思路借鉴，非代码复用）

**参阅**：`CLAUDE.md §二-§三`、`PROJECT_OVERVIEW.md §第三章`

---

### #3 · 2026-06-08 · pre-v0.0.01 · 合规红线 R1-R6

**决策**：六条不可逾越的代码安全边界：

| 编号 | 红线 |
|:--:|------|
| R1 | 禁止对外主动攻击（任何 exploit/payload 模块） |
| R2 | 禁止批量扫描公网 IP 段（仅单 IP/域名） |
| R3 | 禁止远控/后门/木马（关键字扫描） |
| R4 | 仅允许自查自有资产（启动弹窗确认） |
| R5 | MSF 调用限制（仅 auxiliary/scanner/，白名单机制） |
| R6 | 扫描频率限制（并发≤20，间隔≥5秒） |

**后果**：所有代码变更必须通过 Gate A 合规扫描（pre-commit hook 自动执行关键字/MSF/IP 检查）

**参阅**：`CLAUDE.md §五`、`.githooks/pre-commit`

---

### #4 · 2026-06-08 · pre-v0.0.01 · 适配器模式架构

**决策**：所有扫描能力通过 `BaseAdapter` 抽象基类统一接口。核心调度器不直接依赖具体工具——新增能力只需新增 Adapter，不修改核心逻辑。

**架构分层**：交互层 → 核心调度层 → 能力适配层（Adapters） → 规则引擎层 → 日志 & 报告层

**后果**：为未来扩展预留切换机制（轻盾→重盾：Nmap→OpenVAS、JSON→STIX/TAXII、Markdown→PDF/HTML）

**参阅**：`CLAUDE.md §四`、`lightshield/adapters/base.py`

---

### #5 · 2026-06-08 · pre-v0.0.01 · 版本编号铁律

**决策**：LightShield 只使用 `v0.0.XX` 纯线性增长。禁止 `v0.1.0`/`v0.2.0`/`v0.3.1` 等合成格式。里程碑仅用于 GitHub Release，本质仍是 `v0.0.XX`。

**背景**：v0.0.37 时期发现历史版本使用了错误的编号格式（v0.3.0/v0.3.5 等），统一回改为 v0.0.XX。

**后果**：2026-06-15 执行版本号补齐 + CHANGELOG 规范化。v1.0.0 尝试于 v0.0.49 被否决并回滚（版本跳号违规）。

**参阅**：`CLAUDE.md §一-B`

---

### #6 · 2026-06-08 · pre-v0.0.01 · 外部资源评估

**决策**：对四个外部项目的采用/拒绝裁定：

| 项目 | 裁定 | 理由 |
|------|:--:|------|
| hackingtool | ❌ 不引入（仅设计参考） | 75%+ 攻击模块，合规不可控 |
| Metasploit | ✅ 运行时依赖（白名单受控） | auxiliary/scanner 子集，通过 MSF Adapter 调用 |
| agency-agents | ✅ 开发辅助 | ~150 Agent 人格定义，用于开发流程非产品集成 |
| MetaGPT | ❌ 不采用 | 缺乏网安特异性，合规不可控，代码质量不可控 |

**后续**（2026-07-08）：Firecrawl 同样被拒绝——AGPL-3.0 冲突 + Web 爬取与安全自检场景不匹配 + 违背"离线优先"身份。

**参阅**：`CLAUDE.md §二`、`PROGRESS.md 审计日志 2026-07-08`

---

### #7 · 2026-06-09 · v0.0.01 · 6 Agent 开发集群建立

**决策**：建立多 Agent 开发集群，Claude Code 担任架构师+编排器+安全终审。初始 9 Agent（含 Reasonix/CodeWhale/Hermes/Qoder IDE）。

**设计原则**：
- 每个 Agent 通过任务文件下发独立模块
- 并行执行 + 集中集成
- 跨模型审查（不同模型视角消除同源盲区）

**后果**：后续经历 3 次重大集群调整（#12 精简 9→6、#13 Kimi 加入、#22 CodeBuddy A/B 双模式）。详见下。

**参阅**：`CLAUDE.md §零-B`、`.cluster/CLUSTER.md`

---

### #8 · 2026-06-09 · v0.0.01 · 护栏体系 v1.0

**决策**：建立五道质量门禁（Gate A 合规→Gate B 范围→Gate C 质量→Gate D 冲突→Gate E 回归）+ 六大铁律。

**六大铁律**：不盲从 / 不脑补 / 实事求是 / 可落地 / 确认再开工 / 理解再改

**后续演进**：
- v1.1（2026-06-29）：新增 MCP 安全层 + 提示词注入防护
- v1.2（2026-06-30）：八荣八耻→十荣十耻 + 翻车模式七种 + Commit 前四问自检
- v1.3（2026-07-02）：Goal Drift 五模式六反制 + 注意力管理 + 6 Agent 全分发

**参阅**：`.guardrails/AGENT_CODE_OF_CONDUCT.md`、`.guardrails/QUALITY_GATES.md`

---

### #9 · 2026-06-16 · v0.0.37 · 模型优势对齐

**决策**：CC 切 Opus 4.8 回归"编排+架构+安全终审"，9 Agent 按底层模型编码能力重新分配任务。Reasonix 升默认实现主力；CodeWhale 升每版本强制独立审查。

**后续**：此配置在 #12 集群精简时被替换（CC 切回 DS-V4-Pro、3 Agent 退役）。核心原则"模型优势对齐"保留并演化为 #28 分级派遣体系。

**参阅**：`.cluster/CLUSTER.md §九 审计日志 2026-06-16`、commit `b071423`

---

### #10 · 2026-06-17 · v0.0.38 · 沙箱执行器

**决策**：加固脚本执行必须经过 Docker 沙箱隔离——`--network none`（无网络）+ 资源限制（CPU/Mem）+ 只读挂载 + `no-new-privileges`。执行前二次确认。

**后果**：自动加固闭环（v0.0.40）以此为基础；沙箱安全边界后续纳入 Debate 对抗审查适用范围。

**参阅**：`lightshield/sandbox/`、`CLAUDE.md §七 v0.0.38`

---

### #11 · 2026-06-20 · v0.0.39 · Swagger UI 大文件白名单

**决策**：Swagger UI bundle（≈1.49MB）超 pre-commit 500KB 门禁。裁定：「入库 + 门禁加白名单」——pre-commit 顶层全局 `exclude: ^lightshield/web/static/vendor/`。自研源码仍受 500KB + 全部卫生约束。

**后果**：建立 vendored assets vs self-developed code 的治理边界。Gate A 独立 bash 不受 exclude 影响。

**参阅**：`PROGRESS.md 审计日志 2026-06-21`、commit `aebaeee`

---

### #12 · 2026-06-25 · v0.0.40 · 集群精简 9→6

**决策**：退役 3 Agent + 合并 1 Agent：

| Agent | 命运 | 替代 |
|-------|:--:|------|
| Reasonix | 🪦 退役 | CodeBuddy（DS V4-Pro） |
| CodeWhale | 🪦 退役 | CC（审查清单）+ Codex（交叉审） |
| Hermes | 🪦 退役 | CodeBuddy（DS Flash） |
| Qoder IDE | 🔀 合并 | QoderWork 模式 A（同模型 Qwen-3.7-Max） |

**理由**：同模型零能力损失——退役 Agent 的底层模型已存在于保留 Agent 中。

**后果**：集群从 9 Agent 降至 5 + 🆕 Kimi 加入 = 6 Agent。

**参阅**：`.cluster/CLUSTER.md §九 审计日志 2026-06-25`

---

### #13 · 2026-06-25 · v0.0.40 · Kimi 加入集群

**决策**：Kimi 统一 Agent（K2.7-code + K2.6 双模式）作为第 6 Agent 加入集群。

**角色**：
- 模式 A（K2.7-code）：代码审查 + 深度调试 + MCP 工具链（MCP 81.1 集群最强）
- 模式 B（K2.6）：桌面自动化 + Web E2E + 300 子 Agent 并行

**关键价值**：Kimi 是集群**唯一与所有其他 Agent 模型不同的审查者**（Kimi ≠ DS ≠ GPT ≠ Qwen ≠ GLM）——填补 CodeWhale 退役后"同源盲区"的审查缺口。

**参阅**：`.cluster/CLUSTER.md §3.4`、`KIMI.md`

---

### #14 · 2026-06-25 · v0.0.40 · ZCode 角色升级

**决策**：ZCode/GLM-5.2 从"文档自动化（去留待议）"→"🏗️ 长程主力实现 + 全量代码审查"→"🎯 高级开发·特种部队（与 Codex 同级）"。

**依据**：GLM-5.2 实测数据——Code Arena #2（1595）超 GPT-5.5、FrontierSWE 与 Opus 差距 <1%、Design Arena #1 全球、AIME 99.2 超 Opus。1M 上下文实际可用。

**约束**：配额消耗高/速度慢 → 一般任务不轻易使用——关键时刻的杀手锏。

**参阅**：`.cluster/CLUSTER.md §3.6 + §八`

---

### #15 · 2026-06-25 · v0.0.40 · QoderWork 角色升级

**决策**：QoderWork/Qwen-3.7-Max 从"VM 执行+前端 UI"→"🏗️ 高级开发主力"。

**依据**：Qwen-3.7-Max 实测——Code Arena #2（1541）超 GPT-5.5、SWE-Multilingual 78.4 全球纪录、IFBench 81.2 指令遵循新高、35h 无人值守 1158 次工具调用。

**认知偏差修正**：此前的"VM+前端"定位严重低估了 Qwen-3.7-Max 的编码能力。

**参阅**：`.cluster/CLUSTER.md §3.5`

---

### #16 · 2026-06-25 · v0.0.40 · CC 切回 DeepSeek-V4-Pro

**决策**：CC 从 Opus 4.8 切回 DeepSeek-V4-Pro。

**理由**：Opus 4.8 推理速度慢 + 成本高 + 对编排/架构任务的能力溢出（不需要最高推理深度）。DS-V4-Pro 速度最快、性价比最高——更适合 CC 的高频编排角色。

**参阅**：`CLAUDE.md §零-B`

---

### #17 · 2026-06-26 · v0.0.40 · ADR-v040：加固执行基底

**决策**：加固脚本在**真机本地执行**（HostExecutor），而非 Docker 容器内执行。原因：加固操作（防火墙规则/服务管理/注册表）需要 OS 级权限，容器内执行 = 加固容器而非宿主机。

**执行模式**：DRY_RUN（预检报告·不执行） / APPLY（真机执行·二次确认 + 超时 + 审计日志）

**参阅**：`docs/adr-v040-execution-substrate.md`

---

### #18 · 2026-06-26 · v0.0.40 · 十荣十耻行为准则

**决策**：建立 Agent 行为准则 v1.0（八荣八耻）→ v1.1（九荣九耻·新增 MCP 安全）→ v1.2（十荣十耻·新增"以猜测试错为耻，以根因排错为荣"）。

**配套机制**：七种翻车模式（Kitchen Sink/Wrong Abstraction/Optimistic Path/Runaway Refactor/知识幻觉/风格漂移/隐式耦合破坏）+ Commit 前四问自检（范围/影响/覆盖/差异）。

**来源融合**：ZEEKR ARK OS 2 十荣十耻 v3.7.2 + Karpathy 十条军规 + LightShield 独有 MCP 安全层。

**参阅**：`.guardrails/AGENT_CODE_OF_CONDUCT.md`

---

### #19 · 2026-06-26 · v0.0.40 · 三阶段全项目组合排查审查体系

**决策**：每里程碑版本封版前执行一轮三阶段审计：

```
Phase 1: 发现（并行）→ Kimi 深度 BUG + ZCode 屎山+耦合
Phase 2: 验证（集中）→ Codex 可行性边界·反证法
Phase 3: 修复（集中）→ CC 判定 + QoderWork VM 验证
```

**与常规审查的区别**：常规 = 每次 commit/版本·局部·审"改动对不对"；三阶段 = 每里程碑·全局·审"哪里有债/哪里会炸/哪里该重构"

**参阅**：`.cluster/CLUSTER.md §3.7`

---

### #20 · 2026-06-27 · v0.0.40 · Agent 替补体系

**决策**：任何 Agent 下线时按三级递补：L1 同模型优先 → L2 同能力优先 → L3 CC 兜底。

**各 Agent 替补链**：ZCode→CodeBuddy GLM-5.2→Kimi→CC / Codex→Kimi→ZCode→CC / Kimi→ZCode→Codex→CC / QoderWork→CC/CodeBuddy→ZCode→CC

**替补触发规则**：Agent 主动声明不可用；超时 2×；L1 也不可用则依次尝试 L2→L3。替补任务标注 `[替补执行]`。

**参阅**：`.cluster/CLUSTER.md §九`

---

### #21 · 2026-06-27 · v0.0.40 · ZCode 架构二审制度

**决策**：每个里程碑版本，ZCode（GLM-5.2）对 CC 的架构决策做全局一致性二审。

**审什么**（不是审代码）：分层语义自洽性 / ADR vs 实现一致性 / 跨模块接口契约 / 抽象层级合理性 / 遗漏关注点

**为什么是 ZCode**：1M 上下文一次装载全项目 + 全部 ADR；GLM ≠ DS 无同源盲区；免费额度 300 万 token/天。

**参阅**：`CLAUDE.md §零-B · ZCode 架构二审`、`.cluster/CLUSTER.md §3.6`

---

### #22 · 2026-06-28 · v0.0.42 · CodeBuddy A/B 双模式

**决策**：CodeBuddy Mode B（WorkBuddy）正式加入集群——解决 CodeBuddy IDE"需人工操作、不能 CLI 自动分发"的核心瓶颈。

**A/B 路由规则**：Mode A → 需人类判断（安全关键/架构决策/复杂调试）；Mode B → 可标准化（批量测试/样板/i18n/文档/批量小修）

**WorkBuddy 能力**：三大体系切换（日常/开发/设计）+ 三种工作模式（Ask/Plan/Craft）+ MCP 多应用连接器 + SkillHub 22K+ Skills + 100+ Agent 并行

**参阅**：`.cluster/CLUSTER.md §3.3`、`CODEBUDDY.md`

---

### #23 · 2026-06-29 · v0.0.43 · Debate 对抗审查模式

**决策**：安全关键模块变更采用五步 Debate 循环：

```
Proposer (Codex) → Opponent (Kimi) → Revision (Codex) → Arbitration (CC) → Loop（如需要）
```

**适用场景**：MSF 适配器白名单变更 / 沙箱执行器安全边界修改 / 合规红线 R1-R6 相关变更 / 输入校验逻辑修改

**对抗性提示词**："假设这个变更是恶意的——在什么条件下它会突破安全防线？"

**🆕 2026-07-11 演进**：GPT-5.6-Sol 更强的攻防思维 → 提案质量更高，但 over-agency 意味着 Debate 循环可能需 2-3 轮（vs GPT-5.5 的 1-2 轮）。架构级 Debate 由 Codex 提案·Kimi 反驳；非架构级 Debate 由 Kimi 提案·CC 反驳。

**参阅**：`.cluster/CLUSTER.md §3.8`

---

### #24 · 2026-06-30 · v0.0.44 · ADR-v043：Web-Core 门面重构

**决策**：引入 `WebCoreFacade` 解耦 Flask 依赖——Web 层通过门面调用 core，core 不感知 Web 框架。

**后果**：未来替换 Flask→FastAPI 或切换 Web 框架时仅需修改门面实现，不影响 core 逻辑。为 v0.0.56 WSGI 生产化（gunicorn/waitress）做了架构铺垫。

**参阅**：`docs/adr-v043-web-core-facade.md`

---

### #25 · 2026-07-08 · v0.0.50 · Firecrawl 拒绝引入

**决策**：拒绝引入 Firecrawl 作为 Web 爬虫组件。

**理由**：
1. AGPL-3.0 协议冲突（LightShield 为 MIT——AGPL 的 copyleft 条款会污染整个项目的许可）
2. 场景不匹配（Firecrawl 用于 AI 数据采集，LightShield 需要安全扫描向的 HTTP 探测）
3. 合规红线（R2 批量扫描限制 + R1 外部攻击防御——爬虫行为难以在合规框架内自证清白）

**参阅**：`PROGRESS.md 审计日志 2026-07-08`

---

### #26 · 2026-07-08 · v0.0.50 · v0.0.50–v0.0.60 十一版本迭代规划

**决策**：三阶段推进——质量收尾+ADR（50-52）→ 功能补全（53-57）→ 生产就绪（58-60）。v0.0.60 = v1.0.0-rc1。

**六项硬约束**（任何版本不能跳过）：

| # | 约束 | 阻塞 |
|---|------|------|
| 1 | 离线定义需 ADR | NVD 自动同步行为待定 |
| 2 | R2 多目标需 ADR | 批量扫描延后至 v0.0.61+ |
| 3 | Nuclei 过滤机制先行 | 同步功能排在过滤之后 |
| 4 | WSGI 切换先于 API 调优 | 前半不完成不进后半 |
| 5 | Kimi 改审不改编 | E2E 编写→CodeBuddy |
| 6 | QoderWork 均衡负载 | HTML+规则引擎分给 QW |

**🆕 2026-07-11 调整**：v0.0.53 移除 Codex 前端审查 / v0.0.54 新增 Codex 安全审查（Nuclei 过滤器·R1/R5）/ v0.0.55 CVE 从 Codex→QoderWork。

**参阅**：`.guardrails/PROGRESS.md §v0.0.50–v0.0.60`

---

### #27 · 2026-07-08 · v0.0.52 · ADR×3

**2026-07-11 复审状态**：Offline: Accepted；R2 multi-target: Proposed - Changes Required；WSGI: BLOCKED。原有“全部 Accepted”结论已失效，以下内容保留为历史决策正文，不代表可以进入实现。

**决策**：三份架构决策记录（全部 Accepted）：

1. **离线定义**（`adr-v052-offline-definition`）：LightShield"离线"语义 = 纯离线（无需持续联网授权）。DNS 解析为灰色地带（系统级 DNS·非 LightShield 发起的网络请求）
2. **R2 多目标重设计**（`adr-v052-r2-multi-target-redesign`）：从"单一 IP/域名"→ 允许用户自有资产的批量扫描（需显式所有权确认）。公网 IP 段/CIDR 仍禁止
3. **WSGI 迁移**（`adr-v052-wsgi-migration`）：Flask 开发服务器→gunicorn（Linux）/ waitress（Windows）生产 WSGI。pre-fork 模式 + SQLite WAL + SSE→任务状态轮询

**参阅**：`docs/adr-v052-offline-definition.md`、`docs/adr-v052-r2-multi-target-redesign.md`、`docs/adr-v052-wsgi-migration.md`

---

### #28 · 2026-07-11 · v0.0.52 · Codex GPT-5.6-Sol 升级 + 分级派遣体系

**决策**：GPT-5.5→GPT-5.6-Sol + Codex 角色从"安全+前端+审查全干"→🔪 高精度手术刀。

**模型升级数据**：
- Coding Agent Index：76.4 → **80（#1 全球）**
- ExploitBench2：47.9% → **73.5%（+53%）**
- SEC-Bench Pro：45.8% → **71.2%（+55%）**
- 价格：与 GPT-5.5 相同（$5/$30 per 1M tokens）

**分级派遣表**（Codex 仅在这 4 类场景动用）：

| 场景 | 理由 |
|------|------|
| 🔑 安全关键模块实现（sandbox/validator/MSF/R2） | 错误代价最高，精度在这里兑现 |
| 🐛 跨模块集成调试（便宜模型卡住时） | "突破"的真实定义 |
| 🏛️ 新架构设计（无先例·需 ADR 级别） | 推理深度决定设计质量 |
| 🛡️ 发版前关键路径终审 + 安全 commit 审查 | 最后一道关 |

**移交决策**：
- 常规 commit 交叉审查 → Kimi 批量审（攒 5-10 commit 一次）
- 精密前端逻辑 + 常规功能开发 → CodeBuddy DS-V4-Pro
- CVE 扩充（v0.0.55）→ QoderWork

**Codex vs ZCode 正交分工**：🔪 手术刀（最高精度·最高成本） vs ⚔️ 阔剑（最大上下文·最低成本）

**⚠️ 风险与观察点**：
- Sol over-agency（METR 评估作弊率所有公开模型最高）→ CC 必须对所有 Codex 输出做二次验证
- 威慑效应退化（Codex 撤出常规审查后 CC 自检标准可能下降）→ v0.0.53–v0.0.55 观察 Kimi 漏报率
- 复查点：v0.0.55 评估 Kimi 批量审查效果后决定是否固化分工

**ZCode（GLM-5.2）的建议被采纳**：分级派遣代替二元"特种部队"标签；Kimi 接常规审查而非引入 Terra；Codex vs ZCode 手术刀 vs 阔剑·正交不冲突

**参阅**：`CLAUDE.md §零-B`、`.cluster/CLUSTER.md §3.2`、`.guardrails/REVIEW_CHECKLIST.md §六`

---

### #29 · 2026-07-16 · v0.0.52+ · CC 切回 Opus 4.8 + 扩权直做

**决策**：CC 底层模型从 DeepSeek-V4-Pro 切回 **Opus 4.8**（Claude Code 原生模型）。定位保持"架构师 + 编排 + 安全终审"不变，🆕 **扩权**：CC 可直接承接复杂 + 安全关键实现（sandbox/validator/MSF/R2 等），降低对最贵 Agent（Codex $5/$30）的**实现**依赖。

**推翻 #16 的理由**：#16（2026-06-25）以"Opus 溢出/慢/贵"为由切回 DS。本次由用户主动切回 Opus——等于接受"成本换能力"，#16 的成本顾虑不再构成约束。

**定位为何"可变但非被迫"**：
- CC 的编排/架构/安全终审角色从未被 DS 的能力卡住（#9 时 CC=Opus 亦是此角色）→ 升级 Opus 不"强制"改角色
- 但 Opus 4.8 是本文档体系里其他模型对标的基准（GLM 与 Opus <1%、AIME 超 Opus）→ CC 从"集群最快最省但编码上限不如前三"跃入第一梯队 → 解锁"直接吃重活"的**选项**

**三个连带修正**：
1. **评审矩阵同源盲区消除**：原 `REVIEW_CHECKLIST` 判定 CodeBuddy-on-DS 由 CC(DS) 审查 = ❌ 同模型盲区。CC=Opus 后 CC≠DS → 跨模型（✅）；集群无第二个 Opus → CC 审全员皆跨模型
2. **跨模型复审纪律强化**：CC 自写代码仍由不同模型审（安全关键→Codex GPT-5.6-Sol、常规→Kimi K2.7-code，均 ≠ Opus）。CC 写得越多，此门禁越关键、越不可省
3. **ZCode/Codex 措辞校准**：ZCode"集群编码最强"、Codex"唯一能突破"相对 CC 的表述弱化——ZCode 护城河收窄为 1M 上下文 + CLI 异步长任务；Codex 收敛为"最硬骨头 + CC 安全产出复审"。二者相对 CC 的优势从"更强"转为"上下文/模型多样性"

**⚠️ 诚实标注**：GPT-5.6-Sol / GLM-5.2 / Qwen-3.7-Max 等第三方基准数字超出 CC（Opus 4.8）知识范围，无法独立核实；本决策的能力对比在**文档自身框架内** + Opus 4.8 已知能力做出，非为第三方数字背书。

**同步文件**：`CLAUDE.md §零-B`、`.cluster/CLUSTER.md`（header/能力表/§3.1/§3.4/§3.6/§3.7/§四/§八/§九审计/§十）、`.guardrails/REVIEW_CHECKLIST.md`、`.guardrails/PROGRESS.md`

**参阅**：`CLAUDE.md §零-B`、`.cluster/CLUSTER.md §九`、决策 #9（上次 Opus 时期）、#16（被本条推翻）

---

## 待复查决策

以下决策设有明确的复查时间点，到达后需评估是否调整：

| # | 决策 | 复查时间 | 评估指标 |
|:--:|------|:--:|------|
| 28 | Kimi 批量审查替代 Codex 常规审查 | v0.0.55 | Kimi 漏报率 vs Codex 全量审查基准 |
| 26 | v0.0.50–v0.0.60 路线图 | v0.0.55（阶段二中期） | 进度偏差 + Codex 任务是否真正"刀刃" |
| 23 | Debate 循环 2-3 轮 | 每次 Debate 后 | 是否真的需要 3 轮，还是 2 轮足够 |
| 20 | ZCode 下线·CodeBuddy 替补 | ZCode 恢复上线时 | 替补期间产出质量 |
| 29 | CC 扩权直做安全关键实现 | v0.0.55 | CC 自写安全代码的跨模型复审覆盖率 + Codex 调用频率是否真的下降 |

---

## 决策类型分布

```
架构决策（7）： #2 #4 #10 #17 #24 #27（×3）
集群决策（10）：#7 #9 #12 #13 #14 #15 #16 #22 #28 #29
流程决策（7）： #5 #8 #11 #18 #19 #20 #21 #23
产品决策（2）： #1 #26
合规决策（1）： #3
依赖决策（2）： #6 #25
```

---

## 文件索引

| 决策记录位置 | 涵盖决策 |
|------|:--:|
| 本文档 | #1-#29（主索引） |
| `docs/adr-v040-execution-substrate.md` | #17 详细 |
| `docs/adr-v043-web-core-facade.md` | #24 详细 |
| `docs/adr-v052-offline-definition.md` | #27-1 详细 |
| `docs/adr-v052-r2-multi-target-redesign.md` | #27-2 详细 |
| `docs/adr-v052-wsgi-migration.md` | #27-3 详细 |
| `.guardrails/PROGRESS.md` | 全量审计日志（#10-#28） |
| `.cluster/CLUSTER.md §九` | 集群决策（#9 #12-#16 #22 #28 #29） |
| `CLAUDE.md §零-B` | 集群成员 + 编排规则（#7 #12-#16 #28 #29） |
| `.guardrails/AGENT_CODE_OF_CONDUCT.md` | 护栏演进（#8 #18） |
| `.guardrails/REVIEW_CHECKLIST.md §六` | 审查制度（#23 #28） |
| `C:\Users\FJL03\.claude\projects\E--Github-Project-LightShield\memory\` | 会话级决策记录（#25 #26 #28） |
