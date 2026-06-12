"""测试模块：lightshield/adapters/nmap_adapter.py

被测类：NmapAdapter(BaseAdapter)

测试点：
  - capabilities() 返回正确能力列表
  - validate_target() 目标校验委托
  - _parse_nmap_xml() XML 解析（端口/服务/OS/空结果/格式错误）
  - _flag_high_risk_ports() 高危端口标记
  - scan() nmap 不可用时的错误处理
"""

import xml.etree.ElementTree as ET

import pytest

from lightshield.adapters.nmap_adapter import NmapAdapter
from lightshield.utils.constants import ScanStatus


@pytest.fixture
def adapter():
    """返回 NmapAdapter 实例"""
    return NmapAdapter()


# =============================================================================
# capabilities
# =============================================================================


class TestCapabilities:
    """capabilities() 返回正确的能力标签"""

    def test_returns_three_capabilities(self, adapter):
        """返回 ['port_scan', 'service_detect', 'os_detect']"""
        caps = adapter.capabilities()
        assert sorted(caps) == sorted(["port_scan", "service_detect", "os_detect"])

    def test_all_capabilities_are_strings(self, adapter):
        """所有能力标签都是字符串"""
        for cap in adapter.capabilities():
            assert isinstance(cap, str)


# =============================================================================
# validate_target
# =============================================================================


class TestValidateTarget:
    """validate_target() 目标合法性校验"""

    def test_valid_ip_returns_true(self, adapter):
        """合法 IP 地址返回 True"""
        assert adapter.validate_target("127.0.0.1") is True
        assert adapter.validate_target("192.168.1.1") is True

    def test_valid_domain_returns_true(self, adapter):
        """合法域名返回 True"""
        assert adapter.validate_target("example.com") is True

    def test_cidr_range_returns_false(self, adapter):
        """CIDR 网段返回 False（R2 合规红线）"""
        assert adapter.validate_target("192.168.1.0/24") is False

    def test_empty_string_returns_false(self, adapter):
        """空字符串返回 False"""
        assert adapter.validate_target("") is False

    def test_url_returns_false(self, adapter):
        """URL 格式返回 False"""
        assert adapter.validate_target("http://example.com") is False


# =============================================================================
# _parse_nmap_xml
# =============================================================================


SAMPLE_XML = """<?xml version="1.0"?>
<nmaprun>
    <host>
        <os><osmatch name="Linux 5.15"/></os>
        <ports>
            <port portid="22" protocol="tcp">
                <state state="open"/>
                <service name="ssh" product="OpenSSH" version="8.9"/>
            </port>
            <port portid="80" protocol="tcp">
                <state state="open"/>
                <service name="http" product="nginx" version="1.24.0"/>
            </port>
            <port portid="3306" protocol="tcp">
                <state state="open"/>
                <service name="mysql" product="MySQL" version="8.0"/>
            </port>
            <port portid="443" protocol="tcp">
                <state state="closed"/>
                <service name="https"/>
            </port>
        </ports>
    </host>
</nmaprun>"""


