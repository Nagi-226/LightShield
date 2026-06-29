# 🛡️ LightShield CI/CD 质量门禁体系

> **基于**：Nagi Dev Guardrails M6（Reliability Gate）+ M8（Quality Gate）+ M9（Scope Fidelity Gate）
> **适用**：所有 Agent 产出代码在合入前必须通过的门禁

---

## 一、门禁流水线总览

```
Agent 产出代码
    │
    ▼
┌─────────────────────┐
│ Gate A: 合规扫描     │ ← 自动（Pre-commit Hook）
│ R1-R6 关键字检查     │
└────────┬────────────┘
         │ ✅ PASS
         ▼
┌─────────────────────┐
│ Gate B: 范围忠实度   │ ← Claude Code + CodeWhale
│ SF-L1~L4 检测       │
└────────┬────────────┘
         │ ✅ PASS
         ▼
┌─────────────────────┐
│ Gate C: 质量审计     │ ← Claude Code（五维扫描）
│ 架构/安全/性能/质量/测试│
└────────┬────────────┘
         │ ✅ PASS
         ▼
┌─────────────────────┐
│ Gate D: 冲突检测     │ ← Claude Code
│ 多 Agent 产出兼容性   │
└────────┬────────────┘
         │ ✅ PASS
         ▼
┌─────────────────────┐
│ Gate E: 回归验证     │ ← QoderWork VM
│ 现有功能未被破坏      │
└────────┬────────────┘
         │ ✅ PASS
         ▼
      合入主分支 ✅
```

---

## 二、Gate A：合规扫描（自动，不可跳过）

### A-1：关键字黑名单扫描

```bash
# 每次 git commit 前自动执行
grep -rnE "exploit|payload|backdoor|trojan|bind_shell|reverse_shell|ransomware|botnet" lightshield/ --include="*.py"
# 任何命中 → 拦截 commit，标记 Agent
```

### A-2：MSF 路径白名单验证

```bash
# 检查所有 MSF 引用是否仅使用白名单路径
grep -rn "auxiliary/" lightshield/ --include="*.py" | grep -v "auxiliary/scanner/"
# 任何非 scanner 的 auxiliary 引用 → 拦截
```

### A-3：IP 范围扫描检测

```bash
# 检查是否存在 CIDR/IP段的代码
grep -rnE "[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+/[0-9]+" lightshield/ --include="*.py"
grep -rnE "[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+-[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+" lightshield/ --include="*.py"
# 除 validator.py 的检测逻辑外，任何 CIDR 使用 → 拦截
```

### A-4：导入路径检查

```bash
# 检查是否 import 了 hackingtool 的攻击模块
grep -rnE "from hackingtool|import hackingtool" lightshield/ --include="*.py"
# 任何 import → 拦截（hackingtool 不作为依赖）
```

### A-5：MCP 服务器白名单验证（🆕 v1.1 2026-06-29）

> **背景**：2026 年 MCP 工具投毒攻击大规模活跃——恶意 MCP 服务器通过包管理器以合法名称发布，工具描述中嵌入 Unicode 控制字符隐藏 prompt 注入指令，Agent 连接后即被劫持并自动外泄 `.aws/credentials` 等敏感文件。已感染 340+ 开发者。
> 来源：https://kensai.app/zh/blog/2026-04-06-ai-agent-security-framework-tool-poisoning-prompt-leaking-mcp-sandbox-escapes

**集群 MCP 服务器白名单**（仅以下经审查的 MCP 服务器允许接入）：

| MCP 服务器 | 用途 | 审查状态 |
|-----------|------|:--:|
| `context7` | 文档查询（Context7） | ✅ 已审查 |
| 其他任何 MCP 服务器 | — | ❌ 需 CC 安全审查后方可加入白名单 |

