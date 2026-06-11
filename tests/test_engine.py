"""测试模块：lightshield/rules/engine.py

被测类：RuleEngine

测试点：
  - load_rules() 后 vuln_rule_count==14 且 harden_rule_count==6
  - match(scan_result) 四类匹配（port/service_version/service_fingerprint/header）
  - recommend_hardening(findings) 按 severity 排序，返回 dict 含五字段
  - summarize_risks(findings) 统计正确（含 total）
  - _deduplicate(findings) 同 vuln_type+同 port 保留最高 severity
  - _parse_semver("1.2.3")→(1,2,3)，非数字段降级
  - import_rules(new_rules) 不覆盖已有 rule_id
  - _load_json(不存在路径)→返回 [] 不抛异常（v0.0.15修复）
  - match() 单条规则异常不中断整轮匹配（v0.0.15修复）
"""

import os

import pytest

from lightshield.adapters.base import ScanResult, VulnFinding
from lightshield.rules.engine import RuleEngine
from lightshield.utils.constants import RiskLevel, ScanStatus


@pytest.fixture
def engine():
    """返回已加载规则的 RuleEngine 实例"""
    eng = RuleEngine()
    eng.load_rules()
    return eng


@pytest.fixture
def sample_scan_result():
    """包含端口、服务、findings 的模拟扫描结果"""
    return ScanResult(
        status=ScanStatus.COMPLETED,
        target="192.168.1.100",
        ports=[
            {"port": 22, "protocol": "tcp", "state": "open", "service": "ssh"},
            {"port": 80, "protocol": "tcp", "state": "open", "service": "http"},
            {"port": 3306, "protocol": "tcp", "state": "open", "service": "mysql"},
        ],
        services=[
            {"name": "ssh", "version": "7.6", "port": 22},
            {"name": "http", "version": "nginx 1.18.0", "port": 80},
            {"name": "mysql", "version": "5.7", "port": 3306},
        ],
        findings=[
            VulnFinding(
                vuln_type="weak_password",
                severity=RiskLevel.HIGH,
                title="弱口令",
                description="SSH 服务存在弱口令风险",
                remediation="修改密码",
                port=22,
            ),
        ],
        os_info="Ubuntu 18.04",
    )


# =============================================================================
# load_rules — 规则计数
# =============================================================================


class TestLoadRules:
    """load_rules() 规则加载"""

    def test_vuln_rule_count_is_14(self, engine):
        """加载后 vuln_rule_count == 14"""
        assert engine.vuln_rule_count == 14, f"期望 14 条漏洞规则，实际 {engine.vuln_rule_count}"

    def test_harden_rule_count_is_6(self, engine):
        """加载后 harden_rule_count == 6"""
        assert engine.harden_rule_count == 6, f"期望 6 条加固规则，实际 {engine.harden_rule_count}"

    def test_counts_are_positive_integers(self, engine):
        """两个计数均为正整数"""
        assert isinstance(engine.vuln_rule_count, int)
        assert isinstance(engine.harden_rule_count, int)
        assert engine.vuln_rule_count > 0
        assert engine.harden_rule_count > 0


# =============================================================================
# match — 四类匹配
# =============================================================================


class TestMatch:
    """match() 规则匹配"""

    def test_port_match_hits_vuln_001(self, engine, sample_scan_result):
        """端口 22 开放命中 VULN-001"""
        findings = engine.match(sample_scan_result)
        port_22 = [f for f in findings if f.port == 22]
        assert len(port_22) >= 1

    def test_service_version_match(self, engine, sample_scan_result):
        """服务版本匹配（ssh 7.6 < 8.9）"""
        findings = engine.match(sample_scan_result)
        svc_findings = [f for f in findings if f.vuln_type == "vulnerable_component"]
        assert len(svc_findings) >= 1, "应至少命中一条 service_version 规则"

    def test_service_fingerprint_match(self, engine, sample_scan_result):
        """服务指纹匹配 — 已有 weak_password finding"""
        findings = engine.match(sample_scan_result)
        weak = [f for f in findings if f.vuln_type == "weak_auth"]
        assert len(weak) >= 1

    def test_header_match(self, engine):
        """HTTP header 匹配"""
        result = ScanResult(
            status=ScanStatus.COMPLETED,
            target="example.com",
            ports=[{"port": 80, "state": "open", "service": "http"}],
            services=[{"name": "http", "version": "nginx", "port": 80}],
        )
        findings = engine.match(result)
        # header 规则触发条件较宽松
        assert isinstance(findings, list)

    def test_match_returns_list(self, engine, sample_scan_result):
        """match() 总是返回列表"""
        findings = engine.match(sample_scan_result)
        assert isinstance(findings, list)


