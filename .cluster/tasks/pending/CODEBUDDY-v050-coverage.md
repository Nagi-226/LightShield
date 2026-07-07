# CODEBUDDY-v050-coverage：覆盖率 82.95% → 85% 冲刺

> **【CodeBuddy 模式：B · WorkBuddy CLI（批量测试生成）】**
> **【模型切换：DeepSeek-V4-Pro】**
> **【下发 Agent：Claude Code】**
> **【依赖】🟢 不阻塞版本迭代。LOW-001~005 已在 v0.0.49 完成。**
> **【基线】1001 tests / 0 fail / 1 skip / 覆盖率 ~82.95%**

---

## ⚠️ 核心约束摘要（≤5 条）

| # | 约束 | 违反后果 |
|---|------|---------|
| 1 | **只加测试，不改源码** | 无意间引入回归 |
| 2 | 测试必须独立、可重复 | 跨测试状态污染 |
| 3 | 1001 tests 基线不降——每加一个测试就跑全量确认零回归 | 覆盖率上升但回归被打破 |
| 4 | 禁止为凑覆盖率写空断言——每个测试必须有明确的"验证什么"注释 | 假覆盖率 |
| 5 | 不在测试中引入新的外部依赖（网络/Docker/特殊文件路径） | CI 不可运行 |

---

## 一、项目上下文

LightShield v0.0.49。LOW-001~005 五个特定测试缺口已在 v0.0.49 修复。覆盖率 ~82.95%，目标 85%。剩余未覆盖代码集中在三个 I/O 重路径模块：

| 文件 | 未覆盖行数 | 特征 |
|------|:--:|------|
| `lightshield/cli.py` | ~286 行 | CLI 参数解析、交互确认、Hook 执行 |
| `lightshield/core.py` closed_loop | ~124 行 | 闭环编排：扫描→推荐→加固→复扫→验证 |
| `lightshield/web/routes.py` | ~75 行 | Flask API 端点 |

**策略**：先 `--cov-report=term-missing` 精确定位 → 优先纯函数 → mock 隔离 → 复杂 I/O 放最后。

---

## 二、任务详情

### 2.1 准备阶段（定位缺口）

```bash
pytest tests/ --cov=lightshield --cov-report=term-missing -q 2>&1 | grep -E "cli\.py|core\.py|routes\.py"
```

精确列出每个文件未覆盖的行号区间。

### 2.2 阶段 A（优先）— cli.py 纯函数覆盖

cli.py 中不涉及 `input()` / `sys.argv` 的纯逻辑函数优先覆盖：
- 参数校验函数（`validate_*` 系列）
- 格式化/输出函数（`_format_*` 系列）
- 配置加载函数

### 2.3 阶段 B — core.closed_loop mock 覆盖

闭环编排的四个阶段（scan→recommend→harden→verify），通过 mock 隔离测试：
- mock `LightShieldCore` 内部方法返回值
- 验证阶段间数据传递正确性
- 验证异常路径（任一阶段失败时的短路行为）

### 2.4 阶段 C — routes.py API 端点

Flask test_client 集成测试：
- `/api/scan` 端点参数校验
- `/api/recommend` / `/api/harden` 端点
- 错误状态码路径（400/404/500）

---

## 三、代码要求

- [ ] 所有测试中文注释
- [ ] 每个测试函数有明确的"验证什么"docstring
- [ ] 使用 pytest 标准断言，不引入第三方断言库
- [ ] mock 使用 `unittest.mock`，不引入新依赖

---

## 四、验收清单

- [ ] `pytest tests/ -q` 全部通过，测试数 ≥ 1001
- [ ] 覆盖率 ≥ 85%（`fail_under = 85` 替代当前 79）
- [ ] 无新增 ruff/mypy/bandit 违规
- [ ] pre-commit 全绿
- [ ] 全量回归零退化
- [ ] Goal Drift 自检通过

---

## 五、不确定性声明

| 判断 | 置信度 | 替代方案 | 待确认点 |
|------|:--:|------|------|
| DS-V4-Pro 足以完成批量测试生成 | 🟢 | GLM-5.2 推理更强但配额应留给架构二审 | — |
| 85% 门槛不会迫使写无效测试 | 🟡 | 如果剩余未覆盖代码确实是纯 I/O，84% 也可接受 | 需 `term-missing` 输出后确认 |
