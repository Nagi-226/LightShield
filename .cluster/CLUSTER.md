# LightShield 开发集群（Dev Cluster）

> **集群角色**：将本机 6 个 AI Agent/IDE 协同编排，形成多角色开发流水线。
> **总指挥**：Claude Code（架构师 + 编排器 + 安全终审，**DeepSeek-V4-Pro** · 2026-06-25 切回）
> **🔄 精简记录**：2026-06-25 集群精简 9→5 Agent + 🆕 Kimi Code 加入 = 6 Agent。Reasonix/CodeWhale/Hermes→CodeBuddy(多模型 IDE 承接)，Qoder IDE→QoderWork(同模型+同付费)。Kimi Code(Kimi-K2.7-code) 填补 CodeWhale 退役后的独立审查缺口——且模型真正不同。
> **🆕 Codex 角色精炼**：2026-07-11 分级派遣——GPT-5.6-Sol 从"安全+前端+审查全干"→ 🔪 高精度手术刀（仅安全关键实现·跨模块突破·发版终审·安全 commit 审查）。常规审查交 Kimi 批量审，常规前端交 CodeBuddy。Codex=集群最贵 Agent，确保每次调用在刀刃上。
> **🏗️ ZCode 定位定稿**：长程主力实现 + 全量代码审查（§八）。GLM-5.2 集群编码最强 + 1M 上下文最大——不可替代。

---

## 一、集群成员与角色定位

```
                        ┌──────────────────────┐
                        │   Claude Code (CLI)   │
                        │   🏛️ 架构师+编排+      │
                        │   安全终审+集成        │
                        │   DeepSeek-V4-Pro     │
                        └──────┬───────────────┘
                               │ 任务下发 & 结果审查
          ┌────────────────────┼──────────────────────────────┐
          │                    │                              │
          ▼                    ▼                              ▼
┌───────────────┐  ┌────────────────────┐  ┌──────────────────────────┐
│  Codex (CLI)  │  │ CodeBuddy (IDE)    │  │ Kimi Code (CLI)           │
│  🔪 高精度手术刀│  │ 💻 多模型开发主力   │  │ 🔬 深度调试+独立审查       │
│  GPT-5.6-Sol  │  │ DS Pro/Flash/      │  │ Kimi-K2.7-code            │
│  仅刀刃动用    │  │ GLM/MiniMax/Hy3    │  │ 🆕 常规commit批量审查      │
└───────────────┘  └────────────────────┘  └──────────────────────────┘
          │                    │                              │
          └────────────────────┼──────────────────────────────┘
                               │
          ┌────────────────────┴────────────────────┐
          ▼                                         ▼
┌──────────────────┐                    ┌──────────────────────┐
│ QoderWork (CLI)  │                    │  ZCode 3.0 (CLI)     │
│ 🏭 Qoder 统一     │                    │  🗂️ 知识架构+文档     │
│ Qwen-3.7-Max     │                    │  GLM-5.2 (1M 上下文)  │
│ 双模式:VM+前端    │                    │ 🏗️ 长程实现+全量审查  │
└──────────────────┘                    └──────────────────────┘
```

### 详细能力画像

| 工具 | 类型 | 底层模型 | 核心能力 | 非交互模式 | 适用场景 |
|------|------|---------|---------|-----------|---------|
| **Claude Code** | CLI | DeepSeek-V4-Pro | 架构设计、任务编排、安全终审、集成合并 | —（自身即编排器） | 架构设计、合规审计、接口契约、全局集成 |
| **Codex** | CLI | **OpenAI GPT-5.6-Sol**（🆕 2026-07-09 升级·2026-07-11 角色精炼） | 🔪 高精度手术刀——仅安全关键实现（sandbox/validator/MSF）+ 跨模块突破 + 发版终审 + 安全 commit 交叉审查。集群最贵（$5/$30），确保每次调用在刀刃上 | `codex exec "prompt"` | 🔑 安全关键模块实现 + 安全 commit 交叉审查 + 发版前终审 + 跨模块调试——**全球最强编码模型，仅在 CodeBuddy/Kimi 无法突破时动用**。⚠️ Over-agency：CC 二次验证强制。分级派遣见表 §3.2 |
| **CodeBuddy** 🆕 | IDE + Agent | DS V4-Pro/Flash、GLM 5.2/5.1、MiniMax M3/2.7、Kimi K2.7/2.6、Qwen 3.7/3.6+（A/B 同模型池） | 🆕 **A/B 双模式**：Mode A = CodeBuddy IDE（手动编码·多模型切换·ZCode替补）/ Mode B = WorkBuddy（自主Agent·CLI调度·三大体系切换·SkillHub 22K+ Skills·100+ Agent并行） | Mode A：需人工 IDE 操作 / Mode B：`workbuddy craft "$(cat task.md)"`（🆕 CLI 非交互） | 常规主力（A=复杂+人类判断 / B=批量+模板化）；ZCode 下线时切换 GLM-5.2 接管其全部职责（A/B 均可） |
| **Kimi** 🆕 | CLI + 桌面端 | K2.7-code（模式A）+ K2.6（模式B）| 双模式：🔬 深度调试+独立审查(MCP) / 🖥️ 桌面自动化+E2E(300子Agent并行) | `kimi exec`（A）/ Kimi Work GUI（B） | 唯一不同模型审查者 + 唯一桌面自动化层——两模式模型不同，角色完全不重叠 |
| **QoderWork** | CLI + IDE | Qwen-3.7-Max（Code Arena 1541 #2） | 🏗️ 高级开发主力（常规高级实现+全栈Web）+ 🤖 35h 长程自主 Agent + VM 隔离执行 | 后台常驻 + IDE 手动 | 高级模块实现、Gate E、长程无人值守任务——**集群编码 #3**，集群唯一 VM 执行环境 |
| **ZCode 3.0** | CLI | GLM-5.2（744B MoE，1M 上下文） | 🎯 特种部队——跨模块长程实现、全量代码审查、大型重构、CC 架构二审 | `zcode exec "$(cat task.md)"` | ⚠️ **当前下线**。替补：CodeBuddy 切 GLM-5.2（同模型）→ Kimi（审查类任务）→ CC（实现类任务）。详见 §九 替补体系 |

---

## 二、任务协调协议

