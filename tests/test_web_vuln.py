"""测试模块：lightshield/scanners/web_vuln_scanner.py

被测类：WebVulnScanner(BaseAdapter)

测试点：
  - capabilities() 返回 ["web_vuln", "directory_enum"]
  - validate_target 委托 TargetValidator
  - scan(target) mock HTTP → ScanStatus.COMPLETED，不依赖真实网络
  - detect_sqli 对含 SQL 注入 payload 的 URL 返回 list[VulnFinding]
  - detect_xss 返回 list[VulnFinding]，evidence 含注入上下文
  - enumerate_directories 返回 ≤200 条，mock requests 防止真实请求
  - payload 仅检测不利用（无 write/delete/exec 关键词）
"""

from unittest.mock import MagicMock, patch

import pytest

from lightshield.adapters.base import VulnFinding
from lightshield.scanners.web_vuln_scanner import SENSITIVE_DIRS, WebVulnScanner
from lightshield.utils.constants import RiskLevel, ScanStatus

# ── 辅助：构造假 Response ─────────────────────────────────────────────


class _FakeElapsed:
    def __init__(self, seconds: float = 0.1) -> None:
        self._seconds = seconds

    def total_seconds(self) -> float:
        return self._seconds


def _fake_response(
    text: str = "normal page",
    status_code: int = 200,
    elapsed_seconds: float = 0.1,
) -> MagicMock:
    """构造一个模拟的 requests.Response"""
    resp = MagicMock()
    resp.text = text
    resp.status_code = status_code
    resp.elapsed = _FakeElapsed(elapsed_seconds)
    resp.url = "http://example.com/test"
    return resp


# ── 扫描器构造 ──────────────────────────────────────────────────────


@pytest.fixture
def scanner():
    """返回 request_interval=0 的 WebVulnScanner，避免限速等待"""
    return WebVulnScanner(request_interval=0.0)


# =============================================================================
# capabilities
# =============================================================================


class TestCapabilities:
    """capabilities() 返回正确的能力列表"""

    def test_returns_web_vuln_and_directory_enum(self, scanner):
        """返回 ["web_vuln", "directory_enum"]"""
        caps = scanner.capabilities()
        assert "web_vuln" in caps
        assert "directory_enum" in caps
        assert len(caps) == 2


# =============================================================================
# validate_target
# =============================================================================


class TestValidateTarget:
    """validate_target 委托 TargetValidator"""

    def test_single_ip_valid(self, scanner):
        """单 IP 返回 True"""
        assert scanner.validate_target("192.168.1.1") is True

    def test_domain_valid(self, scanner):
        """域名返回 True"""
        assert scanner.validate_target("example.com") is True

    def test_cidr_invalid(self, scanner):
        """CIDR 返回 False"""
        assert scanner.validate_target("192.168.1.0/24") is False

    def test_url_extracts_host_valid(self, scanner):
        """URL 输入提取主机名校验"""
        assert scanner.validate_target("http://example.com/page") is True

    def test_url_invalid_host_rejected(self, scanner):
        """URL 中的主机名不合法时也应拒绝"""
        # 空 host 会被 TargetValidator 拒绝
        assert scanner.validate_target("http://") is False


# =============================================================================
# scan
# =============================================================================


class TestScan:
    """scan() 方法验证（mock HTTP）"""

    def test_scan_mocked_http_returns_completed(self, scanner):
        """Mock HTTP 请求后 scan() 返回 COMPLETED 状态"""
        with patch.object(scanner, "_safe_get", return_value=_fake_response()):
            result = scanner.scan("example.com")
            assert result.status == ScanStatus.COMPLETED
            assert result.target == "example.com"

    def test_scan_invalid_target_returns_failed(self, scanner):
        """非法目标返回 FAILED"""
        result = scanner.scan("", check_sqli=False, check_xss=False, check_dirs=False)
        assert result.status == ScanStatus.FAILED

    def test_scan_respects_check_flags(self, scanner):
        """Kwargs check_sqli/check_xss/check_dirs 控制子检测"""
        with patch.object(scanner, "_safe_get", return_value=_fake_response()):
            # 全部关闭
            result = scanner.scan(
                "example.com",
                check_sqli=False,
                check_xss=False,
                check_dirs=False,
            )
            assert result.status == ScanStatus.COMPLETED
            assert len(result.findings) == 0

    def test_scan_no_params_uses_query_string(self, scanner):
        """scan() 不带 params 时应从 URL 查询串解析"""

        def fake_safe_get(url, params=None):
            if params and any("'" in str(v) for v in params.values()):
                return _fake_response("You have an error in your SQL syntax; check the manual")
            return _fake_response()

        with patch.object(scanner, "_safe_get", side_effect=fake_safe_get):
            result = scanner.scan(
                "http://example.com/search?q=normal",
                check_sqli=True,
                check_xss=False,
                check_dirs=False,
            )
            assert result.status == ScanStatus.COMPLETED


# =============================================================================
# detect_sqli
# =============================================================================


