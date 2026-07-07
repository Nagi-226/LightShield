# KIMI-v047-review：v0.0.47 Codex header 匹配引擎独立审查

> **【Agent：Kimi Code CLI（模式 A）】**
> **【模型：K2.7-code · 集群唯一跨模型审查者（Kimi ≠ DS ≠ GPT ≠ Qwen ≠ GLM）】**
> **【下发 Agent：Claude Code】**
> **【依赖】🔴 阻塞版本 tag — 集群硬规则：每版本强制一次独立审查**

---

## ⚠️ 核心约束摘要（≤5 条，不可被上下文稀释覆盖）

| # | 约束 | 违反后果 |
|---|------|---------|
| 1 | 审查范围限定 v0.0.47 diff（e224044→4aaa40c），不扩展到全项目 | 审查报告膨胀、焦点涣散 |
| 2 | 只看 Codex 写的新代码，不看 graphify-out 的自动生成变更 | 把 graph.html 删除当成"破坏了可视化"误报 |
| 3 | `_match_header` 的无效正则容错路径不能判为 bug——这是有意设计 | 误杀防御性容错逻辑 |
| 4 | 作为 Kimi-K2.7-code 独立视角——不同模型，天然不同推理路径 | 同源盲区审查机会被浪费 |
| 5 | 发现分级：C/H/M/L/I，不上报 style/nit | 噪声淹没关键发现 |

---

## ⚠️ 提问姿态约束（来自注意力机制原理）

**本任务禁止的提问/指令方式**：

| ❌ 禁止（封闭/强势/站队式） | ✅ 必须（开放/遍历/双向式） |
|--------------------------|--------------------------|
| "这段代码有没有 bug" | "逐一审查这段代码的边界情况和异常路径" |
| "这个实现对不对" | "这个实现在什么条件下会失败？有哪些我没考虑到的？" |
| "有没有安全漏洞" | "遍历所有 R1-R6 红线，逐条检查违反情况" |
| "正则匹配合不合理" | "穷举这些正则的误报/漏报场景，逐一验证" |

**Agent 自查**（每次输出前）：
- [ ] 我是否因为审查对象的先验可信而降低审查深度？
- [ ] 我是否在用不同模型的视角审查，还是仅仅在"复述对方的正确"？
- [ ] 如果这段代码是我自己写的，我会放过哪些问题？

---

## 一、项目上下文

LightShield v0.0.47，Codex (GPT-5.5) 刚完成了 HTTP 响应头匹配引擎的实现。5 个源文件变更（不含 graphify-out 自动生成），新增 VULN-015（Nginx < 1.18）和 VULN-016（Apache < 2.4.58）两条规则。996 tests / 0 fail / 1 skip。

**关键架构决策**：
- 响应头采集采用白名单模式（`_COLLECTED_RESPONSE_HEADERS` 14 个安全头），不采集所有头——避免 `services` 膨胀
- Headers 存储在 `ScanResult.services[i]["headers"]` —— 不修改 `ScanResult` / `BaseAdapter` / `VulnFinding` 核心字段
- `_match_header` 是 `engine.py` 中的新方法，之前是占位代码

---

## 二、⚠️ 合规约束片段

| 红线 | 本任务相关？ | 具体要求 |
|:--:|:--:|------|
| R1 | 否 | 本任务为代码审查，不涉及主动攻击 |
| R2 | 否 | 不涉及扫描操作 |
| R3 | 否 | 不涉及远控/后门/木马 |
| R4 | 否 | 不涉及目标资产 |
| R5 | 否 | 不涉及 MSF 调用 |
| R6 | 否 | 不涉及扫描操作 |

---

## 三、审查范围：v0.0.47 diff（e224044 → 4aaa40c）

### 3.1 源文件变更（5 文件，不含 graphify-out）

| 文件 | 变更量 | 审查重点 |
|------|:--:|------|
| `lightshield/scanners/web_vuln_scanner.py` | +86/-? | 响应头白名单 + `_collect_http_service` + `_filter_response_headers` + `_server_product` + `_url_port` |
| `lightshield/rules/engine.py` | +47/-? | `_match_header` 完整实现（替代占位代码） |
| `lightshield/rules/vuln_rules.json` | +24 | VULN-015 Nginx / VULN-016 Apache 规则 |
| `tests/test_engine.py` | +90/-? | `_match_header` 四象限测试 |
| `tests/test_web_vuln.py` | +32 | 响应头采集过滤测试 |

### 3.2 接口契约（审查时验证一致性）

```python
# web_vuln_scanner.py — _filter_response_headers
def _filter_response_headers(self, response: requests.Response) -> dict[str, str]:
    """只保留安全相关响应头和 Server，避免 services 记录膨胀。"""
    # 返回值仅包含 _COLLECTED_RESPONSE_HEADERS 白名单中的头

# engine.py — _match_header
def _match_header(self, rule: dict, result: ScanResult) -> VulnFinding | None:
    """HTTP 响应头特征匹配。
    规则字段：header（响应头名，大小写不敏感）、pattern（re.search 子串匹配）
    无效正则 → warning + return None（不抛异常）
    """
```