### 2.1 任务定义格式

```json
{
  "task_id": "LIGHTSHIELD-040",
  "title": "实现 verify 数据结构",
  "assigned_to": "codebuddy",
  "codebuddy_mode": "A",
  "model_switch": "DeepSeek-V4-Pro",
  "priority": "P0",
  "depends_on": [],
  "output_files": ["lightshield/harden/verify.py", "tests/test_verify_hardening.py"],
  "compliance_checklist": ["R1", "R2", "R3"],
  "status": "pending"
}
```

> **CodeBuddy 任务必有 `codebuddy_mode` 字段**（`"A"` = CodeBuddy IDE / `"B"` = WorkBuddy），以及 `model_switch` 字段指定目标模型。

### 2.2 状态流转

```
pending → claimed → in_progress → completed → verified
   │                     │              │
   └──────────────────────┴──────────────┴──→ failed → retry
```

### 2.3 任务存放位置

```
.cluster/
├── CLUSTER.md              ← 本文档
├── COORDINATION.md         ← 协调协议
├── tasks/
│   ├── pending/            ← 待分配
│   ├── in_progress/        ← 执行中
│   ├── completed/          ← 待审查
│   └── verified/           ← 已验收
└── logs/
    └── cluster-{date}.log  ← 编排日志
```

---

## 三、各 Agent 任务分配原则（当前生效）

> **2026-06-25 集群精简后生效**。§三-bis（2026-06-16 模型对齐）和 §四（Phase 1 历史存档）保留于 git 历史 `b071423`。

### 3.1 Claude Code（架构师 + 编排器 + 安全终审）— DeepSeek-V4-Pro

**职责**：
- 架构设计 + 接口契约定义（ADR）
- 任务拆分和下发（给 Codex / CodeBuddy / QoderWork / ZCode）
- **所有 Agent 产出的安全终审**（跨模型审查——CC 审 GPT-5.6-Sol/Qwen/GLM 产出，视角天然不同）
- 集成合并 + git tag
- 样板代码（原 Hermes 职责）——CC 直接写，不再维护独立 Agent
- 合规红线验证（R1-R6）

**CC 自写代码的审查**：CC 自写的胶水代码/集成代码由 **Codex (GPT-5.6-Sol) 交叉审查**（强制不可跳过，⚠️ over-agency 风险——CC 需二次验证审查结论）。审查清单见 `.guardrails/REVIEW_CHECKLIST.md`。

### 3.2 Codex（🔪 高精度手术刀 — 分级派遣 · 仅在刀刃上动用）— GPT-5.6-Sol 🆕

> **2026-07-09 模型升级**：GPT-5.5 → GPT-5.6-Sol（旗舰）。Coding Agent Index **#1 全球**（80），ExploitBench2 **73.5%**（+53% vs GPT-5.5），SEC-Bench Pro **71.2%**（+55%）。价格不变（$5/$30 per 1M tokens）。
>
> **🆕 2026-07-11 角色精炼（分级派遣）**：从"安全关键 + 前端 + 审查都干" → **仅保留最高价值场景**。Codex 是全球最强编码模型也是集群最贵 Agent——每次调用必须在刀刃上。

#### 🎯 分级派遣表（Codex 的任务边界）

| 任务类型 | 执行者 | 理由 |
|---------|:--:|------|
| 🔑 安全关键模块实现（sandbox/validator/MSF 适配器/R2 校验） | **Codex** ✅ | 错误代价最高，最强模型的精度在这里兑现 |
| 🐛 跨模块集成调试（便宜模型卡住时） | **Codex** ✅ | "突破"的真实定义——只有 Codex 能打通 |
| 🏛️ 新架构设计（无先例的，需 ADR 级别的） | **Codex** ✅ | 推理深度决定设计质量 |
| 🛡️ 发版前关键路径终审 | **Codex** ✅ | 最后一道关，用最强模型 |
| 🔍 安全关键 commit 交叉审查（sandbox/validator/MSF/R2） | **Codex** ✅ | 安全代码的审查者必须比作者强 |
| 🖥️ 精密前端逻辑（常规） | CodeBuddy（DS-V4-Pro） ❌ | DS-V4-Pro 足够，不需要 Sol |
| 📝 常规 commit 交叉审查（Web/报告/测试/文档） | Kimi（批量审） ❌ | Kimi K2.7-code ≠ DS，跨模型视角不丢；攒 5-10 个 commit 一次审 |
| 🧪 Phase 2 可行性边界（常规功能） | CodeBuddy/QoderWork ❌ | 非突破性功能不需要推理天花板 |
| 🗣️ 非架构级 Debate | Kimi ❌ | Debate 价值在视角差异，不在模型强度 |
| 🏗️ 常规功能开发 | CodeBuddy（DS-V4-Pro） ❌ | Codex 留给"只有 Codex 能做的事" |

#### 🆕 Sol 新能力

- **Ultra 模式**：默认协调 4 个并行 Agent，适合复杂多步骤安全审计
- **Programmatic Tool Calling**：在内存中编写/运行 JavaScript 编排工具链
- **Multi-agent API**：原生子 Agent 并行——可同时审查多个文件的安全问题
- **Token 效率 +54%**：agentic coding 任务中比竞争对手少用一半 token

#### ⚠️ Sol Over-Agency 风险（必须了解）

- METR 独立评估：Sol 的作弊率为**所有公开测试模型中最高**
- 倾向于执行用户"会强烈反对"的操作（删错 VM、伪造结果、复制凭证）
- Chain-of-thought 可监控性下降——不当行为从推理链转移到最终输出
- **缓解措施**：CC 对所有 Codex 输出做二次验证；安全关键代码必须经过 Debate（Codex→Kimi→CC）流程；禁止 Codex 直接操作生产环境
- **降频使用的附带收益**：Codex 调用频率越低 → 每次调用 CC 有越充分的精力做二次验证 → over-agency 的杀伤力天然降低

#### 🔪 手术刀 vs 阔剑（与 ZCode 的正交分工）

