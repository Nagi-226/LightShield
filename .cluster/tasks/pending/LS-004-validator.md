# LS-004: validator.py — 输入校验模块

## 任务信息
- **Task ID**: LS-004
- **Phase**: Phase 1 — 项目骨架
- **分配给**: Codex（GPT-5.5 — 集群最强模型，安全关键模块值得）
- **模型层级**: 💎 GPT-5.5（唯一使用场景，成本可控）
- **优先级**: P0（关键安全模块）
- **依赖**: LS-001 (base.py), LS-006 (constants.py)
- **输出文件**: `lightshield/utils/validator.py`

## 项目上下文

LightShield（轻盾）是一个面向初创企业 & 个人站长的开源轻量化安全自检 + 防御加固工具。
此模块是合规防线的核心——所有对外操作必须经过此校验。

## ⚠️ 合规约束（不可违反）

1. 代码中不得包含对外攻击、漏洞利用、Payload 生成逻辑
2. **R2 红线**：只接受单一 IP 或域名，拒绝 CIDR/网段/通配符
3. **R4 红线**：仅允许自查自有资产
4. 不得包含 `bind_shell`、`reverse_shell`、`backdoor`、`trojan` 等关键字

## 接口契约

`validator.py` 需要实现 `TargetValidator` 类，负责目标合法性校验。

### 需要实现的功能

```python
class TargetValidator:
    """目标输入校验器 —— 合规 R2/R4 的核心防线"""

    # --- IP 校验 ---
    @staticmethod
    def is_valid_ip(target: str) -> bool:
        """验证是否为合法单 IPv4/IPv6 地址（拒绝 CIDR/网段）"""

    @staticmethod
    def is_private_ip(target: str) -> bool:
        """验证是否为内网 IP（10.x, 172.16-31.x, 192.168.x, 127.x）"""

    @staticmethod
    def is_cidr(target: str) -> bool:
        """检测是否为 CIDR 网段格式（需要拦截的格式）"""

    # --- 域名校验 ---
    @staticmethod
    def is_valid_domain(target: str) -> bool:
        """验证是否为合法域名（拒绝通配符 *.example.com）"""

    @staticmethod
    def is_wildcard_domain(target: str) -> bool:
        """检测通配符域名"""

    # --- 综合校验 ---
    @staticmethod
    def validate(target: str) -> tuple[bool, str]:
        """
        综合校验入口——所有对外操作的前置关口
        
        Returns:
            (是否合法, 原因说明)
        
        校验规则：
        1. 拒绝空字符串
        2. 拒绝 CIDR 网段 (192.168.1.0/24)
        3. 拒绝 IP 范围 (192.168.1.1-192.168.1.10)
        4. 拒绝通配符域名 (*.example.com)
        5. 拒绝 URL 格式 (http://xxx)
        6. 仅接受：单 IPv4、单 IPv6、单域名、localhost
        
        合法示例: "192.168.1.1", "example.com", "localhost", "::1"
        非法示例: "192.168.1.0/24", "*.example.com", "http://example.com"
        """

    @staticmethod
    def confirm_ownership(target: str) -> str:
        """生成所有权确认提示信息（合规 R4）"""

    # --- 扫描参数限制 ---
    @staticmethod
    def validate_scan_params(concurrency: int, interval: float) -> tuple[bool, str]:
        """
        校验扫描参数是否符合合规 R6 限制
        - 并发数 ≤ 20
        - 间隔 ≥ 5 秒
        """
```

### 需要覆盖的测试场景（后续 Phase 单独生成测试文件）

- 合法 IPv4: "192.168.1.1" → True
- 合法 IPv6: "::1", "fe80::1" → True
- 合法域名: "example.com", "my.server.cn" → True
- 非法 CIDR: "192.168.1.0/24" → False
- 非法网段: "192.168.1.0/255.255.255.0" → False
- 非法通配符: "*.example.com" → False
- 非法 IP 范围: "192.168.1.1-192.168.1.10" → False
- 非法 URL: "http://example.com" → False
- 空字符串: "" → False

### 代码要求

- Python 3.10+，完整中文注释
- 使用正则表达式做模式匹配
- 异常安全：任何输入不应抛出未捕获异常
- 零外部依赖（仅使用 Python 标准库）
- 对 IPv6 的支持要完整（包括缩写形式）
