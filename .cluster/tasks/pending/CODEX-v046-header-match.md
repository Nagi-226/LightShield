# CODEX-v046-header-match：engine.py HTTP 响应头匹配 收发实现

> **【Agent：Codex CLI】**
> **【模型：GPT-5.5（推理天花板——安全关键代码）】**
> **【下发 Agent：Claude Code】**
> **【关联版本：v0.0.46 → v1.0.0】**
> **【关联 TODO：engine.py:399 `TODO(v1.0.0)`】**

---

## ⚠️ 核心约束摘要（≤5 条，不可被上下文稀释覆盖）

| # | 约束 | 违反后果 |
|---|------|---------|
| 1 | 不修改 `BaseAdapter` / `ScanResult` / `VulnFinding` 的核心字段定义（向后兼容） | 所有适配器调用方静默崩溃 |
| 2 | HTTP 响应头采集**仅在 web_vuln_scanner 内**实现，不影响 nmap/nuclei/MSF 适配器 | 引入不必要的耦合 |
| 3 | header 匹配规则中的 `pattern` 字段使用 `re.search`（子串匹配），非 `re.fullmatch`——安全工具规则通常只需匹配关键特征 | 规则编写难度过高，漏报 |
| 4 | `_match_header` 占位实现（仅检测 HTTP 服务存在性）**必须被替换**为真正的 header 匹配逻辑，不是在其上叠加 | 叠加式改法引入死代码 |
| 5 | 新增规则必须使用**仅检测特征**（如 `Server: nginx/1.2` 版本泄露），不依赖主动攻击 payload | 合规红线 R1 违反 |

---

## ⚠️ 提问姿态约束（来自注意力机制原理）

**本任务禁止的指令方式**：

| ❌ 禁止 | ✅ 必须 |
|--------|--------|
| "实现 header 匹配就对了" | "遍历所有已有的 match_type（service_version/fingerprint/header），新实现与它们的一致性如何？接口契约是否相同？" |
| "这样存 headers 没问题" | "ScanResult.services 的 headers 字段新增后，所有现有代码路径是否兼容？分别检查序列化/反序列化/报告生成/数据库存储" |
| "规则够用了" | "分别考虑缺失 header 头、header 值编码异常、pattern 匹配超时(ReDoS)的情况" |

---

## 一、项目上下文（简短）

LightShield v0.0.46。当前 `engine.py` 的 `_match_header` 方法是占位实现（TODO v1.0.0）——仅检测目标是否有 HTTP 服务即返回发现，**未实际使用规则中的 `header`/`pattern` 字段做 HTTP 响应头内容匹配**。

`web_vuln_scanner` 当前发起 HTTP 请求时不保存响应头，导致规则引擎层无法获取 header 数据进行匹配。需要两步走：采集 → 匹配。

---

## 二、⚠️ 合规约束片段（必读）

| 红线 | 本任务相关？ | 具体要求 |
|:--:|:--:|------|
| R1 | 是 | 新规则仅使用**被动检测**特征（响应头版本泄露、安全头缺失），不包含攻击 payload |
| R2 | 否 | — |
| R3 | 否 | — |
| R4 | 否 | — |
| R5 | 否 | — |
| R6 | 否 | — |

---

## 三、接口契约（明确的输入/输出/异常）

### 3.1 web_vuln_scanner 变更

**现状**：HTTP 请求后不保存响应头。

**目标**：对每个成功响应的 HTTP 服务，将响应头写入 `ScanResult.services` 对应条目。

```python
# services 条目扩展（新增 headers 字段，其余不变）
{
    "name": "http",
    "port": 80,
    "version": "nginx",          # 现有字段
    "headers": {                  # 🆕 新增（可选字段，不存在时不影响现有代码）
        "Server": "nginx/1.24.0",
        "X-Frame-Options": "DENY",
        "Content-Security-Policy": "...",
    }
}
```

**反序列化兼容性**：现有代码（报告生成/数据库存储）走 `svc.get("name")` / `svc.get("port")` 模式，新增的 `"headers"` key 对它们透明。如果存在顾虑，可以分析现有所有 services 遍历点。

### 3.2 engine.py `_match_header` 变更

**现状**（占位）：
```python
def _match_header(self, rule: dict, result: ScanResult) -> VulnFinding | None:
    # 仅检测 HTTP 服务存在性
    for svc in result.services:
        if svc.get("name") == "http":
            return VulnFinding(...)
    return None
```

**目标**（收发实现）：
```python
def _match_header(self, rule: dict, result: ScanResult) -> VulnFinding | None:
    header_name = rule.get("header", "").lower()     # 如 "server"
    pattern = rule.get("pattern", "")                 # 如 r"nginx/1\.([0-9]+)"
    if not header_name or not pattern:
        return None  # 规则缺少必要字段

    for svc in result.services:
        if svc.get("name") != "http":
            continue
        headers = svc.get("headers", {})
        if not headers:
            continue
        # 大小写不敏感匹配 header 名
        actual_value = ...
        if re.search(pattern, actual_value):
            return VulnFinding(...)
    return None
```

**关键设计决策**（需要 Codex 在不确定性声明中给出理由）：
1. header 名匹配：遍历 `headers` dict 做大小写不敏感比较 vs 直接用 `headers.get(header_name)`
2. 空 headers 场景：web_vuln_scanner 未运行时的降级行为
3. ReDoS 防护：pattern 来自规则文件（受信输入），是否需要加 `re.search` 超时？