**新增 MCP 服务器的审查流程**：
1. 验证发布来源（官方 GitHub org / 已知维护者）
2. 检查包名是否与知名项目混淆（如 `mcp-github-enhanced` 伪装 `github`）
3. 审查工具描述中是否包含 Unicode 控制字符（`​`、`‌`、`‍`、`﻿` 等零宽字符）
4. 检查是否请求不必要的文件系统/网络/环境变量权限
5. CC 审查通过后更新本白名单

```bash
# 每次 commit 前检查 MCP 配置中是否引用了非白名单服务器
# 检查 .claude/mcp.json、.codex/mcp.json、.kimi/mcp.json 等
grep -rh '"command"' .claude/ .codex/ .kimi/ 2>/dev/null | grep -v "context7"
# 任何非白名单引用 → 🟡 警告 + 需人工确认
```

---

## 三、Gate B：范围忠实度（SF-L1~L4）

> 基于 Nagi M9：Scope Fidelity Gate。防止 Agent "多做"。

| 级别 | 触发条件 | 响应 |
|:--:|------|------|
| **SF-L1** | 1-2 个不必要的变更（格式化、注释修改） | 自查 → 回滚 → 继续 |
| **SF-L2** | 创建了未被请求的文件/目录/抽象层 | 停止 → 重读原始需求 → 最小化实现 |
| **SF-L3** | 修改了 3+ 未被提及的文件，级联修复 | 列出全部变更 → 分类 REQUESTED/EXTRA → 回滚 EXTRA |
| **SF-L4** | 200+ diff 行，进入无限修复循环 | 停止 → 道歉 → 重述原始需求 → ≤10 行方案 |

### 必要性测试（SF-L2+ 触发后执行）

```
对每个被修改的文件问：
"如果回滚这个文件，被请求的功能还能用吗？"
如果回答 NO → 必要变更 ✅
如果回答 YES → 非必要变更 → 立即回滚 ❌
```

### Anti-Grinding 检查表（Agent 提交前自审）

| Agent 冲动 | 正确做法 |
|-----------|---------|
| "这个函数名不好，我改一下" | 不是你该管的。标注但不改。 |
| "加个 try-catch 以防万一" | 这个异常真的会发生吗？不会就别加。 |
| "应该提取成工具函数" | 只用了一次？内联比抽象好。 |
| "用户可能也需要这个功能" | 用户没说 = 不要做。 |
| "我先加个抽象层应对未来" | 你在预测未来。停止。 |
| "我顺便把旁边那个 bug 修了" | 一个修复一个 PR，不要夹带。 |
| "加个设计模式吧（工厂/单例/观察者）" | 模式是用来解决已有问题的，不是装饰品。 |
| "这个很容易实现，我加上" | "容易" ≠ "被请求"。不要擅自加功能。 |
| "让我优化一下性能" | 先测量。没测量就别优化。 |

---

## 四、Gate C：五维质量审计（M8）

> 基于 Nagi M8：Quality Gate。每个里程碑交付后执行。

### 审计维度

```
┌─ M8 Quality Audit ───────────────────────────────────────┐
│                                                           │
│  ① 架构 (Architecture)                                    │
│  [ ] 循环依赖？                                           │
│  [ ] 模块间紧耦合？                                        │
│  [ ] >300 行单体函数？                                    │
│  [ ] 关注点分离是否清晰？                                   │
│                                                           │
│  ② 安全 (Security)                                        │
│  [ ] 硬编码密钥/凭证？                                     │
│  [ ] 所有入口有输入校验？                                   │
│  [ ] SQL/命令注入向量？                                    │
│  [ ] 敏感数据泄露（日志/URL 中的 PII）？                    │
│  [ ] 🆕 沙箱逃逸风险（/proc 暴露、卷挂载遍历、元数据服务）？ │
│  [ ] 🆕 MCP 工具来源是否在白名单内？                        │
│  [ ] 🆕 Agent 提示词注入防护（错误消息/图片注入）？         │
│                                                           │
│  ③ 性能 (Performance)                                     │
│  [ ] N+1 查询或冗余 API 调用？                             │
│  [ ] 重复操作无缓存？                                      │
│  [ ] 阻塞操作在异步路径中？                                 │
│                                                           │
│  ④ 代码质量 (Code Quality)                                 │
│  [ ] 圈复杂度 >15？                                       │
│  [ ] 魔法数字/硬编码常量？                                  │
│  [ ] >5 行重复代码？                                      │
│  [ ] 死代码/注释掉的代码？                                  │
│                                                           │
│  ⑤ 测试覆盖 (Testing)                                     │
│  [ ] 关键路径有至少一个 smoke check？                       │
│  [ ] 边界情况覆盖（空/错误/边界输入）？                      │
│  [ ] 测试套件仍通过？                                      │
└───────────────────────────────────────────────────────────┘
```

