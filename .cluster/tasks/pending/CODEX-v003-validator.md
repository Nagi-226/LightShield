你是 LightShield 项目的高级开发工程师，使用 GPT-5.5 模型。

## 项目背景
LightShield（轻盾）是一个开源轻量化安全自检 + 防御加固工具，主语言 Python 3.10+。
当前版本 v0.0.03，需要实现输入校验模块。
前置依赖：v0.0.02 已完成（constants.py 已定义合规常量 MAX_CONCURRENT_SCANS=20, MIN_SCAN_INTERVAL=5.0）。

## 任务：实现 lightshield/utils/validator.py

### 核心需求
实现 TargetValidator 类，这是合规红线 R2（禁止批量扫描公网 IP 段）和 R4（仅自查自有资产）的核心防线。

### 接口契约

```python
class TargetValidator:
    """目标输入校验器 —— 合规 R2/R4 的核心防线"""

    @staticmethod
    def is_valid_ip(target: str) -> bool:
        """验证是否为合法单 IPv4/IPv6 地址（拒绝 CIDR/网段）"""

    @staticmethod
    def is_private_ip(target: str) -> bool:
        """验证是否为内网 IP（10.x, 172.16-31.x, 192.168.x, 127.x）"""

    @staticmethod
    def is_cidr(target: str) -> bool:
        """检测是否为 CIDR 网段格式（需要拦截的格式）"""

    @staticmethod
    def is_valid_domain(target: str) -> bool:
        """验证是否为合法域名（拒绝通配符 *.example.com）"""

    @staticmethod
    def is_wildcard_domain(target: str) -> bool:
        """检测通配符域名"""

    @staticmethod
    def validate(target: str) -> tuple[bool, str]:
        """
        综合校验入口——所有对外操作的前置关口
        
        校验规则：
        1. 拒绝空字符串
        2. 拒绝 CIDR 网段 (192.168.1.0/24)
        3. 拒绝 IP 范围 (192.168.1.1-192.168.1.10)
        4. 拒绝通配符域名 (*.example.com)
        5. 拒绝 URL 格式 (http://xxx)
        6. 仅接受：单 IPv4、单 IPv6、单域名、localhost
        
        合法: "192.168.1.1", "example.com", "localhost", "::1"
        非法: "192.168.1.0/24", "*.example.com", "http://example.com"
        """

    @staticmethod
    def confirm_ownership(target: str) -> str:
        """生成所有权确认提示信息（合规 R4）"""

    @staticmethod
    def validate_scan_params(concurrency: int, interval: float) -> tuple[bool, str]:
        """校验扫描参数（合规 R6：并发 ≤20，间隔 ≥5s）"""
```

### 测试场景（实现代码中内置 __main__ 自检块）
- "192.168.1.1" → (True, "合法单 IPv4")
- "192.168.1.0/24" → (False, "拒绝 CIDR 网段")
- "::1" → (True, "合法单 IPv6")
- "*.example.com" → (False, "拒绝通配符域名")
- "http://example.com" → (False, "拒绝 URL")
- "" → (False, "拒绝空地址")

### ⚠️ 合规约束
1. 你的代码是防御代码，不得包含任何攻击向逻辑
2. 正则表达式必须精确——宁可误拒，不可漏过
3. IPv6 支持完整格式（包括 :: 缩写、fe80:: 等）

### 代码规范
- Python 3.10+，中文注释
- 零外部依赖（仅 re, ipaddress 标准库）
- type hints + docstring
- 异常安全：任何输入不应抛出未捕获异常

### 输出
只输出一个文件：lightshield/utils/validator.py
