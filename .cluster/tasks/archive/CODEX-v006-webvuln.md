你是 LightShield 项目的高级开发工程师，使用 GPT-5.5 模型。

## 项目背景
LightShield（轻盾）是开源轻量化安全自检 + 防御加固工具，Python 3.10+。
当前版本 v0.0.06。Phase 1 骨架已完成，所有依赖已就绪。

已有文件（你可以直接 import 使用）：
  lightshield/adapters/base.py      → from lightshield.adapters.base import BaseAdapter, ScanResult, VulnFinding
  lightshield/utils/constants.py    → from lightshield.utils.constants import RiskLevel, ScanStatus, ScanType
  lightshield/utils/validator.py    → from lightshield.utils.validator import TargetValidator
  lightshield/utils/logger.py       → from lightshield.utils.logger import get_logger

## 任务：实现 lightshield/scanners/web_vuln_scanner.py

### 核心需求
实现 WebVulnScanner 类，继承 BaseAdapter，自研实现：
1. SQL 注入检测（仅检测，不利用）
2. XSS 检测（反射型 + 存储型）
3. 敏感目录/文件枚举

### ⚠️ 关键边界（合规红线）
- 这是**检测**模块，不是**利用**模块
- SQL 注入：发送测试 payload → 观察响应差异 → 判断是否存在漏洞 → **不提取数据**
- XSS：发送测试 payload → 检查响应中是否未转义 → **不执行脚本**
- 目录枚举：基于内置字典 → **不做暴力破解**

### 接口契约

```python
class WebVulnScanner(BaseAdapter):
    """Web 漏洞检测扫描器 — 自研脚本引擎"""

    # === BaseAdapter 必须实现 ===
    def validate_target(self, target: str) -> bool:
        """委托给 TargetValidator"""

    def scan(self, target: str, **kwargs) -> ScanResult:
        """主扫描入口：依次执行 SQL注入→XSS→目录枚举，汇总为 ScanResult"""

    def capabilities(self) -> list[str]:
        """返回 ["web_vuln", "directory_enum"]"""

    # === SQL 注入检测 ===
    def detect_sqli(self, url: str, params: dict = None) -> list[VulnFinding]:
        """
        基于 OWASP Top 10 的 SQL 注入检测。
        注入测试 payload → 分析响应 → 返回发现列表。
        不做任何数据提取或写操作。
        """

    # === XSS 检测 ===
    def detect_xss(self, url: str, params: dict = None) -> list[VulnFinding]:
        """
        XSS 检测（反射型 + 存储型）。
        发送测试 payload → 检查响应中是否未转义。
        不在浏览器中渲染任何 payload。
        """

    # === 敏感目录枚举 ===
    def enumerate_directories(self, base_url: str) -> list[VulnFinding]:
        """
        基于内置字典猜解常见敏感路径。
        字典 ≤200 条。无递归遍历。无暴力破解。
        """
```

### SQL 注入测试 Payload（仅检测用）
```python
SQLI_TEST_PAYLOADS = [
    ("'", "单引号闭合"),
    ('"', "双引号闭合"),
    ("' OR '1'='1", "OR 永真（仅检测响应差异）"),
    ("' AND '1'='2", "AND 永假"),
    ("'; WAITFOR DELAY '0:0:3'--", "时间盲注（3秒）"),
]
```

### XSS 测试 Payload
```python
XSS_TEST_PAYLOADS = [
    ("<script>alert(1)</script>", "基础 script"),
    ('"><script>alert(1)</script>', "属性闭合"),
    ("<img src=x onerror=alert(1)>", "img onerror"),
]
```

### 敏感目录字典
```python
SENSITIVE_DIRS = [
    "/admin", "/login", "/wp-admin", "/phpmyadmin",
    "/.git", "/.env", "/backup", "/config",
    "/api", "/debug", "/test", "/upload",
    "/robots.txt", "/sitemap.xml", "/readme.html",
    "/server-status", "/.htaccess", "/console",
    "/swagger", "/graphql", "/actuator",
]
```

### 代码规范
- 继承 BaseAdapter，实现三个抽象方法
- Python 3.10+，中文注释
- 依赖：requests, beautifulsoup4（已在 requirements.txt）
- HTTP 超时 10s，请求间隔 ≥1s
- 使用 get_logger() 记录检测过程
- VulnFinding 字段完整填充（特别是 evidence 和 remediation）

### 输出
只输出一个文件：lightshield/scanners/web_vuln_scanner.py
内置 if __name__ == "__main__": 自检块