### 严重等级

| 等级 | 标签 | 动作 | 示例 |
|:--:|------|------|------|
| 🔴 CRITICAL | 交付前必须修复 | 阻塞 | 硬编码密钥、SQL 注入点 |
| 🟠 HIGH | 下次迭代前修复 | 必须 | N+1 查询、循环依赖 |
| 🟡 MEDIUM | 方便时修复 | 建议 | 魔法数字、>300 行函数 |
| 🟢 LOW | 跟踪 | 信息 | 命名不规范 |

### 审计报告模板

```
📋 M8 Quality Audit Report — [Phase N / 模块名]
════════════════════════════════════════════
Overall Grade: [A/B/C/D/F]

① Architecture: [N] issues — [判定]
② Security:     [N] issues — [判定]
③ Performance:  [N] issues — [判定]
④ Code Quality: [N] issues — [判定]
⑤ Testing:      [N] issues — [判定]

🔴 CRITICAL: [N] | 🟠 HIGH: [N] | 🟡 MEDIUM: [N] | 🟢 LOW: [N]

Priority actions:
1. [LEVEL] Description → fix approach

Summary: [此版本可以交付吗？ Y/N 及原因]
```

---

## 五、Gate D：多 Agent 冲突检测

> LightShield 特有门禁。防止集群 Agent 产出相互冲突。

### D-1：接口契约一致性检查

```
检查项：
[ ] 每个模块的公开 API 与 CLAUDE.md 中定义的接口契约一致
[ ] 被依赖模块的接口未被依赖方擅自修改
[ ] Adapter 子类完全实现了 BaseAdapter 抽象方法
```

### D-2：文件归属检查

```
检查规则：
- 每个文件只能由一个 Agent 的产出覆盖
- 如果两个 Agent 都产出了同名文件 → 冲突 → 需 Claude Code 仲裁
- 不同 Agent 产出的文件间的 import 关系必须一致
```

### D-3：Graphify 知识图谱一致性

```bash
# 每次合入前验证图谱连通性
graphify extract . --no-cluster  # AST 层重新提取
# 检查依赖链路是否有断裂（import 了不存在的模块）
```

### D-4：跨 Agent 审阅要求

```
单 Agent 产出 → CodeWhale 审阅 → Claude Code 审阅 → 合入
双 Agent 产出（不同模块）→ CodeWhale 审阅 + 冲突检测 → Claude Code 审阅 → 合入
三+ Agent 产出 → 全量审阅 + Graphify 一致性 + Claude Code 仲裁 → 合入
```

---

## 六、Gate E：回归验证（QoderWork VM）

### E-1：Smoke Test

```bash
# 在 QoderWork VM 中运行
python -c "from lightshield.utils.validator import TargetValidator; \
           assert TargetValidator.validate('192.168.1.1')[0] == True; \
           assert TargetValidator.validate('192.168.1.0/24')[0] == False; \
           print('Validator smoke: PASS')"
```

### E-2：每次合入前执行

- 现有测试套件全部通过
- 新增代码路径的 smoke trace
- 合规扫描门禁全部绿灯

---

