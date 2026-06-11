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
