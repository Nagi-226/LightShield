"""LightShield 适配器抽象基类

定义所有扫描适配器的统一接口。新增任何扫描能力只需实现此基类。
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from lightshield.utils.constants import RiskLevel, ScanStatus

# =============================================================================
# 数据结构
# =============================================================================


@dataclass
class ScanResult:
    """扫描结果统一数据结构——所有适配器返回此格式

    Attributes:
        status: 扫描状态（completed / failed / cancelled）
        target: 扫描目标
        ports: 发现的端口列表 [{"port": 80, "service": "http", "state": "open"}, ...]
        services: 识别的服务列表 [{"name": "nginx", "version": "1.24.0"}, ...]
        os_info: 操作系统探测结果
        findings: 漏洞发现列表
        raw_output: 原始工具输出（调试用）
        error: 错误信息（status=failed 时填充）
        duration_seconds: 扫描耗时
    """

    status: ScanStatus
    target: str
    ports: list[dict] = field(default_factory=list)
    services: list[dict] = field(default_factory=list)
    os_info: str | None = None
    findings: list["VulnFinding"] = field(default_factory=list)
    raw_output: str | None = None
    error: str | None = None
    duration_seconds: float = 0.0

    def to_dict(self) -> dict:
        """导出为字典，方便报告模块消费"""
        return {
            "status": self.status.value,
            "target": self.target,
            "adapter_name": "merged",  # 合并结果用 "merged"，单个适配器结果用 adapter.name
            "ports": self.ports,
            "services": self.services,
            "os_info": self.os_info,
            "findings": [f.to_dict() for f in self.findings],
            "error": self.error,
            "duration_seconds": self.duration_seconds,
        }


@dataclass
class VulnFinding:
    """漏洞发现数据结构——所有检测器输出此格式

    Attributes:
        vuln_type: 漏洞类型（sqli / xss_reflected / weak_password / 等）
        severity: 风险等级
        title: 漏洞标题（中文）
        description: 详细描述（中文）
        evidence: 证实漏洞存在的证据
        remediation: 修复建议（中文）
        url: 受影响的 URL
        parameter: 受影响的参数名
        port: 受影响的端口
        cve_id: 关联 CVE 编号（如有）
        cvss_score: CVSS 评分（如有）
    """

    vuln_type: str
    severity: RiskLevel
    title: str
    description: str
    remediation: str
    url: str | None = None
    parameter: str | None = None
    port: int | None = None
    cve_id: str | None = None
    cvss_score: float | None = None
    evidence: str | None = None

    def to_dict(self) -> dict:
        """导出为字典"""
        return {
            "vuln_type": self.vuln_type,
            "severity": self.severity.value,
            "title": self.title,
            "description": self.description,
            "evidence": self.evidence,
            "remediation": self.remediation,
            "url": self.url,
            "parameter": self.parameter,
            "port": self.port,
            "cve_id": self.cve_id,
            "cvss_score": self.cvss_score,
        }


# =============================================================================
# 抽象基类
# =============================================================================


class BaseAdapter(ABC):
    """所有扫描适配器的抽象基类

    新增扫描能力只需：
    1. 继承 BaseAdapter
    2. 实现 validate_target / scan / capabilities 三个抽象方法
    3. 在 LightShieldCore 中注册

    核心调度器只依赖此抽象接口，不直接依赖具体工具。
    """

    def __init__(self, name: str = ""):
        """初始化适配器。

        Args:
        name: 适配器名称（用于日志和审计）
        """
        self.name = name or self.__class__.__name__
        self._last_result: ScanResult | None = None

    @abstractmethod
    def validate_target(self, target: str) -> bool:
        """目标合法性校验

        所有对外操作的前置关口。默认委托给 TargetValidator.validate()，
        子类可添加额外的工具特定校验。

        Args:
            target: IP 或域名

        Returns:
            True 表示合法目标
        """
        ...

    @abstractmethod
    def scan(self, target: str, **kwargs) -> ScanResult:
        """执行扫描，返回结构化结果

        实现要点：
        1. 调用 validate_target() 前置校验
        2. 构造并执行扫描命令
        3. 解析输出为 ScanResult
        4. 记录审计日志
        5. 异常安全——失败时返回 ScanResult(status=FAILED, error=...)

        Args:
            target: 扫描目标（IP/域名）
            **kwargs: 工具特定参数

        Returns:
            ScanResult 结构化结果
        """
        ...

    @abstractmethod
    def capabilities(self) -> list[str]:
        """返回该适配器支持的能力列表

        Returns:
            能力标识列表，如 ["port_scan", "service_detect", "os_detect"]
        """
        ...

    # ---- 公共方法 ----

    def get_last_result(self) -> ScanResult | None:
        """获取最近一次扫描结果"""
        return self._last_result

    def _log_scan_start(self, target: str, scan_type: str) -> str:
        """记录扫描开始——由子类在 scan() 开头调用

        生成唯一 scan_id，写入审计日志。

        Returns:
            scan_id 用于关联本次扫描的审计日志
        """
        import time
        import uuid

        from lightshield.utils.logger import get_logger

        scan_id = f"LS-{time.strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:6]}"
        logger = get_logger()
        logger.audit_scan_start(target, f"{self.name}:{scan_type}")
        return scan_id

    def _log_scan_end(self, scan_id: str, result: ScanResult) -> None:
        """记录扫描结束——由子类在 scan() 结尾调用

        写入审计日志，保存最近结果。

        Args:
            scan_id: _log_scan_start 返回的扫描 ID
            result: 扫描结果
        """
        from lightshield.utils.logger import get_logger

        self._last_result = result
        logger = get_logger()
        summary = f"status={result.status.value}, ports={len(result.ports)}, findings={len(result.findings)}"
        if result.error:
            summary += f", error={result.error[:100]}"
        logger.audit_scan_end(scan_id, summary)

    def cancel(self) -> None:  # noqa: B027
        """取消当前扫描（子类可重写以支持中断）

        默认实现为空操作。支持长扫描取消的适配器应重写此方法，
        设置内部标志位并在 scan() 中定期检查。
        调用后 get_last_result() 应返回 status=CANCELLED。
        """
        return  # 有意留空——子类按需重写，非抽象方法