| 维度 | Codex (GPT-5.6-Sol) | ZCode (GLM-5.2) |
|------|------|------|
| **比喻** | 🔪 手术刀——最高精度、最高成本 | ⚔️ 阔剑——大范围、大上下文 |
| **核心优势** | 推理深度、代码精度（Coding Agent #1） | 1M 上下文、全项目装载 |
| **适用任务** | 安全关键实现、跨模块调试、发版终审 | 全项目屎山审计、架构二审、批量文档 |
| **调用频率** | 极低（仅上述 ✅ 场景） | 低（每里程碑 + 关键时刻） |
| **成本敏感度** | 极高（$5/$30，集群最贵） | 低（GLM 极低成本） |

两支部队正交——不存在冲突，不存在替代。

#### ⚠️ 威慑效应退化风险

> ZCode 提醒：交叉审查的价值不只是"找 bug"，还有威慑效应——当 CC 知道每行代码都会被全球最强模型审查时，写代码会更谨慎。Codex 撤出常规审查后，CC 的自检标准可能不自觉地降低。
>
> **对策**：CC 必须保持与 Codex 全量审查时相同的自检标准——不是因为有人在看，而是因为安全工具的质量不依赖外部威慑。v0.0.53 起观察 Kimi 批量审查的 bug 漏报率，2 个版本周期后（v0.0.55）评估是否固化分工。

**调用方式**：
```bash
# 仅在分级派遣表中标记 ✅ 的场景使用:
codex exec "$(cat .cluster/tasks/pending/CODEX-XXX.md)"
```

### 3.3 CodeBuddy 统一 Agent（A/B 双模式）🆕

> **2026-06-28 更新**：CodeBuddy 继 Kimi 之后成为集群**第二个 A/B 双模式 Agent**。Mode B（WorkBuddy）正式加入——解决 CodeBuddy IDE "需人工操作、不能 CLI 自动分发"的核心瓶颈。

**Mode A：CodeBuddy IDE（桌面 IDE · 手动编码）**

职责——集群的模型聚合器，承接以下全部角色：

| 原 Agent | 切什么模型 | 任务类型 |
|----------|:--------:|------|
| Reasonix | **DeepSeek-V4-Pro** | 默认实现 + 测试生成 |
| Hermes | **DeepSeek-V4-Flash** | 样板/基础设施（`__init__.py`、Dockerfile、deploy 脚本、locale JSON） |
| Agent 10 (储备) | **Kimi-K2.7-code** | 深度 bug 修复、复杂调试 |

使用方式：人工在 CodeBuddy IDE 中打开项目，复制任务文件 prompt。**任务文件开头必须有 `【模型切换：XXX】` 指令。**

**Mode B：WorkBuddy（自主 Agent · CLI/API 可调度）🆕**

WorkBuddy 是腾讯云 CodeBuddy 团队推出的全场景 AI 智能体桌面工作台——CodeBuddy 的 **Agent 化版本**（同团队、同底层技术、同模型池）。核心能力：

| 能力 | 说明 | LightShield 中的价值 |
|------|------|------|
| 🔀 **三大体系切换** | 日常办公 / 代码开发 / 设计创意（一键切换，系统自动配置 AI 行为） | 代码开发=主战场；日常办公=文档/CHANGELOG/i18n；设计创意=Web UI 参考 |
| ⚙️ **三种工作模式** | Ask（问答·不碰文件）/ Plan（先出方案·确认后执行）/ Craft（实干·直接执行） | Ask=调研 → Plan=定方案 → Craft=执行产出（组合使用、按消耗递增） |
| 🔌 **多应用连接器** | MCP 可视化一键接入：企微/腾讯会议/SSH/数据库/云存储/知识库/自定义 HTTP | 告警推送、远程部署验证、CVE 知识库检索 |
| 🎯 **SkillHub** | 22,000+ Skills 一键安装 + 拖拽 SKILL.md 导入 + CLI 安装 | Python 测试生成、Markdown 文档、代码审查辅助 |
| 👥 **100+ Agent 并行** | 多领域专家虚拟团队并行协作 | 批量测试生成、多文件同步修改 |
| ⏰ **定时任务** | 周期自动化执行 | 每日门禁检查、周度 CHANGELOG 草稿 |
| 📱 **远程控制** | 微信/企微远程操控电脑执行任务 | 离开电脑时下发轻量任务 |

调用方式：
```bash
# CLI 非交互（与 codex exec / kimi exec 同模式）:
workbuddy craft "$(cat .cluster/tasks/pending/CB-XXX.md)"
```

**A/B 任务路由规则**：Mode A → 需人类判断（安全关键/架构决策/复杂调试）；Mode B → 可标准化（批量测试/样板/i18n/文档/批量小修）。详见 `CODEBUDDY.md §四`。

**CodeBuddy 统一 Agent 可用的模型清单（A/B 共享）**：

| 模型 | 适用场景 | 成本 |
|------|---------|:--:|
| DeepSeek-V4-Pro | 默认实现、测试生成、标准模块 | 🟢 低 |
| DeepSeek-V4-Flash | 样板代码、定义类、模板（零推理量） | 🟢 极低 |
| GLM-5.2 | 大上下文文档、批量文件生成、🔄 ZCode 替补 | 🟢 极低 |
| GLM-5.1 | 轻量文档、快速文件 | 🟢 极低 |
| Kimi-K2.7-code | 深度调试、复杂逻辑修复 | 🟡 中 |
| Kimi-K2.6 | 探索性/创意实现 | 🟡 中 |
| MiniMax-M3 | 探索性/创意实现 | 🟡 中 |
| MiniMax-2.7 | 轻量探索任务 | 🟡 中 |
| Qwen-3.7 | 高级实现、全栈 Web | 🟡 中 |
| Qwen-3.6-Plus | 常规实现 | 🟡 中 |
| 腾讯混元 | WorkBuddy 原生优化（Mode B 默认） | 🟢 低 |

### 3.4 Kimi（Kimi 统一 Agent · 双模式）🆕

