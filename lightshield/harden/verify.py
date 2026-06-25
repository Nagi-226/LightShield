"""LightShield v0.0.40 加固闭环 — 验证比对纯函数

本模块包含验证环节（闭环第⑥步）的数据结构与比对逻辑。
`verify_hardening` 是纯函数，无 I/O、无副作用、不联网——
构造 before/after 列表即可全量单测覆盖。

接口契约来源：docs/design-v040-closed-loop.md §5.2 + §7
决策背景：docs/adr-v040-execution-substrate.md

用法：
    from lightshield.harden.verify import VerificationResult, verify_hardening
    result = verify_hardening(before_findings, after_findings, "127.0.0.1")
"""

from __future__ import annotations

from dataclasses import dataclass, field

from lightshield.adapters.base import VulnFinding


# =============================================================================
# 数据结构
# =============================================================================


@dataclass
class VerificationResult:
    """加固前后扫描比对结果——反馈闭环中“修复是否生效”的判定。

    Attributes:
        target: 加固目标（IP/域名）
        resolved: 加固前有、加固后消失的风险（修复成功）
        remaining: 加固前后都在的风险（未修复）
        regressed: 加固后新增的风险（加固引入回归）
        before_count: 加固前扫描发现的总风险数
        after_count: 加固后扫描发现的总风险数
        verdict: 总判定 "verified" | "partial" | "failed"
        audit_id: 关联审计日志的 ID
    """

    target: str
    resolved: list[dict] = field(default_factory=list)
    remaining: list[dict] = field(default_factory=list)
    regressed: list[dict] = field(default_factory=list)
    before_count: int = 0
    after_count: int = 0
    verdict: str = "failed"
    audit_id: str = ""

    def to_dict(self) -> dict:
        """导出为字典，以便 Web/报告直接消费（所有值 JSON 可序列化）。"""
        return {
            "target": self.target,
            "resolved": self.resolved,
            "remaining": self.remaining,
            "regressed": self.regressed,
            "before_count": self.before_count,
            "after_count": self.after_count,
            "verdict": self.verdict,
            "audit_id": self.audit_id,
        }


# =============================================================================
# 比对逻辑（纯函数）
# =============================================================================


def _make_key(finding: VulnFinding) -> tuple[str, int | None]:
    """从 VulnFinding 提取比对键：(vuln_type, port)。

    两个 finding 视为“同一风险”当且仅当 vuln_type 与 port 均相等。
    port 为 None 时视为独立键（例如 URL 型漏洞无端口信息）。
    """
    return (finding.vuln_type, finding.port)


def verify_hardening(
    before: list[VulnFinding],
    after: list[VulnFinding],
    target: str,
) -> VerificationResult:
    """对比加固前后两次扫描结果，分类 resolved / remaining / regressed。

    纯函数：无 I/O、无副作用、不联网。输入两个 finding 列表，
    输出一个 VerificationResult。适合全量单测覆盖。

    比对键（契约）——见 docs/design-v040-closed-loop.md §7：
      - 两个 finding 视为“同一风险”当且仅当 (vuln_type, port) 相等。
      - resolved  = before 有、after 无（修复成功）
      - remaining  = before、after 都有（未修复）
      - regressed  = after 有、before 无（加固引入新风险）

    verdict 规则（契约 §5.2）：
      - "verified"  : resolved 非空 且 remaining 为空 且 regressed 为空
      - "partial"   : resolved 非空 但 remaining 或 regressed 非空
      - "failed"    : resolved 为空（未消除任何风险），
                      或 regressed 非空且 resolved 为空

    Args:
        before: 加固前扫描的 VulnFinding 列表
        after:  加固后扫描的 VulnFinding 列表
        target: 加固目标（IP/域名），填入结果

    Returns:
        VerificationResult 包含三分桶 + 计数 + verdict
    """
    # ---- 构建键集合 ----
    before_keys: dict[tuple[str, int | None], VulnFinding] = {}
    for f in before:
        key = _make_key(f)
        # 同键去重：仅保留首次出现的 finding
        if key not in before_keys:
            before_keys[key] = f

    after_keys: dict[tuple[str, int | None], VulnFinding] = {}
    for f in after:
        key = _make_key(f)
        if key not in after_keys:
            after_keys[key] = f

    # ---- 三分桶（按契约比对键分拣） ----
    resolved: list[dict] = []
    remaining: list[dict] = []
    regressed: list[dict] = []

    before_key_set = set(before_keys.keys())
    after_key_set = set(after_keys.keys())

    # resolved：before 有、after 无
    for key in before_key_set - after_key_set:
        resolved.append(before_keys[key].to_dict())

    # remaining：before 和 after 都有
    for key in before_key_set & after_key_set:
        remaining.append(before_keys[key].to_dict())

    # regressed：after 有、before 无
    for key in after_key_set - before_key_set:
        regressed.append(after_keys[key].to_dict())

    # ---- verdict ----
    before_count = len(before)
    after_count = len(after)

    has_resolved = len(resolved) > 0
    has_remaining = len(remaining) > 0
    has_regressed = len(regressed) > 0

    if has_resolved and not has_remaining and not has_regressed:
        verdict = "verified"
    elif has_resolved and (has_remaining or has_regressed):
        verdict = "partial"
    else:
        # resolved 为空 → failed
        verdict = "failed"

    return VerificationResult(
        target=target,
        resolved=resolved,
        remaining=remaining,
        regressed=regressed,
        before_count=before_count,
        after_count=after_count,
        verdict=verdict,
        audit_id="",
    )


