# LightShield 开发集群（Dev Cluster）

> **集群角色**：将本机 6 个 AI Agent/IDE 协同编排，形成多角色开发流水线。
> **总指挥**：Claude Code（架构师 + 编排器 + 安全终审，**DeepSeek-V4-Pro** · 2026-06-25 切回）
> **🔄 精简记录**：2026-06-25 集群精简 9→5 Agent + 🆕 Kimi Code 加入 = 6 Agent。Reasonix/CodeWhale/Hermes→CodeBuddy(多模型 IDE 承接)，Qoder IDE→QoderWork(同模型+同付费)。Kimi Code(Kimi-K2.7-code) 填补 CodeWhale 退役后的独立审查缺口——且模型真正不同。
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
│  💎 安全关键   │  │ 💻 多模型开发主力   │  │ 🔬 深度调试+独立审查       │
│  GPT-5.5      │  │ DS Pro/Flash/      │  │ Kimi-K2.7-code            │
│               │  │ GLM/MiniMax/Hy3    │  │ 256K 上下文 · MCP 最强     │
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
| **Codex** | CLI | OpenAI GPT-5.5 | 安全关键代码、精密前端逻辑 | `codex exec "prompt"` | 🔑 安全关键模块、CC 自写代码交叉审查 |
| **CodeBuddy** | IDE | DS V4-Pro（可切 Flash/GLM-5.2/MiniMax-M3/Hy3） | 多模型切换：默认实现+测试+样板；🔄 **ZCode 替补（切 GLM-5.2 时）——同模型零能力损失** | —（需人工在 IDE 中操作，任务文件指定模型） | 常规主力；ZCode 下线时切换 GLM-5.2 接管其全部职责 |
| **Kimi** 🆕 | CLI + 桌面端 | K2.7-code（模式A）+ K2.6（模式B）| 双模式：🔬 深度调试+独立审查(MCP) / 🖥️ 桌面自动化+E2E(300子Agent并行) | `kimi exec`（A）/ Kimi Work GUI（B） | 唯一不同模型审查者 + 唯一桌面自动化层——两模式模型不同，角色完全不重叠 |
| **QoderWork** | CLI + IDE | Qwen-3.7-Max（Code Arena 1541 #2，超 GPT-5.5） | 🏗️ 高级开发主力（常规高级实现+全栈Web）+ 🤖 35h 长程自主 Agent + VM 隔离执行 | 后台常驻 + IDE 手动 | 高级模块实现、Gate E、长程无人值守任务——**集群编码 #2，常规高级开发第一选择** |
| **ZCode 3.0** | CLI | GLM-5.2（744B MoE，1M 上下文） | 🎯 特种部队——跨模块长程实现、全量代码审查、大型重构、CC 架构二审 | `zcode exec "$(cat task.md)"` | ⚠️ **当前下线**。替补：CodeBuddy 切 GLM-5.2（同模型）→ Kimi（审查类任务）→ CC（实现类任务）。详见 §九 替补体系 |

---

## 二、任务协调协议

### 2.1 任务定义格式

```json
{
  "task_id": "LIGHTSHIELD-040",
  "title": "实现 verify 数据结构",
  "assigned_to": "codebuddy",
  "model_switch": "DeepSeek-V4-Pro",
  "priority": "P0",
  "depends_on": [],
  "output_files": ["lightshield/harden/verify.py", "tests/test_verify_hardening.py"],
  "compliance_checklist": ["R1", "R2", "R3"],
  "status": "pending"
}
```

> **CodeBuddy 任务必有 `model_switch` 字段**，指定在 IDE 中切换的目标模型。

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
- **所有 Agent 产出的安全终审**（跨模型审查——CC 审 GPT-5.5/Qwen/GLM 产出，视角天然不同）
- 集成合并 + git tag
- 样板代码（原 Hermes 职责）——CC 直接写，不再维护独立 Agent
- 合规红线验证（R1-R6）

**CC 自写代码的审查**：CC 自写的胶水代码/集成代码由 **Codex (GPT-5.5) 交叉审查**（强制不可跳过）。审查清单见 `.guardrails/REVIEW_CHECKLIST.md`。

### 3.2 Codex（安全关键模块 + 交叉审查 + 可行性边界验证）— GPT-5.5

**职责**：
- 🔑 安全关键模块（validator R2 / payload 检测 / CSRF / 鉴权）
- 精密前端逻辑
- **CC 自写代码的交叉审查**（GPT-5.5 独立视角，替代原 CodeWhale 角色）
- 🧪 **可行性边界验收检查（🆕 三阶段审计 Phase 2）**：对 Kimi + ZCode 的 Phase 1 发现做"反证法"验证。穷举边界条件（GPT-5.5 推理天花板），区分"真 bug" vs "刻意设计" vs "无害异味"。输出分级报告
- GPT-5.5 很贵，非安全关键任务不给 Codex