## 七、门禁自动化配置

### .githooks/pre-commit（Gate A 自动执行）

```bash
#!/bin/bash
# LightShield Pre-commit Compliance Hook
# 自动执行 R1-R6 合规扫描

echo "🛡️ Running compliance scan..."

# R1/R3: 关键字黑名单
if grep -rqE "exploit|payload|backdoor|trojan|bind_shell|reverse_shell" lightshield/ --include="*.py"; then
    echo "❌ BLOCKED: 检测到违规关键字"
    exit 1
fi

# R5: MSF 白名单
if grep -rh "auxiliary/" lightshield/ --include="*.py" | grep -qv "auxiliary/scanner/"; then
    echo "❌ BLOCKED: 检测到非白名单 MSF 路径"
    exit 1
fi

# R2: IP 段扫描
if grep -rqP "\d+\.\d+\.\d+\.\d+/\d+" lightshield/ --include="*.py" | grep -qv "validator"; then
    echo "❌ BLOCKED: 检测到 CIDR IP 段"
    exit 1
fi

echo "✅ Compliance scan passed"
```

### .github/workflows/quality-gates.yml（Gate C + D + E）

```yaml
name: LightShield Quality Gates
on:
  pull_request:
    branches: [main]
  push:
    branches: [main]

jobs:
  compliance-scan:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: R1-R6 Compliance Check
        run: .githooks/pre-commit

  quality-audit:
    needs: compliance-scan
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Python Lint
        run: |
          pip install ruff
          ruff check lightshield/
      - name: Type Check
        run: |
          pip install basedpyright
          basedpyright lightshield/

  regression-test:
    needs: compliance-scan
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Run Tests
        run: |
          pip install -r requirements.txt
          python -m pytest tests/ -v

  scope-fidelity:
    needs: compliance-scan
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: File Change Audit
        run: |
          CHANGED=$(git diff --name-only origin/main...HEAD | wc -l)
          if [ $CHANGED -gt 20 ]; then
            echo "⚠️ Large PR: $CHANGED files changed. Consider splitting."
          fi
```

---

## 八、门禁执行责任矩阵

| Gate | 触发时机 | 执行者 | 自动化 | 可跳过 |
|------|------|------|:--:|:--:|
| **A** 合规扫描 | 每次 commit | Pre-commit hook | ✅ | ❌ |
| **A-5** MCP 白名单 | 每次 commit + 新 MCP 引入时 | Pre-commit hook + CC | ✅ | ❌ |
| **B** 范围忠实度 | 每个任务完成 | Claude Code + CodeWhale | 🟡 | ❌ |
| **C** 质量审计 | 每个里程碑 | Claude Code（M8） | 🟡 | ❌ |
| **D** 冲突检测 | 多 Agent 产出合入前 | Claude Code + Graphify | 🟡 | ❌ |
| **E** 回归验证 | 每次合入前 | QoderWork VM | ✅ | ❌ |

> **不可绕过声明**：所有 Gate 均为强制门禁。即使用户说"不用检查了"，Agent 仍需在后台完成检查并保留记录。类似飞行安全清单——乘客可以不看，但机长必须过。

---

## 九、🆕 沙箱逃逸防御（v1.1 2026-06-29）

> **背景**：2026 年 5 月披露 VM2 沙箱逃逸 CVE（CVSS 9.0-10.0），影响多个 AI Agent 平台的容器级沙箱。攻击途径包括 `/proc/pid/mem` 注入、卷挂载遍历、云元数据服务（169.254.169.254）凭证窃取。Docker 于 2026 年初发布 Sandboxes 产品，推荐使用 gVisor 或 Firecracker microVM 替代标准容器沙箱。
> 来源：https://cheesecat.net/blog/prompt-injection-sandbox-escape-cve-2026-25592-2026-zh-tw/、https://chen-blog-sigma.vercel.app/ai-agent-sandbox-security/

### 沙箱安全清单

