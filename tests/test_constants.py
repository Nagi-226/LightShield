"""测试模块：lightshield/utils/constants.py

覆盖内容：
  - 枚举值存在性与正确性（RiskLevel / ScanStatus / ScanType / AdapterType / OSPlatform / OutputFormat）
  - MSF 白名单/黑名单双向不重叠校验
  - HIGH_RISK_PORTS 结构验证
  - 合规约束常量的精确值
  - WEAK_PASSWORD_PATTERNS 列表完整性
  - 合规 R1/R3/R5：测试代码不含攻击向 payload
"""

import pytest

from lightshield.utils.constants import (
    ALLOWED_MSF_PREFIXES,
    BLOCKED_MSF_PREFIXES,
    DEFAULT_SCAN_TIMEOUT,
    HIGH_RISK_PORTS,
    MAX_CONCURRENT_SCANS,
    MAX_TARGETS_PER_SESSION,
    MIN_SCAN_INTERVAL,
    WEAK_PASSWORD_PATTERNS,
    AdapterType,
    OSPlatform,
    OutputFormat,
    RiskLevel,
    ScanStatus,
    ScanType,
)

# =============================================================================
# RiskLevel 枚举
# =============================================================================


class TestRiskLevelEnum:
    """RiskLevel 枚举值存在性与正确性"""

    def test_critical_value(self):
        """CRITICAL 的值为 'critical'"""
        assert RiskLevel.CRITICAL.value == "critical"

    def test_high_value(self):
        """HIGH 的值为 'high'"""
        assert RiskLevel.HIGH.value == "high"

    def test_medium_value(self):
        """MEDIUM 的值为 'medium'"""
        assert RiskLevel.MEDIUM.value == "medium"

    def test_low_value(self):
        """LOW 的值为 'low'"""
        assert RiskLevel.LOW.value == "low"

    def test_info_value(self):
        """INFO 的值为 'info'"""
        assert RiskLevel.INFO.value == "info"

    def test_all_members_present(self):
        """RiskLevel 包含全部 5 个成员"""
        members = {m.name for m in RiskLevel}
        assert members == {"CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO"}


# =============================================================================
# ScanStatus 枚举
# =============================================================================


class TestScanStatusEnum:
    """ScanStatus 枚举值存在性（含 v0.0.04 新增的 PARTIAL / CANCELLED）"""

    @pytest.mark.parametrize(
        "name,value",
        [
            ("PENDING", "pending"),
            ("RUNNING", "running"),
            ("COMPLETED", "completed"),
            ("PARTIAL", "partial"),
            ("FAILED", "failed"),
            ("CANCELLED", "cancelled"),
        ],
    )
    def test_scan_status_value(self, name, value):
        """ScanStatus.{name}.value == {value}"""
        member = getattr(ScanStatus, name)
        assert member.value == value

    def test_all_members_present(self):
        """ScanStatus 包含全部 6 个成员"""
        members = {m.name for m in ScanStatus}
        assert members == {"PENDING", "RUNNING", "COMPLETED", "PARTIAL", "FAILED", "CANCELLED"}


# =============================================================================
# ScanType 枚举
# =============================================================================


class TestScanTypeEnum:
    """ScanType 枚举值存在性"""

    @pytest.mark.parametrize(
        "name,value",
        [
            ("PORT_SCAN", "port_scan"),
            ("SERVICE_DETECT", "service_detect"),
            ("WEB_VULN", "web_vuln"),
            ("WEAK_PASSWORD", "weak_password"),
            ("COMPONENT_CHECK", "component_check"),
        ],
    )
    def test_scan_type_value(self, name, value):
        """ScanType.{name}.value == {value}"""
        member = getattr(ScanType, name)
        assert member.value == value


# =============================================================================
# AdapterType 枚举
# =============================================================================


class TestAdapterTypeEnum:
    """AdapterType 枚举值存在性"""

    @pytest.mark.parametrize(
        "name,value",
        [
            ("NMAP", "nmap"),
            ("SELF_SCRIPT", "self_script"),
            ("MSF_SCANNER", "msf_scanner"),
        ],
    )
    def test_adapter_type_value(self, name, value):
        """AdapterType.{name}.value == {value}"""
        member = getattr(AdapterType, name)
        assert member.value == value


# =============================================================================
# OSPlatform 枚举
# =============================================================================


class TestOSPlatformEnum:
    """OSPlatform 枚举值存在性"""

    @pytest.mark.parametrize(
        "name,value",
        [
            ("LINUX", "linux"),
            ("WINDOWS", "windows"),
            ("UNKNOWN", "unknown"),
        ],
    )
    def test_os_platform_value(self, name, value):
        """OSPlatform.{name}.value == {value}"""
        member = getattr(OSPlatform, name)
        assert member.value == value


# =============================================================================
# OutputFormat 枚举
# =============================================================================


class TestOutputFormatEnum:
    """OutputFormat 枚举值存在性"""

    @pytest.mark.parametrize(
        "name,value",
        [
            ("MARKDOWN", "markdown"),
            ("TEXT", "text"),
        ],
    )
    def test_output_format_value(self, name, value):
        """OutputFormat.{name}.value == {value}"""
        member = getattr(OutputFormat, name)
        assert member.value == value


# =============================================================================
# MSF 白名单/黑名单不重叠（R5 合规）
# =============================================================================


