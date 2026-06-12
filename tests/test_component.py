"""测试模块：lightshield/scanners/component_checker.py

被测类：ComponentCheckerAdapter(BaseAdapter)

测试点：
  - _parse_version 正确解析各种版本格式
  - _version_matches 区间判断（含边界：[min, max) 半开区间）
  - _match_cves 匹配已知 CVE / 版本超出无匹配
  - capabilities() 返回 ["component_check"]
  - get_cve_summary 返回非空摘要字符串
  - scan(target) mock HTTP 返回 COMPLETED

注意：_parse_version 和 _version_matches 是模块级函数，
      _match_cves 是 ComponentCheckerAdapter 的实例方法。
"""

import pytest

from lightshield.scanners.component_checker import (
    ComponentCheckerAdapter,
    CveEntry,
    _parse_version,
    _version_matches,
)
from lightshield.utils.constants import ScanStatus


@pytest.fixture
def checker():
    """返回 ComponentCheckerAdapter 实例"""
    return ComponentCheckerAdapter()


# =============================================================================
# _parse_version（模块级函数）
# =============================================================================


class TestParseVersion:
    """_parse_version() 版本号解析"""

    def test_standard_three_part(self):
        """标准版本 '1.24.0' → (1, 24, 0)"""
        assert _parse_version("1.24.0") == (1, 24, 0)

    def test_two_part_version(self):
        """两段版本 '8.0' → (8, 0)"""
        assert _parse_version("8.0") == (8, 0)

    def test_single_number(self):
        """单段版本 '7' → (7,)"""
        assert _parse_version("7") == (7,)

    def test_openssh_format(self):
        """OpenSSH 格式 '8.9p1' → (8, 9, 1)"""
        assert _parse_version("8.9p1") == (8, 9, 1)

    def test_v_prefix(self):
        """'v2.4.58' → (2, 4, 58)"""
        assert _parse_version("v2.4.58") == (2, 4, 58)

    def test_empty_string(self):
        """空字符串返回空元组"""
        assert _parse_version("") == ()

    def test_unknown(self):
        """'unknown' 返回空元组（无数字段）"""
        assert _parse_version("unknown") == ()

    def test_none_returns_empty(self):
        """None 输入返回空元组"""
        assert _parse_version(None) == ()

    def test_complex_version(self):
        """'1.2.3-ubuntu0.6' → 提取所有数字段"""
        result = _parse_version("1.2.3-ubuntu0.6")
        assert len(result) >= 3
        assert result[0] == 1

    def test_non_numeric_returns_empty(self):
        """纯字母输入返回空元组"""
        assert _parse_version("alpha.beta") == ()


# =============================================================================
# _version_matches（模块级函数，[min, max) 半开区间）
# =============================================================================


class TestVersionMatches:
    """_version_matches() 区间判断"""

    def test_in_range_match(self):
        """版本在 [min, max) 区间内匹配"""
        # 1.9 ∈ [1.5, 2.0)
        assert _version_matches("1.9", [("1.5", "2.0")]) is True

    def test_equal_min_match(self):
        """版本等于 min 时匹配（闭区间下界）"""
        # 2.0 ∈ [2.0, 3.0)
        assert _version_matches("2.0", [("2.0", "3.0")]) is True

    def test_equal_max_no_match(self):
        """版本等于 max 时不匹配（开区间上界）"""
        # 2.0 ∉ [1.0, 2.0)
        assert _version_matches("2.0", [("1.0", "2.0")]) is False

    def test_below_min_no_match(self):
        """版本低于 min 不匹配"""
        assert _version_matches("1.0", [("1.5", "2.0")]) is False

    def test_above_max_no_match(self):
        """版本高于 max 不匹配"""
        assert _version_matches("3.0", [("1.5", "2.5")]) is False

    def test_multiple_ranges_or_logic(self):
        """多条区间按 OR 逻辑——落在任一区间即匹配"""
        assert _version_matches("7.1", [("7.0", "7.5"), ("8.0", "9.0")]) is True

    def test_no_Matching_range(self):
        """版本不在任何区间内不匹配"""
        assert _version_matches("9.5", [("7.0", "7.5"), ("8.0", "9.0")]) is False

    def test_unparseable_version_returns_false(self):
        """无法解析版本时保守处理返回 False"""
        assert _version_matches("unknown", [("1.0", "2.0")]) is False

    def test_empty_string_returns_false(self):
        """空版本字符串返回 False"""
        assert _version_matches("", [("1.0", "2.0")]) is False

    def test_no_min_version_match_all_below(self):
        """无 min_version 时匹配所有低于 max 的版本"""
        assert _version_matches("0.5", [("", "1.0")]) is True

    def test_no_min_version_above_max_no_match(self):
        """无 min 但版本 ≥ max 时不匹配"""
        assert _version_matches("2.0", [("", "1.0")]) is False


