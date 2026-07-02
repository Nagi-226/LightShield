# 🛡️ LightShield CI/CD 质量门禁体系

> **版本**：v1.3 | **生效日期**：2026-07-01
> **基于**：Nagi Dev Guardrails M6（Reliability Gate）+ M8（Quality Gate）+ M9（Scope Fidelity Gate）
> **适用**：所有 Agent 产出代码在合入前必须通过的门禁
> **变更**：
>   - v1.3 (2026-07-01) — 新增 Gate A-6（外部输入安全扫描·Miasma/symlink/LiteLLM）+ §十二（CI/CD Secret 隔离策略）
>   - v1.1 (2026-06-29) — 新增 Gate A-5（MCP 白名单验证）+ §九（沙箱逃逸防御）+ §十（自动化调度）+ §十一（审计日志）

---

## 一、门禁流水线总览

```
Agent 产出代码
    │
    ▼
┌──────────────────────────────────┐
│ Gate A: 合规扫描                  │ ← 自动（Pre-commit Hook）
│ A-1~A-4 代码合规 + A-5 MCP 白名单 │
│ 🆕 A-6 外部输入安全扫描           │
└────────┬─────────────────────────┘
         │ ✅ PASS
         ▼
┌──────────────────────────────────┐
│ Gate B: 范围忠实度                │ ← Claude Code + CodeWhale
│ SF-L1~L4 检测 + Goal Drift 自检   │
└────────┬─────────────────────────┘
         │ ✅ PASS
         ▼
┌──────────────────────────────────┐
│ Gate C: 质量审计                  │ ← Claude Code（五维扫描）
│ 架构/安全/性能/质量/测试           │
└────────┬─────────────────────────┘
         │ ✅ PASS
         ▼
┌──────────────────────────────────┐
│ Gate D: 冲突检测                  │ ← Claude Code + Graphify
│ 多 Agent 产出兼容性               │
└────────┬─────────────────────────┘
         │ ✅ PASS
         ▼
┌──────────────────────────────────┐
│ Gate E: 回归验证                  │ ← QoderWork VM
│ 现有功能未被破坏                  │
└────────┬─────────────────────────┘
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

### A-5：MCP 服务器白名单验证（v1.1 2026-06-29 → 🆕 v1.3 2026-07-01 审查流程 5→7 步）

> **背景**：
> - 2026 年 MCP 工具投毒攻击大规模活跃——恶意 MCP 服务器通过包管理器以合法名称发布，工具描述中嵌入 Unicode 控制字符隐藏 prompt 注入指令，Agent 连接后即被劫持并自动外泄 `.aws/credentials` 等敏感文件。已感染 340+ 开发者。
>   → https://kensai.app/zh/blog/2026-04-06-ai-agent-security-framework-tool-poisoning-prompt-leaking-mcp-sandbox-escapes
> - **DNS Rebinding CVE-2026-11624**（2026-06）：MCP Server v0.25 之前版本缺少 Origin Header 校验，攻击者可通过浏览器 DNS Rebinding 直接调用本地 MCP Server 任意工具。
>   → https://threat-modeling.com/cve-2026-11624-mcp-dns-rebinding/
> - **30 个 MCP CVE 集中爆发**（2026-01~02）：最高 CVSS 9.6（无需认证远程代码执行），38% 的 MCP Server 默认无认证运行。
>   → https://anonymize.dev/blog/mcp-server-security-vulnerabilities-2026.html
> - **MCP 市场供应链投毒实测**（2026-06）：安全团队测试 11 个 MCP 市场，9 个市场成功植入恶意包。单个恶意 MCP 包可被数千开发者安装，每次安装即给攻击者完整命令执行权限。
>   → https://cn-sec.com/archives/5180670.html

**集群 MCP 服务器白名单**（仅以下经审查的 MCP 服务器允许接入）：

| MCP 服务器 | 用途 | 当前版本 | 最低安全版本 | 审查日期 | 审查状态 |
|-----------|------|---------|------------|---------|:--:|
| `context7` | 文档查询（Context7） | — | — | 2026-06-29 | ✅ 已审查 |
| 其他任何 MCP 服务器 | — | — | — | — | ❌ 需 7 步审查后方可加入 |

**MCP Server 安全版本基线**（集群 Agent 工具的最低安全版本要求）：

| Agent 工具 | MCP 相关组件 | 最低安全版本 | 修复的 CVE |
|-----------|-------------|:--:|------|
| Claude Code | MCP Client | v2.1.150+ | 沙箱逃逸修复 |
| Codex CLI | MCP Client + Sandbox | latest | CVE-2026-40217 (LiteLLM) |
| Kimi Code CLI | MCP Client | v0.16.0+ | Anthropic 兼容供应商凭证泄漏 |
| 所有 MCP Server | MCP Server 框架 | v0.25+ | CVE-2026-11624 (DNS Rebinding) |

**新增 MCP 服务器的审查流程**（7 步，🆕 v1.3 从 5 步扩展）：
1. **验证发布来源**：官方 GitHub org / 已知维护者 / npm/PyPI 发布历史 ≥ 6 个月
2. **检查包名混淆**：是否与知名项目名称相似（如 `mcp-github-enhanced` 伪装 `github`、`mcp-jira-sync` 伪装 `jira`）
3. **Unicode 控制字符扫描**：审查工具描述中是否包含零宽字符（`​`、`‌`、`‍`、`﻿`）及其他隐藏注入载荷
4. **权限最小化检查**：是否请求不必要的文件系统/网络/环境变量权限。拒绝请求 `*` 通配符权限的 MCP 服务器
5. **🆕 版本安全检查**：MCP Server 版本是否 ≥ 安全基线（v0.25+ 修复 DNS Rebinding CVE-2026-11624；查 NVD 确认当前版本无已知 CRITICAL/HIGH CVE）
6. **🆕 运行时认证检查**：MCP Server 是否默认启用认证？（38% 的 MCP Server 默认无认证——必须确认认证已启用）。检查是否支持 Origin Header 校验
7. **CC 终审 + 白名单更新**：CC 审查通过后更新本白名单，记录审查日期和 MCP Server 版本号

```bash
# 每次 commit 前检查 MCP 配置中是否引用了非白名单服务器
# 检查 .claude/mcp.json、.codex/mcp.json、.kimi/mcp.json 等
grep -rh '"command"' .claude/ .codex/ .kimi/ 2>/dev/null | grep -v "context7"
# 任何非白名单引用 → 🟡 警告 + 需人工确认
```

### A-6：Agent 外部输入安全扫描（🆕 v1.3 2026-07-01）

> **背景**：
> - **Miasma 蠕虫**（2026-06-03 披露）：通过 GitHub 仓库投毒 57 个恶意 npm 包（286+ 版本），利用 `binding.gyp` 触发配置注入，影响 Claude Code、Codex 等多款 Agent 工具。攻击面：Agent 自动读取恶意仓库文件时被注入后门指令。
>   → https://safedep.io/miasma-worm-ai-coding-agent-config-injection/
> - **Symlink 伪装 RCE**（2026-06 披露）：利用符号链接伪装文件复制操作，Agent 审批提示与实际执行内容不符，实现 RCE。Claude Code、Codex、CodeBuddy 等 6 大 Agent 工具均受影响。
>   → https://adversa.ai/blog/top-agentic-ai-security-resources-june-2026
> - **LiteLLM 沙箱逃逸 CVE-2026-40217**：通过 `exec()` 带全 builtins 逃逸代码沙箱，可建立反向 Shell。影响所有依赖 LiteLLM 回调机制的 Agent 工具链。
>   → https://venturebeat.com/security/copilot-searched-your-mailbox-litellm-handed-out-admin

> **核心原则**：传统 Gate A-1~A-4 扫描的是**我们写的代码**。但 Agent 在处理**外部输入**（clone 的仓库、npm 包、用户上传的文件）时，也需要安全扫描。Miasma 蠕虫证明：恶意代码不需要在我们的源码中——它可以通过 Agent 的工具调用进入执行链。

**A-6-1：外部仓库/包文件扫描**

Agent 在读取或执行任何外部来源的文件前，必须扫描以下投毒特征：

```bash
# 扫描外部仓库/包中的投毒特征文件
# 这些文件在正常项目中不应包含可疑指令

