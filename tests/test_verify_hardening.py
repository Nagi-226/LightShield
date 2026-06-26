"""LightShield v0.0.40 — verify_hardening 纯函数单元测试

测试目标：
  - verify_hardening 的三类分桶（resolved/remaining/regressed）
  - 三种 verdict 判定（verified/partial/failed）及其边界
  - 比对键 (vuln_type, port) 的正确性（同类型不同端口算两条）
  - 空输入、完全覆盖等边界
  - VerificationResult.to_dict() JSON 可序列化

所有测试构造 before/after VulnFinding 列表输入，纯函数无 mock 需求。
"""

from __future__ import annotations

import json

import pytest

from lightshield.adapters.base import VulnFinding
from lightshield.harden.verify import verify_hardening
from lightshield.utils.constants import RiskLevel

# =============================================================================
# 测试辅助
# =============================================================================


def _finding(
    vuln_type: str,
    port: int | None = None,
    severity: RiskLevel = RiskLevel.HIGH,
) -> VulnFinding:
    """快速构造一个 VulnFinding 实例，用于测试。"""
    return VulnFinding(
        vuln_type=vuln_type,
        severity=severity,
        title=f"测试风险 {vuln_type}",
        description="测试用",
        remediation="测试修复建议",
        port=port,
    )


# =============================================================================
# 分桶测试
# =============================================================================


class TestBucketing:
    """三分桶（resolved/remaining/regressed）的正确性。"""

    def test_all_resolved(self):
        """加固前有 2 个风险，加固后全部消失 → verified。"""
        before = [_finding("high_risk_port", 22), _finding("sqli")]
        after: list[VulnFinding] = []
        r = verify_hardening(before, after, "127.0.0.1")
        assert r.verdict == "verified"
        assert len(r.resolved) == 2
        assert len(r.remaining) == 0
        assert len(r.regressed) == 0
        assert r.before_count == 2
        assert r.after_count == 0

    def test_some_resolved_some_remaining(self):
        """部分修复 → partial。"""
        before = [_finding("high_risk_port", 22), _finding("high_risk_port", 3306)]
        after = [_finding("high_risk_port", 3306)]
        r = verify_hardening(before, after, "127.0.0.1")
        assert r.verdict == "partial"
        assert len(r.resolved) == 1
        assert r.resolved[0]["port"] == 22
        assert len(r.remaining) == 1
        assert r.remaining[0]["port"] == 3306
        assert len(r.regressed) == 0

    def test_none_resolved_all_remaining(self):
        """未修复任何风险 → failed。"""
        before = [_finding("high_risk_port", 22), _finding("high_risk_port", 3306)]
        after = [_finding("high_risk_port", 22), _finding("high_risk_port", 3306)]
        r = verify_hardening(before, after, "127.0.0.1")
        assert r.verdict == "failed"
        assert len(r.resolved) == 0
        assert len(r.remaining) == 2
        assert len(r.regressed) == 0

    def test_only_regressed_no_resolved(self):
        """Resolved 为空 + regressed 非空 → failed。

        before 有 A/22；after 仍有 A/22 且多了 B/3306。
        即 A/22 未消除（resolved=0），同时引入 B/3306（regressed=1）。
        """
        before = [_finding("high_risk_port", 22)]
        after = [_finding("high_risk_port", 22), _finding("high_risk_port", 3306)]
        r = verify_hardening(before, after, "127.0.0.1")
        assert r.verdict == "failed"
        assert len(r.resolved) == 0
        assert len(r.remaining) == 1  # 端口 22 仍在
        assert len(r.regressed) == 1  # 端口 3306 新出现

    def test_resolved_and_regressed(self):
        """有修复也有回归 → partial。"""
        before = [_finding("high_risk_port", 22), _finding("high_risk_port", 3306)]
        after = [_finding("high_risk_port", 22), _finding("sqli")]
        r = verify_hardening(before, after, "127.0.0.1")
        assert r.verdict == "partial"
        assert len(r.resolved) == 1  # 端口 3306 修复
        assert len(r.remaining) == 1  # 端口 22 仍存在
        assert len(r.regressed) == 1  # sql injection 新出现

    def test_same_type_different_port_different_keys(self):
        """同 (vuln_type) 不同 (port) → 两条独立的比对键。"""
        before = [_finding("high_risk_port", 22), _finding("high_risk_port", 3306)]
        after = [_finding("high_risk_port", 3306)]
        r = verify_hardening(before, after, "127.0.0.1")
        assert len(r.resolved) == 1
        assert r.resolved[0]["port"] == 22
        assert len(r.remaining) == 1
        assert r.remaining[0]["port"] == 3306

    def test_same_port_different_type_different_keys(self):
        """同端口、不同漏洞类型 → 两条独立的比对键。"""
        before = [_finding("high_risk_port", 22), _finding("weak_password")]
        after = [_finding("high_risk_port", 22)]
        r = verify_hardening(before, after, "127.0.0.1")
        assert len(r.resolved) == 1
        assert r.resolved[0]["vuln_type"] == "weak_password"
        assert len(r.remaining) == 1
        assert r.remaining[0]["vuln_type"] == "high_risk_port"


# =============================================================================
# verdict 边界测试
# =============================================================================