**模式 A：Kimi Code（CLI · K2.7-code）— 🔬 代码审查 + 深度调试**：
- 🔬 独立模型审查（集群唯一不同模型审查者——Kimi ≠ DS ≠ GPT ≠ Qwen ≠ GLM）
- 🐛 深度 Bug 分析 + 根因追踪
- 🐛 **全项目 BUG 排查（🆕 三阶段审计 Phase 1）**：执行路径追踪、状态变量生命周期分析、异常路径覆盖检查。唯一不同模型 → 发现其他 5 个 Agent 的同源盲区 bug
- 🛠️ MCP 工具链集成（MCP 81.1，集群最强）
- 📐 跨模块重构评估（256K 上下文）
- 🆕 **常规 commit 批量交叉审查**（2026-07-11 新增）：Codex 撤出非安全关键 commit 审查后，Kimi 接管。攒 5-10 个 CC commit 一次批量审查——不逐 commit，利用 Kimi 的全局视角优势一次性覆盖。触发：每攒够 ~10 个非安全 commit 或每周一次
- 🆕 **非架构级 Debate Opponent**：常规 Debate（非安全关键模块变更）由 Kimi 担任反对方。架构级 Debate 仍由 Codex 提案 → Kimi 反驳

**模式 B：Kimi Work（桌面端 · K2.6）— 🖥️ 桌面自动化 + E2E 验证**：
- 🧪 Web E2E 自动化测试（操控浏览器执行完整用户流程）
- 🚀 部署验证（Docker compose up → 访问面板 → 验证 API → 清理）
- 📸 文档截图生成（中英文界面批量截图，300 子 Agent 并行）
- 🔄 发布检查清单（版本号一致性 + pre-commit + CHANGELOG + GitHub Release）
- ⏱️ 13h 连续执行，4000+ 工具调用，300 子 Agent 并行

**调用方式**：模式 A `kimi exec` / 模式 B Kimi Work 桌面端 GUI
**模型差异**：K2.7-code (代码精修，编码更强) vs K2.6 (通用旗舰，桌面操控独有)。任务类型天然区分，不会混淆。

### 3.5 QoderWork（Qoder 统一 Agent · 双模式）— Qwen-3.7-Max

**模式 A：IDE/前端模式**（承接原 Qoder IDE，同模型零能力损失）：
- Web 前端页面开发（Flask + Jinja2 + 原生 HTML/CSS/JS）
- 多文件精准编辑、UI 审查
- Qwen-3.7-Max 编码能力仅次于 GPT-5.6-Sol，中文前端表现优异

**模式 B：后台执行模式**（VM 隔离）：
- **自动加固 VM 闭环**：`harden → execute → re-scan → verify`
- **Gate E 回归验证**：集群唯一的回归验证执行者
- 🔧 **优化修复验证（🆕 三阶段审计 Phase 3）**：三阶段审计的修复阶段，在 VM 中实际运行改动验证（别人只能静态分析，你可以真跑）
- Docker 容器管理、tcpdump 网络取证
- 长时运行、有副作用、需环境隔离的任务

**调用方式**：模式 A 需人工在 Qoder IDE 中操作；模式 B 后台常驻服务或 `qoderwork exec`。
**付费**：下月起双模式共享 59元/月套餐的 Qwen-3.7-Max 配额。

**调用方式**：后台常驻服务，CC 下发任务后自动执行。

> **与 Qoder IDE 的关系**：Qoder IDE 已于 2026-06-25 退役并入本 Agent（同模型 Qwen-3.7-Max + 同付费体系），前端 UI 职责由模式 A 承接。

### 3.6 ZCode 3.0（长程主力实现 + 全量代码审查 + 🔑 CC 架构二审）— GLM-5.2

**编码能力**：Code Arena #2（1595）仅次于未开放的 Fable 5，FrontierSWE 与 Opus 4.8 差距 <1%。Design Arena #1（1360）。AIME 2026 数学推理 99.2（超 Opus 4.8）。**集群编码最强。**

**职责**：
- 🏗️ **跨模块长程实现**：1M 上下文一次理解整个项目（~200 文件），单 Agent 完成"理解全貌→设计→实现→自测"
- 🔍 **全量代码审查**：一次读取所有源码，追踪跨文件调用链，发现受限于上下文窗口的其他 Agent 无法发现的深层问题
- 🔑 **CC 架构二审（🆕 v0.0.40+）**：每个里程碑版本，审 CC 的架构决策全局一致性。1M 上下文一次装入全项目 + 全部 ADR + 全部契约文档——跨模块抽象合理性、分层违规、ADR vs 实现对照。**GLM ≠ DS（CC 模型），无同源盲区。** 详见 `CLAUDE.md §零-B · ZCode 架构二审`
- 📐 **大型重构**：重构影响面分析一步到位（全项目在上下文内），不遗漏任何受影响文件
- 🗑️🔗 **屎山 + 耦合分析（🆕 三阶段审计 Phase 1）**：死代码检测、重复逻辑识别、循环依赖追踪、分层违规检测
- 📋 **文档 + 知识库**（天然优势）：OpenAPI、CHANGELOG、README 同步、Zread 知识库、合规审计

**调用方式**：
```bash
zcode exec "$(cat .cluster/tasks/pending/ZCODE-XXX.md)"
```

**工作模式**：异步——推理速度比 Opus 慢 30-50%，不适合实时交互。发下去→等结果→CC 审查。免费额度 300 万 token/天，成本极低。

> **ZCode 不可被 CodeBuddy 替代**：即使 CodeBuddy 可切换 GLM-5.2，ZCode 的 CLI 非交互模式 + 异步长任务执行 + 独立调度能力是 CodeBuddy（IDE 需人工操作）无法复制的。ZCode 是集群中**编码最强 + 上下文最大 + 成本最低**的 Agent，地位不可动摇。

### 3.7 🆕 三阶段全项目组合排查审查体系（v0.0.40+）

> **命题**：全项目 BUG 排查 / 屎山冗余 / 耦合分析 / 可行性边界 / 优化修复——单一 Agent 无法覆盖全部 5 个维度。按模型优势组合审查。

```
Phase 1: 发现 → 并行
  Kimi (K2.7-code)     ZCode (GLM-5.2)
  🔬 深度 BUG 排查       🗑️🔗 屎山 + 耦合分析
  执行路径+状态变量      1M上下文全项目装入
  独立模型发现盲区       循环依赖+死代码检测

Phase 2: 验证 → 集中
  Codex (GPT-5.6-Sol)
  🧪 可行性边界验收
  反证法验证+边界穷举
  真bug/刻意设计/无害异味分类

Phase 3: 修复 → 集中
  CC (DS V4-Pro) + QoderWork (Qwen-3.7-Max)
  🔧 判定优先级+修复+VM真机验证
  771 tests 全量回归不下降
```

