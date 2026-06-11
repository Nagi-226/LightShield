"""LightShield 端口扫描器

基于 NmapAdapter 的高层封装，提供面向用户的资产扫描能力。
包括：端口扫描、服务识别、敏感目录探测、高危端口告警。

用法：
    from lightshield.scanners.port_scanner import PortScanner
    scanner = PortScanner()
    result = scanner.scan("192.168.1.1")
"""

from lightshield.adapters.base import ScanResult
from lightshield.adapters.nmap_adapter import NmapAdapter
from lightshield.utils.constants import HIGH_RISK_PORTS, ScanStatus
from lightshield.utils.logger import get_logger
from lightshield.utils.validator import TargetValidator


class PortScanner:
    """端口扫描器 — 资产发现的入口

    封装 NmapAdapter，提供更友好的扫描接口：
    - 快速扫描（top 100 端口）
    - 全量扫描（top 1000 端口）
    - 自定义端口范围
    - 高危端口专项检查
    """

    def __init__(self, nmap_adapter: NmapAdapter = None):
        """初始化端口扫描器。

        Args:
        nmap_adapter: Nmap 适配器实例，默认自动创建
        """
        self._adapter = nmap_adapter or NmapAdapter()
        self._logger = get_logger()

    # =========================================================================
    # 扫描方法
    # =========================================================================

    def quick_scan(self, target: str) -> ScanResult:
        """快速扫描 — Top 100 端口，适合日常检查"""
        self._logger.info("port_scanner", f"快速扫描: {target}")
        return self._adapter.scan(target, ports="1-100")

    def full_scan(self, target: str) -> ScanResult:
        """全量扫描 — Top 1000 端口，适合初次评估"""
        self._logger.info("port_scanner", f"全量扫描: {target}")
        return self._adapter.scan(target)

    def custom_scan(self, target: str, ports: str) -> ScanResult:
        """自定义端口范围扫描

        Args:
            target: 扫描目标
            ports: 端口范围（如 "80,443,3306" 或 "1-1024"）
        """
        self._logger.info("port_scanner", f"自定义扫描: {target} 端口:{ports}")
        return self._adapter.scan(target, ports=ports)

    # =========================================================================
    # 分析
    # =========================================================================

    def analyze_ports(self, result: ScanResult) -> dict:
        """分析扫描结果的端口分布

        Returns:
            {
                "total": 总端口数,
                "open": 开放数,
                "filtered": 被过滤数,
                "closed": 关闭数,
                "high_risk": 高危端口发现数,
                "services": 识别的服务数,
            }
        """
        open_count = sum(1 for p in result.ports if p.get("state") == "open")
        filtered_count = sum(1 for p in result.ports if p.get("state") == "filtered")
        closed_count = sum(1 for p in result.ports if p.get("state") == "closed")

        # 高危端口数
        high_risk = sum(1 for p in result.ports if p.get("state") == "open" and p.get("port") in HIGH_RISK_PORTS)

        return {
            "total": len(result.ports),
            "open": open_count,
            "filtered": filtered_count,
            "closed": closed_count,
            "high_risk": high_risk,
            "services": len(result.services),
            "os_info": result.os_info,
        }

    def get_high_risk_ports(self, result: ScanResult) -> list[dict]:
        """提取高危端口详情"""
        return [
            {
                "port": p.get("port"),
                "protocol": p.get("protocol"),
                "service": p.get("service"),
                "risk": HIGH_RISK_PORTS.get(p.get("port", 0), "未知风险"),
            }
            for p in result.ports
            if p.get("state") == "open" and p.get("port") in HIGH_RISK_PORTS
        ]

    def get_open_ports_summary(self, result: ScanResult) -> str:
        """生成开放端口摘要（用于报告）

        Returns:
            格式化的端口摘要文本
        """
        analysis = self.analyze_ports(result)
        lines = [
            f"扫描目标: {result.target}",
            f"扫描耗时: {result.duration_seconds}s",
            f"端口总数: {analysis['total']}",
            f"  开放: {analysis['open']}",
            f"  过滤: {analysis['filtered']}",
            f"  关闭: {analysis['closed']}",
            f"高危端口: {analysis['high_risk']}",
        ]

        if result.os_info:
            lines.append(f"操作系统: {result.os_info}")

        if result.services:
            lines.append("")
            lines.append("识别服务:")
            for svc in result.services:
                lines.append(f"  {svc.get('name')} {svc.get('version')} (端口 {svc.get('port')})")

        return "\n".join(lines)


# =============================================================================
# 自检
# =============================================================================

if __name__ == "__main__":
    print("=== PortScanner 自检 ===")

    scanner = PortScanner()

    # 1. 目标校验
    assert TargetValidator.validate("127.0.0.1")[0]
    print("  目标校验通过")

    # 2. 高危端口识别（用模拟数据）
    from lightshield.adapters.base import ScanResult

    mock_result = ScanResult(
        status=ScanStatus.COMPLETED,
        target="127.0.0.1",
        ports=[
            {"port": 22, "protocol": "tcp", "state": "open", "service": "ssh"},
            {"port": 80, "protocol": "tcp", "state": "open", "service": "http"},
            {"port": 3306, "protocol": "tcp", "state": "open", "service": "mysql"},
            {"port": 443, "protocol": "tcp", "state": "closed", "service": "https"},
        ],
        services=[
            {"name": "ssh", "version": "OpenSSH 8.9", "port": 22},
            {"name": "http", "version": "nginx 1.24", "port": 80},
            {"name": "mysql", "version": "MySQL 8.0", "port": 3306},
        ],
        os_info="Ubuntu 22.04",
    )

    analysis = scanner.analyze_ports(mock_result)
    assert analysis["open"] == 3
    assert analysis["high_risk"] == 2  # 22 + 3306
    print(f"  端口分析: {analysis['open']} 开放, {analysis['high_risk']} 高危")

    high_risk = scanner.get_high_risk_ports(mock_result)
    for hr in high_risk:
        print(f"    高危端口 {hr['port']}: {hr['risk']}")

    summary = scanner.get_open_ports_summary(mock_result)
    print(f"  端口摘要已生成 ({len(summary)} 字符)")

    print("=== PortScanner 自检全部通过 ===")
