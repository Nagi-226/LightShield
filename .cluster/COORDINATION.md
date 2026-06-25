# 🔗 LightShield 集群协调协议（Coordination Protocol）

> **目的**：确保 6 Agent 并行开发的产出不相互冲突
> **核心原则**：一个文件一个 Agent，接口契约先行，冲突自动检测

---

## 一、文件归属机制

### 1.1 归属表（当前 v0.0.39 · 2026-06-25 集群精简后）

| 文件 | 归属 Agent | 状态 |
|------|-----------|:--:|
| `lightshield/` 所有源码 | Claude Code（集成） | ✅ 已实现 |
| `lightshield/web/` 前端模板 | QoderWork 模式 A（前端 UI，原 Qoder IDE） | 🟢 v0.0.40+ |
| `tests/` 所有测试 | CodeBuddy（默认实现 + 测试生成）+ CC（集成审查） | ✅ 已实现 |
| `requirements.txt` | CodeBuddy（Flash 模式，原 Hermes） | ✅ 已实现 |
| `.gitignore` | CodeBuddy（Flash 模式，原 Hermes） | ✅ 已实现 |
| 各 `__init__.py` | CodeBuddy（Flash 模式，原 Hermes） | ✅ 已实现 |
| `Dockerfile`, `docker-compose.yml` | CodeBuddy（Flash 模式，原 Hermes） | ✅ 已实现 |
| `lightshield/web/locales/` | CodeBuddy（Flash 模式，原 Hermes） | 🟢 v0.0.40+ |
| | | |
| `CLAUDE.md` | Claude Code（治理段）+ ZCode（项目身份段） | ✅ |
| `README.md` | ZCode 3.0 | ✅ |
| `CHANGELOG.md` | ZCode 3.0 | ✅ |
| `docs/INSTALL.md` | ZCode 3.0 | ✅ |
| `docs/USAGE.md` | ZCode 3.0 | ✅ |
| `docs/FAQ.md` | ZCode 3.0 | ✅ |
| `PROJECT_OVERVIEW.md` | ZCode 3.0 | ✅ |
| `.guardrails/PROGRESS.md` | Claude Code | CC 自行维护 |
| `.guardrails/audit-log.md` | Claude Code | CC 自行维护 |
| `.guardrails/REVIEW_CHECKLIST.md` | Claude Code | CC 自行维护 |
| | | |
| `.cluster/CLUSTER.md` | Claude Code（集群治理） | CC 自行维护 |
| `.cluster/COORDINATION.md` | Claude Code（集群治理） | CC 自行维护 |
| 根目录各 `<AGENT>.md` | Claude Code（集群治理） | CC 自行维护 ¹ |

> ¹ **活跃 Agent .md**：CODEX.md / CODEBUDDY.md / KIMI.md 🆕 / QODERWORK.md / ZCODE.md。Reasonix / CodeWhale / Hermes / Qoder IDE 已于 2026-06-25 退役并删除（历史保留于 git）。

### 1.2 冲突规则

```
规则 1: 同一文件只能由一个 Agent 修改
规则 2: 如果 Agent B 需要修改 Agent A 的文件 → 提交变更请求 → Claude Code 仲裁
规则 3: 新增文件需先在归属表中注册
规则 4: 文件删除需 Claude Code 确认
```

---

## 二、接口契约机制

### 2.1 契约定义（Claude Code 在 Phase 1 架构设计时产出）

每个模块在开发前，Claude Code 先定义接口契约（函数签名 + 类型标注 + 行为语义）：

```python
# 契约示例：config.py 的公开接口
class LightShieldConfig:
    def load(self, path: str) -> None: ...
    def to_dict(self) -> dict[str, Any]: ...
    def validate_msf_config(self) -> bool: ...
```

### 2.2 契约锁定规则

```
1. Claude Code 定义接口契约 → 写入 CLAUDE.md 或对应任务文件
2. Agent 按契约实现，不得修改公开接口签名
3. 如需修改接口 → 提交 ADR → Claude Code 审批 → 同步更新所有依赖方
4. 契约变更触发依赖方重新验证（Gate D）
```

---

## 三、并行执行规则

### 3.1 可并行（不同文件，无依赖）

```
v0.0.40 可并行任务：
├── CODEX-v040  HostExecutor + 编排（安全关键，GPT-5.5）
├── CB-v040      verify 数据结构（切 DS V4-Pro，原 Reasonix）
├── CB-v040      i18n 闭环 key（切 DS Flash，原 Hermes）
├── QW-v040      Web 对比页面（QoderWork 模式 A，Qwen-3.7-Max）
├── KIMI-A-v040  闭环实现全量审查（K2.7-code，独立模型审查）
├── KIMI-B-v040  Web E2E 自动化测试 + 部署验证（K2.6，桌面自动化）
└── ZCODE-XXX    文档同步（GLM-5.2，独立任务）
```

### 3.2 必须串行（有依赖）

```
v0.0.40 依赖链：
CB verify 数据结构 → Codex HostExecutor + 编排 → QoderWork Web 对比页面(模式A) → Kimi Code 独立审查 → QoderWork Gate E(模式B)
```

