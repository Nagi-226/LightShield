"""
LightShield 轻盾 — 全局常量与枚举定义

包含：
  - 风险等级、扫描状态、扫描类型等枚举
  - MSF 模块白名单/黑名单过滤器
  - 高危端口清单
  - 合规约束常量
  - 弱口令模式库（演示/检测用）

⚠ 合规约束：
  - 不得包含任何攻击向关键词
  - MSF 白名单不得包含 exploit/payload/post/evasion/nops 路径
"""

from enum import Enum


# ============================================================
# 枚举定义
# ============================================================

class RiskLevel(Enum):
    """风险等级"""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class ScanStatus(Enum):
    """扫描状态"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    PARTIAL = "partial"      # 部分完成（某些适配器失败）
    FAILED = "failed"
    CANCELLED = "cancelled"   # 用户取消（v0.0.04 S1 修复）


class ScanType(Enum):
    """扫描类型"""
    PORT_SCAN = "port_scan"
    SERVICE_DETECT = "service_detect"
    WEB_VULN = "web_vuln"
    WEAK_PASSWORD = "weak_password"
    COMPONENT_CHECK = "component_check"


class AdapterType(Enum):
    """扫描适配器类型"""
    NMAP = "nmap"
    SELF_SCRIPT = "self_script"
    MSF_SCANNER = "msf_scanner"


class OSPlatform(Enum):
    """操作系统平台"""
    LINUX = "linux"
    WINDOWS = "windows"
    UNKNOWN = "unknown"


class OutputFormat(Enum):
    """报告输出格式"""
    MARKDOWN = "markdown"
    TEXT = "text"


# ============================================================
# MSF 模块白名单（R5 防线）
# ============================================================

ALLOWED_MSF_PREFIXES: list[str] = [
    "auxiliary/scanner/portscan/",
    "auxiliary/scanner/discovery/",
    "auxiliary/scanner/http/",
    "auxiliary/scanner/smb/",
    "auxiliary/scanner/ssh/",
    "auxiliary/scanner/mysql/",
    "auxiliary/scanner/ftp/",
    "auxiliary/scanner/ssl/",
    "auxiliary/scanner/dns/",
]

BLOCKED_MSF_PREFIXES: list[str] = [
    "exploit/",
    "payload/",
    "post/",
    "evasion/",
    "nops/",
    "auxiliary/scanner/backdoor/",
    "auxiliary/dos/",
    "auxiliary/admin/",
]


# ============================================================
# 高危端口清单
# ============================================================

HIGH_RISK_PORTS: dict[int, str] = {
    21: "FTP（明文传输）",
    22: "SSH（如使用弱口令则高危）",
    23: "Telnet（明文传输，极度危险）",
    25: "SMTP（邮件服务）",
    135: "RPC（Windows 远程调用）",
    139: "NetBIOS（文件共享）",
    445: "SMB（永恒之蓝漏洞）",
    1433: "MSSQL（数据库）",
    3306: "MySQL（数据库）",
    3389: "RDP（远程桌面）",
    5432: "PostgreSQL（数据库）",
    6379: "Redis（如无密码则高危）",
    8080: "HTTP 代理/管理面板",
    27017: "MongoDB（数据库）",
}


# ============================================================
# 合规约束常量
# ============================================================

MAX_CONCURRENT_SCANS: int = 20            # R6：扫描并发上限
MIN_SCAN_INTERVAL: float = 5.0           # R6：扫描间隔（秒）
MAX_TARGETS_PER_SESSION: int = 1         # R2：每次仅允许一个目标
DEFAULT_SCAN_TIMEOUT: int = 30           # 默认超时（秒）


# ============================================================
# 弱口令模式库（检测用）
# ============================================================

WEAK_PASSWORD_PATTERNS: list[str] = [
    "admin", "password", "123456", "root", "test",
    "guest", "qwerty", "letmein", "monkey", "dragon",
    "master", "passwd", "mysql", "oracle", "sa",
    "1234", "12345", "12345678", "123456789",
    "abc123", "admin123", "password123",
]


# =============================================================================
# 自检
# =============================================================================

if __name__ == "__main__":
    print("=== constants self-check ===")

    # 枚举值存在性
    assert RiskLevel.CRITICAL.value == "critical"
    assert ScanStatus.COMPLETED.value == "completed"
    assert ScanStatus.PARTIAL.value == "partial"
    assert ScanStatus.CANCELLED.value == "cancelled"
    print("OK enums")

    # MSF 白名单/黑名单不重叠
    for blocked in BLOCKED_MSF_PREFIXES:
        for allowed in ALLOWED_MSF_PREFIXES:
            assert not blocked.startswith(allowed), f"Conflict: {blocked} vs {allowed}"
            assert not allowed.startswith(blocked), f"Conflict: {allowed} vs {blocked}"
    print("OK MSF whitelist/blacklist no overlap")

    # 高危端口字典非空
    assert len(HIGH_RISK_PORTS) > 0
    print(f"OK high-risk ports: {len(HIGH_RISK_PORTS)} entries")

    # 弱口令模式非空
    assert len(WEAK_PASSWORD_PATTERNS) > 0
    print(f"OK weak password patterns: {len(WEAK_PASSWORD_PATTERNS)} entries")

    # 合规常量
    assert MAX_CONCURRENT_SCANS == 20
    assert MIN_SCAN_INTERVAL == 5.0
    assert MAX_TARGETS_PER_SESSION == 1
    print("OK compliance constants")

    print("=== constants: ALL PASSED ===")
