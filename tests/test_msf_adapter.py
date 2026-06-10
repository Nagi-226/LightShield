"""MsfScannerAdapter 单元测试。

覆盖 LightShield R5 合规防线：
- 白名单模块允许调用。
- 黑名单模块强制拒绝，且黑名单优先。
- 非法模块路径和命令注入字符必须拒绝。
- scan() 不触发真实 msfconsole，使用 subprocess.run mock 验证流程。
"""

from __future__ import annotations

import os
import sys
from types import SimpleNamespace
from unittest.mock import patch

import pytest


# 允许直接执行本文件或从 tests/ 目录运行 pytest。
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from lightshield.adapters.msf_adapter import MsfScannerAdapter, SecurityViolationError
from lightshield.utils.constants import ScanStatus


@pytest.fixture
def adapter() -> MsfScannerAdapter:
    """创建不依赖真实 msfconsole 的适配器实例。"""
    return MsfScannerAdapter(msf_path="msfconsole")


@pytest.mark.parametrize(
    "module_path",
    [
        "auxiliary/scanner/ssh/ssh_version",
        "auxiliary/scanner/portscan/tcp",
        "auxiliary/scanner/http/title",
        "auxiliary/scanner/mysql/mysql_version",
        "auxiliary/scanner/ftp/anonymous",
        "auxiliary/scanner/ssl/openssl_heartbleed",
        "auxiliary/scanner/dns/dns_amp",
    ],
)
def test_is_module_allowed_accepts_whitelisted_scanners(
    adapter: MsfScannerAdapter,
    module_path: str,
) -> None:
    """白名单中的 auxiliary/scanner 子集应允许。"""
    assert adapter.is_module_allowed(module_path) is True, f"{module_path} 应通过白名单"


@pytest.mark.parametrize(
    "module_path",
    [
        "exploit/windows/smb/example",
        "payload/windows/meterpreter/example",
        "post/windows/gather/example",
        "evasion/windows/example",
        "nops/x86/example",
        "auxiliary/dos/http/example",
        "auxiliary/admin/http/example",
        "auxiliary/scanner/backdoor/example",
    ],
)
def test_is_module_allowed_rejects_blacklisted_modules(
    adapter: MsfScannerAdapter,
    module_path: str,
) -> None:
    """黑名单路径必须拒绝，覆盖 exploit/payload/post/evasion/dos/admin/backdoor。"""
    assert adapter.is_module_allowed(module_path) is False, f"{module_path} 命中黑名单，必须拒绝"


def test_blacklist_has_priority_over_broad_scanner_whitelist(adapter: MsfScannerAdapter) -> None:
    """黑名单优先：即使 broad scanner 白名单误配置，也不能放过 backdoor。"""
    adapter._allowed_prefixes = ("auxiliary/scanner/",)

    assert adapter.is_module_allowed("auxiliary/scanner/backdoor/example") is False, (
        "auxiliary/scanner/backdoor 同时匹配 broad 白名单时也必须被黑名单拦截"
    )


@pytest.mark.parametrize(
    "module_path",
    [
        None,
        "",
        "unknown/module",
        "scanner/ssh/ssh_version",
        "auxiliary/scanner/ssh/ssh_version; exit",
        "auxiliary/scanner/ssh/ssh_version\nrun",
        "auxiliary/scanner/ssh/ssh version",
        "auxiliary/scanner/ssh/ssh_version\rrun",
    ],
)
def test_is_module_allowed_rejects_invalid_or_injection_inputs(
    adapter: MsfScannerAdapter,
    module_path: object,
) -> None:
    """异常输入、未匹配模块和注入字符必须拒绝。"""
    assert adapter.is_module_allowed(module_path) is False, f"{module_path!r} 应被 R5 防线拒绝"