class TestParseNmapXml:
    """_parse_nmap_xml() XML 解析"""

    def test_returns_completed_status(self, adapter):
        """正常 XML 返回 COMPLETED"""
        result = adapter._parse_nmap_xml(SAMPLE_XML, "127.0.0.1")
        assert result.status == ScanStatus.COMPLETED
        assert result.target == "127.0.0.1"

    def test_parses_all_ports(self, adapter):
        """解析所有端口（含 open 和 closed）"""
        result = adapter._parse_nmap_xml(SAMPLE_XML, "127.0.0.1")
        assert len(result.ports) == 4  # 3 open + 1 closed

    def test_port_has_correct_fields(self, adapter):
        """每个端口包含 port / protocol / state / service"""
        result = adapter._parse_nmap_xml(SAMPLE_XML, "127.0.0.1")
        ssh_ports = [p for p in result.ports if p["port"] == 22]
        assert len(ssh_ports) == 1
        assert ssh_ports[0]["protocol"] == "tcp"
        assert ssh_ports[0]["state"] == "open"
        assert ssh_ports[0]["service"] == "ssh"

    def test_parses_services_with_versions(self, adapter):
        """服务列表包含版本信息"""
        result = adapter._parse_nmap_xml(SAMPLE_XML, "127.0.0.1")
        # 仅开放端口有服务
        open_services = [s for s in result.services if s["name"]]
        assert len(open_services) >= 3

    def test_extracts_os_info(self, adapter):
        """提取 OS 信息"""
        result = adapter._parse_nmap_xml(SAMPLE_XML, "127.0.0.1")
        assert result.os_info == "Linux 5.15"

    def test_no_os_element_returns_none(self, adapter):
        """无 <os> 元素时 os_info 为 None"""
        xml_no_os = """<?xml version="1.0"?>
        <nmaprun>
            <host>
                <ports>
                    <port portid="80" protocol="tcp">
                        <state state="open"/>
                        <service name="http" product="nginx" version="1.24"/>
                    </port>
                </ports>
            </host>
        </nmaprun>"""
        result = adapter._parse_nmap_xml(xml_no_os, "127.0.0.1")
        assert result.os_info is None

    def test_no_ports_element_returns_empty(self, adapter):
        """无 <ports> 元素时返回空端口列表"""
        xml_no_ports = """<?xml version="1.0"?>
        <nmaprun>
            <host>
            </host>
        </nmaprun>"""
        result = adapter._parse_nmap_xml(xml_no_ports, "127.0.0.1")
        assert result.ports == []
        assert result.services == []

    def test_empty_ports_returns_empty_lists(self, adapter):
        """Ports 下无 port 时返回空列表"""
        xml_empty = """<?xml version="1.0"?>
        <nmaprun>
            <host>
                <ports>
                </ports>
            </host>
        </nmaprun>"""
        result = adapter._parse_nmap_xml(xml_empty, "127.0.0.1")
        assert result.ports == []
        assert result.services == []

    def test_malformed_xml_raises_parse_error(self, adapter):
        """格式错误的 XML 抛出 ET.ParseError"""
        with pytest.raises(ET.ParseError):
            adapter._parse_nmap_xml("this is not xml", "127.0.0.1")

    def test_multiple_hosts_aggregates_ports(self, adapter):
        """多 host 节点聚合所有端口"""
        xml_multi = """<?xml version="1.0"?>
        <nmaprun>
            <host>
                <ports>
                    <port portid="22" protocol="tcp">
                        <state state="open"/>
                        <service name="ssh" product="OpenSSH" version="8.9"/>
                    </port>
                </ports>
            </host>
            <host>
                <ports>
                    <port portid="80" protocol="tcp">
                        <state state="open"/>
                        <service name="http" product="nginx" version="1.24"/>
                    </port>
                </ports>
            </host>
        </nmaprun>"""
        result = adapter._parse_nmap_xml(xml_multi, "127.0.0.1")
        assert len(result.ports) == 2

    def test_port_without_service_element(self, adapter):
        """无 <service> 子元素的端口不崩溃"""
        xml_no_svc = """<?xml version="1.0"?>
        <nmaprun>
            <host>
                <ports>
                    <port portid="80" protocol="tcp">
                        <state state="filtered"/>
                    </port>
                </ports>
            </host>
        </nmaprun>"""
        result = adapter._parse_nmap_xml(xml_no_svc, "127.0.0.1")
        assert len(result.ports) == 1
        assert result.ports[0]["service"] == ""

    def test_port_without_state_element(self, adapter):
        """无 <state> 子元素的端口 state 为 'unknown'"""
        xml_no_state = """<?xml version="1.0"?>
        <nmaprun>
            <host>
                <ports>
                    <port portid="80" protocol="tcp">
                        <service name="http"/>
                    </port>
                </ports>
            </host>
        </nmaprun>"""
        result = adapter._parse_nmap_xml(xml_no_state, "127.0.0.1")
        assert result.ports[0]["state"] == "unknown"

    def test_findings_initially_empty(self, adapter):
        """新解析结果 findings 为空列表"""
        result = adapter._parse_nmap_xml(SAMPLE_XML, "127.0.0.1")
        assert result.findings == []


# =============================================================================
# _flag_high_risk_ports
# =============================================================================