**调用方式**：
```bash
codex exec "$(cat .cluster/tasks/pending/CODEX-XXX.md)"
```

### 3.3 CodeBuddy（多模型 IDE 开发主力）

**职责**——集群的模型聚合器，承接以下全部角色：

| 原 Agent | 切什么模型 | 任务类型 |
|----------|:--------:|------|
| Reasonix | **DeepSeek-V4-Pro** | 默认实现 + 测试生成 |
| Hermes | **DeepSeek-V4-Flash** | 样板/基础设施（`__init__.py`、Dockerfile、deploy 脚本、locale JSON） |
| Agent 10 (储备) | **Kimi-K2.7-code** | 深度 bug 修复、复杂调试 |

**使用方式**：人工在 CodeBuddy IDE 中打开项目，复制任务文件 prompt。**任务文件开头必须有 `【模型切换：XXX】` 指令。**

**CodeBuddy 可用的模型清单**：

| 模型 | 适用场景 | 成本 |
|------|---------|:--:|
| DeepSeek-V4-Pro | 默认实现、测试生成、标准模块 | 🟢 低 |
| DeepSeek-V4-Flash | 样板代码、定义类、模板（零推理量） | 🟢 极低 |
| GLM-5.2 | 大上下文文档、批量文件生成 | 🟢 极低 |
| GLM-5.0-Turbo | 轻量文档、快速文件 | 🟢 极低 |
| Kimi-K2.7-code | 深度调试、复杂逻辑修复 | 🟡 中 |
| MiniMax-M3 | 探索性/创意实现 | 🟡 中 |
| Hy3-Preview | 探索性任务 | 🟡 中 |

### 3.4 Kimi（Kimi 统一 Agent · 双模式）🆕

**模式 A：Kimi Code（CLI · K2.7-code）— 🔬 代码审查 + 深度调试**：
- 🔬 独立模型审查（集群唯一不同模型审查者——Kimi ≠ DS ≠ GPT ≠ Qwen ≠ GLM）
- 🐛 深度 Bug 分析 + 根因追踪
- 🐛 **全项目 BUG 排查（🆕 三阶段审计 Phase 1）**：执行路径追踪、状态变量生命周期分析、异常路径覆盖检查。唯一不同模型 → 发现其他 5 个 Agent 的同源盲区 bug
- 🛠️ MCP 工具链集成（MCP 81.1，集群最强）
- 📐 跨模块重构评估（256K 上下文）

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
- Qwen-3.7-Max 编码能力仅次于 GPT-5.5，中文前端表现优异

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

**编码能力**：Code Arena #2（1595）仅次于未开放的 Fable 5，**超过 GPT-5.5**，FrontierSWE 与 Opus 4.8 差距 <1%。Design Arena #1（1360）。AIME 2026 数学推理 99.2（超 Opus 4.8）。**集群编码最强。**

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
  Codex (GPT-5.5)
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
| 2 | **Codex** | GPT-5.5 | 可行性边界 | 推理天花板 → 穷举"什么条件下会炸"；反证法区分真假问题 |
| 3 | **CC** | DS V4-Pro | 判定 + 修复 | 最了解代码库；决定哪些修、哪些已知悉不修 |
| 3 | **QoderWork** | Qwen-3.7-Max | VM 验证 | 唯一有执行环境的 Agent；别人静态分析，他可以真跑 |

**触发时机**：每里程碑版本封版前（≈ 每 5-10 个小版本），或发现多处 bug/耦合时提前触发。

**与常规审查的区别**：
- 常规审查（Codex 交叉审查 / Kimi 独立审查）：每次 commit / 每版本，局部视角，审"这次改动对不对"
- 三阶段审计：每里程碑，全局视角，审"整个项目哪里有债、哪里会炸、哪里该重构"

---

## 四、集群模型实际配置

| Agent | 模型 | 编码能力 | 成本 | 非交互调用 |
|-------|------|:--:|:--:|:--:|
| **Claude Code** | **DeepSeek-V4-Pro** | 🟡 良好 | 🟢 低 | —（2026-06-25 切回，原 Opus 4.8） |
| **Codex** | **GPT-5.5** | 🟢 **最强** | 🔴 高 | `codex exec` |
| **CodeBuddy** | **多模型**（DS Pro/Flash/GLM/MiniMax/Hy3） | 🟡~🟢 可调 | 🟢 低 | 需人工 |
| **Kimi** 🆕 | **K2.7-code**（A）/ **K2.6**（B） | 🟢 **很强** | 🟡 中 | `kimi exec`（A）/ GUI（B） |
| **QoderWork** | **Qwen-3.7-Max** | 🟢 **集群 #2**（Code Arena 1541 #2，超 GPT-5.5） | 🟡 中（59元/月套餐） | 后台常驻 + IDE 手动 |
| **ZCode 3.0** | **GLM-5.2** | 🟢 **集群最强**（Code Arena 1595 #2） | 🟡 配额消耗高（免费额度但单次消耗大——特种部队节制使用） | `zcode exec` |

