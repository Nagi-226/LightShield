你是 LightShield 项目的工具链 + 基础设施专家，使用 DeepSeek-V4-flash 模型。

## 项目背景
LightShield（轻盾）是开源轻量化安全自检 + 防御加固工具，Python 3.10+。
你要同时完成 v0.0.01（项目骨架）和 v0.0.02（常量定义）。

## 任务A：v0.0.01 — 项目骨架

### A-1：创建目录结构
在项目根目录下创建：
lightshield/
lightshield/adapters/
lightshield/scanners/
lightshield/rules/
lightshield/harden/templates/
lightshield/report/
lightshield/utils/
tests/
docs/
scripts/

### A-2：requirements.txt（中文注释）
```
# === LightShield 轻盾 — Python 依赖 ===
# 目标部署包 ≤500MB

# 核心依赖
python-nmap>=0.7.0,<1.0        # Nmap Python 封装
PyYAML>=6.0                     # YAML 配置文件解析

# Web 扫描（自研脚本，最小依赖）
requests>=2.28.0,<3.0           # HTTP 请求库
beautifulsoup4>=4.11.0,<5.0    # HTML 解析

# 报告生成
markdown>=3.4.0                 # Markdown 报告渲染
```

### A-3：.gitignore（中文注释每个规则）
```
# Python 缓存
__pycache__/
*.pyc
*.pyo

# 虚拟环境
.venv/
venv/
env/

# 运行时生成
logs/
reports/
*.log

# IDE
.vscode/
.idea/
*.swp

# 操作系统
.DS_Store
Thumbs.db

# 敏感文件
*.key
*.pem
*.p12
*.pfx

# 本地配置
lightshield.local.yaml

# 测试
.pytest_cache/
.coverage

# MSF 相关
msf_cache/
.msf4/
```

### A-4：__init__.py 文件（每个包含中文 docstring + __all__）
lightshield/__init__.py：
```python
"""
LightShield 轻盾 — 轻量化安全自检 + 防御加固工具
"""
__version__ = "0.0.2"
__author__ = "LightShield Team"
__license__ = "MIT"
__all__ = ["core", "config"]
```

其余 6 个 __init__.py（adapters/scanners/rules/harden/report/utils）：
- 中文 docstring 说明该子包的用途
- __all__ 留空列表（后续模块加入时更新）

## 任务B：v0.0.02 — constants.py

创建 lightshield/utils/constants.py，包含以下内容。

### 枚举
```python
from enum import Enum

class RiskLevel(Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"

class ScanStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"

class ScanType(Enum):
    PORT_SCAN = "port_scan"
    SERVICE_DETECT = "service_detect"
    WEB_VULN = "web_vuln"
    WEAK_PASSWORD = "weak_password"
    COMPONENT_CHECK = "component_check"

class AdapterType(Enum):
    NMAP = "nmap"
    SELF_SCRIPT = "self_script"
    MSF_SCANNER = "msf_scanner"

class OSPlatform(Enum):
    LINUX = "linux"
    WINDOWS = "windows"
    UNKNOWN = "unknown"

class OutputFormat(Enum):
    MARKDOWN = "markdown"
    TEXT = "text"
```

### MSF 白名单（R5 防线）
```python
ALLOWED_MSF_PREFIXES = [
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

BLOCKED_MSF_PREFIXES = [
    "exploit/",
    "payload/",
    "post/",
    "evasion/",
    "nops/",
    "auxiliary/scanner/backdoor/",
    "auxiliary/dos/",
    "auxiliary/admin/",
]
```

### 高危端口清单
```python
HIGH_RISK_PORTS = {
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
```

### 合规常量
```python
MAX_CONCURRENT_SCANS = 20     # R6：扫描并发上限
MIN_SCAN_INTERVAL = 5.0       # R6：扫描间隔（秒）
MAX_TARGETS_PER_SESSION = 1   # R2：每次仅允许一个目标
DEFAULT_SCAN_TIMEOUT = 30     # 默认超时（秒）
```

### 弱口令模式
```python
WEAK_PASSWORD_PATTERNS = [
    "admin", "password", "123456", "root", "test",
    "guest", "qwerty", "letmein", "monkey", "dragon",
    "master", "passwd", "mysql", "oracle", "sa",
    "1234", "12345", "12345678", "123456789",
    "abc123", "admin123", "password123",
]
```

## ⚠️ 合规约束
- 常量定义中不得出现任何攻击向关键词
- MSF 白名单不得包含 exploit/payload/post/evasion/nops 路径

## 代码规范
- Python 3.10+，中文注释
- 所有枚举值使用小写（Value 属性）
- 字典类型标注完整 `dict[int, str]`

## 输出文件
1. requirements.txt
2. .gitignore
3. lightshield/__init__.py
4. lightshield/adapters/__init__.py
5. lightshield/scanners/__init__.py
6. lightshield/rules/__init__.py
7. lightshield/harden/__init__.py
8. lightshield/report/__init__.py
9. lightshield/utils/__init__.py
10. lightshield/utils/constants.py
11. tests/.gitkeep, docs/.gitkeep, scripts/.gitkeep