# 1. binding.gyp 注入（Miasma 蠕虫特征）
grep -rnE "node \-e|eval\(|child_process\.exec|require\('child_process'\)" **/binding.gyp 2>/dev/null

# 2. package.json 中的 install/postinstall 脚本注入
grep -rnE '"postinstall"|"preinstall"' **/package.json 2>/dev/null | grep -v "echo\|exit"

# 3. setup.py / Makefile 可疑命令
grep -rnE "curl.*\|.*sh|wget.*\|.*bash|python.*\-c.*import" **/setup.py **/Makefile 2>/dev/null

# 4. CMakeLists.txt / configure.ac 中的命令执行
grep -rnE "execute_process|add_custom_command.*COMMAND" **/CMakeLists.txt 2>/dev/null
```

**A-6-2：Symlink 伪装检测**

Agent 在执行文件复制/移动/读取操作前，必须检测 symlink 伪装：

```
检测规则（Agent 工具链层面）：
1. 操作的目标路径是符号链接？
   → 解析真实路径 → 比较"审批提示中显示的路径" vs "真实路径"
   → 不一致 → 🚫 拦截 + 告警

2. 操作涉及跨文件系统边界（如从用户目录写入系统目录）？
   → 🚫 拦截 + 需人工确认

3. 操作的目标路径在操作前不存在，操作后立即被替换为 symlink？
   → TOCTOU 攻击特征 → 🚫 拦截 + 告警