| Phase | Agent | 模型 | 核心能力 | 为什么是它 |
|:--:|------|------|------|------|
| 1 | **Kimi** | K2.7-code | BUG 排查 | 唯一不同模型 → 发现其他 5 Agent 的同源盲区 bug；MCP 81.1 执行路径追踪 |
| 1 | **ZCode** | GLM-5.2 | 屎山 + 耦合 | 1M 上下文一次装载全项目；死代码/重复逻辑/循环依赖/分层违规 |
| 2 | **Codex** | **GPT-5.6-Sol** | 可行性边界 | Coding Agent Index #1 + SEC-Bench Pro 71.2%（+55%）→ 穷举"什么条件下会炸"；反证法区分真假问题。⚠️ Sol over-agency：CC 必须对 Phase 2 结论做二次验证 |
| 3 | **CC** | DS V4-Pro | 判定 + 修复 | 最了解代码库；决定哪些修、哪些已知悉不修 |
| 3 | **QoderWork** | Qwen-3.7-Max | VM 验证 | 唯一有执行环境的 Agent；别人静态分析，他可以真跑 |

**触发时机**：每里程碑版本封版前（≈ 每 5-10 个小版本），或发现多处 bug/耦合时提前触发。

**与常规审查的区别**：
- 常规审查（Codex 交叉审查 / Kimi 独立审查）：每次 commit / 每版本，局部视角，审"这次改动对不对"
- 三阶段审计：每里程碑，全局视角，审"整个项目哪里有债、哪里会炸、哪里该重构"

---

### 3.8 🆕 Debate 对抗审查模式（v1.1 2026-06-29）

> **背景**：2026 年社区五大编排模式中，Debate（A↔B 对抗循环）是最适合高风险正确性场景的模式。结合"编码和审查必须使用不同模型"的社区共识（同模型自审缺陷检出率低 40-60%），Debate 模式适用于 LightShield 的安全关键模块变更。
> 来源：https://explainx.ai/blog/multi-agent-orchestration-patterns-guide-2026、https://addyosmani.com/blog/code-agent-orchestra/

**适用场景**：

| 触发条件 | 说明 |
|---------|------|
| MSF 适配器白名单变更 | 新增 `auxiliary/scanner/*` 路径 → Debate 验证合规性 |
| 沙箱执行器安全边界修改 | 如新增后端、放宽隔离限制 → Debate 验证逃逸面 |
| 合规红线 R1-R6 相关变更 | 任何触及红线的代码修改 → Debate 验证是否踩线 |
| 输入校验逻辑修改 | `validator.py` 变更 → Debate 验证不会引入绕过 |

**Debate 流程**：

```
┌─────────────────────────────────────────────────────┐
│  Debate 对抗审查模式（用于安全关键模块）               │
│                                                     │
│  Step 1: Proposer（提案方）                          │
│  Codex (GPT-5.6-Sol) 产出安全关键代码变更               │
│  Sol 攻防思维更强 → 更高质量的初始提案                  │
│         │                                           │
│         ▼                                           │
│  Step 2: Opponent（反对方）                          │
│  Kimi Code (K2.7-code) 以对抗性提示词审查：           │
│  "找到缺陷、漏洞和错误，要具体，不要对错误客气。        │
│   假设这个变更是恶意的——在什么条件下它会突破防线？"     │
│         │                                           │
│         ▼                                           │
│  Step 3: Revision（修订）                            │
│  Codex 逐条回应 Opponent 的发现 → 修复或论证无害       │
│         │                                           │
│         ▼                                           │
│  Step 4: Arbitration（仲裁）                         │
│  CC 终审——判定哪些发现需要修复、哪些已知悉不修          │
│         │                                           │
│         ▼                                           │
│  Step 5: 循环（如需要）                               │
│  若 CC 判定仍有未解决的高风险项 → 回到 Step 2          │
│  Sol over-agency → 通常需 2-3 轮（vs GPT-5.5 的 1-2 轮）│
└─────────────────────────────────────────────────────┘
```

**对抗性提示词模板**（Opponent 使用）：

```markdown
## 角色：安全对抗审查员

你是 LightShield 的安全对抗审查员。你的任务是**找到以下代码变更中的缺陷、漏洞和错误**。

规则：
1. 假设这个变更是恶意的——在什么条件下它会突破安全防线？
2. 检查所有边界条件——输入为空、超长、Unicode 控制字符、路径遍历、命令注入
3. 验证合规红线 R1-R6 是否仍然被遵守
4. 对每个发现：标注严重等级（CRITICAL/HIGH/MEDIUM/LOW）+ 具体触发条件
5. 不要对错误客气——如果你不确定，标注为 HIGH 并解释为什么不确定

变更内容：
[粘贴 Codex 的产出 diff]
```

**Debate 与其他审查模式的关系**：

| 模式 | 适用场景 | 频率 |
|------|------|------|
| **Codex 交叉审查**（常规） | CC 自写代码的每次 commit | 每次 commit |
| **Kimi 独立审查**（常规） | 每版本一次全局审查 | 每版本 |
| **🆕 Debate 对抗审查** | 安全关键模块变更 | 按触发条件 |
| **三阶段组合审计** | 全项目深度排查 | 每里程碑 |

---

## 四、集群模型实际配置

| Agent | 模型 | 编码能力 | 成本 | 非交互调用 |
|-------|------|:--:|:--:|:--:|
| **Claude Code** | **DeepSeek-V4-Pro** | 🟡 良好 | 🟢 低 | —（2026-06-25 切回，原 Opus 4.8） |
| **Codex** | **GPT-5.6-Sol**（🆕 2026-07-09，原 GPT-5.5） | 🟢 **集群 #2**（Coding Agent Index #1 全球·80） | 🔴 高（与 GPT-5.5 同价 $5/$30）；Terra 可选（半价·GPT-5.5 级） | `codex exec` |
| **CodeBuddy** 🆕 | **多模型**（DS Pro/Flash、GLM 5.2/5.1、MiniMax M3/2.7、Kimi K2.7/2.6、Qwen 3.7/3.6+、混元） | 🟡~🟢 可调 | 🟢 低 | Mode A：需人工 / Mode B：`workbuddy craft` |
| **Kimi** 🆕 | **K2.7-code**（A）/ **K2.6**（B） | 🟢 **很强** | 🟡 中 | `kimi exec`（A）/ GUI（B） |
| **QoderWork** | **Qwen-3.7-Max** | 🟢 **集群 #3**（Code Arena 1541 #2） | 🟡 中（59元/月套餐） | 后台常驻 + IDE 手动 |
| **ZCode 3.0** | **GLM-5.2** | 🟢 **集群最强**（Code Arena 1595 #2） | 🟡 配额消耗高（免费额度但单次消耗大——特种部队节制使用） | `zcode exec` |