# =============================================================================
# 自检
# =============================================================================

if __name__ == "__main__":
    from lightshield.utils.constants import RiskLevel

    print("=== verify_hardening 自检 ===")

    # 构造测试 finding 的辅助函数
    def _f(
        vuln_type: str,
        port: int | None = None,
        severity: RiskLevel = RiskLevel.HIGH,
    ) -> VulnFinding:
        return VulnFinding(
            vuln_type=vuln_type,
            severity=severity,
            title=f"测试风险 {vuln_type}",
            description="测试用",
            remediation="测试修复建议",
            port=port,
        )

    # 场景1：全部修复 → verified
    before = [_f("high_risk_port", 22), _f("sqli", None)]
    after: list[VulnFinding] = []
    r = verify_hardening(before, after, "127.0.0.1")
    assert r.verdict == "verified", f"预期 verified，实际 {r.verdict}"
    assert len(r.resolved) == 2
    assert len(r.remaining) == 0
    assert len(r.regressed) == 0
    assert r.before_count == 2
    assert r.after_count == 0
    print("  [OK] 全部修复 → verified（2 条 resolved）")

    # 场景2：部分修复 → partial
    before2 = [_f("high_risk_port", 22), _f("high_risk_port", 3306)]
    after2 = [_f("high_risk_port", 3306)]  # 22 修了，3306 还在
    r2 = verify_hardening(before2, after2, "127.0.0.1")
    assert r2.verdict == "partial", f"预期 partial，实际 {r2.verdict}"
    assert len(r2.resolved) == 1  # 端口 22 消除
    assert len(r2.remaining) == 1  # 端口 3306 仍在
    assert len(r2.regressed) == 0
    print("  [OK] 部分修复 → partial（1 resolved + 1 remaining）")

    # 场景3：未修复任何风险 → failed
    before3 = [_f("high_risk_port", 22), _f("high_risk_port", 3306)]
    after3 = [_f("high_risk_port", 22), _f("high_risk_port", 3306)]
    r3 = verify_hardening(before3, after3, "127.0.0.1")
    assert r3.verdict == "failed", f"预期 failed，实际 {r3.verdict}"
    assert len(r3.resolved) == 0
    assert len(r3.remaining) == 2
    print("  [OK] 未修复任何风险 → failed（0 resolved）")

    # 场景4：加固引入新风险（swap：旧端口修复 + 新端口出现）→ partial
    before4 = [_f("high_risk_port", 22)]
    after4 = [_f("high_risk_port", 3306)]  # 22 修了（resolved），3306 是新的（regressed）
    r4 = verify_hardening(before4, after4, "127.0.0.1")
    assert r4.verdict == "partial", f"预期 partial（有修复+回归），实际 {r4.verdict}"
    assert len(r4.resolved) == 1  # 端口 22 消失 → resolved
    assert len(r4.regressed) == 1  # 端口 3306 新出现 → regressed
    assert r4.resolved[0]["port"] == 22
    assert r4.regressed[0]["port"] == 3306
    print("  [OK] 旧风险修复 + 新风险出现 → partial")

    # 场景5：部分修复但有回归 → partial
    before5 = [_f("high_risk_port", 22), _f("high_risk_port", 3306)]
    after5 = [_f("high_risk_port", 22), _f("sqli", None)]  # 3306 修了，但多了 sqli
    r5 = verify_hardening(before5, after5, "127.0.0.1")
    assert r5.verdict == "partial", f"预期 partial，实际 {r5.verdict}"
    assert len(r5.resolved) == 1  # 端口 3306
    assert len(r5.remaining) == 1  # 端口 22
    assert len(r5.regressed) == 1  # sqli
    print("  [OK] 有修复也有回归 → partial（1 resolved + 1 remaining + 1 regressed）")

    # 场景6：(vuln_type, port) 同类型不同端口算两条
    before6 = [_f("high_risk_port", 22), _f("high_risk_port", 3306)]
    after6 = [_f("high_risk_port", 3306)]
    r6 = verify_hardening(before6, after6, "127.0.0.1")
    assert len(r6.resolved) == 1
    assert r6.resolved[0]["port"] == 22
    assert len(r6.remaining) == 1
    assert r6.remaining[0]["port"] == 3306
    print("  [OK] 同类型不同端口 → 两条独立（resolved=22, remaining=3306）")

    # 场景7：空输入
    r7 = verify_hardening([], [], "127.0.0.1")
    assert r7.verdict == "failed", f"空输入预期 failed，实际 {r7.verdict}"
    assert r7.before_count == 0
    assert r7.after_count == 0
    print("  [OK] 空输入 → failed（无风险可消除）")

    # 场景8：to_dict 往返验证
    d = r.to_dict()
    assert d["target"] == "127.0.0.1"
    assert d["verdict"] == "verified"
    assert isinstance(d["resolved"], list)
    assert isinstance(d["before_count"], int)
    print("  [OK] to_dict 往返验证通过")

    print("=== verify_hardening 自检全部通过 ===")
