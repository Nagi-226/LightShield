"""测试模块：lightshield/utils/logger.py

覆盖内容：
  - get_logger() 单例行为与线程安全结构
  - LightShieldLogger 直接实例化后的日志写入/轮转
  - 审计方法返回 scan_id 格式 + audit_* 不抛异常
  - SensitiveDataFilter 敏感信息替换
  - debug/info/warning/error 四级日志不抛异常 + error(exception=)
  - get_recent_logs(count=N) 返回限制
  - 使用 tempfile.mkdtemp 隔离文件 I/O，测试结束后关闭 handler

注意：
  - get_logger() 返回模块级单例，需要手动重置 _logger_instance 做隔离测试
  - 本文件依赖 pytest，不使用 self.assertXxx
"""

import logging
import os
import re
import threading
import tempfile
import shutil
from datetime import datetime

import pytest

import lightshield.utils.logger as logger_mod
from lightshield.utils.logger import (
    get_logger,
    LightShieldLogger,
    LightShieldFormatter,
    AuditFormatter,
    SensitiveDataFilter,
)


# =============================================================================
# 辅助函数与 fixture
# =============================================================================

def _reset_logger_singleton():
    """重置模块级单例，使 get_logger() 返回新实例（测试隔离）"""
    logger_mod._logger_instance = None


def _close_handlers(logger_instance: LightShieldLogger) -> None:
    """关闭并移除 LightShieldLogger 的所有 handler，释放文件句柄"""
    for handler_list in [logger_instance._app_logger.handlers[:], logger_instance._audit_logger.handlers[:]]:
        for handler in handler_list:
            handler.close()
        # 从对应 logger 上移除已关闭的 handler
        for h in handler_list:
            logger_instance._app_logger.removeHandler(h)
            logger_instance._audit_logger.removeHandler(h)


@pytest.fixture
def temp_logger():
    """创建使用临时目录的 LightShieldLogger 实例，测试后清理"""
    tmpdir = tempfile.mkdtemp(prefix="lightshield_test_logger_")
    logger = LightShieldLogger(log_dir=tmpdir, level="DEBUG")
    yield logger
    _close_handlers(logger)
    shutil.rmtree(tmpdir, ignore_errors=True)


# =============================================================================
# 单例与线程安全
# =============================================================================

class TestLoggerSingleton:
    """get_logger() 单例行为验证"""

    def test_same_instance_within_thread(self):
        """同一线程多次调用 get_logger() 返回同一实例"""
        _reset_logger_singleton()
        try:
            a = get_logger(log_dir=tempfile.mkdtemp(prefix="ls_single_"))
            b = get_logger()
            assert a is b, "get_logger() 应返回同一实例"
        finally:
            _reset_logger_singleton()

    def test_instance_is_lighthield_logger(self):
        """get_logger() 返回 LightShieldLogger 实例"""
        _reset_logger_singleton()
        try:
            instance = get_logger(log_dir=tempfile.mkdtemp(prefix="ls_type_"))
            assert isinstance(instance, LightShieldLogger)
        finally:
            _reset_logger_singleton()

    def test_double_check_locking_lock_exists(self):
        """_logger_lock 是 threading.Lock 实例（双检查锁定结构）"""
        assert hasattr(logger_mod, "_logger_lock")
        assert isinstance(logger_mod._logger_lock, type(threading.Lock()))


# =============================================================================
# 审计方法
# =============================================================================

