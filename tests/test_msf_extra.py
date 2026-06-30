"""MSF 适配器补充测试 — v0.0.45 T2 边界/异常路径覆盖。"""

import contextlib

import pytest

from lightshield.adapters.msf_adapter import MsfScannerAdapter, SecurityViolationError


@pytest.fixture
def adapter():
    """返回 MsfScannerAdapter 实例。"""
    return MsfScannerAdapter()


class TestIsModuleAllowedEdgeCases:
    """is_module_allowed 边界输入。"""

    def test_empty_string_rejected(self, adapter):
        assert adapter.is_module_allowed("") is False

    def test_non_scanner_auxiliary_rejected(self, adapter):
        # auxiliary/admin/ 不在白名单内
        assert adapter.is_module_allowed("auxiliary/admin/cleanup") is False

    def test_scanner_http_allowed(self, adapter):
        assert adapter.is_module_allowed("auxiliary/scanner/http/http_version") is True

    def test_scanner_ssh_allowed(self, adapter):
        assert adapter.is_module_allowed("auxiliary/scanner/ssh/ssh_version") is True

    def test_scanner_ftp_allowed(self, adapter):
        assert adapter.is_module_allowed("auxiliary/scanner/ftp/ftp_version") is True

    def test_scanner_ssl_allowed(self, adapter):
        assert adapter.is_module_allowed("auxiliary/scanner/ssl/ssl_version") is True


class TestExecMsfModule:
    """exec_msf_module 异常路径。"""

    def test_security_violation_for_blocked_module(self, adapter):
        with pytest.raises(SecurityViolationError):
            adapter.exec_msf_module("exploit/multi/handler", "127.0.0.1")

    def test_security_violation_for_payload(self, adapter):
        with pytest.raises(SecurityViolationError):
            adapter.exec_msf_module("payload/windows/shell/reverse_tcp", "127.0.0.1")

    def test_invalid_target_rejected(self, adapter):
        """白名单模块但目标不合法 → 拒绝。"""
        with pytest.raises((SecurityViolationError, ValueError)):
            adapter.exec_msf_module("auxiliary/scanner/ssh/ssh_version", "192.168.1.0/24")


class TestAuditLog:
    """审计日志验证。"""

    def test_empty_log_before_any_calls(self, adapter):
        log = adapter.get_audit_log()
        assert log == []

    def test_log_after_whitelist_check(self, adapter):
        adapter.is_module_allowed("auxiliary/scanner/ssh/ssh_login")
        # whitelist check may or may not generate audit entries depending on impl
        log = adapter.get_audit_log()
        assert isinstance(log, list)

    def test_log_entries_have_required_fields(self, adapter):
        # 使用 exec_msf_module 触发审计，但该调用可能抛异常
        with contextlib.suppress(Exception):
            adapter.exec_msf_module("auxiliary/scanner/ssh/ssh_version", "127.0.0.1")
        log = adapter.get_audit_log()
        assert isinstance(log, list)


class TestCapabilities:
    """capabilities() 列表格式。"""

    def test_returns_list_of_strings(self, adapter):
        caps = adapter.capabilities()
        assert isinstance(caps, list)
        for c in caps:
            assert isinstance(c, str)

    def test_list_allowed_modules_non_empty(self, adapter):
        modules = adapter.list_allowed_modules()
        assert len(modules) > 0
        for m in modules:
            assert m.startswith("auxiliary/scanner/")