| 检查项 | 说明 | 当前状态 |
|--------|------|:--:|
| 禁用云元数据服务 | 阻止容器访问 `169.254.169.254`（AWS/阿里云/腾讯云 IMDS） | ⬜ 待确认 |
| `/proc` 文件系统限制 | 限制 `/proc/pid/mem`、`/proc/self/mounts` 等敏感伪文件暴露 | ⬜ 待确认 |
| 卷挂载最小化 | 仅挂载必要目录，禁止 `-v /:/host` 全根挂载 | ✅ `docker_executor.py` 仅挂载脚本目录 |
| 网络隔离 | `--network none` 锁死容器网络 | ✅ 已实现 |
| 特权模式禁止 | 禁止 `--privileged`、`--cap-add=SYS_ADMIN` | ✅ 已实现 |
| 非 root 用户运行 | 容器内使用非 root 用户执行脚本 | ⬜ 待确认 |
| 只读根文件系统 | `--read-only` + 必要时 `tmpfs` 挂载临时目录 | ⬜ 待确认 |
| 资源限制 | CPU/Memory 限制防 DoS | ✅ `SANDBOX_DEFAULT_TIMEOUT` |

### 中长期升级路径

```
当前（Docker + --network none）→ 评估 gVisor（用户态内核，无 /proc 逃逸面）→ 评估 Firecracker（microVM，硬件级隔离）
```

---

## 十、🆕 自动化调度（v1.1 2026-06-29）

> **背景**：Claude Code 拥有业内最完整的自主工作栈——`/goal`（条件驱动自主循环）+ `/loop`（定时重复）+ `/schedule`（后台定时独立运行）+ Stop Hooks（脚本判定退出）。可用于门禁自动化。
> 来源：https://sotasync.com/reader/2026-05-15-claude-code-goal-loop-schedule-stop-hooks/

### 可自动化的门禁任务

| 任务 | 工具 | 频率 | 说明 |
|------|------|------|------|
| 每夜全量回归 | `/schedule` | 每日 02:00 | `pytest tests/ -v`，失败则 CC 自动分析 |
| 合规扫描巡检 | `/schedule` | 每日 06:00 | Gate A 全量重扫 + 新依赖审计 |
| 门禁绿灯自检 | `/goal` + Stop Hook | 按需 | 条件："784 tests pass + ruff/mypy/bandit 零违规" → 满足则自动停 |
| 依赖安全审计 | `/schedule` | 每周一 08:00 | `pip-audit` + CVE 数据库对照 |

### Goal Mode 安全约束（防止 Token 黑洞）

> 社区实测：Goal 条件设置不当（如"改进代码质量"），单任务消耗 500 万 Token 仍未达成。

| 约束 | 说明 |
|------|------|
| **必须包含硬限制** | 所有 Goal 必须带 `or stop after N turns` 或 `or stop after 30 minutes` |
| **条件必须可机器验证** | 评估器只能读 transcript——条件必须是 Claude 能从输出中自行证明的。✅ "All tests pass and npm test exits 0" / ❌ "looks clean" |
| **Stop Hook 优先** | script-based Stop Hook 是最可靠的停止机制——让测试脚本而非模型判断何时完成 |
| **Token 预算上限** | 单 Goal 任务消耗不超过 500k token（正常任务的 ~5×） |

---

## 十一、审计日志

每次门禁触发都记录到 `.guardrails/audit-log.md`：

```markdown
| 时间 | Gate | Agent | 结果 | 详情 |
|------|------|-------|------|------|
| 2026-06-09 20:00 | A | Codex | ✅ PASS | validator.py 合规 |
| 2026-06-09 20:15 | B | Codex | 🟡 SF-L1 | 多改了 1 个注释 → 已回滚 |
| 2026-06-09 20:30 | D | Claude | 🟠 CONFLICT | config.py 被两个 Agent 同时修改 → 已仲裁 |
```