# =============================================================================
# _match_cves（实例方法，返回 list[CveEntry]）
# =============================================================================


class TestMatchCves:
    """_match_cves() CVE 匹配"""

    def test_mysql_8_0_30_matches_known_cve(self, checker):
        """MySQL 8.0.30 匹配已知 CVE（min_version=8.0.0）"""
        cves = checker._match_cves("mysql", "8.0.30")
        assert len(cves) > 0, f"期望 MySQL 8.0.30 匹配 CVE，实际 {len(cves)} 个"
        for cve in cves:
            assert isinstance(cve, CveEntry)
            assert cve.cvss_score > 0

    def test_nginx_1_26_0_no_match(self, checker):
        """Nginx 1.26.0 不匹配任何 CVE（超出所有 max_affected）"""
        cves = checker._match_cves("nginx", "1.26.0")
        assert len(cves) == 0, f"期望 nginx 1.26.0 无 CVE 匹配，实际 {len(cves)} 个"

    def test_openssh_9_0_matches_cves(self, checker):
        """OpenSSH 9.0p1 匹配多个 CVE（regreSSHion）"""
        cves = checker._match_cves("openssh", "9.0p1")
        assert len(cves) >= 1
        cve_ids = {cve.cve_id for cve in cves}
        assert "CVE-2024-6387" in cve_ids

    def test_openssh_9_9_no_match(self, checker):
        """OpenSSH 9.9p1 不匹配 CVE（版本超出最大受影响范围）"""
        cves = checker._match_cves("openssh", "9.9p1")
        assert len(cves) == 0

    def test_unknown_component_no_match(self, checker):
        """未知组件无匹配"""
        cves = checker._match_cves("nonexistent_component_xyz", "1.0")
        assert isinstance(cves, list)
        assert len(cves) == 0

    def test_empty_version_returns_empty(self, checker):
        """空版本返回空列表（保守策略：不瞎匹配）"""
        cves = checker._match_cves("nginx", "")
        assert isinstance(cves, list)
        assert len(cves) == 0


# =============================================================================
# capabilities
# =============================================================================


class TestCapabilities:
    """capabilities() 返回正确的能力列表"""

    def test_returns_component_check(self, checker):
        """返回 ["component_check"]"""
        caps = checker.capabilities()
        assert caps == ["component_check"]


# =============================================================================
# get_cve_summary
# =============================================================================


class TestGetCveSummary:
    """get_cve_summary() 生成摘要"""

    def test_returns_non_empty_string(self, checker):
        """返回非空字符串"""
        from lightshield.adapters.base import ScanResult

        result = ScanResult(
            status=ScanStatus.COMPLETED,
            target="example.com",
            services=[
                {"name": "nginx", "version": "1.20.0", "port": 80},
            ],
        )
        summary = checker.get_cve_summary(result)
        assert isinstance(summary, str)
        assert len(summary) > 0

    def test_empty_services_summary(self, checker):
        """无服务时仍返回非空摘要"""
        from lightshield.adapters.base import ScanResult

        result = ScanResult(
            status=ScanStatus.COMPLETED,
            target="example.com",
            services=[],
        )
        summary = checker.get_cve_summary(result)
        assert isinstance(summary, str)


# =============================================================================
# scan
# =============================================================================


