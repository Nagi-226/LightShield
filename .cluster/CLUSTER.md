# LightShield 开发集群（Dev Cluster）

> **集群角色**：将本机 9 个 AI Agent/IDE 协同编排，形成多角色开发流水线。
> **总指挥**：Claude Code（架构师 + 编排器，**Opus 4.8** · 2026-06-15 起由 DeepSeek-V4-Pro 切换）
> **🔄 当前分工**：2026-06-16 起按底层模型优势对齐重排，**当前生效分工以 §三-bis 为准**（§三/§四 为历史存档）。

---

## 一、集群成员与角色定位

```
                        ┌──────────────────────┐
                        │   Claude Code (CLI)   │
                        │   🏛️ 架构师 + 编排器   │
                        │   复杂推理、全局调度    │
                        └──────┬───────────────┘
                               │ 任务下发 & 结果审查
        ┌──────────────────────┼──────────────────────────┐
        │                      │                          │
        ▼                      ▼                          ▼
┌───────────────┐    ┌───────────────┐    ┌───────────────────────┐
│  Codex (CLI)  │    │ Reasonix(CLI) │    │ CodeWhale (CLI)       │
│  💎 高级开发   │    │ 🔧 成本优化开发│    │ 🔍 代码审查专员        │
│  脚本/模块实现  │    │ 中文任务/测试  │    │ diff审查/质量把控      │
└───────────────┘    └───────────────┘    └───────────────────────┘
        │                      │                          │
        └──────────────────────┼──────────────────────────┘
                               │
                               ▼
        ┌──────────────────────────────────────────────────┐
        │              Hermes (CLI)                         │
        │              🛠️ 工具链 + 基础设施                  │
        │              依赖管理/环境搭建/MCP集成               │
        └──────────────────────────────────────────────────┘
                               │
                               ▼
        ┌──────────────────────┬───────────────────────────┐
        │  CodeBuddy (IDE)     │  Qoder (IDE + Quest)      │
        │  💻 大规模模块开发    │  🖥️ UI/前端/编辑器内开发    │
        │  VS Code 内核        │  Cursor-like AI补全        │
        └──────────────────────┘───────────────────────────┘
                               │
                               ▼
                        ┌──────────────────┐
                        │ QoderWork (CLI)  │
                        │ 🏭 后台任务执行器 │
                        │ VM隔离/长时间任务 │
                        └──────────────────┘
                               │
                               ▼
                        ┌──────────────────────────┐
                        │  ZCode 3.0 (CLI)         │
                        │  🗂️ 知识架构师 + 文档自动化│
                        │  1M上下文 / Zread知识库   │
                        │  GLM-5.2 · 异步任务       │
                        └──────────────────────────┘
```

### 详细能力画像

| 工具 | 类型 | 底层模型 | 核心能力 | 非交互模式 | 适用场景 |
|------|------|---------|---------|-----------|---------|
| **Claude Code** | CLI | Claude Opus 4.8 | 复杂推理、架构设计、多文件编排 | —（自身即编排器） | 架构设计、合规审计、全局集成 |
| **Codex** | CLI | OpenAI GPT-5.5 | 代码生成、单文件实现、脚本 | `codex exec "prompt"` | 🔑 安全关键模块、精密前端逻辑 |
| **Reasonix** | CLI | DeepSeek-V4-Pro | 批量实现、测试生成、缓存命中 | `reasonix run "task"` | 主力实现、单元测试、中文文档 |
| **CodeWhale** | CLI | DeepSeek-V4-Pro | 代码审查、diff分析 | `codewhale exec "prompt"` | 每版本强制独立审查、合规检查 |
| **Hermes** | CLI | DeepSeek-V4-Flash | MCP集成、工具链、部署 | `hermes -z "prompt"` | 环境搭建、依赖管理、i18n locale 骨架 |
| **CodeBuddy** | IDE | DeepSeek-V4-Pro | 编辑器内大模块开发 | — | 多文件联动、全栈大模块 |
| **Qoder** | IDE | Qwen-3.7-Max | AI补全 + Quest Agent | — | 重前端 UI、多文件精准编辑 |
| **QoderWork** | CLI | Qwen-3.7-Max | 后台执行、VM隔离 | 后台常驻 | 自动加固 VM 闭环、长时任务、真机验证 |
| **ZCode 3.0** | CLI | GLM-5.2 (744B MoE) | 全量文档同步、知识库生成、合规审计 | `zcode exec "$(cat task.md)"` | 文档/知识/审计——异步任务 |

