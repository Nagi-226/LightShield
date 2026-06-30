"""PortScanner 单元测试 — v0.0.45 覆盖率提升 T1。

覆盖 lightshield/scanners/port_scanner.py：快速/全量/自定义扫描、
端口分析、高危端口提取、摘要生成。
"""

from __future__ import annotations

from unittest.mock import patch

from lightshield.adapters.base import ScanResult
from lightshield.adapters.nmap_adapter import NmapAdapter
from lightshield.scanners.port_scanner import PortScanner
from lightshield.utils.constants import HIGH_RISK_PORTS, ScanStatus

# =============================================================================
# 辅助：构造受控的 ScanResult
# =============================================================================


def _make_result(**overrides) -> ScanResult:
    """构造测试用 ScanResult，默认值最小化。"""
    defaults = {
        "target": "127.0.0.1",
        "status": ScanStatus.COMPLETED,
        "ports": [],
        "services": [],
        "os_info": None,
        "duration_seconds": 2.0,
    }
    defaults.update(overrides)
    return ScanResult(**defaults)


# =============================================================================
# 构造与初始化
# =============================================================================


class TestConstruction:
    """PortScanner 构造：默认适配器 / 注入适配器。"""

    def test_default_adapter_creates_nmap(self):
        scanner = PortScanner()
        assert isinstance(scanner._adapter, NmapAdapter)

    def test_custom_adapter_injected(self):
        mock = NmapAdapter()
        scanner = PortScanner(nmap_adapter=mock)
        assert scanner._adapter is mock


# =============================================================================
# 扫描委托（quick / full / custom）
# =============================================================================


class TestScanDelegation:
    """quick_scan / full_scan / custom_scan 均委托给 NmapAdapter.scan()。"""

    def test_quick_scan_delegates_with_top100(self):
        with patch.object(NmapAdapter, "scan", return_value=_make_result()) as mock_scan:
            scanner = PortScanner()
            result = scanner.quick_scan("10.0.0.1")
            mock_scan.assert_called_once_with("10.0.0.1", ports="1-100")
            assert result.target == "127.0.0.1"

    def test_full_scan_delegates_with_default_ports(self):
        with patch.object(NmapAdapter, "scan", return_value=_make_result()) as mock_scan:
            scanner = PortScanner()
            result = scanner.full_scan("10.0.0.1")
            mock_scan.assert_called_once_with("10.0.0.1")
            assert result.status == ScanStatus.COMPLETED

    def test_custom_scan_delegates_with_given_ports(self):
        with patch.object(NmapAdapter, "scan", return_value=_make_result()) as mock_scan:
            scanner = PortScanner()
            result = scanner.custom_scan("10.0.0.1", ports="80,443")
            mock_scan.assert_called_once_with("10.0.0.1", ports="80,443")
            assert result is not None


# =============================================================================
# analyze_ports — 核心逻辑
# =============================================================================


class TestAnalyzePorts:
    """端口分析：统计 open/filtered/closed/high_risk。"""

    def test_empty_ports_returns_zeros(self):
        scanner = PortScanner()
        result = _make_result(ports=[])
        analysis = scanner.analyze_ports(result)
        assert analysis == {
            "total": 0,
            "open": 0,
            "filtered": 0,
            "closed": 0,
            "high_risk": 0,
            "services": 0,
            "os_info": None,
        }

    def test_mixed_states_counted_correctly(self):
        scanner = PortScanner()
        result = _make_result(
            ports=[
                {"port": 22, "protocol": "tcp", "state": "open", "service": "ssh"},
                {"port": 80, "protocol": "tcp", "state": "open", "service": "http"},
                {"port": 25, "protocol": "tcp", "state": "filtered", "service": "smtp"},
                {"port": 443, "protocol": "tcp", "state": "closed", "service": "https"},
            ],
        )
        analysis = scanner.analyze_ports(result)
        assert analysis["total"] == 4
        assert analysis["open"] == 2
        assert analysis["filtered"] == 1
        assert analysis["closed"] == 1

    def test_high_risk_ports_identified(self):
        """22 (SSH) 和 3306 (MySQL) 在高危端口列表中。"""
        scanner = PortScanner()
        assert 22 in HIGH_RISK_PORTS
        assert 3306 in HIGH_RISK_PORTS

        result = _make_result(
            ports=[
                {"port": 22, "protocol": "tcp", "state": "open", "service": "ssh"},
                {"port": 3306, "protocol": "tcp", "state": "open", "service": "mysql"},
                {"port": 80, "protocol": "tcp", "state": "open", "service": "http"},
            ],
        )
        analysis = scanner.analyze_ports(result)
        assert analysis["high_risk"] == 2

    def test_high_risk_only_counts_open_ports(self):
        """高危端口仅在 state=open 时计数。"""
        scanner = PortScanner()
        result = _make_result(
            ports=[
                {"port": 22, "protocol": "tcp", "state": "closed", "service": "ssh"},
            ],
        )
        analysis = scanner.analyze_ports(result)
        assert analysis["high_risk"] == 0

    def test_services_count_from_result(self):
        scanner = PortScanner()
        result = _make_result(
            ports=[{"port": 80, "protocol": "tcp", "state": "open", "service": "http"}],
            services=[
                {"name": "http", "version": "nginx 1.24", "port": 80},
                {"name": "ssh", "version": "OpenSSH 8.9", "port": 22},
            ],
        )
        analysis = scanner.analyze_ports(result)
        assert analysis["services"] == 2

    def test_os_info_passthrough(self):
        scanner = PortScanner()
        result = _make_result(os_info="Ubuntu 22.04")
        analysis = scanner.analyze_ports(result)
        assert analysis["os_info"] == "Ubuntu 22.04"