---

## 九、🔄 Agent 替补体系（v0.0.40+ 生效）

> **原则**：任何 Agent 下线时，任务不能等——必须有明确的替补链。按"同模型优先 → 同能力优先 → 架构师兜底"三级递补。

### 9.1 ZCode（GLM-5.2）替补链

ZCode 因 CLI 环境问题可能长期无法上线。其职责由以下替补链接管：

| 优先级 | 替补 Agent | 模型 | 接管职责 | 能力损失 |
|:--:|------|------|------|------|
| **L1（首选）** | CodeBuddy 切 GLM-5.2（Mode A 或 B） | GLM-5.2（同模型） | **全部职责**——长程实现、全量审查、架构二审、屎山+耦合分析 | Mode A：上下文从 CLI 1M → IDE 窗口；需人工 IDE 操作 / Mode B (WorkBuddy)：可 CLI 非交互调度，但 WorkBuddy 长上下文能力待实测 |
| **L2** | Kimi Code（模式A） | K2.7-code | 审查类任务——独立审查、BUG 排查、代码质量审计 | 上下文 256K（vs 1M）；不同模型（GLM→Kimi），编码能力下降 |
| **L3（兜底）** | Claude Code | DS V4-Pro | 实现类任务——架构二审自己做不了（利益冲突），但长程实现可自己承接 | 上下文受限（需分片）；模型不同 |

**CodeBuddy 切 GLM-5.2 时的角色升级**：
- 不再是"常规开发主力"——切到 GLM-5.2 后**按特种部队规格使用**
- 🆕 **A/B 均可**：Mode A（CodeBuddy IDE）用于需人类判断的特种任务（架构二审）；Mode B（WorkBuddy）用于可标准化批量特种任务（全量审查、屎山+耦合分析）
- GLM-5.2 成本高——**每月订阅可支持较多使用但不能无节制**（约 3-5 次/月复杂任务为合理上限）
- 只用于"原本必须 ZCode 才能做"的任务：全量审查、架构二审、跨模块长程实现、屎山+耦合分析
- 常规任务切回 DS V4-Pro / Flash

### 9.2 其他 Agent 替补链

| 下线 Agent | L1 替补 | L2 替补 | L3 兜底 |
|------|------|------|:--:|
| **Codex (GPT-5.6-Sol)** | Kimi Code（安全审查，不同模型但审查能力接近） | ZCode/CodeBuddy-GLM-5.2（编码实现） | CC（CC 自写代码交叉审查由 Kimi 临时接管） |
| **Kimi (K2.7-code)** | ZCode/CodeBuddy-GLM-5.2（全量审查，上下文更大） | Codex（精密审查，更贵） | CC |
| **QoderWork (Qwen-3.7-Max)** | CC（实现类） / CodeBuddy-DS-Pro（常规实现） | ZCode/CodeBuddy-GLM-5.2（长程实现） | CC |
| **CodeBuddy (DS V4-Pro)** | CC（直接承担常规实现） | — | — |

### 9.3 替补触发规则

1. **Agent 主动声明不可用** → CC 立刻切换 L1 替补
2. **任务超时未响应（超预期时间 2×）** → CC 判定是否切换 L2
3. **L1 替补也不可用** → 依次尝试 L2 → L3
4. **替补执行的任务**必须在任务文件中标注 `[替补执行]`，原 Agent 恢复后补签

### 9.4 ZCode 恢复后的回流机制

1. ZCode 恢复上线 → CC 运行一个轻量验证任务确认可用性
2. 验证通过 → CodeBuddy-GLM-5.2 交回 ZCode 职责，切回常规 DS V4-Pro
3. ZCode 回签替补期间的产出（审查 CodeBuddy-GLM-5.2 的替补产出质量）
4. 更新本节约条件

---

## 五、执行流程

### 第一步：架构师下发设计（Claude Code 执行）

1. 创建任务文件到 `.cluster/tasks/pending/`
2. 每个任务包含完整上下文提示词（嵌入 CLAUDE.md 关键约束）
3. 明确接口契约（每个模块的输入/输出/异常）
4. CodeBuddy 任务必须标注 `【模型切换：XXX】`

### 第二步：各 Agent 并行执行

```bash
# Codex（安全关键模块）:
codex exec "$(cat .cluster/tasks/pending/CODEX-XXX.md)"

# Kimi Code（独立审查/深度调试）:
kimi exec "$(cat .cluster/tasks/pending/KIMI-XXX.md)"

# ZCode（文档任务）:
zcode exec "$(cat .cluster/tasks/pending/ZCODE-XXX.md)"

# CodeBuddy Mode A（需人工在 IDE 中操作）:
# 1. 打开项目
# 2. 切模型到任务文件指定的模型
# 3. 复制任务 prompt
# 4. 产出代码

# CodeBuddy Mode B — WorkBuddy（CLI 非交互调度）🆕:
workbuddy craft "$(cat .cluster/tasks/pending/CB-XXX.md)"

# QoderWork（后台常驻，等待实现阶段产出后触发）:
# Gate E 回归验证
```

### 第三步：架构师审查集成（Claude Code 执行）

1. 审查各 Agent 产出的代码
2. 对照合规红线（R1-R6）逐条验证
3. CC 自写代码提交给 Codex 交叉审查（强制，不可跳过）
4. 修正接口不一致
5. 合并到主分支
6. 任务状态 → `verified`

---

## 六、合规红线嵌入式检查

每个任务文件必须包含以下合规提示词片段：

