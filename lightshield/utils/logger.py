"""LightShield 结构化日志系统

支持：
  - 控制台 + 文件双输出
  - 按日期自动轮转
  - 审计专用方法（扫描/加固操作记录）
  - 敏感信息过滤
  - 线程安全

用法：
    from lightshield.utils.logger import get_logger
    logger = get_logger()
    logger.info("core", "扫描开始", target="192.168.1.1")
"""

import logging
import os
import re
import threading
from datetime import datetime
from logging.handlers import RotatingFileHandler

# =============================================================================
# 日志格式化
# =============================================================================


class LightShieldFormatter(logging.Formatter):
    """自定义日志格式：[时间] [级别] [模块] 消息"""

    def __init__(self):
        super().__init__(
            fmt="%(asctime)s [%(levelname)-5s] [%(name)s] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )


class AuditFormatter(logging.Formatter):
    """审计日志专用格式，包含更多上下文"""

    def __init__(self):
        super().__init__(
            fmt="%(asctime)s [AUDIT] [%(name)s] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )


# =============================================================================
# 敏感信息过滤器
# =============================================================================


class SensitiveDataFilter(logging.Filter):
    """过滤日志中的敏感信息（密码、Token、密钥等）"""

    _SENSITIVE_PATTERNS = [
        (re.compile(r"password\s*[=:]\s*\S+", re.IGNORECASE), "password=***REDACTED***"),
        (re.compile(r"token\s*[=:]\s*\S+", re.IGNORECASE), "token=***REDACTED***"),
        (re.compile(r"secret\s*[=:]\s*\S+", re.IGNORECASE), "secret=***REDACTED***"),
        (re.compile(r"api_key\s*[=:]\s*\S+", re.IGNORECASE), "api_key=***REDACTED***"),
        (re.compile(r"key\s*[=:]\s*[\w-]{20,}", re.IGNORECASE), "key=***REDACTED***"),
    ]

    def filter(self, record: logging.LogRecord) -> bool:
        if hasattr(record, "msg") and isinstance(record.msg, str):
            for pattern, replacement in self._SENSITIVE_PATTERNS:
                record.msg = pattern.sub(replacement, record.msg)
        return True


# =============================================================================
# 日志管理器
# =============================================================================


class LightShieldLogger:
    """LightShield 结构化日志系统

    特性：
    - 同时输出到控制台和文件
    - 按日期命名日志文件
    - 单文件最大 10MB，自动轮转，保留 7 个备份
    - 审计操作专用方法
    - 敏感信息自动过滤
    """

    def __init__(self, log_dir: str = "./logs", level: str = "INFO"):
        """初始化日志管理器。

        Args:
        log_dir: 日志文件目录
        level: 日志级别（DEBUG / INFO / WARNING / ERROR）
        """
        self._log_dir = log_dir
        self._lock = threading.Lock()

        # 确保日志目录存在
        os.makedirs(log_dir, exist_ok=True)

        # 应用日志
        self._app_logger = logging.getLogger("lightshield")
        self._app_logger.setLevel(getattr(logging, level.upper(), logging.INFO))
        self._app_logger.handlers.clear()

        # 控制台输出
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(LightShieldFormatter())
        console_handler.addFilter(SensitiveDataFilter())
        self._app_logger.addHandler(console_handler)

        # 文件输出（按日期）
        today = datetime.now().strftime("%Y-%m-%d")
        log_file = os.path.join(log_dir, f"lightshield-{today}.log")
        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=10 * 1024 * 1024,  # 10MB
            backupCount=7,
            encoding="utf-8",
        )
        file_handler.setFormatter(LightShieldFormatter())
        file_handler.addFilter(SensitiveDataFilter())
        self._app_logger.addHandler(file_handler)

        # 审计日志（单独文件）
        self._audit_logger = logging.getLogger("lightshield.audit")
        self._audit_logger.setLevel(logging.INFO)
        self._audit_logger.handlers.clear()
        self._audit_logger.propagate = False  # 不重复输出到应用日志

        audit_file = os.path.join(log_dir, f"audit-{today}.log")
        audit_handler = RotatingFileHandler(
            audit_file,
            maxBytes=10 * 1024 * 1024,
            backupCount=30,
            encoding="utf-8",
        )
        audit_handler.setFormatter(AuditFormatter())
        self._audit_logger.addHandler(audit_handler)

    # =========================================================================
    # 通用日志方法
    # =========================================================================

    def debug(self, module: str, message: str, **extra) -> None:
        """调试日志"""
        self._app_logger.debug(f"[{module}] {message}", extra=extra)

    def info(self, module: str, message: str, **extra) -> None:
        """信息日志"""
        self._app_logger.info(f"[{module}] {message}", extra=extra)

    def warning(self, module: str, message: str, **extra) -> None:
        """警告日志"""
        self._app_logger.warning(f"[{module}] {message}", extra=extra)

    def error(self, module: str, message: str, exception: Exception | None = None, **extra) -> None:
        """错误日志

        Args:
            module: 模块名
            message: 错误描述
            exception: 关联的异常对象（如有）
        """
        if exception:
            self._app_logger.error(f"[{module}] {message} | 异常: {type(exception).__name__}: {exception}", extra=extra)
        else:
            self._app_logger.error(f"[{module}] {message}", extra=extra)

    # =========================================================================
    # 审计专用方法
    # =========================================================================

    def audit_scan_start(self, target: str, scan_type: str) -> str:
        """记录扫描开始——生成 scan_id

        Args:
            target: 扫描目标
            scan_type: 扫描类型

        Returns:
            唯一 scan_id 用于关联后续日志
        """
        import uuid

        scan_id = f"LS-{datetime.now().strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:6]}"
        self._audit_logger.info(f"scan_start | id={scan_id} | target={target} | type={scan_type}")
        self.info("audit", f"扫描开始 scan_id={scan_id} target={target} type={scan_type}")
        return scan_id

    def audit_scan_end(self, scan_id: str, result_summary: str) -> None:
        """记录扫描结束"""
        self._audit_logger.info(f"scan_end | id={scan_id} | result={result_summary}")
        self.info("audit", f"扫描结束 scan_id={scan_id} result={result_summary}")

    def audit_harden_action(self, target: str, action: str, result: str) -> None:
        """记录加固操作（合规 R4：每一条加固操作留痕）

        Args:
            target: 操作目标
            action: 执行的加固操作
            result: 操作结果
        """
        self._audit_logger.info(f"harden | target={target} | action={action} | result={result}")
        self.info("audit", f"加固操作 target={target} action={action} result={result}")

    def audit_msf_call(self, module_path: str, target: str, success: bool, duration: float = 0.0) -> None:
        """记录 MSF 调用（合规 R5：每次调用留痕）

        Args:
            module_path: MSF 模块路径
            target: 目标
            success: 是否成功
            duration: 耗时
        """
        status = "success" if success else "failed"
        self._audit_logger.info(
            f"msf_call | module={module_path} | target={target} | status={status} | duration={duration}s"
        )
        self.info("audit", f"MSF调用 module={module_path} target={target} status={status} duration={duration}s")

    def audit_config_change(self, key: str, old_value: str, new_value: str) -> None:
        """记录配置变更"""
        self._audit_logger.info(f"config_change | key={key} | old={old_value} | new={new_value}")

    # =========================================================================
    # 工具方法
    # =========================================================================

    def get_log_dir(self) -> str:
        """返回日志目录路径"""
        return self._log_dir

    def get_recent_logs(self, count: int = 50) -> list[str]:
        """获取最近的应用日志行（从今天的日志文件）"""
        today = datetime.now().strftime("%Y-%m-%d")
        log_file = os.path.join(self._log_dir, f"lightshield-{today}.log")
        if not os.path.exists(log_file):
            return []
        with open(log_file, encoding="utf-8") as f:
            lines = f.readlines()
        return [line.rstrip() for line in lines[-count:]]


# =============================================================================
# 单例
# =============================================================================

_logger_instance: LightShieldLogger | None = None
_logger_lock = threading.Lock()


def get_logger(log_dir: str = "./logs", level: str = "INFO") -> LightShieldLogger:
    """获取全局日志单例（线程安全）

    首次调用时创建实例，后续调用返回同一实例。

    Args:
        log_dir: 日志目录（仅首次调用时生效）
        level: 日志级别（仅首次调用时生效）

    Returns:
        LightShieldLogger 单例
    """
    global _logger_instance
    if _logger_instance is None:
        with _logger_lock:
            if _logger_instance is None:
                _logger_instance = LightShieldLogger(log_dir=log_dir, level=level)
    return _logger_instance


# =============================================================================
# 自检
# =============================================================================

if __name__ == "__main__":
    import tempfile

    # 用临时目录测试，避免污染项目 logs/
    tmpdir = tempfile.mkdtemp(prefix="lightshield_test_")
    try:
        logger = LightShieldLogger(log_dir=tmpdir, level="DEBUG")

        # 通用日志
        logger.info("core", "LightShield 启动")
        logger.debug("config", "加载配置", path="lightshield.yaml")
        logger.warning("validator", "检测到可疑输入", input="192.168.1.0/24")
        logger.error("nmap", "扫描超时", exception=TimeoutError("连接超时"))

        # 敏感信息过滤
        logger.info("auth", "用户登录", password="Secret123!", token="abc123xyz")

        # 审计日志
        scan_id = logger.audit_scan_start("192.168.1.1", "port_scan")
        logger.audit_scan_end(scan_id, "发现 3 个开放端口")
        logger.audit_harden_action("192.168.1.1", "关闭端口 23 (Telnet)", "成功")
        logger.audit_msf_call("auxiliary/scanner/ssh/ssh_login", "192.168.1.1", True, 12.5)

        # 读取日志
        recent = logger.get_recent_logs(count=5)

        # 关闭所有 handler，释放文件句柄（Windows 兼容）
        for handler in logger._app_logger.handlers[:]:
            handler.close()
            logger._app_logger.removeHandler(handler)
        for handler in logger._audit_logger.handlers[:]:
            handler.close()
            logger._audit_logger.removeHandler(handler)

        print("[OK] Logger self-check done")
        print(f"   log dir: {tmpdir}")
        print(f"   recent {len(recent)} lines")
        for line in recent[:2]:
            print(f"   {line[:100]}...")
    finally:
        import shutil

        shutil.rmtree(tmpdir, ignore_errors=True)