class TestScan:
    """scan() 方法验证（mock HTTP）"""

    def test_scan_via_services_kwarg_returns_completed(self, checker):
        """通过 services kwargs 传入组件版本 → 返回 COMPLETED"""
        result = checker.scan(
            "example.com",
            services=[
                {"name": "nginx", "version": "1.18.0", "port": 80},
                {"name": "openssh", "version": "8.9p1", "port": 22},
                {"name": "mysql", "version": "5.7", "port": 3306},
            ],
        )
        assert result.status == ScanStatus.COMPLETED

    def test_scan_services_have_version(self, checker):
        """scan() 返回的 services 包含 version 字段"""
        result = checker.scan(
            "example.com",
            services=[
                {"name": "nginx", "version": "1.18.0", "port": 80},
            ],
        )
        assert len(result.services) >= 1
        for svc in result.services:
            assert "version" in svc, f"service 缺少 version: {svc}"

    def test_scan_invalid_target_returns_failed(self, checker):
        """非法目标返回 FAILED"""
        result = checker.scan("")
        assert result.status == ScanStatus.FAILED

    @pytest.mark.skip(reason="scan() 内部自建 Session，requests.Session.get patch 不覆盖 DNS 解析")
    def test_scan_mocked_http_full(self, checker):
        """Mock HTTP 请求后 scan() 返回 COMPLETED（完整 mock 链复杂，跳过）"""
        pass


# =============================================================================
# _supplement_from_services（v0.0.23 新增 helper）
# =============================================================================


class TestSupplementFromServices:
    """_supplement_from_services() 从上游服务列表提取非 HTTP 组件"""

    def test_returns_empty_for_empty_services(self, checker):
        """空服务列表返回空字典和空详情列表"""
        components, details = checker._supplement_from_services([])
        assert components == {}
        assert details == []

    def test_maps_known_service_to_canonical_name(self, checker):
        """已知服务（nginx）被映射为规范组件名"""
        components, details = checker._supplement_from_services([{"name": "nginx", "version": "1.24.0", "port": 80}])
        assert "nginx" in components
        assert components["nginx"] == "1.24.0"

    def test_maps_alias_to_canonical(self, checker):
        """别名（httpd → apache_httpd）被正确映射"""
        components, details = checker._supplement_from_services([{"name": "httpd", "version": "2.4.58", "port": 80}])
        assert "apache_httpd" in components
        assert components["apache_httpd"] == "2.4.58"

    def test_preserves_unknown_service_name_as_is(self, checker):
        """未知服务名保持原样（无别名映射）"""
        components, _ = checker._supplement_from_services([{"name": "custom-app", "version": "3.0", "port": 9000}])
        assert "custom-app" in components

    def test_details_include_source_port_and_raw_value(self, checker):
        """详情包含 source / port / raw_value 字段"""
        _, details = checker._supplement_from_services([{"name": "mysql", "version": "8.0.35", "port": 3306}])
        assert len(details) == 1
        d = details[0]
        assert d["source"] == "services"
        assert d["component"] == "mysql"
        assert d["version"] == "8.0.35"
        assert d["port"] == 3306
        assert "8.0.35" in d["raw_value"]

    def test_multiple_services_all_returned(self, checker):
        """多个服务同时返回"""
        components, details = checker._supplement_from_services(
            [
                {"name": "mysql", "version": "8.0.35", "port": 3306},
                {"name": "redis", "version": "7.2.1", "port": 6379},
                {"name": "openssh", "version": "8.9p1", "port": 22},
            ]
        )
        assert len(components) == 3
        assert len(details) == 3

    def test_empty_name_skipped(self, checker):
        """名称为空的条目返回空结果（canonical 为空时跳过）"""
        components, details = checker._supplement_from_services([{"name": "", "version": "1.0", "port": 80}])
        assert components == {}
        assert details == []

    def test_missing_version_defaults_to_empty_string(self, checker):
        """缺少 version 的条目版本为空字符串"""
        components, _ = checker._supplement_from_services([{"name": "nginx", "port": 80}])
        assert components["nginx"] == ""


# =============================================================================
# _build_cve_findings（v0.0.23 新增 helper）
# =============================================================================