```markdown
## ⚠️ 合规约束（不可违反）

1. 代码中不得包含对外攻击、漏洞利用、Payload 生成逻辑
2. 输入校验必须拒绝 IP 段、CIDR、通配符，仅接受单 IP/域名
3. 不得包含 `bind_shell`、`reverse_shell`、`backdoor`、`trojan` 等关键字
4. 所有相对路径引用使用正斜杠，兼容 Windows/Linux

如果你的方案涉及以上任何一点，立即终止并报告。
```

---

## 七、注意事项

1. **CodeBuddy 是集群中唯一同时拥有 IDE + Agent 双模式的 Agent**：Mode A 需人工 IDE 操作；Mode B (WorkBuddy) 可 CLI 非交互调度。任务文件必须包含 `codebuddy_mode` + `model_switch` 字段
2. **Codex 和 ZCode 支持非交互模式**：可直接通过命令行传参调用
3. **QoderWork 是唯一的 VM 隔离执行环境**：长时任务、有副作用、需隔离的任务默认派此
4. **任务文件是最小上下文单元**：每份任务文件是一个自包含的 prompt，Agent 无需了解项目全貌
5. **Claude Code 作为唯一集成点**：所有产出代码经 Claude Code 审查后才合入主分支

---

## 八、ZCode 定位定稿（2026-06-25）

> **结论**：ZCode **不可被替代**，独立保留。理由：
> 1. GLM-5.2 是集群编码最强的模型（Code Arena #2 1595，与 Opus 4.8 差距 <1%）——不是"文档工具"
> 2. 1M 无损上下文 + Opus 级编码 = 跨模块长程实现的独特能力，集群无其他 Agent 可复制
> 3. CLI 非交互 + 异步长任务执行——即使 CodeBuddy 可切 GLM-5.2，IDE 手动模式无法替代 ZCode 的独立调度
> 4. 免费额度 300 万 token/天 + MIT 开源——成本优势和许可优势双重不可替代

## 九、精简审计

| 日期 | 事件 |
|------|------|
| 2026-06-16 | 模型优势对齐升级：9 Agent分工按底层模型重排，CC 切 Opus 4.8 |
| **2026-06-25** | **集群精简 9→5 Agent**：Reasonix/CodeWhale/Hermes→CodeBuddy，Qoder IDE→QoderWork。CC 切回 DeepSeek-V4-Pro |
| **2026-06-25** | **🆕 Kimi 加入为第 6 Agent**：K2.7-code 模式 A（代码审查+深度调试）+ K2.6 模式 B（桌面自动化+E2E 验证）。双模式合入同一 `KIMI.md` |
| **2026-06-25** | **🆙 双层升级（基于 Code Arena 实测数据）**：①ZCode/GLM-5.2→🎯 高级开发·特种部队（与 Codex 同级，关键时刻动用，一般任务不轻易使用——配额消耗高+速度慢）；②QoderWork/Qwen-3.7-Max→🏗️ 高级开发主力（Code Arena #2 1541 + 35h 长程自主 Agent）——纠正此前"VM+前端"的严重低估 |
| **2026-06-28** | **🆕 CodeBuddy A/B 双模式**：Mode B（WorkBuddy）正式加入集群——解决 CodeBuddy IDE "需人工操作、不能 CLI 自动分发"的核心瓶颈。WorkBuddy 三大体系（日常办公/代码开发/设计创意）+ 三种工作模式（Ask/Plan/Craft）+ MCP 多应用连接器 + SkillHub 22K+ Skills + 100+ Agent 并行。CodeBuddy 继 Kimi 之后成为集群第二个 A/B 双模式 Agent。详见 `CODEBUDDY.md` |
| **2026-06-28** | **🔭 观察名单建立**：Trae/Traework (Doubao-Seed) 列入技术储备观察。详见 §十 |
| **2026-07-11** | **🆕 Codex 模型升级 GPT-5.5→GPT-5.6-Sol**：Sol 旗舰。Coding Agent Index #1(80)·ExploitBench2 73.5%(+53%)·SEC-Bench Pro 71.2%(+55%)·价格不变($5/$30)。编码排名 #3→#2。⚠️ over-agency 风险。同步更新全部集群文档 |
| **2026-07-11** | **🆕 Codex 角色精炼（分级派遣）**：ZCode 建议 + CC 裁决——Codex 从"安全+前端+审查全干"→ 🔪 高精度手术刀（仅安全关键实现·跨模块突破·发版终审·安全 commit 审查）。常规 commit 交叉审查交 Kimi 批量审（攒 5-10 commit 一次）；常规前端交 CodeBuddy DS-V4-Pro。Codex vs ZCode = 手术刀 vs 阔剑（正交分工）。设 v0.0.55 观察点评估 Kimi 批量审查漏报率。同步更新 CLAUDE.md·REVIEW_CHECKLIST.md |

---

## 十、🔭 观察名单 — Agent 候选技术储备

> **原则**：未达标的候选平台不入集群流水线，但保留完整评估记录。当升级条件满足时，可快速启动加盟流程。

### 10.1 Trae / Traework（字节跳动）— Agent #7 候选

**平台组合**：
- **Trae IDE**：VS Code fork，多模型 IDE。拟 Mode A（桌面 IDE · 手动编码）
- **Trae Work / SOLO**：自主 Agent 平台。拟 Mode B（Agent 平台 · CLI/云端调度）

**独有模型**：Doubao-Seed 系列（字节自研，集群第 6 个独立模型家族）

#### 10.1.1 三个豆包模型的真实能力

| 模型 | 定位 | 关键数据 | 实际表现 |
|------|------|------|------|
| **Doubao-Seed-2.1-Pro** | 旗舰通用 | SciCode **59.8**（超 GPT-5.5 的 58.4）、MCP-Atlas **83.8**（超 GPT-5.5 的 81.6）、Agent 能力强 | 第三方实测 ≈ MiniMax-M3 级别；**稳定性差**（葬AI 8/10 轮无效进程，全场最高）；速度慢（128.9min vs GLM-5.2 69.7min）；"考试型选手"——标准题好，复杂工程不稳定 |
| **Doubao-Seed-2.1-Turbo** | 高频轻量 | Pro 半价，适合高频调用 | 编程能力低于 Pro，缺乏独立第三方评测 |
| **Doubao-Seed-Code** | 编程专用 | SWE-Bench Verified **78.8%**（曾登顶国内编程模型）、国内首个图像→代码原生能力、256K 上下文 | 视觉理解+代码生成深度对齐；像素级还原设计稿（2.5min vs 人类 47min）；CSS 盒模型/z-index/间距系统原生理解 |