```

**A-6-3：Agent 工具链依赖安全基线**

> 背景：LiteLLM CVE-2026-40217 表明 Agent 工具自身的依赖链也可能被利用。

```bash
# 每周执行（通过 /schedule 自动化）
npm audit --prefix ~/.claude/ 2>/dev/null          # Claude Code 依赖
npm audit --prefix ~/.codex/ 2>/dev/null            # Codex CLI 依赖
npm audit --prefix ~/.kimi/ 2>/dev/null             # Kimi Code CLI 依赖

# Python Agent 工具
pip-audit --local 2>/dev/null                       # 当前 venv 依赖

# 任何 CRITICAL/HIGH 漏洞 → 立即升级对应工具版本
```

**A-6 与 A-1~A-5 的关系**：

```
A-1~A-4：扫描我们写的代码（源码合规）
A-5：扫描 MCP 工具来源（工具供应链）
A-6 🆕：扫描 Agent 读取的外部文件 + symlink 操作（输入面安全）
```

> **原则**：Agent 的输入面 = 源码 + MCP 工具 + 外部文件 + 用户输入。四者都必须经过安全扫描。

---

## 三、Gate B：范围忠实度

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
| **A-6** 🆕 外部输入扫描 | Agent 读取外部仓库/包/文件时 | Agent 自身 + Pre-commit hook | 🟡 | ❌ |
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

## 十、🆕 自动化调度 + Loop Engineering（v1.1 2026-06-29 → v1.3 2026-07-01）

> **背景**：Claude Code 拥有业内最完整的自主工作栈——`/goal`（条件驱动自主循环）+ `/loop`（定时重复）+ `/schedule`（后台定时独立运行）+ Stop Hooks（脚本判定退出）。可用于门禁自动化。
> **🆕 Loop Engineering**：Google 工程师 Addy Osmani 2026-06 系统整理了 Loop Engineering 概念（Anthropic Claude Code 负责人 Boris Cherny 背书），核心理念从「写好 prompt 让 AI 一次完成」转向「设计循环让 AI 自己校验、自己修正」。
> 来源：https://sotasync.com/reader/2026-05-15-claude-code-goal-loop-schedule-stop-hooks/、https://knightli.com/en/2026/06/10/loops-replace-prompts-agent-loop-engineering/

### 10.1 可自动化的门禁任务

| 任务 | 工具 | 频率 | 说明 |
|------|------|------|------|
| 每夜全量回归 | `/schedule` | 每日 02:00 | `pytest tests/ -v`，失败则 CC 自动分析 |
| 合规扫描巡检 | `/schedule` | 每日 06:00 | Gate A 全量重扫 + 新依赖审计 |
| 门禁绿灯自检 | `/goal` + Stop Hook | 按需 | 条件："931 tests pass + ruff/mypy/bandit 零违规" → 满足则自动停 |
| 依赖安全审计 | `/schedule` | 每周一 08:00 | `pip-audit` + CVE 数据库对照 |
| 🆕 Agent 工具链安全审计 | `/schedule` | 每周一 09:00 | `npm audit` 各 Agent CLI 工具 + 版本基线对照 |
| 🆕 MCP Server 版本基线检查 | `/schedule` | 每周一 10:00 | 对照 Gate A-5 版本基线表，检查是否有过期 MCP Server |

### 10.2 🆕 Loop Engineering 设计原则（v1.3）

> **核心理念**：Loop Engineering 将 Agent 自动化从「一次性任务」升级为「自校验闭环」。每个 Loop 必须具备三项关键指标和三层递进体系。

**Loop 设计三要素（任何自动化 Loop 必须回答）**：

| 要素 | 定义 | 示例（好） | 示例（差） |
|------|------|-----------|-----------|
| **退出条件** | Loop 何时停止？条件必须可机器验证 | `pytest tests/ --tb=short` exit 0 | "代码看起来不错" |
| **Token 预算** | 单次 Loop 最多消耗多少 Token？ | ≤ 100k token/loop | 无上限 → Token 黑洞 |
| **失败升级** | Loop 失败后如何升级？不能无限重试 | 失败 3 次 → 暂停 → 通知 CC | 无限重试直到手动停止 |

**三层递进体系（选择合适的 Loop 粒度）**：

```
Layer 1: Session Loop (/loop)
  ├─ 用途：同一 session 内的短期重复任务
  ├─ 特点：session-scoped，3 天过期，适合"每 5 分钟检查一次"
  ├─ 示例：/loop 5m "检查 pytest 是否全部通过，失败则分析并修复"
  └─ 限制：单 session 最多 50 个任务，最小间隔 1 分钟

