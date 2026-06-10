"""测试模块：lightshield/scanners/weak_password.py

被测类：WeakPasswordAdapter(BaseAdapter)

测试点：
  - capabilities() 返回 ["weak_password"]
  - _match_service_type 端口→服务类型映射
  - _discover_services 从 kwargs 的 ports/services 解析服务列表
  - _is_port_open mock socket 验证端口可达/不可达
  - MAX_PASSWORD_ATTEMPTS = 10（R6 合规常量）
  - reset_attempts() 清零内部计数器
  - scan() 返回 COMPLETED，findings 含弱口令发现
"""

import socket
from unittest.mock import MagicMock, patch

import pytest

from lightshield.scanners.weak_password import WeakPasswordAdapter
from lightshield.adapters.base import VulnFinding
from lightshield.utils.constants import ScanStatus, RiskLevel


@pytest.fixture
def adapter():
    """返回 WeakPasswordAdapter 实例"""
    return WeakPasswordAdapter()


# =============================================================================
# capabilities
# =============================================================================

class TestCapabilities:
    """capabilities() 返回正确的能力列表"""

    def test_returns_weak_password(self, adapter):
        """返回 ["weak_password"]"""
        caps = adapter.capabilities()
        assert caps == ["weak_password"]


# =============================================================================
# MAX_PASSWORD_ATTEMPTS 常量
# =============================================================================

class TestMaxAttempts:
    """MAX_PASSWORD_ATTEMPTS 合规常量"""

    def test_max_attempts_value(self, adapter):
        """MAX_PASSWORD_ATTEMPTS == 10"""
        assert adapter.MAX_PASSWORD_ATTEMPTS == 10


# =============================================================================
# _match_service_type
# =============================================================================

class TestMatchServiceType:
    """_match_service_type 端口→服务类型映射"""

    def test_port_22_ssh_returns_ssh(self, adapter):
        """端口 22 + 服务名 ssh → 'ssh'"""
        assert adapter._match_service_type(22, "ssh") == "ssh"

    def test_port_3306_mysql_returns_mysql(self, adapter):
        """端口 3306 + 服务名 mysql → 'mysql'"""
        assert adapter._match_service_type(3306, "mysql") == "mysql"

    def test_port_80_http_returns_http(self, adapter):
        """端口 80 + 服务名 http → 'http'"""
        assert adapter._match_service_type(80, "http") == "http"

    def test_port_443_https_returns_http(self, adapter):
        """端口 443（HTTPS）也映射为 http"""
        result = adapter._match_service_type(443, "https")
        assert result == "http"

    def test_port_8080_nginx_returns_http(self, adapter):
        """端口 8080 + nginx 映射为 http"""
        result = adapter._match_service_type(8080, "nginx")
        assert result == "http"

    def test_port_9999_unknown_returns_none(self, adapter):
        """端口 9999 + unknown → None"""
        result = adapter._match_service_type(9999, "unknown")
        assert result is None

    def test_port_only_match_without_service_name(self, adapter):
        """纯端口匹配（service_name 为空）"""
        assert adapter._match_service_type(22, "") == "ssh"
        assert adapter._match_service_type(3306, "") == "mysql"
        assert adapter._match_service_type(80, "") == "http"


# =============================================================================
# _discover_services
# =============================================================================

class TestDiscoverServices:
    """_discover_services 从 kwargs 解析服务"""

    def test_ports_kwarg_discovers_services(self, adapter):
        """通过 ports kwargs 发现 SSH/MySQL/HTTP 服务"""
        ports_info = [
            {"port": 22, "protocol": "tcp", "state": "open", "service": "ssh"},
            {"port": 3306, "protocol": "tcp", "state": "open", "service": "mysql"},
            {"port": 80, "protocol": "tcp", "state": "open", "service": "http"},
        ]
        discovered = adapter._discover_services("127.0.0.1", ports=ports_info)
        types = {d["type"] for d in discovered}
        assert types == {"ssh", "mysql", "http"}
        assert len(discovered) == 3

    def test_closed_ports_ignored(self, adapter):
        """closed 状态的端口被忽略"""
        ports_info = [
            {"port": 22, "protocol": "tcp", "state": "open", "service": "ssh"},
            {"port": 443, "protocol": "tcp", "state": "closed", "service": "https"},
        ]
        discovered = adapter._discover_services("127.0.0.1", ports=ports_info)
        assert len(discovered) == 1
        assert discovered[0]["type"] == "ssh"

    def test_services_kwarg_discovers_services(self, adapter):
        """通过 services kwargs 发现服务"""
        services_info = [
            {"name": "ssh", "version": "OpenSSH 8.9", "port": 22},
            {"name": "mysql", "version": "MySQL 8.0", "port": 3306},
        ]
        discovered = adapter._discover_services("127.0.0.1", services=services_info)
        types = {d["type"] for d in discovered}
        assert types == {"ssh", "mysql"}


