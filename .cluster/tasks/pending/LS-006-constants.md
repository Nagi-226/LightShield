# LS-006: constants.py — 常量与枚举定义

## 任务信息
- **Task ID**: LS-006
- **Phase**: Phase 1 — 项目骨架
- **分配给**: Hermes（DeepSeek-V4-flash，纯数据定义零推理，Flash 足够）
- **模型层级**: ⚡ Flash
- **优先级**: P0
- **依赖**: 无
- **输出文件**: `lightshield/utils/constants.py`

## 项目上下文

LightShield（轻盾）是一个面向初创企业 & 个人站长的开源轻量化安全自检 + 防御加固工具。
常量模块定义整个项目共享的枚举、常量、配置映射等。

## ⚠️ 合规约束（不可违反）

1. 不得包含对外攻击、漏洞利用相关常量定义
2. MSF 黑名单路径必须完整且不可被绕过（合规 R5）
3. 不得包含 `bind_shell`、`reverse_shell`、`backdoor`、`trojan` 等关键字

## 接口契约

### 枚举类型

```python
from enum import Enum, auto

class RiskLevel(Enum):
    """风险等级"""
    CRITICAL = "critical"   # 严重：RCE、SQL注入
    HIGH = "high"           # 高危：弱口令、高危端口
    MEDIUM = "medium"       # 中危：信息泄露、配置问题
    LOW = "low"             # 低危：最佳实践偏离
    INFO = "info"           # 提示

class ScanStatus(Enum):
    """扫描状态"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

class ScanType(Enum):
    """扫描类型"""
    PORT_SCAN = "port_scan"           # 端口扫描
    SERVICE_DETECT = "service_detect"  # 服务识别
    WEB_VULN = "web_vuln"             # Web 漏洞检测
    WEAK_PASSWORD = "weak_password"   # 弱口令检测
    COMPONENT_CHECK = "component_check"  # 组件版本检查

class AdapterType(Enum):
    """适配器类型"""
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
```

### 常量定义

```python
# === MSF 白名单（合规 R5）===
# 仅允许这些路径前缀的模块被调用
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

# === MSF 黑名单（合规 R5）===
# 即使误触也会拦截
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

# === 高危端口清单 ===
HIGH_RISK_PORTS: dict[int, str] = {
    21: "FTP（明文传输）",
    22: "SSH（如使用弱口令则高危）",
    23: "Telnet（明文传输，极度危险）",
    25: "SMTP（邮件服务）",
    53: "DNS（区域传输风险）",
    110: "POP3（明文邮件）",
    135: "RPC（Windows 远程调用）",
    139: "NetBIOS（文件共享）",
    445: "SMB（永恒之蓝漏洞）",
    1433: "MSSQL（数据库）",
    1521: "Oracle（数据库）",
    3306: "MySQL（数据库）",
    3389: "RDP（远程桌面）",
    5432: "PostgreSQL（数据库）",
    6379: "Redis（如无密码则高危）",
    8080: "HTTP 代理/管理面板",
    8443: "HTTPS 管理面板",
    27017: "MongoDB（数据库）",
}

# === 弱口令匹配模式 ===
WEAK_PASSWORD_PATTERNS: list[str] = [
    "admin", "password", "123456", "root", "test",
    "guest", "qwerty", "letmein", "monkey", "dragon",
    "master", "passwd", "mysql", "oracle", "sa",
]

# === 合规约束 ===
MAX_CONCURRENT_SCANS: int = 20     # R6: 并发上限
MIN_SCAN_INTERVAL: float = 5.0     # R6: 扫描间隔（秒）
MAX_TARGETS_PER_SESSION: int = 1   # R2: 每次扫描仅允许一个目标
```

### 代码要求

- Python 3.10+，完整中文注释
- 使用 Enum 或 StrEnum（Python 3.11+ 兼容）
- 常量使用大写命名
- 字典类型常量带完整类型标注 `dict[int, str]`
