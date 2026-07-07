# Kimi v0.0.47 独立审查报告

> **审查对象**：commit `4aaa40c`（v0.0.47 vs v0.0.46 `e224044`）
> **审查范围**：5 个源文件（不含 graphify-out 自动生成）
>   - `lightshield/scanners/web_vuln_scanner.py`
>   - `lightshield/rules/engine.py`
>   - `lightshield/rules/vuln_rules.json`
>   - `tests/test_engine.py`
>   - `tests/test_web_vuln.py`
> **审查日期**：2026-07-04
> **测试基线**：996 passed / 0 failed / 1 skipped

## 模型独立性声明

- **审查模型**：Kimi-K2.7-code (Moonshot)
- **被审查代码作者模型**：Codex / GPT-5.5 (OpenAI)
- **跨模型审查**：✅ 是（Kimi ≠ GPT 家族）
- **审查方式**：独立阅读源码 + 构造反例 + 对照测试 + 边界验证

---

## 总体结论

v0.0.47 的 HTTP 响应头匹配引擎整体实现符合预期：白名单采集避免 `services` 膨胀，`_match_header` 完成从占位代码到真实正则子串匹配的替换，VULN-015/016 正则边界正确，测试覆盖了四象限（命中/未命中/缺头/无效正则）。全量测试 996/0/1 通过，未引入合规红线风险。

发现 **1 个 MEDIUM**：`_server_product` 对纯空白 `Server` 头处理不当，会触发 `IndexError` 并导致整次 Web 扫描返回 `FAILED`。另有 2 个 INFO 级改进点（正则覆盖 wording、额外 HTTP 请求）。无 CRITICAL/HIGH。

---

## CRITICAL / HIGH / MEDIUM

| 编号 | 严重度 | 文件:行号 | 问题 | 怎么触发 | 建议修复 |
|:--:|:--:|:--|:--|:--|:--|
| M-01 | 🟡 MEDIUM | `lightshield/scanners/web_vuln_scanner.py:397-401` | `_server_product` 未处理空白-only 字符串，`"   ".split()` 返回空列表，导致 `IndexError` | 目标返回 `Server:` 头但值为纯空格/制表符，例如 `Server:   ` | 将空值判断改为 `if not server_header or not server_header.strip(): return ""` |

### M-01 详细说明

```python
@staticmethod
def _server_product(server_header: str) -> str:
    if not server_header:          # 对 "   " 判断为 True，继续执行
        return ""
    return server_header.split()[0][:80]   # split() -> []，IndexError
```

在 `_collect_http_service` 中调用：

```python
service = {
    "name": "http",
    "port": self._url_port(url),
    "version": self._server_product(headers.get("Server", "")),
}
```

虽然 `scan()` 外层有 `except Exception` 兜底不会让进程崩溃，但会使得本次 Web 扫描整体 `FAILED`，丢失所有其他 findings。这是一个真实的鲁棒性缺陷，且未在现有测试覆盖。

**验证脚本输出**（已跑通）：

```text
=== scan with whitespace-only Server header ===
status=ScanStatus.FAILED, error=Web 漏洞检测失败：list index out of range
```

---

## LOW / INFO

| 编号 | 严重度 | 文件:行号 | 问题 | 建议 |
|:--:|:--:|:--|:--|:--|
| I-01 | 💡 INFO | `lightshield/rules/vuln_rules.json:167-177` | VULN-015 描述写“Nginx 1.18 之前的版本特征”，但正则 `(?i)nginx/1\.([0-9]|1[0-7])\.)` 只匹配 Nginx 1.0–1.17，不包含 Nginx 0.x | 若有意只覆盖 1.x，可将描述改为“Nginx 1.18 之前的 1.x 版本特征”；如需覆盖 0.x，扩展正则为 `(?i)nginx/(0\.\d+|1\.([0-9]|1[0-7]))\.` |
| I-02 | 💡 INFO | `lightshield/scanners/web_vuln_scanner.py:367-381` | `_collect_http_service` 在 `scan()` 开头发起一次 HTTP 请求获取响应头，随后 `detect_sqli` 基线请求会再次请求同一 URL/params，存在一次冗余请求 | 可在后续版本中考虑把 `_collect_http_service` 的响应复用为 SQLi/XSS 基线响应，但会引入函数耦合，需权衡 |
| I-03 | 💡 INFO | `lightshield/rules/engine.py:425-431` | `_match_header` 大小写不敏感遍历普通 dict；若 `headers` 中同时存在 `Server` 和 `server`，结果取决于 dict 迭代顺序 | 当前流程中 `_filter_response_headers` 已统一规范名，此情况不会出现；如对外部构造的 ScanResult 有要求，可在文档中声明“headers 应使用规范头名” |

---

## 通过的维度

- **逻辑正确性**：发现 1 问题（M-01 `_server_product` 空白头）。`_filter_response_headers` 的 `Mapping` 守卫、`_match_header` 的大小写不敏感查找、`_url_port` 的非标准 scheme/非法端口回退均正确。
- **正则质量**：VULN-015/016 边界正确，无 ReDoS 风险。实测 10k 字符输入匹配耗时 < 0.0002s。
- **数据流完整性**：`_collect_http_service` → `ScanResult.services` → `_match_header` → `VulnFinding` 链路完整；`services[i]["headers"]` 的唯一消费者使用 `dict.get("headers", {})`，兼容。
- **安全边界**：白名单未收集 `Set-Cookie` 等敏感头，无 R1-R6 违规；正则无回溯爆炸风险。
- **测试充分性**：四象限覆盖 header 命中/未命中/缺头/无效正则；响应头过滤测试验证白名单有效。未覆盖 M-01 空白头场景。

---

## 已知债务（新增）

- `web_vuln_scanner._server_product` 对纯空白 `Server` 头存在 `IndexError`（M-01）。

---

## 不确定性声明

| 判断 | 置信度 | 替代方案 | 待确认点 |
|:--|:--:|:--|:--|
| M-01 应按 MEDIUM 定级 | 🟢 高 | 若团队认为纯空白 Server 头极罕见，可降级为 LOW | 是否需要在本版本修复，还是作为已知债务带入 v1.0.0 |
| I-01 是否需扩展正则覆盖 Nginx 0.x | 🟡 中 | 保持现状，仅修正描述 wording | 产品对“老旧版本”定义是否包含 Nginx 0.x |
| I-02 冗余请求是否值得重构 | 🟡 中 | 维持现状，不做改动 | 性能验收是否对 Web 扫描请求数有硬性上限 |

---

## 审查验收清单

- [x] 独立读完所有 5 个源文件的 diff
- [x] 构造了至少 3 个反例并验证代码是否处理（空白 Server 头、非标准 scheme、重复大小写 key、非 dict headers、int value、ReDoS）
- [x] 审查了 VULN-015/016 正则的误报/漏报
- [x] 验证了 `_filter_response_headers` 白名单未被绕过（`Set-Cookie` 未采集）
- [x] 验证了 `_match_header` 的大小写不敏感查找无冲突（在规范名 dict 前提下）
- [x] 审查报告已写入 `docs/review-v047-kimi.md`
- [x] 发现分级使用 C/H/M/L/I 五级体系，未上报 style/nit
- [x] Goal Drift 自检通过：未超出 5 文件范围，未改动 graphify-out，未将防御性容错路径误判为 bug