---

## 九、🔄 Agent 替补体系（v0.0.40+ 生效）

> **原则**：任何 Agent 下线时，任务不能等——必须有明确的替补链。按"同模型优先 → 同能力优先 → 架构师兜底"三级递补。

### 9.1 ZCode（GLM-5.2）替补链

ZCode 因 CLI 环境问题可能长期无法上线。其职责由以下替补链接管：

| 优先级 | 替补 Agent | 模型 | 接管职责 | 能力损失 |
|:--:|------|------|------|------|
| **L1（首选）** | CodeBuddy 切 GLM-5.2 | GLM-5.2（同模型） | **全部职责**——长程实现、全量审查、架构二审、屎山+耦合分析 | 上下文从 CLI 1M → IDE 内使用（取决于 IDE 实际窗口）；需人工在 IDE 中操作 |
| **L2** | Kimi Code（模式A） | K2.7-code | 审查类任务——独立审查、BUG 排查、代码质量审计 | 上下文 256K（vs 1M）；不同模型（GLM→Kimi），编码能力下降 |
| **L3（兜底）** | Claude Code | DS V4-Pro | 实现类任务——架构二审自己做不了（利益冲突），但长程实现可自己承接 | 上下文受限（需分片）；模型不同 |

**CodeBuddy 切 GLM-5.2 时的角色升级**：
- 不再是"常规开发主力"——切到 GLM-5.2 后**按特种部队规格使用**
- GLM-5.2 成本高——**每月订阅可支持较多使用但不能无节制**（约 3-5 次/月复杂任务为合理上限）
- 只用于"原本必须 ZCode 才能做"的任务：全量审查、架构二审、跨模块长程实现、屎山+耦合分析
- 常规任务切回 DS V4-Pro / Flash

### 9.2 其他 Agent 替补链

| 下线 Agent | L1 替补 | L2 替补 | L3 兜底 |
|------|------|------|:--:|
| **Codex (GPT-5.5)** | Kimi Code（安全审查，不同模型但审查能力接近） | ZCode/CodeBuddy-GLM-5.2（编码实现） | CC |
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

# CodeBuddy（需人工在 IDE 中操作）:
# 1. 打开项目
# 2. 切模型到任务文件指定的模型
# 3. 复制任务 prompt
# 4. 产出代码

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

1. **CodeBuddy 是唯一的 IDE 类 Agent**：需人工参与，任务文件必须包含模型切换指令
2. **Codex 和 ZCode 支持非交互模式**：可直接通过命令行传参调用
3. **QoderWork 是唯一的 VM 隔离执行环境**：长时任务、有副作用、需隔离的任务默认派此
4. **任务文件是最小上下文单元**：每份任务文件是一个自包含的 prompt，Agent 无需了解项目全貌
5. **Claude Code 作为唯一集成点**：所有产出代码经 Claude Code 审查后才合入主分支

---

## 八、ZCode 定位定稿（2026-06-25）

> **结论**：ZCode **不可被替代**，独立保留。理由：
> 1. GLM-5.2 是集群编码最强的模型（Code Arena #2 1595，超 GPT-5.5，与 Opus 4.8 差距 <1%）——不是"文档工具"
> 2. 1M 无损上下文 + Opus 级编码 = 跨模块长程实现的独特能力，集群无其他 Agent 可复制
> 3. CLI 非交互 + 异步长任务执行——即使 CodeBuddy 可切 GLM-5.2，IDE 手动模式无法替代 ZCode 的独立调度
> 4. 免费额度 300 万 token/天 + MIT 开源——成本优势和许可优势双重不可替代

## 九、精简审计

| 日期 | 事件 |
|------|------|
| 2026-06-16 | 模型优势对齐升级：9 Agent分工按底层模型重排，CC 切 Opus 4.8 |
| **2026-06-25** | **集群精简 9→5 Agent**：Reasonix/CodeWhale/Hermes→CodeBuddy，Qoder IDE→QoderWork。CC 切回 DeepSeek-V4-Pro |
| **2026-06-25** | **🆕 Kimi 加入为第 6 Agent**：K2.7-code 模式 A（代码审查+深度调试）+ K2.6 模式 B（桌面自动化+E2E 验证）。双模式合入同一 `KIMI.md` |
| **2026-06-25** | **🆙 双层升级（基于 Code Arena 实测数据）**：①ZCode/GLM-5.2→🎯 高级开发·特种部队（与 Codex 同级，关键时刻动用，一般任务不轻易使用——配额消耗高+速度慢）；②QoderWork/Qwen-3.7-Max→🏗️ 高级开发主力（Code Arena #2 1541 超 GPT-5.5 + 35h 长程自主 Agent）——纠正此前"VM+前端"的严重低估 |
