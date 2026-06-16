"""LightShield 轻盾 — 全局常量与枚举定义

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
    PARTIAL = "partial"  # 部分完成（某些适配器失败）
    FAILED = "failed"
    CANCELLED = "cancelled"  # 用户取消（v0.0.04 S1 修复）


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
# Nuclei 模板标签白名单/黑名单（R1 + R5 防线）
# ============================================================

# 安全检测标签——仅允许信息收集/配置检测/暴露发现类模板
NUCLEI_ALLOWED_TAGS: list[str] = [
    "detection",  # 版本/服务检测
    "discovery",  # 服务发现
    "tech",  # 技术栈识别
    "config",  # 配置检测
    "exposure",  # 暴露面检测
    "enum",  # 枚举
    "misconfig",  # 错误配置检测
    "token-spray",  # Token 喷洒（仅检测，不爆破）
]

# 禁止的攻击标签——任何包含这些标签的模板一律拒绝
NUCLEI_BLOCKED_TAGS: list[str] = [
    "exploit",  # 漏洞利用
    "intrusive",  # 侵入式
    "attack",  # 攻击
    "dos",  # 拒绝服务
    "fuzz",  # 模糊测试
    "bruteforce",  # 暴力破解
    "sqli",  # SQL 注入（主动注入）
    "xss",  # 跨站脚本（主动注入）
    "rce",  # 远程代码执行
    "lfi",  # 本地文件包含
    "ssrf",  # 服务端请求伪造
    "injection",  # 注入类
    "file-upload",  # 文件上传
    "code-injection",  # 代码注入
    "command-injection",  # 命令注入
    "deserialization",  # 反序列化
]

# Nuclei 默认扫描超时（秒）
NUCLEI_DEFAULT_TIMEOUT: int = 120


# ============================================================
# 沙箱执行器（v0.0.38 — R1 + R4 防线）
# ============================================================
# 沙箱用于在隔离的 Docker 容器中安全执行加固脚本，绝不在宿主机直接运行。
# 默认配置以"最大隔离"为原则：无网络、资源受限、容器即用即销毁。

SANDBOX_DEFAULT_IMAGE: str = "ubuntu:22.04"  # 需含 bash（加固脚本依赖 bash 语法）
SANDBOX_DEFAULT_TIMEOUT: int = 120  # 沙箱执行超时（秒）
SANDBOX_DEFAULT_MEMORY: str = "256m"  # 容器内存上限（防内存炸弹）
SANDBOX_DEFAULT_CPUS: str = "1.0"  # 容器 CPU 上限
SANDBOX_DEFAULT_PIDS_LIMIT: int = 256  # 容器进程数上限（防 fork 炸弹）
SANDBOX_DEFAULT_NETWORK: str = "none"  # R1 防线：沙箱内无网络，脚本无法对外发起连接/攻击
SANDBOX_MAX_SCRIPT_BYTES: int = 1024 * 1024  # 待执行脚本体积上限 1MB（防异常输入）
SANDBOX_CONTAINER_SCRIPT_PATH: str = "/sandbox/script.sh"  # 容器内脚本只读挂载路径


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

MAX_CONCURRENT_SCANS: int = 20  # R6：扫描并发上限
MIN_SCAN_INTERVAL: float = 5.0  # R6：扫描间隔（秒）
MAX_TARGETS_PER_SESSION: int = 1  # R2：每次仅允许一个目标
DEFAULT_SCAN_TIMEOUT: int = 30  # 默认超时（秒）


# ============================================================
# 弱口令模式库（检测用）
# ============================================================

WEAK_PASSWORD_PATTERNS: list[str] = [
    "admin",
    "password",
    "123456",
    "root",
    "test",
    "guest",
    "qwerty",
    "letmein",
    "monkey",
    "dragon",
    "master",
    "passwd",
    "mysql",
    "oracle",
    "sa",
    "1234",
    "12345",
    "12345678",
    "123456789",
    "abc123",
    "admin123",
    "password123",
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

    # Nuclei 标签白名单/黑名单不重叠
    for blocked in NUCLEI_BLOCKED_TAGS:
        assert blocked not in NUCLEI_ALLOWED_TAGS, f"Nuclei tag conflict: {blocked} in both lists"
    print(f"OK Nuclei tags: {len(NUCLEI_ALLOWED_TAGS)} allowed + {len(NUCLEI_BLOCKED_TAGS)} blocked")

    # Nuclei 超时常量
    assert NUCLEI_DEFAULT_TIMEOUT == 120
    print("OK Nuclei timeout constant")

    # 沙箱执行器常量（v0.0.38）
    assert SANDBOX_DEFAULT_NETWORK == "none", "R1 防线：沙箱默认必须无网络"
    assert SANDBOX_MAX_SCRIPT_BYTES > 0
    assert SANDBOX_CONTAINER_SCRIPT_PATH.startswith("/")
    assert SANDBOX_DEFAULT_PIDS_LIMIT > 0
    print(
        f"OK Sandbox constants: image={SANDBOX_DEFAULT_IMAGE} "
        f"network={SANDBOX_DEFAULT_NETWORK} timeout={SANDBOX_DEFAULT_TIMEOUT}s"
    )

    print("=== constants: ALL PASSED ===")