def test_exec_msf_module_raises_security_violation_for_blocked_module(
    adapter: MsfScannerAdapter,
) -> None:
    """非法模块执行前必须抛出 SecurityViolationError，不能进入 subprocess。"""
    with patch("lightshield.adapters.msf_adapter.subprocess.run") as mocked_run:
        with pytest.raises(SecurityViolationError) as exc_info:
            adapter.exec_msf_module("exploit/windows/smb/example", "127.0.0.1")

    assert "安全违规" in str(exc_info.value), "异常信息应明确提示安全违规"
    assert mocked_run.called is False, "黑名单模块不得触发 subprocess.run"


def test_get_audit_log_is_empty_before_any_msf_call(adapter: MsfScannerAdapter) -> None:
    """审计日志初始应为空。"""
    assert adapter.get_audit_log() == [], "新适配器实例不应有审计日志"
    assert adapter.get_audit_log(limit=0) == [], "limit=0 应返回空列表"


def test_scan_returns_completed_result_for_valid_module_with_mocked_subprocess(
    adapter: MsfScannerAdapter,
) -> None:
    """合法白名单模块在 mock subprocess 成功时应返回 COMPLETED ScanResult。"""
    fake_completed = SimpleNamespace(
        returncode=0,
        stdout="[+] SSH service found on 127.0.0.1\n",
        stderr="",
    )

    with patch("lightshield.adapters.msf_adapter.subprocess.run", return_value=fake_completed) as mocked_run:
        result = adapter.scan(
            "127.0.0.1",
            msf_module="auxiliary/scanner/ssh/ssh_version",
            options={"THREADS": "1"},
        )

    assert result.status == ScanStatus.COMPLETED, f"合法模块 mock 成功应完成，实际：{result.error}"
    assert result.target == "127.0.0.1"
    assert result.findings, "stdout 中包含 [+] 时应生成提示型 finding"
    assert result.findings[0].vuln_type == "msf_scanner_finding"
    assert mocked_run.call_args.kwargs["timeout"] == 60, "MSF 子进程必须设置 60 秒超时"

    audit_log = adapter.get_audit_log()
    assert len(audit_log) == 1, "成功执行后应记录 1 条审计日志"
    assert audit_log[0]["module"] == "auxiliary/scanner/ssh/ssh_version"
    assert audit_log[0]["target"] == "127.0.0.1"
    assert audit_log[0]["options"]["RHOSTS"] == "127.0.0.1"
    assert audit_log[0]["result"] == "completed"


def test_scan_returns_failed_result_for_invalid_module(adapter: MsfScannerAdapter) -> None:
    """非法模块 scan() 应返回 FAILED，且不得触发 subprocess.run。"""
    with patch("lightshield.adapters.msf_adapter.subprocess.run") as mocked_run:
        result = adapter.scan(
            "127.0.0.1",
            msf_module="payload/windows/meterpreter/example",
            options={"THREADS": "1"},
        )

    assert result.status == ScanStatus.FAILED, "非法模块应返回 FAILED"
    assert result.error and "安全违规" in result.error, "失败信息应包含安全违规提示"
    assert mocked_run.called is False, "非法模块不得触发 subprocess.run"
    assert adapter.get_audit_log() == [], "被 R5 拦截的调用不应写入执行审计日志"


def test_scan_returns_failed_result_for_invalid_target(adapter: MsfScannerAdapter) -> None:
    """非法目标 scan() 应返回 FAILED，且不得触发 subprocess.run。"""
    with patch("lightshield.adapters.msf_adapter.subprocess.run") as mocked_run:
        result = adapter.scan(
            "192.168.1.0/24",
            msf_module="auxiliary/scanner/ssh/ssh_version",
            options={"THREADS": "1"},
        )

    assert result.status == ScanStatus.FAILED, "CIDR 目标应被 R2 拦截"
    assert result.error and "目标非法" in result.error, "失败信息应说明目标非法"
    assert mocked_run.called is False, "非法目标不得触发 subprocess.run"


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