### 3.3 Agent 内串行

```
同一 Agent 的任务按优先级串行执行：
CodeBuddy: verify 数据结构 → i18n key
QoderWork: Web 对比页面(模式A·IDE) → Gate E 夹具(模式B·VM，等 Kimi 审查后触发)
Kimi Code: v0.0.40 闭环全量独立审查（在 Codex+CB 产出全部合入前触发）
```
```
```

---

## 四、冲突检测流程

### 4.1 合入前检测（Gate D）

```
每次 Agent 产出提交后，Claude Code 执行：

1. 文件归属检查：
   - 该文件是否已在归属表中注册给其他 Agent？
   - 是否修改了其他 Agent 的接口签名？

2. 导入路径检查：
   - import 的模块是否存在？（防止引用未实现的模块）
   - import 路径是否与其他 Agent 的产出一致？

3. Graphify 一致性：
   - graphify extract .  → 重建知识图谱
   - 检查依赖链路是否完整
```

### 4.2 冲突解决

```
冲突类型              → 解决方式
─────────────────────────────────────────────
同名文件被两个 Agent 修改 → Claude Code 仲裁（选择最优或合并）
接口签名不一致          → 以 Claude Code 定义的契约为准
Import 路径冲突         → Claude Code 统一 → 通知双方
架构模式偏离            → 触发 ADR 更新 → 全集群通知
```

---

## 五、Agent 间通信协议

### 5.1 不直接通信

Agent 之间**不直接通信**——所有协调通过 Claude Code 中转。

```
Codex ──→ 需要修改 validator.py 的接口
         │
         ▼
    任务文件更新 (.cluster/tasks/)
         │
         ▼
    Claude Code 审查 → 更新契约 → 通知依赖方（Reasonix）
         │
         ▼
    Reasonix 收到通知 → 适配 config.py 的调用方式
```

### 5.2 共享知识层

所有 Agent 通过以下共享层获取全局信息：

```
┌─────────────────────────────────────┐
│          CLAUDE.md                   │ ← 架构、合规、接口契约
├─────────────────────────────────────┤
│          PROJECT_OVERVIEW.md         │ ← 技术路线、目录结构
├─────────────────────────────────────┤
│          .guardrails/                │ ← 项目契约、质量门禁
├─────────────────────────────────────┤
│          graphify-out/graph.json     │ ← 代码知识图谱
├─────────────────────────────────────┤
│          .cluster/tasks/             │ ← 任务文件和状态
└─────────────────────────────────────┘
```

---

## 六、知识缺口预防机制

> 针对"用户某些知识面缺乏导致错误决策"的预防

### 6.1 决策前强制确认（Nagi Principle 5）

```
任何涉及以下领域的决策，必须先给出选项+风险分析，等用户确认：
- 安全工具集成方式（MSF、Nmap 的使用边界）
- 合规相关的设计（输入校验范围、白名单配置）
- 技术选型变更（引入新依赖、更换框架）
- 架构层面改动（新增 Adapter 类型、修改 BaseAdapter 接口）
```

### 6.2 技术可行性预检（Nagi Principle 1+3）

```
收到需求后，先做可行性检查：
1. 是否在已确认的技术边界内？（参考 boundaries.md）
2. 是否存在已知的技术陷阱？
3. 是否有更简单的替代方案？

如果用户需求踩红线：
→ 立即拦截 → 解释原因 → 提供 2-3 个合规的降级方案
```

### 6.3 复杂度乘数检测（Nagi M7-B）

```
检测用户需求中的技术关键词堆叠：
- Tier 1 (高风险): 区块链/AI大模型/自动驾驶/Web3
- Tier 2 (中风险): 分布式/实时同步/高并发100万+/微服务

总分 ≥ 5 → 🟡 复杂度警告
总分 ≥ 8 → 🔴 强制拆分
```

### 6.4 "随便"防御协议（Nagi M7-A）

```
Strike 1: 给出默认方案表 + 排除项
Strike 2: 缩短到 3 项硬决策
Strike 3: 锁定默认方案 + 正式声明（不接受事后推翻架构决策）
```

---

## 七、Agent 行为护栏

> 所有 Agent 必须遵守的行为边界（写入各自的 MD 文件）

### 7.1 不盲从（Principle 1）

```
如果任务文件中的需求存在技术错误或安全风险 → 停止执行 → 回传问题给 Claude Code
```

### 7.2 不脑补（Principle 2）

```
任务文件中的需求模糊 → 不自行假设 → 标记为"需要澄清" → 回传
```

### 7.3 实事求是（Principle 3）

```
能力边界外的工作 → 不承诺 → 明确告知局限性 → 建议替代方案
```

### 7.4 可落地（Principle 4）

```
所有产出代码必须可运行，无不完整实现，无占位符
```

### 7.5 确认再开工（Principle 5）

```
非微调任务（>3 文件或涉及架构决策）→ 先确认范围和方法 → 再写代码
```