class TestDetectSqli:
    """detect_sqli() SQL 注入检测"""

    def test_returns_list_of_vuln_findings(self, scanner):
        """返回 list[VulnFinding]"""
        with patch.object(
            scanner,
            "_safe_get",
            return_value=_fake_response("You have an error in your SQL syntax"),
        ):
            result = scanner.detect_sqli("http://example.com/search", {"q": "test"})
            assert isinstance(result, list)
            if result:
                assert all(isinstance(f, VulnFinding) for f in result)

    def test_finding_has_severity(self, scanner):
        """发现的 VulnFinding 有非 None 的 severity"""
        with patch.object(
            scanner,
            "_safe_get",
            return_value=_fake_response("You have an error in your SQL syntax"),
        ):
            result = scanner.detect_sqli("http://example.com/search", {"q": "test"})
            for f in result:
                assert f.severity is not None
                assert isinstance(f.severity, RiskLevel)

    def test_vuln_type_is_sqli(self, scanner):
        """vuln_type 为 'sqli'"""
        with patch.object(
            scanner,
            "_safe_get",
            return_value=_fake_response("You have an error in your SQL syntax"),
        ):
            result = scanner.detect_sqli("http://example.com/search", {"q": "test"})
            for f in result:
                assert f.vuln_type == "sqli"

    def test_empty_params_returns_empty(self, scanner):
        """无参数时返回空列表"""
        result = scanner.detect_sqli("http://example.com", params={})
        assert result == []

    def test_no_payloads_contain_write_delete_exec(self, scanner):
        """SQL 注入测试 payload 不含 write/delete/exec 等利用关键词"""
        from lightshield.scanners.web_vuln_scanner import SQLI_TEST_PAYLOADS

        dangerous = {"write", "delete", "exec", "drop", "shutdown"}
        for payload, _ in SQLI_TEST_PAYLOADS:
            payload_lower = payload.lower()
            for keyword in dangerous:
                assert keyword not in payload_lower, f"payload {payload!r} 含利用关键词 '{keyword}'"


# =============================================================================
# detect_xss
# =============================================================================


class TestDetectXss:
    """detect_xss() XSS 检测"""

    def test_returns_list_of_vuln_findings(self, scanner):
        """返回 list[VulnFinding]"""

        def fake_get(url, params=None):
            if params:
                val = next(iter(params.values()))
                return _fake_response(val)
            return _fake_response("normal page")

        with patch.object(scanner, "_safe_get", side_effect=fake_get):
            result = scanner.detect_xss("http://example.com/search", {"q": "test"})
            assert isinstance(result, list)

    def test_xss_finding_has_evidence(self, scanner):
        """XSS 发现的 evidence 包含注入上下文"""

        def fake_get(url, params=None):
            if params and any(v and "<script>" in str(v) for v in params.values()):
                val = str(next(iter(params.values())))
                # 未转义回显
                return _fake_response(val)
            return _fake_response("normal")

        with patch.object(scanner, "_safe_get", side_effect=fake_get):
            result = scanner.detect_xss("http://example.com/search", {"q": "test"})
            for f in result:
                assert f.evidence is not None
                assert isinstance(f.evidence, str)
                assert len(f.evidence) > 0

    def test_no_payloads_contain_write_exec(self, scanner):
        """XSS 测试 payload 不含利用关键词"""
        from lightshield.scanners.web_vuln_scanner import XSS_TEST_PAYLOADS

        dangerous = {"write", "delete", "exec", "drop"}
        for payload, _ in XSS_TEST_PAYLOADS:
            payload_lower = payload.lower()
            for keyword in dangerous:
                assert keyword not in payload_lower, f"payload {payload!r} 含利用关键词 '{keyword}'"


# =============================================================================
# enumerate_directories
# =============================================================================


class TestEnumerateDirectories:
    """enumerate_directories() 敏感目录枚举"""

    def test_returns_at_most_200(self, scanner):
        """返回不超过 200 条"""

        def fake_get(url, params=None):
            return _fake_response(status_code=200)

        with patch.object(scanner, "_safe_get", side_effect=fake_get):
            result = scanner.enumerate_directories("http://example.com")
            assert len(result) <= 200

    def test_404_directories_not_reported(self, scanner):
        """HTTP 404 的路径不报告"""

        def fake_get(url, params=None):
            return _fake_response(status_code=404)

        with patch.object(scanner, "_safe_get", side_effect=fake_get):
            result = scanner.enumerate_directories("http://example.com")
            assert len(result) == 0

    def test_200_directories_reported(self, scanner):
        """HTTP 200 的敏感路径被报告为 sensitive_dir"""

        def fake_get(url, params=None):
            if "/.env" in url:
                return _fake_response("DB_PASSWORD=secret", status_code=200)
            return _fake_response(status_code=404)

        with patch.object(scanner, "_safe_get", side_effect=fake_get):
            result = scanner.enumerate_directories("http://example.com")
            assert len(result) >= 1
            finding = result[0]
            assert finding.vuln_type == "sensitive_dir"

    def test_401_directories_reported_as_low(self, scanner):
        """HTTP 401 的路径报告为 LOW 级别"""

        def fake_get(url, params=None):
            if "/admin" in url:
                return _fake_response(status_code=401)
            return _fake_response(status_code=404)

        with patch.object(scanner, "_safe_get", side_effect=fake_get):
            result = scanner.enumerate_directories("http://example.com")
            assert len(result) >= 1
            assert result[0].severity == RiskLevel.LOW

    def test_sensitive_dirs_length(self):
        """SENSITIVE_DIRS 列表长度 ≤200"""
        assert len(SENSITIVE_DIRS) <= 200
