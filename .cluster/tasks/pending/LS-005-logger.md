# LS-005: logger.py — 日志系统模块

## 任务信息
- **Task ID**: LS-005
- **Phase**: Phase 1 — 项目骨架
- **分配给**: Reasonix
- **优先级**: P0
- **依赖**: LS-003 (config.py 接口)
- **输出文件**: `lightshield/utils/logger.py`

## 项目上下文

LightShield（轻盾）是一个面向初创企业 & 个人站长的开源轻量化安全自检 + 防御加固工具。
日志模块用于记录所有扫描行为、操作审计、错误追踪。
项目是中文为主的工具（中文注释、中文报告、中文日志）。

## ⚠️ 合规约束（不可违反）

1. 不得记录敏感信息（密码、Token、私钥）到日志
2. 日志中必须记录每次扫描的目标地址和执行时间（合规 R4）
3. 不得包含 `bind_shell`、`reverse_shell`、`backdoor`、`trojan` 等关键字

## 接口契约

`logger.py` 需要实现一个结构化日志系统。

### 需要实现的功能

```python
class LightShieldLogger:
    """LightShield 结构化日志系统"""

    def __init__(self, log_dir: str = "./logs", level: str = "INFO"):
        """
        初始化日志系统。
        - 同时输出到控制台和文件
        - 文件按日期轮转（每天一个文件）
        - 格式：[时间] [级别] [模块] 消息
        """

    def info(self, module: str, message: str, **extra) -> None: ...
    def warning(self, module: str, message: str, **extra) -> None: ...
    def error(self, module: str, message: str, exception: Exception = None, **extra) -> None: ...
    def debug(self, module: str, message: str, **extra) -> None: ...

    # --- 审计专用方法 ---
    def audit_scan_start(self, target: str, scan_type: str) -> str:
        """记录扫描开始——生成 scan_id，记录目标地址"""

    def audit_scan_end(self, scan_id: str, result_summary: str) -> None:
        """记录扫描结束"""

    def audit_harden_action(self, target: str, action: str, result: str) -> None:
        """记录加固操作（合规要求：每一条加固操作留痕）"""

    # --- 工具方法 ---
    def get_recent_logs(self, count: int = 50) -> list[str]:
        """获取最近的日志行"""

    def get_log_dir(self) -> str:
        """返回日志目录路径"""
```

### 日志格式

```
2026-06-09 20:15:32 [INFO] [core] 开始扫描目标: 192.168.1.1
2026-06-09 20:15:35 [WARNING] [nmap_adapter] 端口 3389 开放 — 高危端口
2026-06-09 20:15:40 [ERROR] [msf_adapter] MSF 连接失败: Connection refused
2026-06-09 20:16:00 [AUDIT] [core] scan_id=LS-20260609-001, target=192.168.1.1, result=完成
```

### 安全要求

1. **敏感信息过滤**：在 `_sanitize()` 方法中过滤 password、token、secret、key、api_key 等敏感字段（替换为 `***REDACTED***`）
2. **日志文件权限**：设置日志文件为仅所有者可读写
3. **日志轮转**：单个日志文件最大 10MB，超过自动分割

### 代码要求

- Python 3.10+，完整中文注释
- 基于标准库 `logging` 模块封装
- 异常安全：日志模块自身出错不应影响主程序
- 线程安全（可能被多个扫描任务并发调用）