### 3.3 vuln_rules.json 新增规则

新增 2-3 条使用 `match_type: "header"` 的示例规则：

```json
{
    "rule_id": "VULN-XXX",
    "match_type": "header",
    "header": "Server",
    "pattern": "nginx/1\\.([0-9]|1[0-7])\\.",
    "vuln_type": "outdated_software",
    "severity": "medium",
    "title": "Nginx 版本过旧（< 1.18）",
    "description": "Server 响应头泄露了 Nginx 版本号...",
    "remediation": "升级 Nginx 到最新稳定版，或配置 server_tokens off;"
}
```

建议覆盖的规则场景：
- 软件版本泄露（如 `Server` 头暴露 Nginx/Apache 过旧版本）
- 安全头缺失（如缺少 `X-Frame-Options` / `Content-Security-Policy`，使用否定匹配）

---

## 四、任务详情

### 4.1 现状

- `engine.py:_match_header`：占位实现，仅检测 HTTP 服务存在性
- `web_vuln_scanner.py`：HTTP 请求后不保存响应头
- `vuln_rules.json`：无 `match_type: "header"` 规则
- 测试：`test_engine.py` 有基本规则引擎测试，无 header 匹配专项测试

### 4.2 目标

1. web_vuln_scanner 在扫描 HTTP 服务时捕获响应头并存入 services
2. engine.py `_match_header` 实现真正的 header + pattern 正则匹配
3. vuln_rules.json 新增示例规则
4. 新增测试覆盖
5. 全量回归 991 tests 不下降

### 4.3 要求

1. 响应头采集仅收集**安全相关头 + Server 头**（不全量采集），控制 services 条目大小
2. `_match_header` 的返回值 `VulnFinding.evidence` 字段应包含匹配到的实际 header 值
3. 规则匹配异常（如无效正则）应容错跳过，不中断整体规则匹配
4. 参考 `_match_service_version` 和 `_match_service_fingerprint` 的实现风格

---

## 五、代码要求

- [ ] 所有代码中文注释
- [ ] 类型标注完整（Python 3.10+ typing）
- [ ] 异常捕获完善（网络超时 → 友好提示，无效正则 → 跳过规则）
- [ ] 遵循 CLAUDE.md §四 的六层架构分层（scanner 层采集、engine 层匹配）
- [ ] ruff / mypy / bandit 零违规

---

## 六、测试要求

- [ ] `test_web_vuln_extra.py` 或 `test_web_vuln.py`：验证响应头采集逻辑（mock HTTP response）
- [ ] `test_engine.py`：验证 `_match_header` 匹配/不匹配/headers 缺失/无效 pattern 四种场景
- [ ] 全量回归通过（`python -m pytest tests/ -v`，当前基线 991 tests）
- [ ] 🆕 影响驱动测试：改完代码后 grep 所有引用 `_match_header`、`ScanResult.services`、`web_vuln_scanner` 的测试文件并全部跑过

---

## 七、验收清单

> **Agent 注意**：此清单即子目标列表。每完成一项打勾，完成前不扩展新目标（防 Subgoal Displacement）。

- [ ] web_vuln_scanner 响应头采集逻辑实现
- [ ] engine.py `_match_header` 收发实现（替换占位）
- [ ] vuln_rules.json 新增 ≥2 条 `match_type: "header"` 规则
- [ ] 单元测试新增（响应头采集 + header 匹配四种场景）
- [ ] 全量回归 991 tests 通过
- [ ] pre-commit 全部通过（ruff/mypy/bandit/Gate A）
- [ ] 🆕 Goal Drift 自检通过（对照 AGENT_CODE_OF_CONDUCT.md §8.4）

---

## 八、不确定性声明

> **要求**：Agent 必须列出本次任务中置信度🟡中/🔴低的技术判断，标注替代方案或待确认点。

| 判断 | 置信度 | 替代方案 | 待确认点 |
|------|:--:|------|------|
| headers 存入 `ScanResult.services[i]["headers"]` 是最小侵入方案 | 🟡 | 也可存为独立字段 `ScanResult.response_headers`，但需要改核心 dataclass | 现有 services 序列化/反序列化是否完全兼容 dict 新增 key |
| `re.search` 适合安全规则匹配（子串匹配比精确匹配更实用） | 🟢 | `re.fullmatch` 更严格但规则编写成本高 | — |
| 规则文件是受信输入（本地 JSON），不需要 ReDoS 超时保护 | 🟡 | 加上 `re.search(pattern, value, timeout=1)` 防御深度更好 | Python 3.10 的 `regex` 超时需 `regex` 三方库，`re` 模块不支持 |
| web_vuln_scanner 采集 headers 对现有扫描性能影响可忽略 | 🟢 | — | — |

> **铁律**：🔴 置信度的决策，Agent 不得自行执行。必须先上报 CC 确认。

---

## 九、关联资源

- 关联 TODO：`lightshield/rules/engine.py:399` — `TODO(v1.0.0)`
- 关联模块：
  - `lightshield/scanners/web_vuln_scanner.py`（采集端）
  - `lightshield/rules/engine.py`（匹配端）
  - `lightshield/rules/vuln_rules.json`（规则定义）
  - `lightshield/adapters/base.py`（ScanResult / VulnFinding 数据结构）
- 参考实现：`engine.py:_match_service_version`（类似的字段匹配逻辑）
- 测试参考：`tests/test_engine.py`, `tests/test_web_vuln.py`, `tests/test_web_vuln_extra.py`