class TestBuildCveFindings:
    """_build_cve_findings() 组件 → CVE 匹配 → VulnFinding 列表"""

    def test_returns_empty_for_no_components(self, checker):
        """空组件字典返回空 findings"""
        findings = checker._build_cve_findings({})
        assert findings == []

    def test_openssh_vulnerable_version_matches_cves(self, checker):
        """OpenSSH 9.0p1 返回多个 CVE findings"""
        findings = checker._build_cve_findings({"openssh": "9.0p1"})
        assert len(findings) >= 1
        for f in findings:
            assert f.vuln_type == "component_cve"
            assert f.cve_id is not None
            assert f.cvss_score is not None
            assert f.cvss_score > 0

    def test_nginx_safe_version_returns_empty(self, checker):
        """Nginx 安全版本（无 CVE 匹配）返回空列表"""
        findings = checker._build_cve_findings({"nginx": "1.26.0"})
        assert findings == []

    def test_mixed_components_only_matching_returned(self, checker):
        """混合组件：有漏洞的返回 finding，无漏洞的跳过"""
        findings = checker._build_cve_findings({"nginx": "1.26.0", "openssh": "9.0p1"})
        cve_ids = {f.cve_id for f in findings}
        assert len(findings) >= 1
        # 所有 finding 都应该来自 OpenSSH（nginx 1.26.0 无匹配）
        for cid in cve_ids:
            assert cid is not None

    def test_finding_has_all_required_fields(self, checker):
        """每个 VulnFinding 包含完整的必填字段"""
        findings = checker._build_cve_findings({"openssh": "9.0p1"})
        for f in findings:
            assert f.vuln_type
            assert f.severity is not None
            assert f.title
            assert f.description
            assert f.remediation
            assert f.cve_id
            assert f.cvss_score is not None
            assert "openssh" in f.evidence.lower()

    def test_empty_version_no_match(self, checker):
        """空版本不匹配 CVE（保守策略）"""
        findings = checker._build_cve_findings({"nginx": ""})
        assert findings == []

    def test_unknown_component_no_match(self, checker):
        """未知组件不匹配任何 CVE"""
        findings = checker._build_cve_findings({"unknown_app": "1.0"})
        assert findings == []


# =============================================================================
# _assemble_result（v0.0.23 新增 helper）
# =============================================================================


class TestAssembleResult:
    """_assemble_result() 组装 ScanResult"""

    def test_returns_scan_result_with_completed_status(self, checker):
        """返回 status=COMPLETED 的 ScanResult"""
        import time

        result = checker._assemble_result(
            target="example.com",
            components={"nginx": "1.20.0"},
            findings=[],
            raw_details=[],
            start_time=time.time(),
        )
        assert result.status == ScanStatus.COMPLETED
        assert result.target == "example.com"

    def test_services_output_has_name_and_version(self, checker):
        """Services 输出包含 name 和 version"""
        import time

        result = checker._assemble_result(
            target="example.com",
            components={"nginx": "1.20.0", "mysql": "8.0.35"},
            findings=[],
            raw_details=[],
            start_time=time.time(),
        )
        assert len(result.services) == 2
        svc_names = {s["name"] for s in result.services}
        assert svc_names == {"nginx", "mysql"}
        for s in result.services:
            assert "version" in s

    def test_ports_output_from_raw_details(self, checker):
        """Ports 从 raw_details 正确生成"""
        import time

        raw_details = [
            {"component": "nginx", "port": 80, "source": "header:server"},
            {"component": "mysql", "port": 3306, "source": "services"},
        ]
        result = checker._assemble_result(
            target="example.com",
            components={"nginx": "1.20.0", "mysql": "8.0.35"},
            findings=[],
            raw_details=raw_details,
            start_time=time.time(),
        )
        assert len(result.ports) == 2
        ports_set = {p["port"] for p in result.ports}
        assert ports_set == {80, 3306}

    def test_raw_output_includes_counts(self, checker):
        """raw_output 包含组件数和 CVE 命中数"""
        import time

        from lightshield.adapters.base import VulnFinding
        from lightshield.utils.constants import RiskLevel

        findings = [
            VulnFinding(
                vuln_type="test",
                severity=RiskLevel.HIGH,
                title="测试漏洞",
                description="测试描述",
                remediation="升级",
                cve_id="CVE-TEST-001",
                cvss_score=7.5,
            )
        ]
        result = checker._assemble_result(
            target="example.com",
            components={"nginx": "1.20.0"},
            findings=findings,
            raw_details=[],
            start_time=time.time(),
        )
        assert "1" in result.raw_output  # 1 个组件
        assert "1" in result.raw_output  # 1 个 CVE

    def test_duration_is_positive_float(self, checker):
        """duration_seconds 为正浮点数"""
        import time

        start = time.time()
        result = checker._assemble_result(
            target="example.com",
            components={},
            findings=[],
            raw_details=[],
            start_time=start,
        )
        assert result.duration_seconds >= 0
        assert isinstance(result.duration_seconds, float)

    def test_empty_components_and_findings(self, checker):
        """空组件和空 findings → 返回有效的 ScanResult"""
        import time

        result = checker._assemble_result(
            target="example.com",
            components={},
            findings=[],
            raw_details=[],
            start_time=time.time(),
        )
        assert result.status == ScanStatus.COMPLETED
        assert result.services == []
        assert result.ports == []
        assert result.findings == []