---

## 二、任务协调协议

### 2.1 任务定义格式（JSON Schema）

```json
{
  "task_id": "LIGHTSHIELD-001",
  "phase": "Phase 1 — 项目骨架",
  "title": "实现 config.py",
  "description": "...",
  "assigned_to": "codex",
  "priority": "P0",
  "depends_on": [],
  "input_files": ["CLAUDE.md", "PROJECT_OVERVIEW.md"],
  "output_files": ["lightshield/config.py"],
  "compliance_checklist": ["R1", "R2", "R3"],
  "context_prompt": "...",
  "status": "pending"
}
```

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
├── tasks/
│   ├── pending/            ← 待分配
│   ├── in_progress/        ← 执行中
│   ├── completed/          ← 待审查
│   └── verified/           ← 已验收
└── logs/
    └── cluster-{date}.log  ← 编排日志
```

---

## 三、各 Agent 任务分配原则

> ⚠️ **本节为分工原则的历史叙述**。**2026-06-16 模型优势对齐后的当前生效分工以 [§三-bis](#三-bis模型优势对齐分工2026-06-16--当前生效) 为准**——若本节描述与 §三-bis 冲突，以 §三-bis 为准。

### 3.1 Claude Code（架构师 + 编排器）

**不参与具体代码实现，专注**：
- 模块接口设计（定义每个模块的公开 API）
- 架构决策记录（ADR）
- 任务拆分和下发
- 最终代码审查和集成
- 合规红线验证（R1-R6）

**调用方式**：自身即执行体

### 3.2 Codex（高级开发工程师）

**负责**：需要精准实现的独立模块
- 给定接口规范，实现具体逻辑
- 单文件 Python 模块
- 脚本和工具函数

**调用方式**（非交互）：
```bash
codex exec "@.cluster/tasks/pending/LIGHTSHIELD-XXX.md"
```

**优点**：OpenAI 模型代码生成能力强，适合"给定接口→实现模块"的工作流

### 3.3 Reasonix（开发工程师 — DeepSeek 原生）

**负责**：大量重复性、低 token 成本任务
- 单元测试批量生成
- 中文文档和注释
- 规则库 JSON 文件生成

**调用方式**（非交互）：
```bash
reasonix run "@.cluster/tasks/pending/LIGHTSHIELD-XXX.md"
```

**优点**：DeepSeek 缓存命中率高，token 成本低，中文能力强

### 3.4 CodeWhale（代码审查专员）

**负责**：独立视角的代码审查
- diff 审查（`codewhale review`）
- 合规检查清单验证
- 与 Claude Code 形成双审机制

**调用方式**（非交互）：
```bash
codewhale exec "@.cluster/tasks/pending/LIGHTSHIELD-XXX-review.md"
```

**优点**：独立于 Claude/OpenAI 的第三方视角，避免审查同源偏差

### 3.5 Hermes（工具链 + 基础设施）⚡ Flash 模型即可

**负责**：环境搭建、依赖管理、MCP 集成
- `requirements.txt` 依赖管理
- 部署脚本生成和测试
- 外部工具链集成
- `__init__.py` 样板代码和目录骨架

**调用方式**（非交互，强制使用 Flash）：
```bash
# ⚡ 所有 Hermes 任务一律使用 deepseek-v4-flash，禁止使用 Pro
hermes -m deepseek-v4-flash -z "$(cat .cluster/tasks/pending/LS-007-infra.md)"
```

**为什么 Flash 足够**：
- Hermes 在 LightShield 中的任务全是样板代码/定义类（requirements.txt、.gitignore、`__init__.py`）
- 这些任务零推理复杂度，本质是"按模板输出"
- Flash 模型在此场景下与 Pro 质量无差别，但 token 费用节省约 70%

### 3.6 CodeBuddy（IDE — 需要人工交互）

**负责**：编辑器内的大规模模块开发
- 多文件联动修改
- IDE 内调试和测试
- 复杂重构

**使用方式**：人工在 CodeBuddy IDE 中打开项目，加载对应任务文件

### 3.7 Qoder + Quest（IDE — 需要人工交互）

**负责**：精准代码修改、AI 补全辅助
- UI 代码（Flask/Tkinter）
- 代码补全和局部修改
- 前端页面开发

**使用方式**：人工在 Qoder IDE 中打开项目

### 3.8 QoderWork（后台任务执行器）

**负责**：长时间运行、VM 隔离的任务
- 部署脚本测试
- 沙箱环境验证
- 扫描功能集成测试（在隔离 VM 中运行）

### 3.9 ZCode 3.0（知识架构师 + 文档自动化专员）🆕

**负责**：利用 1M 上下文全量读取项目，生成/同步文档和知识库
- 全量文档同步（CLAUDE.md / README / CHANGELOG / FAQ / INSTALL / USAGE）
- Zread 知识库生成（结构化项目文档，比 graphify 更叙事化）
- 合规审计报告（R1-R6 全量扫描）
- API 文档生成（从 routes.py 提取端点文档）
- 新成员上手指南

**调用方式**（非交互）：
```bash
zcode exec "$(cat .cluster/tasks/pending/ZCODE-XXX.md)"
```

**优点**：
- **1M 上下文**——集群中唯一能一次读取整个项目的 Agent
- **Zread 知识库**——独有功能，自动生成结构化文档
- **工具调用 100% JSON 合法率**——批量合规扫描零格式错误
- **MIT 开源**——无许可风险

**注意事项**：
- ⚠️ 推理速度比 Claude Opus 慢 ~30%，所有任务为异步模式（发下去→等结果→审查）
- ⚠️ 多步指令偶有缺失，任务文件必须分步明确
- ⚠️ 不发安全关键模块实现（由 CC/Codex 负责）
- ⚠️ 不发实时代码审查（由 CodeWhale/CC 负责）

**详细配置**：见 `.cluster/agents/ZCODE.md`

---

## 三-bis、模型优势对齐分工（2026-06-16 · 当前生效）

> **触发**：Claude Code 于 2026-06-15 从 DeepSeek-V4-Pro 切换为 **Opus 4.8**。借此对全集群按"底层模型优势"重排任务，纠正三处错配：① CC 长期超载兼任默认实现者；② Qoder/QoderWork（Qwen-3.7-Max，编码很强）长期闲置（各仅 1 任务）；③ 多数版本仅 CC 自审、CodeWhale 强制审查缺位（同源盲区）。
>
> **核心原则**：**按底层模型优势分派，CC 不当默认实现者。**

### 权威分工表（与各 `<AGENT>.md` 同源）

| Agent | 底层模型 | 当前职责（升级后） | 相对此前的变化 |
|-------|---------|------------------|---------------|
| **Claude Code** | **Opus 4.8** | 编排 + 架构设计 + 接口契约 + 安全终审 + 集成 | 🔻 卸下默认实现者；常规实现/测试下沉 Reasonix |
| **Codex** | GPT-5.5 | 🔑 安全关键模块（validator R2 / payload 检测 / CSRF / 鉴权）+ 精密前端逻辑 | 🔻 移出 CVE 录入、规则批量扩充（→ Reasonix/ZCode），不浪费贵 token |
| **Reasonix** | DeepSeek-V4-Pro | **默认实现 + 测试生成主力**：标准复杂度模块 + 单元测试默认派此 | 🔺 升级——承接原压在 CC 上的常规实现/测试 |
| **CodeWhale** | DeepSeek-V4-Pro | **每版本强制一次独立审查**（合入前必须） | 🔺 升级——从"偶尔审"到"强制审"，与 CC 构成真双审 |
| **Hermes** | DeepSeek-V4-Flash | 样板/基础设施（依赖/部署/`__init__`）+ **i18n locale 机械骨架** | ➡️ 维持 Flash + 新增 v0.0.39 locale 键值骨架 |
| **CodeBuddy** | DeepSeek-V4-Pro | **主动承接多文件/全栈大模块**（Web 前后端联动、跨模块重构） | 🔺 升级——从闲置（1 任务）到主力 IDE 大模块 |
| **Qoder** | Qwen-3.7-Max | **重前端 / 多文件 UI 主力**；v0.0.40 Web"一键加固+复扫+对比"页面主导 | 🔺 升级——从闲置到重前端主力（比 GPT-5.5 便宜且强） |
| **QoderWork** | Qwen-3.7-Max | **接管 v0.0.40 自动加固 VM 闭环**（`harden→execute→re-scan→verify`）+ v0.0.38 真机 Docker 验证 | 🔺 大幅启用——VM 隔离正是自动加固最缺的能力 |
| **ZCode 3.0** | GLM-5.2（1M） | 文档自动化（**OpenAPI/审计**）+ Zread 知识库 + 全量文档同步 | 🆕 承接 v0.0.39 OpenAPI 文档生成 |

### 改派后的近期版本归属

| 版本 | 主交付 | 归属（升级后） |
|:--:|------|---------------|
| **v0.0.39** | OpenAPI 文档 + i18n | **ZCode**（OpenAPI/Swagger 从 routes 提取）+ **Hermes**（zh-CN/en-US locale 骨架）+ **CC**（集成接线 + 翻译复核） |
| **v0.0.40** | 自动加固闭环 + 发布 | **QoderWork**（VM 闭环执行）+ **Qoder**（Web 加固页面）+ **CodeWhale**（强制全量审查）+ **CC**（架构 + 集成 + git tag） |

---

## 四、LightShield Phase 1 任务拆分方案（历史存档）

> 📦 **历史存档**：本节为 Phase 1（v0.0.01-0.0.10）当时的任务拆分与模型配置，模型列反映**当时**状态（CC 当时为 DeepSeek-V4）。**当前生效分工见 §三-bis**。

### Phase 1 目标：项目骨架
**产出**：`core.py`, `config.py`, `validator.py`, `logger.py`, `base.py`, `constants.py`, `__init__.py`, `requirements.txt`, `.gitignore`

### 任务分配表

| Task ID | 模块 | 分配给 | 模型 | 理由 |
|---------|------|--------|------|------|
| LS-001 | `base.py` — Adapter 抽象基类 | **Claude Code** | DeepSeek-V4 | 架构核心接口，需要全局视角和模块间权衡 |
| LS-002 | `core.py` — 主调度器 | **Claude Code** | DeepSeek-V4 | 编排逻辑，依赖 LS-001 接口定义 |
| LS-003 | `config.py` — 配置管理 | **Reasonix** | DeepSeek-V4 | 标准配置加载模式，DeepSeek-V4 足够 |
| LS-004 | `validator.py` — 输入校验 | **Codex** | GPT-5.5 | 🔑 安全关键模块，正则精密度要求高，最强模型值得 |
| LS-005 | `logger.py` — 日志系统 | **Reasonix** | DeepSeek-V4 | logging 标准封装，无复杂推理 |
| LS-006 | `constants.py` — 常量枚举 | **Hermes** | DeepSeek-V4-flash | 纯数据定义，零推理 |
| LS-007 | `requirements.txt` + 骨架 | **Hermes** | DeepSeek-V4-flash | 纯样板代码 |
| LS-008 | 代码审查（合规+质量） | **CodeWhale** + **Qoder** | DeepSeek-V4 + Qwen-3.7-max | 双模型双审，消除单模型盲区 |

### 集群模型实际配置

| Agent | 模型 | 编码能力 | 成本 | 非交互调用 |
|-------|------|:--:|:--:|:--:|
| **Claude Code** | **Opus 4.8** | 🟢 **最强** | 🔴 高 | —（2026-06-15 起，原 DeepSeek-V4） |
| **Codex** | **GPT-5.5** | 🟢 **最强** | 🔴 高 | `codex exec` |
| **Reasonix** | DeepSeek-V4-Pro | 🟡 良好 | 🟢 低 | `reasonix run` |
| **CodeWhale** | DeepSeek-V4-Pro | 🟡 良好 | 🟢 低 | `codewhale exec` |
| **Hermes** | DeepSeek-V4-Flash | 🟠 一般 | 🟢 极低 | `hermes -z` |
| **CodeBuddy** | DeepSeek-V4-Pro | 🟡 良好 | 🟢 低 | 需人工 |
| **Qoder** | **Qwen-3.7-max** | 🟢 **很强** | 🟡 中 | 需人工 |
| **QoderWork** | **Qwen-3.7-max** | 🟢 **很强** | 🟡 中 | 后台常驻 |
| **ZCode 3.0** | **GLM-5.2** | 🟢 **很强** | 🟢 极低（免费） | `zcode exec` |

### 任务分配逻辑（已优化）

> **GPT-5.5 很贵，要用在刀刃上。Qwen-3.7-max 编码很强但不能 CLI 调用，留给 IDE 场景。**

1. **Codex (GPT-5.5)**：仅分配安全关键、精密度要求最高的模块。本次 Phase 1 只有 `validator.py`（R2 防线）。配置加载、日志封装等普通任务不给 Codex——成本浪费。
2. **Qoder (Qwen-3.7-max)**：编码能力仅次于 GPT-5.5。Phase 1 不能 CLI 调用，但 Phase 9（Flask Web + Tkinter UI）以及多文件重构时发挥最大价值。Phase 1 中作为 CodeWhale 的双审搭档。
3. **Reasonix (DeepSeek-V4-Pro)**：主力开发。处理大多数标准模块实现。成本低，能批量产出。
4. **Hermes (DeepSeek-V4-Flash)**：样板代码和定义类任务。纯模板输出，Flash 绰绰有余。
5. **CodeWhale (DeepSeek-V4-Pro)**：独立视角审查。搭配 Qoder（Qwen-3.7-max）形成**双模型双审**机制。

**Hermes 在 LightShield 全局使用 Flash**：

| Phase | Hermes 任务 | 复杂度 | 模型 |
|-------|------------|:--:|:--:|
| Phase 1 | `requirements.txt`、`.gitignore`、`__init__.py` | 纯样板 | ⚡ Flash |
| Phase 7 | Linux/Windows 加固脚本模板 | 模板生成 | ⚡ Flash |
| Phase 8 | `deploy_linux.sh`、`deploy_win.ps1` | Shell 脚本 | ⚡ Flash |
| 全阶段 | 依赖更新、环境检查 | 工具链操作 | ⚡ Flash |

**结论**：Hermes 在 LightShield 项目中 **100% 的任务都适合 Flash 模型**，无需使用 Pro。配置已内置于任务文件中。

---

## 五、执行流程

### 第一步：架构师下发设计（Claude Code 执行）

1. 创建任务文件到 `.cluster/tasks/pending/`
2. 每个任务包含完整上下文提示词（嵌入 CLAUDE.md 关键约束）
3. 明确接口契约（每个模块的输入/输出/异常）

### 第二步：各 Agent 并行执行

```bash
# 并行启动各 Agent（不同终端窗口/后台进程）
# Codex:
codex exec "$(cat .cluster/tasks/pending/LS-003-config.md)"

# Reasonix:
reasonix run "$(cat .cluster/tasks/pending/LS-005-logger.md)"

# Hermes:
hermes -z "$(cat .cluster/tasks/pending/LS-007-requirements.md)"

# CodeWhale（在代码产出后执行）:
codewhale exec "$(cat .cluster/tasks/pending/LS-008-review.md)"
```

### 第三步：架构师审查集成（Claude Code 执行）

1. 审查各 Agent 产出的代码
2. 对照合规红线（R1-R6）逐条验证
3. 修正接口不一致
4. 合并到主分支
5. 任务状态 → `verified`

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

1. **IDE 类工具（CodeBuddy/Qoder）需人工参与**：它们无法通过 CLI 全自动调用，需要人打开 IDE 并输入任务
2. **Codex/Reasonix/CodeWhale/Hermes 支持非交互模式**：可直接通过命令行传参调用
3. **任务文件是最小上下文单元**：每份任务文件是一个自包含的 prompt，Agent 无需了解项目全貌
4. **Claude Code 作为唯一集成点**：所有产出代码经 Claude Code 审查后才合入主分支