class TestVerdictBoundary:
    """三种 verdict 的边界条件。"""

    def test_verified_exact(self):
        """resolved>0, remaining=0, regressed=0 → verified。"""
        r = verify_hardening(
            [_finding("a", 1)],
            [],
            "x",
        )
        assert r.verdict == "verified"

    def test_partial_by_remaining(self):
        """resolved>0 但 remaining>0 → partial。"""
        r = verify_hardening(
            [_finding("a", 1), _finding("b", 2)],
            [_finding("b", 2)],
            "x",
        )
        assert r.verdict == "partial"

    def test_partial_by_regressed(self):
        """resolved>0 但 regressed>0 → partial。"""
        r = verify_hardening(
            [_finding("a", 1), _finding("b", 2)],
            [_finding("a", 1), _finding("c", 3)],
            "x",
        )
        assert r.verdict == "partial"

    def test_failed_no_resolved(self):
        """resolved=0 → failed（即便 remaining 为空）。"""
        r = verify_hardening(
            [_finding("a", 1)],
            [_finding("a", 1)],
            "x",
        )
        assert r.verdict == "failed"

    def test_failed_regressed_only(self):
        """regressed>0 且 resolved=0 → failed。

        原风险未消除 + 新风险出现 = 加固失败。
        """
        r = verify_hardening(
            [_finding("a", 1)],
            [_finding("a", 1), _finding("b", 2)],  # a/1 仍在 + b/2 新出现
            "x",
        )
        assert r.verdict == "failed"
        assert len(r.resolved) == 0
        assert len(r.regressed) == 1


# =============================================================================
# 空输入 / 边界
# =============================================================================


class TestEdgeCases:
    """边界情况：空列表、None port、重复键等。"""

    def test_empty_both(self):
        """空输入 → failed（无风险可消除）。"""
        r = verify_hardening([], [], "127.0.0.1")
        assert r.verdict == "failed"
        assert r.before_count == 0
        assert r.after_count == 0
        assert len(r.resolved) == 0

    def test_empty_before_nonempty_after(self):
        """加固前无风险、加固后有风险 → failed（全是 regressed，无 resolved）。"""
        r = verify_hardening(
            [],
            [_finding("high_risk_port", 22)],
            "x",
        )
        assert r.verdict == "failed"
        assert len(r.regressed) == 1
        assert len(r.resolved) == 0

    def test_nonempty_before_empty_after(self):
        """加固前有风险、加固后为空 → verified（全部修复）。"""
        r = verify_hardening(
            [_finding("high_risk_port", 22)],
            [],
            "x",
        )
        assert r.verdict == "verified"
        assert len(r.resolved) == 1

    def test_none_port_as_key(self):
        """port=None 是合法比对键（Web 类漏洞无端口）。"""
        before = [_finding("sqli", None), _finding("xss_reflected", None)]
        after = [_finding("sqli", None)]
        r = verify_hardening(before, after, "x")
        assert len(r.resolved) == 1
        assert r.resolved[0]["vuln_type"] == "xss_reflected"
        assert len(r.remaining) == 1
        assert r.remaining[0]["vuln_type"] == "sqli"

    def test_duplicate_keys_deduplicated(self):
        """同键多个 finding → 仅保留第一个（去重）。"""
        before = [
            _finding("sqli"),
            _finding("sqli", None),  # 同键 (sqli, None)
        ]
        after: list[VulnFinding] = []
        r = verify_hardening(before, after, "x")
        assert len(r.resolved) == 1  # 去重后只有一条
        assert r.verdict == "verified"

    def test_target_passed_through(self):
        """Target 字段正确透传。"""
        r = verify_hardening([], [], "example.com")
        assert r.target == "example.com"


# =============================================================================
# to_dict 测试
# =============================================================================


class TestToDict:
    """VerificationResult.to_dict() JSON 可序列化性。"""

    def test_dict_json_serializable(self):
        """to_dict 输出可直接 json.dumps 无崩溃。"""
        r = verify_hardening(
            [_finding("high_risk_port", 22), _finding("sqli")],
            [],
            "127.0.0.1",
        )
        d = r.to_dict()
        s = json.dumps(d, ensure_ascii=False)
        assert isinstance(s, str)
        assert "verified" in s

    def test_dict_fields_complete(self):
        """to_dict 包含所有契约字段。"""
        r = verify_hardening(
            [_finding("a", 1)],
            [_finding("a", 1)],
            "t",
        )
        d = r.to_dict()
        expected_keys = {
            "target",
            "resolved",
            "remaining",
            "regressed",
            "before_count",
            "after_count",
            "verdict",
            "audit_id",
        }
        assert set(d.keys()) == expected_keys

    def test_dict_nested_fields_present(self):
        """Resolved 中的 finding dict 包含关键字段。"""
        r = verify_hardening(
            [_finding("high_risk_port", 22)],
            [],
            "127.0.0.1",
        )
        d = r.to_dict()
        resolved_item = d["resolved"][0]
        assert "vuln_type" in resolved_item
        assert "port" in resolved_item
        assert "severity" in resolved_item
        assert "title" in resolved_item
        assert resolved_item["port"] == 22

    def test_dict_counts_are_ints(self):
        """before_count / after_count 为整数类型。"""
        r = verify_hardening(
            [_finding("a"), _finding("b")],
            [],
            "x",
        )
        d = r.to_dict()
        assert isinstance(d["before_count"], int)
        assert isinstance(d["after_count"], int)

    def test_audit_id_default_empty(self):
        """默认 audit_id 为空字符串。"""
        r = verify_hardening([], [], "x")
        assert r.audit_id == ""


# =============================================================================
# 直接执行
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