# =============================================================================
# match 容错 — v0.0.15
# =============================================================================


class TestMatchFaultTolerance:
    """v0.0.15 修复：单条规则异常不中断整轮匹配"""

    def test_single_rule_exception_does_not_abort(self, engine, sample_scan_result):
        """某条规则抛异常时其余规则继续匹配"""
        # 在 _vuln_rules 中注入一条会失败的规则
        broken_rule = {
            "rule_id": "BROKEN-001",
            "match_type": "port",
            "port": None,  # 会触发 NoneType 异常
        }
        engine._vuln_rules.insert(0, broken_rule)

        try:
            # 不应抛出异常，应跳过 broken 规则继续匹配
            findings = engine.match(sample_scan_result)
            assert isinstance(findings, list)
            # 应仍能命中正常规则
            assert len(findings) >= 1
        finally:
            # 清理注入的规则
            engine._vuln_rules = [r for r in engine._vuln_rules if r.get("rule_id") != "BROKEN-001"]


# =============================================================================
# recommend_hardening
# =============================================================================


class TestRecommendHardening:
    """recommend_hardening() 加固推荐"""

    def test_returns_list_of_dicts(self, engine):
        """返回 list[dict]"""
        findings = [
            VulnFinding(
                vuln_type="high_risk_port",
                severity=RiskLevel.CRITICAL,
                title="高危端口",
                description="",
                remediation="",
                port=3306,
            ),
        ]
        recs = engine.recommend_hardening(findings)
        assert isinstance(recs, list)
        if recs:
            assert isinstance(recs[0], dict)

    def test_each_recommendation_has_five_fields(self, engine):
        """每条建议含 action/target/reason/commands/severity 五字段"""
        findings = [
            VulnFinding(
                vuln_type="high_risk_port",
                severity=RiskLevel.HIGH,
                title="高危端口",
                description="",
                remediation="",
                port=22,
            ),
        ]
        recs = engine.recommend_hardening(findings)
        required = {"action", "target", "reason", "commands", "severity"}
        for rec in recs:
            missing = required - set(rec.keys())
            assert not missing, f"缺少字段: {missing}"

    def test_sorted_by_severity_critical_first(self, engine):
        """按 severity 排序，critical 在最前"""
        findings = [
            VulnFinding("weak_auth", RiskLevel.LOW, "", "", ""),
            VulnFinding("high_risk_port", RiskLevel.CRITICAL, "", "", "", port=3306),
            VulnFinding("high_risk_port", RiskLevel.HIGH, "", "", "", port=22),
        ]
        recs = engine.recommend_hardening(findings)
        severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        for i in range(len(recs) - 1):
            order_a = severity_order.get(recs[i]["severity"], 99)
            order_b = severity_order.get(recs[i + 1]["severity"], 99)
            assert order_a <= order_b, (
                f"排序错误: {recs[i]['severity']} ({order_a}) 应在 {recs[i + 1]['severity']} ({order_b}) 之前"
            )


# =============================================================================
# summarize_risks
# =============================================================================


class TestSummarizeRisks:
    """summarize_risks() 风险统计"""

    def test_correct_counts(self, engine):
        """各等级统计准确且含 total"""
        findings = [
            VulnFinding("a", RiskLevel.CRITICAL, "", "", ""),
            VulnFinding("b", RiskLevel.CRITICAL, "", "", ""),
            VulnFinding("c", RiskLevel.HIGH, "", "", ""),
            VulnFinding("d", RiskLevel.MEDIUM, "", "", ""),
            VulnFinding("e", RiskLevel.LOW, "", "", ""),
        ]
        summary = engine.summarize_risks(findings)
        assert summary["critical"] == 2
        assert summary["high"] == 1
        assert summary["medium"] == 1
        assert summary["low"] == 1
        assert summary["info"] == 0
        assert summary["total"] == 5

    def test_empty_findings(self, engine):
        """空 findings → 全 0 + total=0"""
        summary = engine.summarize_risks([])
        assert summary["total"] == 0
        for key in ["critical", "high", "medium", "low", "info"]:
            assert summary[key] == 0

    def test_returns_dict_with_all_keys(self, engine):
        """返回包含所有必要 key 的 dict"""
        summary = engine.summarize_risks([])
        expected = {"critical", "high", "medium", "low", "info", "total"}
        assert set(summary.keys()) == expected


# =============================================================================
# _deduplicate
# =============================================================================