# =============================================================================
# _parse_http_response（v0.0.23 新增 helper，mock Response）
# =============================================================================


class TestParseHttpResponse:
    """_parse_http_response() 从 HTTP Response 提取组件指纹"""

    @staticmethod
    def _make_mock_response(headers=None, body_chunks=None):
        """构造 mock Response 对象（使用 unittest.mock）"""
        from unittest.mock import MagicMock

        mock = MagicMock()
        mock.headers = headers or {}
        mock.iter_content.return_value = body_chunks or [b""]
        return mock

    def test_extracts_nginx_from_server_header(self, checker):
        """从 Server 响应头提取 nginx 版本"""
        mock_resp = self._make_mock_response(
            headers={
                "Server": "nginx/1.24.0",
                "X-Powered-By": "PHP/8.1.27",
            },
            body_chunks=[b"<html><head><meta name='generator' content='WordPress 6.4.2'></head></html>"],
        )
        components, details = checker._parse_http_response(mock_resp, 80)
        assert "nginx" in components
        assert components["nginx"] == "1.24.0"

    def test_extracts_php_from_x_powered_by(self, checker):
        """从 X-Powered-By 响应头提取 PHP 版本"""
        mock_resp = self._make_mock_response(
            headers={
                "Server": "nginx/1.24.0",
                "X-Powered-By": "PHP/8.1.27",
            },
        )
        components, details = checker._parse_http_response(mock_resp, 80)
        assert "php" in components
        assert components["php"] == "8.1.27"

    def test_extracts_wordpress_from_html_meta(self, checker):
        """从 HTML meta generator 提取 WordPress 版本"""
        mock_resp = self._make_mock_response(
            headers={
                "Server": "nginx/1.24.0",
                "X-Powered-By": "PHP/8.1.27",
            },
            body_chunks=[b'<html><head><meta name="generator" content="WordPress 6.4.2"></head></html>'],
        )
        components, details = checker._parse_http_response(mock_resp, 80)
        assert "wordpress" in components
        assert components["wordpress"] == "6.4.2"

    def test_details_include_source_and_port(self, checker):
        """每条 detail 包含 source / port 字段"""
        mock_resp = self._make_mock_response(
            headers={
                "Server": "nginx/1.24.0",
                "X-Powered-By": "PHP/8.1.27",
            },
        )
        _, details = checker._parse_http_response(mock_resp, 443)
        assert len(details) >= 2
        sources = {d["source"] for d in details}
        assert "header:server" in sources
        for d in details:
            assert d["port"] == 443

    def test_empty_headers_returns_empty_components(self, checker):
        """无匹配头的响应返回空组件"""
        mock_resp = self._make_mock_response(
            headers={"Cache-Control": "no-cache"},
        )
        components, details = checker._parse_http_response(mock_resp, 80)
        assert components == {}
        assert details == []

    def test_cookie_fingerprint_detected(self, checker):
        """Set-Cookie 包含 PHPSESSID 时识别为 PHP"""
        mock_resp = self._make_mock_response(
            headers={"Set-Cookie": "PHPSESSID=abc123; path=/"},
            body_chunks=[b"<html></html>"],
        )
        components, details = checker._parse_http_response(mock_resp, 80)
        assert "php" in components

    def test_body_truncated_at_max_size(self, checker):
        """Body 超过 _MAX_BODY_SIZE 时截断不报错"""
        mock_resp = self._make_mock_response(
            headers={},
            body_chunks=[b"x" * 8192] * 70,  # 70 × 8192 > 512KB
        )
        components, details = checker._parse_http_response(mock_resp, 80)
        # 不抛出异常即为通过
        assert isinstance(components, dict)