class TestMsfWhitelistBlacklist:
    """MSF 白名单与黑名单必须完全无交集（双向检查）"""

    def test_whitelist_non_empty(self):
        """白名单不应为空"""
        assert len(ALLOWED_MSF_PREFIXES) > 0

    def test_blacklist_non_empty(self):
        """黑名单不应为空"""
        assert len(BLOCKED_MSF_PREFIXES) > 0

    def test_no_blocked_starts_with_allowed(self):
        """黑名单条目不与任何白名单条目互为前缀（方向: blocked → allowed）"""
        for blocked in BLOCKED_MSF_PREFIXES:
            for allowed in ALLOWED_MSF_PREFIXES:
                assert not blocked.startswith(allowed), f"MSF 配置冲突：黑名单 [{blocked}] 以白名单 [{allowed}] 开头"

    def test_no_allowed_starts_with_blocked(self):
        """白名单条目不与任何黑名单条目互为前缀（方向: allowed → blocked）"""
        for allowed in ALLOWED_MSF_PREFIXES:
            for blocked in BLOCKED_MSF_PREFIXES:
                assert not allowed.startswith(blocked), f"MSF 配置冲突：白名单 [{allowed}] 以黑名单 [{blocked}] 开头"

    def test_exploit_not_in_whitelist(self):
        """'exploit/' 前缀不在白名单中（R5 合规）"""
        for allowed in ALLOWED_MSF_PREFIXES:
            assert not allowed.startswith("exploit/"), f"exploit/ 路径出现在白名单中: {allowed}"

    def test_payload_not_in_whitelist(self):
        """'payload/' 前缀不在白名单中（R5 合规）"""
        for allowed in ALLOWED_MSF_PREFIXES:
            assert not allowed.startswith("payload/"), f"payload/ 路径出现在白名单中: {allowed}"

    def test_all_whitelist_under_auxiliary_scanner(self):
        """所有白名单条目均在 auxiliary/scanner/ 下（R5 合规）"""
        for allowed in ALLOWED_MSF_PREFIXES:
            assert allowed.startswith("auxiliary/scanner/"), f"白名单条目不在 auxiliary/scanner/ 下: {allowed}"


# =============================================================================
# HIGH_RISK_PORTS 字典
# =============================================================================


class TestHighRiskPorts:
    """高危端口字典结构验证"""

    def test_non_empty(self):
        """HIGH_RISK_PORTS 字典非空"""
        assert len(HIGH_RISK_PORTS) > 0

    def test_keys_are_int(self):
        """所有 key 为 int 类型"""
        for key in HIGH_RISK_PORTS:
            assert isinstance(key, int), f"key {key!r} 不是 int"

    def test_values_are_str(self):
        """所有 value 为 str 类型"""
        for value in HIGH_RISK_PORTS.values():
            assert isinstance(value, str), f"value {value!r} 不是 str"

    def test_known_ports_present(self):
        """确认关键高危端口在字典中"""
        expected_ports = {22, 23, 445, 3306, 3389, 6379}
        missing = expected_ports - set(HIGH_RISK_PORTS.keys())
        assert not missing, f"缺失关键高危端口: {missing}"


# =============================================================================
# 合规约束常量
# =============================================================================


class TestComplianceConstants:
    """合规约束常量的精确值"""

    def test_max_concurrent_scans(self):
        """MAX_CONCURRENT_SCANS == 20"""
        assert MAX_CONCURRENT_SCANS == 20
        assert isinstance(MAX_CONCURRENT_SCANS, int)

    def test_min_scan_interval(self):
        """MIN_SCAN_INTERVAL == 5.0"""
        assert MIN_SCAN_INTERVAL == 5.0
        assert isinstance(MIN_SCAN_INTERVAL, float)

    def test_max_targets_per_session(self):
        """MAX_TARGETS_PER_SESSION == 1"""
        assert MAX_TARGETS_PER_SESSION == 1
        assert isinstance(MAX_TARGETS_PER_SESSION, int)

    def test_default_scan_timeout(self):
        """DEFAULT_SCAN_TIMEOUT == 30"""
        assert DEFAULT_SCAN_TIMEOUT == 30
        assert isinstance(DEFAULT_SCAN_TIMEOUT, int)


# =============================================================================
# WEAK_PASSWORD_PATTERNS 列表
# =============================================================================


class TestWeakPasswordPatterns:
    """弱口令模式库验证"""

    def test_non_empty(self):
        """WEAK_PASSWORD_PATTERNS 非空列表"""
        assert len(WEAK_PASSWORD_PATTERNS) > 0

    def test_all_elements_are_str(self):
        """所有元素为 str 类型"""
        for item in WEAK_PASSWORD_PATTERNS:
            assert isinstance(item, str), f"元素 {item!r} 不是 str"

    def test_known_patterns_present(self):
        """确认关键弱口令在列表中"""
        must_have = {"admin", "password", "123456", "root", "guest"}
        found = set(WEAK_PASSWORD_PATTERNS)
        missing = must_have - found
        assert not missing, f"缺失关键弱口令模式: {missing}"

    def test_no_empty_strings(self):
        """列表中不应有空字符串"""
        for item in WEAK_PASSWORD_PATTERNS:
            assert item != "", "发现空字符串弱口令模式"