---

## 四、审查维度（Kimi 独立视角优势）

### 4.1 逻辑正确性（Kimi-K2.7-code 深度执行路径追踪）
- `_filter_response_headers` 对 `Mapping` 类型守卫是否在所有调用路径上都安全
- `_match_header` 的大小写不敏感查找是否存在多 key 冲突（如同时有 `Server` 和 `server`）
- `_server_product` 对畸形 Server 头（空字符串/纯空格/超长）的鲁棒性
- `_url_port` 对非标准 scheme（如 `file://`）的处理

### 4.2 正则模式质量（Kimi 独立评估误报/漏报）
- VULN-015 `(?i)nginx/1\.([0-9]|1[0-7])\.` 是否覆盖所有老旧 Nginx 1.x 版本
- VULN-016 `(?i)apache/2\.4\.(?:[0-9]|[1-4][0-9]|5[0-7])\b` 的边界是否正确（2.4.0-2.4.57）
- 是否遗漏了重要的 Server 头变体（如带括号的 Ubuntu/Debian 补丁版本）

### 4.3 数据流完整性（跨文件追踪）
- `_collect_http_service` → `ScanResult.services` → `_match_header` → `VulnFinding` 的数据流是否完整
- `services[i]["headers"]` 在现有代码中的消费者是否兼容（`dict.get("headers", {})` 是否足够）

### 4.4 安全边界（对照 R1-R6）
- 响应头采集是否会意外泄露用户敏感信息（如 `Set-Cookie` 被误采集——需验证白名单过滤）
- 正则是否存在 ReDoS 风险（回溯爆炸——尤其 `(?i)` 配合 `\b` 的场景）

---

## 五、审查步骤

### Step 1：独立阅读源码（15 min）
**不要先看 Codex 的注释或 commit message**。用自己的视角理解每个函数的意图和边界。

### Step 2：构造反例（15 min）
对每个新函数，问自己：
- 如果我来写单元测试，哪些输入会打破它？
- 这个函数的"隐性契约"（调用方对返回值的假设）是什么？

### Step 3：对照 v0.0.46 基准（10 min）
- `_match_header` v0.0.46 是占位代码 → v0.0.47 是完整实现——是否有功能退化？
- 新增的 `_collect_http_service` 调用是否改变了 `web_vuln_scanner.scan()` 的语义？

### Step 4：对照测试验证（10 min）
- 测试是否覆盖了 Step 2 中构造的反例？
- Codex 的测试是否存在"测试实现了功能而非验证了功能"的问题？

### Step 5：输出审查报告（20 min）
格式要求：
```markdown
# Kimi v0.0.47 独立审查报告

## 总体结论（一段话）

## CRITICAL / HIGH / MEDIUM（如有）
| 编号 | 严重度 | 文件:行号 | 问题 | 怎么触发 | 建议修复 |

## LOW / INFO（如有）
| 编号 | 严重度 | 文件:行号 | 问题 | 建议 |

## 通过的维度（明确列出）
- 逻辑正确性：通过 / 发现 N 问题
- 正则质量：通过 / 发现 N 问题
- 数据流完整性：通过 / 发现 N 问题
- 安全边界：通过 / 发现 N 问题
- 测试充分性：通过 / 发现 N 问题

## 已知债务（如有新增）
```

---

## 六、验收清单

- [ ] 独立读完所有 5 个源文件的 diff
- [ ] 构造了至少 3 个反例并验证代码是否处理
- [ ] 审查了 VULN-015/016 正则的误报/漏报
- [ ] 验证了 `_filter_response_headers` 白名单未被绕过
- [ ] 验证了 `_match_header` 的大小写不敏感查找无冲突
- [ ] 审查报告已写入 `docs/review-v047-kimi.md`
- [ ] 发现分级使用 C/H/M/L/I 五级体系，不上报 style/nit
- [ ] Goal Drift 自检通过（对照 AGENT_CODE_OF_CONDUCT.md §8.4）

---

## 七、不确定性声明

| 判断 | 置信度 | 替代方案 | 待确认点 |
|------|:--:|------|------|
| {审查中发现的技术判断} | 🟢/🟡/🔴 | {替代方案} | {待确认点} |

---

## 八、关联资源

- 审查对象 commit：`4aaa40c`（v0.0.47）
- Codex 任务文件：`.cluster/tasks/archive/CODEX-v046-header-match.md`
- 集群规则：`.cluster/CLUSTER.md` 规则 #4 — Kimi 每版本强制一次独立审查
- 审查清单：`.guardrails/REVIEW_CHECKLIST.md`
- Codex 反馈原文：见 CC 会话中 Codex 的交付报告
