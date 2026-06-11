"""LightShield Nmap 适配器

封装 Nmap 端口扫描、服务识别、OS 探测能力。
通过 python-nmap 库调用，输出标准化的 ScanResult。

用法：
    from lightshield.adapters.nmap_adapter import NmapAdapter
    adapter = NmapAdapter()
    result = adapter.scan("192.168.1.1", ports="1-1000")
"""

import subprocess
import xml.etree.ElementTree as ET

from lightshield.adapters.base import BaseAdapter, ScanResult, VulnFinding
from lightshield.utils.constants import HIGH_RISK_PORTS, RiskLevel, ScanStatus
from lightshield.utils.logger import get_logger
from lightshield.utils.validator import TargetValidator


class NmapAdapter(BaseAdapter):
    """Nmap 扫描适配器 — 端口扫描 + 服务识别 + OS 探测

    封装 nmap 命令行工具，解析 XML 输出为结构化 ScanResult。
    支持通过 python-nmap 或直接 subprocess 调用。

    能力清单：
    - port_scan: TCP/UDP 端口扫描
    - service_detect: 服务版本检测
    - os_detect: 操作系统指纹识别
    """

    def __init__(self, nmap_path: str = "nmap", nmap_args: str = "-sV -O --top-ports 1000"):
        """初始化 Nmap 适配器。

        Args:
        nmap_path: Nmap 可执行文件路径
        nmap_args: Nmap 默认参数
        """
        super().__init__(name="NmapAdapter")
        self._nmap_path = nmap_path
        self._nmap_args = nmap_args
        self._logger = get_logger()

    # =========================================================================
    # BaseAdapter 实现
    # =========================================================================

    def capabilities(self) -> list[str]:
        """返回 ["port_scan", "service_detect", "os_detect"]"""
        return ["port_scan", "service_detect", "os_detect"]

    def validate_target(self, target: str) -> bool:
        """目标合法性校验——委托给 TargetValidator"""
        is_valid, reason = TargetValidator.validate(target)
        if not is_valid:
            self._logger.warning("nmap", f"目标校验失败: {target} — {reason}")
        return is_valid

    def scan(self, target: str, **kwargs) -> ScanResult:
        """执行 Nmap 扫描

        Args:
            target: 扫描目标（单 IP/域名）
            **kwargs:
                ports: 端口范围（如 "1-1000", "80,443"）
                extra_args: 额外 Nmap 参数
                timeout: 超时秒数（默认 60）

        Returns:
            ScanResult 结构化结果
        """
        # 1. 前置校验
        if not self.validate_target(target):
            return ScanResult(
                status=ScanStatus.FAILED,
                target=target,
                error="目标校验不通过",
            )

        # 2. 记录审计
        scan_id = self._log_scan_start(target, "nmap")

        # 3. 构造命令
        ports = kwargs.get("ports", "")
        extra_args = kwargs.get("extra_args", "")
        timeout = kwargs.get("timeout", 60)

        cmd = [self._nmap_path, "-oX", "-"]  # XML 输出到 stdout
        if ports:
            cmd.extend(["-p", str(ports)])
        if extra_args:
            cmd.extend(extra_args.split())
        else:
            cmd.extend(self._nmap_args.split())
        cmd.append(target)

        self._logger.info("nmap", f"执行扫描: {' '.join(cmd)}")

        # 4. 执行
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
        except subprocess.TimeoutExpired:
            error_msg = f"Nmap 扫描超时（{timeout}s）"
            self._logger.error("nmap", error_msg)
            return ScanResult(
                status=ScanStatus.FAILED,
                target=target,
                error=error_msg,
                duration_seconds=timeout,
            )
        except FileNotFoundError:
            error_msg = f"Nmap 未安装或路径错误: {self._nmap_path}"
            self._logger.error("nmap", error_msg)
            return ScanResult(
                status=ScanStatus.FAILED,
                target=target,
                error=error_msg,
            )
        except Exception as e:
            self._logger.error("nmap", "扫描异常", exception=e)
            return ScanResult(
                status=ScanStatus.FAILED,
                target=target,
                error=str(e),
            )

        # 5. 解析 XML 输出
        try:
            # Nmap 可能返回非 0 但仍产生有效输出
            if result.returncode != 0 and not result.stdout.strip():
                return ScanResult(
                    status=ScanStatus.FAILED,
                    target=target,
                    error=f"Nmap 返回码 {result.returncode}: {result.stderr[:200]}",
                    raw_output=result.stderr,
                )

            scan_result = self._parse_nmap_xml(result.stdout, target)
            scan_result.raw_output = result.stdout

            # 标记高危端口
            self._flag_high_risk_ports(scan_result)

            # 6. 记录审计
            self._log_scan_end(scan_id, scan_result)
            self._logger.info(
                "nmap",
                f"扫描完成: {len(scan_result.ports)} 端口, {len(scan_result.findings)} 高危发现",
            )

            return scan_result

        except ET.ParseError as e:
            self._logger.error("nmap", "XML 解析失败", exception=e)
            return ScanResult(
                status=ScanStatus.FAILED,
                target=target,
                error=f"XML 解析失败: {e}",
                raw_output=result.stdout,
            )

    # =========================================================================
    # XML 解析
    # =========================================================================

    def _parse_nmap_xml(self, xml_output: str, target: str) -> ScanResult:
        """解析 Nmap XML 输出为 ScanResult

        Args:
            xml_output: Nmap -oX 输出的 XML 字符串
            target: 扫描目标

        Returns:
            ScanResult
        """
        root = ET.fromstring(xml_output)  # nosec B314 — Nmap 本地 XML 输出（可信本地工具），非外部不可信 XML

        ports = []
        services = []
        os_info = None

        for host in root.findall("host"):
            # OS 探测
            os_elem = host.find("os")
            if os_elem is not None:
                os_matches = os_elem.findall("osmatch")
                if os_matches:
                    os_info = os_matches[0].get("name", "")

            # 端口
            ports_elem = host.find("ports")
            if ports_elem is None:
                continue

            for port in ports_elem.findall("port"):
                port_id = int(port.get("portid", "0"))
                protocol = port.get("protocol", "tcp")

                state_elem = port.find("state")
                state = state_elem.get("state", "unknown") if state_elem is not None else "unknown"

                service_elem = port.find("service")
                service_name = ""
                service_version = ""
                if service_elem is not None:
                    service_name = service_elem.get("name", "")
                    service_version = (service_elem.get("product", "") + " " + service_elem.get("version", "")).strip()

                ports.append(
                    {
                        "port": port_id,
                        "protocol": protocol,
                        "state": state,
                        "service": service_name,
                    }
                )

                if service_name:
                    services.append(
                        {
                            "name": service_name,
                            "version": service_version,
                            "port": port_id,
                        }
                    )

        return ScanResult(
            status=ScanStatus.COMPLETED,
            target=target,
            ports=ports,
            services=services,
            os_info=os_info,
            findings=[],
        )

    # =========================================================================
    # 高危端口标记
    # =========================================================================

    def _flag_high_risk_ports(self, result: ScanResult) -> None:
        """标记扫描结果中的高危端口为 VulnFinding

        对照 HIGH_RISK_PORTS 字典，将开放的已知高危端口
        转换为 VulnFinding 记录。

        Args:
            result: 扫描结果（原地修改 findings 字段）
        """
        for port_info in result.ports:
            port_num = port_info.get("port", 0)
            if port_num in HIGH_RISK_PORTS and port_info.get("state") == "open":
                risk_desc = HIGH_RISK_PORTS[port_num]
                finding = VulnFinding(
                    vuln_type="high_risk_port",
                    severity=RiskLevel.HIGH,
                    title=f"高危端口开放: {port_num} ({risk_desc})",
                    description=(
                        f"端口 {port_num}（{risk_desc}）处于开放状态。"
                        f"该端口是常见的攻击入口，建议评估是否需要对外开放。"
                    ),
                    remediation=(
                        f"1. 评估是否需要对外开放此端口\n"
                        f"2. 如不需要，通过防火墙关闭端口 {port_num}\n"
                        f"3. 如必须开放，配置 IP 白名单和访问控制\n"
                        f"4. 确保服务的认证机制（如 SSH 密钥登录、强密码）"
                    ),
                    port=port_num,
                    evidence=f"端口 {port_num} 状态: {port_info.get('state')}, 服务: {port_info.get('service', 'unknown')}",
                )
                result.findings.append(finding)


# =============================================================================
# 自检
# =============================================================================

if __name__ == "__main__":
    print("=== NmapAdapter 自检 ===")

    adapter = NmapAdapter()
    print(f"能力: {adapter.capabilities()}")

    # 1. 目标校验
    assert adapter.validate_target("127.0.0.1")
    assert not adapter.validate_target("192.168.1.0/24")
    print("  目标校验通过")

    # 2. XML 解析（用模拟数据）
    sample_xml = """<?xml version="1.0"?>
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
            </ports>
        </host>
    </nmaprun>"""

    result = adapter._parse_nmap_xml(sample_xml, "127.0.0.1")
    assert result.status == ScanStatus.COMPLETED
    assert len(result.ports) == 3
    assert result.os_info == "Linux 5.15"
    print(f"  XML 解析通过: {len(result.ports)} 端口, OS: {result.os_info}")

    # 3. 高危端口标记
    adapter._flag_high_risk_ports(result)
    print(f"  高危发现: {len(result.findings)} 个")
    for f in result.findings:
        print(f"    [{f.severity.value}] {f.title}")

    print("=== NmapAdapter 自检全部通过 ===")