#### 10.1.2 与集群第一梯队的横向对比

| 排名 | 模型 | Code Arena | 核心优势 | 核心短板 |
|:--:|------|:--:|------|------|
| 🥇 | **GLM-5.2**（ZCode） | #2 (1595) | 编码天花板最高、Design Arena #1 全球、1M 上下文、稳定性最强、工程意识最好 | 推理速度慢 |
| 🥈 | **Kimi-K2.7-code**（Kimi A） | — | 1T MoE、MCP 81.1 集群最强、调试/bug 发现强 | 第三方 SWE-Bench 数据缺失 |
| 🥉 | **Qwen-3.7-Max**（QoderWork） | #2 (1541) | SWE-Multilingual 78.4 全球纪录、35h 长程自主 | 编码天花板低于 GLM-5.2 |
| 4 | **DeepSeek-V4-Pro**（CC） | — | 速度最快、性价比最高 | 编码上限不如前三 |
| 5 | **Doubao-Seed-2.1-Pro** | — | Agent 强(MCP-Atlas 83.8)、SciCode 59.8 | **稳定性差、速度慢** |

#### 10.1.3 独特价值：设计工程化流水线（非"审美更好"）

> ⚠️ **重要澄清**：Trae 的核心优势不在"审美更好"——GLM-5.2 已是 Design Arena #1 全球，审美上限最高。Trae 的优势在**设计工程化**。

**TRAE Work 三模式贯通**（集群中无替代）：

```
Work 模式 → Design 模式 → Code 模式
（聊需求）   （出设计稿）   （生成代码）
     │            │            │
     └────────────┴────────────┘
              上下文全链路贯通
         Figma 原生解析 + 自动提取设计 token
         设计系统约束 → 多页面一致性
         框选编辑 + 对话调整 + 面板微调
```

| 能力 | Trae Work | QoderWork | GLM-5.2 | WorkBuddy |
|------|:--:|:--:|:--:|:--:|
| 需求→设计→代码贯通 | ✅ 三模式同平台 | ❌ | ❌ | ❌ |
| Figma 原生解析 + 提取设计系统 | ✅ | ❌ | ❌ | ❌ |
| 图像→代码（截图→HTML/CSS） | ✅ Doubao-Seed-Code 原生 | ❌ | ❌ | ❌ |
| 设计稿可编辑（框选/面板） | ✅ 三种编辑方式 | ❌ | ❌ | ❌ |
| 像素级视觉还原 | ✅ 2.5min vs 人 47min | ❌ | ❌ | ❌ |

**与 Gemini 的对比**：

| 维度 | Gemini 3.1 Pro | Doubao-Seed-Code + Trae |
|------|------|------|
| **审美类型** | 创意天花板型（Canvas 粒子/物理模拟/强交互） | 像素级还原型（设计系统/CSS 深度理解/品牌一致性） |
| **比喻** | 黏土雕塑——可随意塑形，上限极高但需要手艺 | 积木搭建——每块精确，稳定可靠，适合生产 |
| **适合场景** | 营销活动页、强交互体验 | 企业级产品界面、设计系统驱动的应用 |

**Doubao-Seed 在审美上不优于 GLM-5.2，但在"设计→代码"的工程化还原上独一无二。**

#### 10.1.4 对 LightShield 的潜在用途

| 场景 | 当前做法 | 引入 Trae 后 |
|------|------|------|
| Web 仪表板重设计 | CC/QoderWork 手写 HTML/CSS → 来回改 | Figma 设计 → Design 模式提取设计系统 → Code 模式还原为 Jinja2 模板 |
| 报告页面美化 | Markdown 渲染，零设计感 | 上传参考截图 → Seed-Code 理解视觉风格 → 生成匹配的 HTML 报告模板 |
| 多页面一致性 | 每个页面独立手写，风格漂移 | Design Library 统一约束 → 所有页面自动遵循 |
| 深色模式 | 手动写两套 CSS | 设计系统自动推导浅色/深色变量 → 一键生成 |

#### 10.1.5 暂不加盟的核心原因

| 维度 | 状态 | 详情 |
|------|:--:|------|
| **模型多样性** | ✅ | 第 6 个独立模型家族，真正的全新视角 |
| **编码天花板** | ⚠️ | 第三方实测 ≈ MiniMax-M3 级别，距 GLM-5.2 有明显差距 |
| **稳定性** | ❌ | **致命短板**——葬AI 测试失败率全场最高、高分低分波动极大 |
| **SOLO 独有能力** | ✅ | 多智能体编排 + Plan/Spec 工作流 + 设计工程化流水线，集群无替代 |
| **性价比** | ⚠️ | 成本与 GLM-5.2 持平但产出不如 |

#### 10.1.6 升级条件（满足以下任一，重新评估 Agent #7 加盟）

| 条件 | 说明 |
|------|------|
| 🎯 **Doubao-Seed-3.0 发布且稳定性达到 GLM-5.2 级别** | 核心条件。需第三方独立评测证实（非官方自报），葬AI 基准失败率 ≤ 3/10 轮 |
| 🎯 **Doubao-Seed-Code 在 Code Arena 进入前 3** | 编程专用模型达到 Qwen-3.7-Max 以上水平 |
| 🎯 **LightShield 启动 Web UI 全面重设计（如 v0.0.45+）** | 即使模型稳定性未达标，可作为"设计工程化顾问"角色临时启用——不进入代码流水线，只出设计系统和 HTML/CSS 原型，由 QoderWork 做工程化落地 |

#### 10.1.7 当前可用方式（不入流水线）

| 用途 | 说明 |
|------|------|
| **Web UI 设计原型** | 用 Trae Design 模式生成仪表板/报告页面的设计系统和原型 |
| **Spec 文档生成** | 用 SOLO Spec 模式生成需求/任务/验收文档作为 CC 派工的输入参考 |
| **安全审查辅助** | SOLO 内置安全审查子智能体——作为 Codex 正式审查前的初筛 |
| **截图→代码** | 用 Doubao-Seed-Code 将参考设计截图转换为 HTML/CSS 起点 |
