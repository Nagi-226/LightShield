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
| **B** 范围忠实度 | 每个任务完成 | Claude Code + CodeWhale | 🟡 | ❌ |
| **C** 质量审计 | 每个里程碑 | Claude Code（M8） | 🟡 | ❌ |
| **D** 冲突检测 | 多 Agent 产出合入前 | Claude Code + Graphify | 🟡 | ❌ |
| **E** 回归验证 | 每次合入前 | QoderWork VM | ✅ | ❌ |

> **不可绕过声明**：所有 Gate 均为强制门禁。即使用户说"不用检查了"，Agent 仍需在后台完成检查并保留记录。类似飞行安全清单——乘客可以不看，但机长必须过。

---

## 九、审计日志

每次门禁触发都记录到 `.guardrails/audit-log.md`：

```markdown
| 时间 | Gate | Agent | 结果 | 详情 |
|------|------|-------|------|------|
| 2026-06-09 20:00 | A | Codex | ✅ PASS | validator.py 合规 |
| 2026-06-09 20:15 | B | Codex | 🟡 SF-L1 | 多改了 1 个注释 → 已回滚 |
| 2026-06-09 20:30 | D | Claude | 🟠 CONFLICT | config.py 被两个 Agent 同时修改 → 已仲裁 |
```