# =============================================================================
# get_high_risk_ports — 高危端口详情
# =============================================================================


class TestGetHighRiskPorts:
    """提取高危端口详情列表。"""

    def test_no_high_risk_returns_empty(self):
        scanner = PortScanner()
        result = _make_result(
            ports=[{"port": 80, "protocol": "tcp", "state": "open", "service": "http"}],
        )
        assert scanner.get_high_risk_ports(result) == []

    def test_high_risk_returns_details(self):
        scanner = PortScanner()
        result = _make_result(
            ports=[
                {"port": 23, "protocol": "tcp", "state": "open", "service": "telnet"},
                {"port": 22, "protocol": "tcp", "state": "open", "service": "ssh"},
            ],
        )
        high_risk = scanner.get_high_risk_ports(result)
        assert len(high_risk) == 2
        ports = {h["port"] for h in high_risk}
        assert ports == {23, 22}
        # 每条记录包含风险描述
        for h in high_risk:
            assert "risk" in h
            assert h["protocol"] == "tcp"

    def test_high_risk_ignores_non_open(self):
        """过滤掉非 open 状态的高危端口。"""
        scanner = PortScanner()
        result = _make_result(
            ports=[{"port": 23, "protocol": "tcp", "state": "filtered", "service": "telnet"}],
        )
        assert scanner.get_high_risk_ports(result) == []


# =============================================================================
# get_open_ports_summary — 文本摘要
# =============================================================================


class TestGetOpenPortsSummary:
    """生成格式化的文本摘要。"""

    def test_summary_includes_basic_info(self):
        scanner = PortScanner()
        result = _make_result(
            target="192.168.1.1",
            duration_seconds=3.5,
            ports=[{"port": 80, "protocol": "tcp", "state": "open", "service": "http"}],
        )
        summary = scanner.get_open_ports_summary(result)
        assert "192.168.1.1" in summary
        assert "3.5s" in summary
        assert "端口总数: 1" in summary
        assert "开放: 1" in summary

    def test_summary_includes_os_when_present(self):
        scanner = PortScanner()
        result = _make_result(os_info="Debian 12")
        summary = scanner.get_open_ports_summary(result)
        assert "Debian 12" in summary

    def test_summary_skips_os_when_none(self):
        scanner = PortScanner()
        result = _make_result(os_info=None)
        summary = scanner.get_open_ports_summary(result)
        assert "操作系统" not in summary

    def test_summary_includes_services_when_present(self):
        scanner = PortScanner()
        result = _make_result(
            ports=[{"port": 22, "protocol": "tcp", "state": "open", "service": "ssh"}],
            services=[{"name": "ssh", "version": "OpenSSH 8.9", "port": 22}],
        )
        summary = scanner.get_open_ports_summary(result)
        assert "识别服务" in summary
        assert "OpenSSH 8.9" in summary

    def test_summary_skips_services_when_empty(self):
        scanner = PortScanner()
        result = _make_result(services=[])
        summary = scanner.get_open_ports_summary(result)
        assert "识别服务" not in summary