Layer 2: Scheduled Task (/schedule)
  ├─ 用途：跨 session 的定时任务
  ├─ 特点：后台独立运行，无需打开 session，适合"每天凌晨 2 点"
  ├─ 示例：/schedule "每日 02:00 运行 pytest + ruff + mypy + bandit，失败则生成报告"
  └─ 限制：Anthropic 云端托管，适合生产环境

Layer 3: Stop Hook (script-based)
  ├─ 用途：最可靠的停止机制——脚本判定，非模型判定
  ├─ 特点：脚本 exit 0 → 停；exit ≠ 0 → 读失败输出 → 重试
  ├─ 示例：bash run_all_checks.sh（内含 pytest + ruff + mypy + bandit）
  └─ 原则：你回来时要么是 green build，要么有清晰解释
```

**LightShield Loop Engineering 组合方案**：

| 场景 | 组合 | 说明 |
|------|------|------|
| **日常质量守护** | `/schedule` (Layer 2) | 每日凌晨全量回归 + 合规扫描，失败自动告警 |
| **发版前自检** | Stop Hook (Layer 3) | 脚本运行全部 12 项 pre-commit + 931 tests，全部通过才允许封版 |
| **迭代重构** | `/loop` (Layer 1) | 每轮修改后自动跑测试 → 通过则继续下一项 → 失败则修复 |
| **长程覆盖率提升** | `/goal` + Stop Hook | Goal："覆盖率 ≥ 82% 且全部 tests pass" + Stop Hook 验证 |

### 10.3 Goal Mode 安全约束（防止 Token 黑洞）

> 社区实测：Goal 条件设置不当（如"改进代码质量"），单任务消耗 500 万 Token 仍未达成。

| 约束 | 说明 |
|------|------|
| **必须包含硬限制** | 所有 Goal 必须带 `or stop after N turns` 或 `or stop after 30 minutes` |
| **条件必须可机器验证** | 评估器只能读 transcript——条件必须是 Claude 能从输出中自行证明的。✅ "All tests pass and npm test exits 0" / ❌ "looks clean" |
| **Stop Hook 优先** | script-based Stop Hook 是最可靠的停止机制——让测试脚本而非模型判断何时完成 |
| **Token 预算上限** | 单 Goal 任务消耗不超过 500k token（正常任务的 ~5×） |
| 🆕 **Loop 三要素检查** | 每个 Loop/G goal 启动前，确认：退出条件是否可机器验证？Token 预算是否已设？失败升级路径是否明确？ |

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

---

## 十二、🆕 CI/CD Secret 隔离策略（v1.3 2026-07-01）

> **背景**：Microsoft Threat Intelligence（2026-06-05）正式确认 Claude Code GitHub Action 在特定条件下会将 workflow secrets 暴露给被 prompt-injected 的 Agent。这是 Agent 时代的**新型攻击面**——传统 CI/CD 的 secret mask 机制（将 secret 替换为 `***`）对 Agent 工具链不生效，因为 Agent 通过 tool call 参数而非日志输出获取 secret 值。
> 来源：https://www.microsoft.com/en-us/security/blog/2026/06/05/securing-ci-cd-in-agentic-world-claude-code-github-action-case/

### 12.1 核心原则

```
🚫 workflow secrets 不得经过 Agent 工具链
   → Agent 的 tool call 参数中不应包含 secret 值
   → Agent 的输出/日志中不应出现 secret 值
   → Agent 不应有权读取 .env、secrets.*、credentials.* 等文件