# =============================================================================
# _is_port_open
# =============================================================================

class TestIsPortOpen:
    """_is_port_open() 端口可达性探测（mock socket）"""

    def test_open_port_returns_true(self, adapter):
        """mock socket 连接成功返回 True"""
        with patch("socket.create_connection", return_value=MagicMock()) as mock_sock:
            assert adapter._is_port_open("127.0.0.1", 22) is True
            mock_sock.assert_called_once()

    def test_connection_refused_returns_false(self, adapter):
        """连接被拒绝返回 False"""
        with patch(
            "socket.create_connection",
            side_effect=ConnectionRefusedError(),
        ):
            assert adapter._is_port_open("127.0.0.1", 19999) is False

    def test_timeout_returns_false(self, adapter):
        """连接超时返回 False"""
        with patch(
            "socket.create_connection",
            side_effect=socket.timeout(),
        ):
            assert adapter._is_port_open("192.168.1.1", 80) is False

    def test_oserror_returns_false(self, adapter):
        """OSError 返回 False"""
        with patch(
            "socket.create_connection",
            side_effect=OSError(),
        ):
            assert adapter._is_port_open("192.168.1.1", 80) is False


# =============================================================================
# reset_attempts
# =============================================================================

class TestResetAttempts:
    """reset_attempts() 计数器清零"""

    def test_resets_counter_to_zero(self, adapter):
        """reset_attempts() 后内部计数器为 0"""
        adapter._attempt_count = 5
        adapter.reset_attempts()
        assert adapter._attempt_count == 0


# =============================================================================
# scan
# =============================================================================

class TestScan:
    """scan() 方法完整流程验证"""

    def test_scan_returns_completed(self, adapter):
        """scan() 返回 ScanStatus.COMPLETED"""
        ports_info = [
            {"port": 22, "protocol": "tcp", "state": "open", "service": "ssh"},
            {"port": 3306, "protocol": "tcp", "state": "open", "service": "mysql"},
        ]
        result = adapter.scan("127.0.0.1", ports=ports_info, max_attempts=3)
        assert result.status == ScanStatus.COMPLETED

    def test_scan_findings_include_weak_password(self, adapter):
        """scan() 的 findings 包含弱口令发现"""
        ports_info = [
            {"port": 22, "protocol": "tcp", "state": "open", "service": "ssh"},
        ]
        result = adapter.scan("127.0.0.1", ports=ports_info, max_attempts=3)
        assert len(result.findings) >= 1
        # SSH 弱口令发现
        ssh_findings = [f for f in result.findings if f.port == 22]
        assert len(ssh_findings) >= 1

    def test_scan_with_no_services_returns_empty_findings(self, adapter):
        """无可用服务时 findings 为空"""
        with patch.object(adapter, "_discover_services", return_value=[]):
            result = adapter.scan("127.0.0.1")
            assert result.status == ScanStatus.COMPLETED
            assert len(result.findings) == 0

    def test_scan_ports_in_result(self, adapter):
        """scan() 结果中包含 ports 信息"""
        ports_info = [
            {"port": 22, "protocol": "tcp", "state": "open", "service": "ssh"},
        ]
        result = adapter.scan("127.0.0.1", ports=ports_info, max_attempts=3)
        assert len(result.ports) >= 1
        assert result.ports[0]["port"] == 22

    def test_scan_invalid_target_returns_failed(self, adapter):
        """非法目标返回 FAILED"""
        result = adapter.scan("")
        assert result.status == ScanStatus.FAILED