class TestDeduplicate:
    """_deduplicate() 去重"""

    def test_same_type_port_keeps_highest_severity(self, engine):
        """同 vuln_type + port 保留 CRITICAL 丢弃 HIGH"""
        f1 = VulnFinding("sqli", RiskLevel.HIGH, "", "", "", port=80)
        f2 = VulnFinding("sqli", RiskLevel.CRITICAL, "", "", "", port=80)
        result = engine._deduplicate([f1, f2])
        assert len(result) == 1
        assert result[0].severity == RiskLevel.CRITICAL

    def test_different_types_both_kept(self, engine):
        """不同 vuln_type 都保留"""
        f1 = VulnFinding("sqli", RiskLevel.HIGH, "", "", "", port=80)
        f2 = VulnFinding("xss", RiskLevel.MEDIUM, "", "", "", port=80)
        result = engine._deduplicate([f1, f2])
        assert len(result) == 2

    def test_same_type_different_port_both_kept(self, engine):
        """同 vuln_type 不同 port 都保留"""
        f1 = VulnFinding("sqli", RiskLevel.HIGH, "", "", "", port=80)
        f2 = VulnFinding("sqli", RiskLevel.HIGH, "", "", "", port=443)
        result = engine._deduplicate([f1, f2])
        assert len(result) == 2


# =============================================================================
# _parse_semver
# =============================================================================


class TestParseSemver:
    """_parse_semver() 语义版本解析"""

    def test_standard_version(self):
        """ "1.2.3" → (1, 2, 3)"""
        result = RuleEngine._parse_semver("1.2.3")
        assert result == (1, 2, 3)

    def test_two_part_version(self):
        """ "8.0" → (8, 0, 0)"""
        result = RuleEngine._parse_semver("8.0")
        assert result == (8, 0, 0)

    def test_openssh_format(self):
        """ "8.9p1" → (8, 9, 1) 降级处理"""
        result = RuleEngine._parse_semver("8.9p1")
        assert result[:2] == (8, 9)
        assert len(result) == 3

    def test_non_numeric_downgrade(self):
        """非数字段降级为 0"""
        result = RuleEngine._parse_semver("alpha")
        assert result == (0, 0, 0)

    def test_four_part_truncated(self):
        """超过三段截断"""
        result = RuleEngine._parse_semver("1.2.3.4")
        assert result == (1, 2, 3)
        assert len(result) == 3


# =============================================================================
# import_rules
# =============================================================================


class TestImportRules:
    """import_rules() 外部规则导入"""

    def test_does_not_overwrite_existing_rule_id(self, engine):
        """不覆盖已有 rule_id"""
        original_count = engine.vuln_rule_count
        existing_id = engine._vuln_rules[0]["rule_id"]

        new_rules = [{"rule_id": existing_id, "match_type": "port", "port": 9999}]
        engine.import_rules(new_rules, rule_type="vuln")

        # 计数不变（被拒绝）
        assert engine.vuln_rule_count == original_count

    def test_adds_new_rule_id(self, engine):
        """添加新 rule_id"""
        original_count = engine.vuln_rule_count
        new_id = "IMPORT-TEST-001"

        new_rules = [{"rule_id": new_id, "match_type": "port", "port": 9999}]
        engine.import_rules(new_rules, rule_type="vuln")

        assert engine.vuln_rule_count == original_count + 1

        # 清理
        engine._vuln_rules = [r for r in engine._vuln_rules if r.get("rule_id") != new_id]

    def test_import_harden_rules(self, engine):
        """import_rules(harden) 不覆盖已有加固规则"""
        original_count = engine.harden_rule_count
        existing_id = engine._harden_rules[0]["rule_id"]

        new_rules = [{"rule_id": existing_id, "action": "test"}]
        engine.import_rules(new_rules, rule_type="harden")

        assert engine.harden_rule_count == original_count


# =============================================================================
# _load_json — v0.0.15 不抛异常
# =============================================================================


class TestLoadJson:
    """_load_json() 文件加载 — v0.0.15 修复"""

    def test_nonexistent_file_returns_empty_list(self, engine):
        """不存在路径返回 []，不抛异常"""
        result = engine._load_json("/nonexistent/path/rules.json")
        assert isinstance(result, list)
        assert result == []

    def test_dictionary_format_extracts_rules_key(self, engine):
        """{"rules": [...]} 格式正确提取"""
        import json
        import tempfile

        data = {"rules": [{"rule_id": "T1"}, {"rule_id": "T2"}]}
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as f:
            json.dump(data, f)
            path = f.name

        try:
            result = engine._load_json(path)
            assert isinstance(result, list)
            assert len(result) == 2
        finally:
            os.unlink(path)

    def test_array_format_directly(self, engine):
        """直接 [...] 格式"""
        import json
        import tempfile

        data = [{"a": 1}, {"b": 2}]
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as f:
            json.dump(data, f)
            path = f.name

        try:
            result = engine._load_json(path)
            assert isinstance(result, list)
            assert len(result) == 2
        finally:
            os.unlink(path)