🚫 CI 环境中的 Agent 运行在最小权限上下文
   → GITHUB_TOKEN 限定最小 scope（仅需读仓库内容，不写 issues/PRs）
   → 禁止 Agent 在 CI 中访问 GitHub Secrets API
```

### 12.2 LightShield CI/CD Secret 隔离策略

| 策略 | 说明 | 当前状态 |
|------|------|:--:|
| **Secret 不进入 Agent 上下文** | workflow 中 secret 通过 `${{ secrets.XXX }}` 注入环境变量，Agent 不直接读取 | ⬜ 待审查 |
| **GitHub Action 最小权限 Token** | `permissions:` 块显式声明最小 scope，不依赖默认权限 | ⬜ 待配置 |
| **Agent 文件访问白名单** | CI 环境中 Agent 只能读取 `lightshield/`、`tests/`、`docs/` 目录 | ⬜ 待配置 |
| **禁止读取敏感文件** | `.env`、`secrets.*`、`credentials.*`、`*.pem` 等文件在 CI 中对 Agent 不可见 | ⬜ 待配置 |
| **Agent CI 输出脱敏** | Agent 在 CI 中的输出经过 secret mask 再写入日志（防止无意泄露） | ⬜ 待配置 |
| **不可信仓库隔离** | 不在包含外部 PR 的 CI run 中启用 Agent（仅限内部分支） | ✅ 设计原则 |

### 12.3 GitHub Action 安全配置模板

```yaml
# .github/workflows/agent-ci.yml — 安全配置示例
name: LightShield Agent CI (Secure)

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]
    # ⚠️ 仅对内部 PR 启用 Agent 步骤（外部 PR 跳过 Agent 步骤）
    types: [opened, synchronize]

permissions:
  contents: read        # 仅读仓库内容
  # ⚠️ 不授予 issues: write / pull-requests: write / secrets: read

jobs:
  agent-review:
    runs-on: ubuntu-latest
    # ⚠️ 仅内部分支运行 Agent
    if: github.event.pull_request.head.repo.full_name == github.repository
    steps:
      - uses: actions/checkout@v4

      - name: Setup Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.12'

      - name: Standard CI (no Agent)
        run: |
          pip install -r requirements.txt
          python -m pytest tests/ -v
          ruff check lightshield/

      # ⚠️ Agent 步骤隔离：使用受限 token + 无 secret 注入
      - name: Agent Review (内部 PR 仅)
        env:
          # ⚠️ 仅注入必要环境变量，不注入 secrets
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
          # ❌ 以下 secret 绝不对 Agent 暴露
          # PYPI_TOKEN: ${{ secrets.PYPI_TOKEN }}
          # DEPLOY_KEY: ${{ secrets.DEPLOY_KEY }}
        run: |
          # Agent 在此步骤中运行，只能访问已显式注入的环境变量
          echo "Agent review step — restricted environment"
```

### 12.4 Secret 暴露应急响应

如果怀疑 CI/CD 中的 Agent 已暴露 secret：

```
1. 立即撤销所有 CI/CD secret（GitHub Settings → Secrets and variables → Actions → Remove）
2. 审计 Agent 输出日志，确认泄露范围
3. 重新生成所有可能暴露的凭证（token/key/password）
4. 在 .guardrails/audit-log.md 中记录事件
5. 修复隔离策略后重新配置 secret
```

> **原则**：Agent 在 CI/CD 中是**不可信的执行者**，和任何第三方代码一样需要沙箱隔离。Trust no agent in CI.

---