class TestFlagHighRiskPorts:
    """_flag_high_risk_ports() 高危端口标记"""

    def test_open_high_risk_port_flagged(self, adapter):
        """开放的高危端口被标记为 VulnFinding"""
        from lightshield.adapters.base import ScanResult

        result = ScanResult(
            status=ScanStatus.COMPLETED,
            target="127.0.0.1",
            ports=[
                {"port": 23, "protocol": "tcp", "state": "open", "service": "telnet"},
            ],
        )
        adapter._flag_high_risk_ports(result)
        assert len(result.findings) >= 1
        finding = result.findings[0]
        assert finding.vuln_type == "high_risk_port"
        assert finding.port == 23

    def test_closed_port_not_flagged(self, adapter):
        """关闭的高危端口不标记"""
        from lightshield.adapters.base import ScanResult

        result = ScanResult(
            status=ScanStatus.COMPLETED,
            target="127.0.0.1",
            ports=[
                {"port": 23, "protocol": "tcp", "state": "closed", "service": ""},
            ],
        )
        adapter._flag_high_risk_ports(result)
        assert result.findings == []

    def test_non_high_risk_port_not_flagged(self, adapter):
        """非高危端口不标记"""
        from lightshield.adapters.base import ScanResult

        result = ScanResult(
            status=ScanStatus.COMPLETED,
            target="127.0.0.1",
            ports=[
                {"port": 80, "protocol": "tcp", "state": "open", "service": "http"},
            ],
        )
        adapter._flag_high_risk_ports(result)
        assert result.findings == []

    def test_multiple_high_risk_ports_all_flagged(self, adapter):
        """多个高危端口全部被标记"""
        from lightshield.adapters.base import ScanResult

        result = ScanResult(
            status=ScanStatus.COMPLETED,
            target="127.0.0.1",
            ports=[
                {"port": 21, "protocol": "tcp", "state": "open", "service": "ftp"},
                {"port": 23, "protocol": "tcp", "state": "open", "service": "telnet"},
            ],
        )
        adapter._flag_high_risk_ports(result)
        assert len(result.findings) == 2
        ports_flagged = {f.port for f in result.findings}
        assert ports_flagged == {21, 23}

    def test_mixed_open_closed_only_open_flagged(self, adapter):
        """混合场景：只标记 open 的高危端口"""
        from lightshield.adapters.base import ScanResult

        result = ScanResult(
            status=ScanStatus.COMPLETED,
            target="127.0.0.1",
            ports=[
                {"port": 21, "protocol": "tcp", "state": "open", "service": "ftp"},
                {"port": 23, "protocol": "tcp", "state": "closed", "service": ""},
                {"port": 80, "protocol": "tcp", "state": "open", "service": "http"},
            ],
        )
        adapter._flag_high_risk_ports(result)
        assert len(result.findings) == 1
        assert result.findings[0].port == 21

    def test_empty_ports_no_error(self, adapter):
        """空端口列表不抛异常"""
        from lightshield.adapters.base import ScanResult

        result = ScanResult(
            status=ScanStatus.COMPLETED,
            target="127.0.0.1",
            ports=[],
        )
        adapter._flag_high_risk_ports(result)
        assert result.findings == []

    def test_finding_has_all_required_fields(self, adapter):
        """生成的 VulnFinding 包含所有必填字段"""
        from lightshield.adapters.base import ScanResult

        result = ScanResult(
            status=ScanStatus.COMPLETED,
            target="127.0.0.1",
            ports=[
                {"port": 23, "protocol": "tcp", "state": "open", "service": "telnet"},
            ],
        )
        adapter._flag_high_risk_ports(result)
        finding = result.findings[0]
        assert finding.vuln_type
        assert finding.severity is not None
        assert finding.title
        assert finding.description
        assert finding.remediation
        assert finding.port == 23
        assert finding.evidence


# =============================================================================
# scan() — error paths (nmap not available on test machine)
# =============================================================================


class TestScanErrorPaths:
    """scan() 错误路径测试（不依赖 nmap 实际安装）"""

    def test_invalid_target_returns_failed(self, adapter):
        """非法目标返回 FAILED"""
        result = adapter.scan("")
        assert result.status == ScanStatus.FAILED
        assert "校验" in result.error

    def test_cidr_target_rejected(self, adapter):
        """CIDR 网段被 R2 拦截"""
        result = adapter.scan("192.168.1.0/24")
        assert result.status == ScanStatus.FAILED

    def test_nmap_not_found_returns_failed(self, adapter):
        """Nmap 不在 PATH 时返回 FAILED（FileNotFoundError）"""
        # 使用不存在的 nmap 路径
        adapter_bad = NmapAdapter(nmap_path="nonexistent_nmap_binary_xyz")
        result = adapter_bad.scan("127.0.0.1")
        assert result.status == ScanStatus.FAILED
        assert "未安装" in result.error or "nonexistent" in result.error