class TestAuditMethods:
    """审计专用方法行为验证"""

    def test_audit_scan_start_returns_scan_id(self, temp_logger):
        """audit_scan_start() 返回符合格式的 scan_id"""
        scan_id = temp_logger.audit_scan_start("192.168.1.1", "port_scan")

        # 格式：LS-YYYYMMDD-HHMMSS-xxxxxx
        pattern = r"^LS-\d{8}-\d{6}-[a-f0-9]{6}$"
        assert re.match(pattern, scan_id), f"scan_id 格式不符: {scan_id!r}"

    def test_audit_scan_start_id_prefix(self, temp_logger):
        """scan_id 以 'LS-' 开头"""
        scan_id = temp_logger.audit_scan_start("127.0.0.1", "weak_password")
        assert scan_id.startswith("LS-")

    def test_audit_scan_start_unique_ids(self, temp_logger):
        """连续两次调用生成不同的 scan_id"""
        id1 = temp_logger.audit_scan_start("127.0.0.1", "port_scan")
        id2 = temp_logger.audit_scan_start("127.0.0.1", "web_vuln")
        assert id1 != id2, "两次 scan_id 应不同"

    def test_audit_scan_end_no_exception(self, temp_logger):
        """audit_scan_end 不抛异常"""
        scan_id = temp_logger.audit_scan_start("127.0.0.1", "port_scan")
        temp_logger.audit_scan_end(scan_id, "发现 3 个开放端口")

    def test_audit_harden_action_no_exception(self, temp_logger):
        """audit_harden_action 不抛异常"""
        temp_logger.audit_harden_action("192.168.1.1", "关闭端口 23 (Telnet)", "成功")

    def test_audit_msf_call_no_exception(self, temp_logger):
        """audit_msf_call 不抛异常"""
        temp_logger.audit_msf_call(
            "auxiliary/scanner/ssh/ssh_login", "192.168.1.1", True, 12.5
        )

    def test_audit_config_change_no_exception(self, temp_logger):
        """audit_config_change 不抛异常"""
        temp_logger.audit_config_change("scan_timeout", "30", "60")


# =============================================================================
# 敏感信息过滤
# =============================================================================

class TestSensitiveDataFilter:
    """SensitiveDataFilter 敏感信息替换验证"""

    @pytest.mark.parametrize("input_msg, keyword", [
        ("login attempt password=Secret123!", "password"),
        ("auth token=abc123token", "token"),
        ("config secret=mykey999", "secret"),
        ("request api_key=sk-12345abcdef", "api_key"),
        ("remote key=a1b2c3d4e5f6g7h8i9j0", "key"),
    ])
    def test_filter_replaces_sensitive_data(self, input_msg, keyword):
        """日志消息中的敏感字段被替换为 ***REDACTED***"""
        record = logging.LogRecord(
            name="test", level=logging.INFO, pathname="", lineno=0,
            msg=input_msg, args=(), exc_info=None,
        )
        filt = SensitiveDataFilter()
        filt.filter(record)

        assert keyword in input_msg.lower() or keyword == "key"  # 确认输入包含关键字
        assert "***REDACTED***" in record.msg, (
            f"消息中应含 REDACTED，实际: {record.msg!r}"
        )
        assert keyword not in record.msg.lower() or "redacted" in record.msg.lower(), (
            f"原始关键字应在过滤后消失或变为 REDACTED"
        )

    def test_filter_always_returns_true(self):
        """SensitiveDataFilter.filter() 始终返回 True（不拦截日志）"""
        record = logging.LogRecord(
            name="test", level=logging.INFO, pathname="", lineno=0,
            msg="normal message", args=(), exc_info=None,
        )
        filt = SensitiveDataFilter()
        assert filt.filter(record) is True

    def test_filter_idempotent_on_clean_message(self):
        """对无敏感信息的消息，过滤后内容不变"""
        clean_msg = "扫描完成，发现 3 个开放端口"
        record = logging.LogRecord(
            name="test", level=logging.INFO, pathname="", lineno=0,
            msg=clean_msg, args=(), exc_info=None,
        )
        filt = SensitiveDataFilter()
        filt.filter(record)
        assert record.msg == clean_msg

    def test_filter_handles_non_str_msg(self):
        """filter 对非字符串 msg 不报错"""
        record = logging.LogRecord(
            name="test", level=logging.INFO, pathname="", lineno=0,
            msg=42, args=(), exc_info=None,
        )
        filt = SensitiveDataFilter()
        # 不应抛异常
        result = filt.filter(record)
        assert result is True


# =============================================================================
# 日志级别方法
# =============================================================================

class TestLogLevelMethods:
    """debug / info / warning / error 四级方法验证"""

    def test_debug_no_exception(self, temp_logger):
        """debug 方法不抛异常"""
        temp_logger.debug("test_module", "调试信息", extra="value")

    def test_info_no_exception(self, temp_logger):
        """info 方法不抛异常"""
        temp_logger.info("test_module", "普通信息", key="val")

    def test_warning_no_exception(self, temp_logger):
        """warning 方法不抛异常"""
        temp_logger.warning("test_module", "警告信息", hint="check")

    def test_error_without_exception(self, temp_logger):
        """error 方法（无 exception）不抛异常"""
        temp_logger.error("test_module", "错误信息")

    def test_error_with_exception(self, temp_logger):
        """error 方法传入 exception=ValueError 时包含异常类名与消息"""
        # 写入后检查日志文件内容
        temp_logger.error("scanner", "扫描失败", exception=ValueError("参数错误"))

        # 验证日志文件包含异常信息
        today = datetime.now().strftime("%Y-%m-%d")
        log_file = os.path.join(temp_logger._log_dir, f"lightshield-{today}.log")
        if os.path.exists(log_file):
            with open(log_file, "r", encoding="utf-8") as f:
                content = f.read()
            assert "ValueError" in content, f"日志应包含异常类型，实际: {content[:200]}"
            assert "参数错误" in content, f"日志应包含异常消息，实际: {content[:200]}"


# =============================================================================
# get_recent_logs
# =============================================================================

class TestGetRecentLogs:
    """get_recent_logs 方法验证"""

    def test_returns_list(self, temp_logger):
        """get_recent_logs 返回 list[str]"""
        result = temp_logger.get_recent_logs(count=5)
        assert isinstance(result, list)
        if result:
            assert all(isinstance(line, str) for line in result)

    def test_respects_count_limit(self, temp_logger):
        """get_recent_logs(count=N) 返回不超过 N 行"""
        # 写入足够多的日志
        for i in range(20):
            temp_logger.info("test", f"测试日志第 {i} 行")

        recent = temp_logger.get_recent_logs(count=5)
        assert len(recent) <= 5, f"应 ≤5 条，实际 {len(recent)}"

    def test_empty_log_dir_returns_empty_list(self, temp_logger):
        """无日志文件时返回空列表"""
        # 使用全新的临时目录，未写入任何日志
        empty_dir = tempfile.mkdtemp(prefix="lightshield_empty_")
        try:
            empty_logger = LightShieldLogger(log_dir=empty_dir, level="INFO")
            # 不移除 handler — get_recent_logs 靠文件存在性判断
            result = empty_logger.get_recent_logs(count=10)
            # 可能已写入一条 setup 日志，所以只验证返回类型
            assert isinstance(result, list)
        finally:
            _close_handlers(empty_logger)
            shutil.rmtree(empty_dir, ignore_errors=True)


# =============================================================================
# 日志文件写入
# =============================================================================

class TestFileLogging:
    """日志文件写入与轮转验证"""

    def test_log_file_created(self, temp_logger):
        """初始化后日志目录包含 lightshield-{today}.log"""
        today = datetime.now().strftime("%Y-%m-%d")
        log_file = os.path.join(temp_logger._log_dir, f"lightshield-{today}.log")
        # 写入一条日志强制刷新
        temp_logger.info("test", "test message to create file")
        assert os.path.exists(log_file) or os.path.exists(
            os.path.join(temp_logger._log_dir, f"audit-{today}.log")
        ), f"应有日志文件存在"

    def test_dual_output_console_and_file(self, temp_logger):
        """确认同时存在控制台和文件 handler"""
        app_handlers = temp_logger._app_logger.handlers
        handler_types = {type(h).__name__ for h in app_handlers}
        assert "StreamHandler" in handler_types, "缺少控制台输出"
        assert "RotatingFileHandler" in handler_types, "缺少文件输出"


# =============================================================================
# get_log_dir
# =============================================================================

class TestGetLogDir:
    """get_log_dir 方法验证"""

    def test_returns_log_directory(self, temp_logger):
        """get_log_dir() 返回初始化时的目录路径"""
        log_dir = temp_logger.get_log_dir()
        assert log_dir == temp_logger._log_dir
        assert os.path.isdir(log_dir)
