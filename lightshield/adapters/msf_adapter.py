"""LightShield MSF 扫描器安全适配器。

本模块是合规红线 R5 的核心防线：所有 Metasploit 模块调用必须先经过
黑名单优先、白名单放行的路径校验，仅允许 auxiliary/scanner 子集。
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
import time
from datetime import datetime
from typing import Any

if __package__ in {None, ""}:  # 允许直接执行本文件进行自检。
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from lightshield.adapters.base import BaseAdapter, ScanResult, VulnFinding
from lightshield.utils.constants import (
    ALLOWED_MSF_PREFIXES,
    BLOCKED_MSF_PREFIXES,
    RiskLevel,
    ScanStatus,
)
from lightshield.utils.logger import get_logger
from lightshield.utils.validator import TargetValidator


class SecurityViolationError(Exception):
    """合规违规异常——尝试调用非白名单模块时抛出。"""

    def __init__(self, module_path: str, reason: str):
        self.module_path = module_path
        self.reason = reason
        super().__init__(f"安全违规: {module_path} — {reason}")


class InvalidTargetError(Exception):
    """目标校验失败异常。"""

    def __init__(self, target: str, reason: str):
        self.target = target
        self.reason = reason
        super().__init__(f"目标非法: {target} — {reason}")


class MsfScannerAdapter(BaseAdapter):
    """MSF 扫描器适配器 — 合规 R5 白名单防线。"""

    def __init__(self, msf_path: str | None = None):
        """初始化 MSF 适配器，加载白名单/黑名单。

        Args:
            msf_path: msfconsole 可执行文件路径，默认使用 PATH 中的 msfconsole。
        """
        super().__init__(name="MsfScannerAdapter")
        self._msf_path = msf_path or "msfconsole"
        self._allowed_prefixes = tuple(ALLOWED_MSF_PREFIXES)
        self._blocked_prefixes = tuple(BLOCKED_MSF_PREFIXES)
        self._audit_log: list[dict[str, Any]] = []
        self._logger = get_logger()

    def capabilities(self) -> list[str]:
        """返回 MSF 适配器能力。"""
        return ["msf_scan"]

    def validate_target(self, target: str) -> bool:
        """目标合法性校验——委托给 TargetValidator。"""
        is_valid, reason = TargetValidator.validate(target)
        if not is_valid:
            self._logger.warning("msf", f"目标校验失败: {target} — {reason}")
        return is_valid

    def scan(self, target: str, **kwargs: Any) -> ScanResult:
        """执行 MSF scanner 模块扫描。

        Args:
            target: 单个自有 IP/域名。
            **kwargs:
                msf_module: 必填，MSF 模块路径，必须通过 R5 校验。
                options: 可选，MSF set 参数。
        """
        started_at = time.monotonic()
        module_path = str(kwargs.get("msf_module") or "")
        options = kwargs.get("options") or {}

        try:
            exec_result = self.exec_msf_module(module_path, target, options)
            findings = self._findings_from_output(exec_result.get("stdout", ""), target, module_path)
            exec_completed = exec_result.get("result") == "completed"
            result = ScanResult(
                status=ScanStatus.COMPLETED if exec_completed else ScanStatus.FAILED,
                target=target,
                findings=findings,
                raw_output=exec_result.get("stdout", ""),
                error=None if exec_completed else (exec_result.get("stderr") or "MSF 执行失败"),
                duration_seconds=time.monotonic() - started_at,
            )
            self._log_scan_end(f"MSF-{int(started_at)}", result)
            return result
        except (SecurityViolationError, InvalidTargetError) as exc:
            self._logger.error("msf", str(exc))
            result = ScanResult(
                status=ScanStatus.FAILED,
                target=target,
                error=str(exc),
                duration_seconds=time.monotonic() - started_at,
            )
            self._log_scan_end(f"MSF-{int(started_at)}", result)
            return result
        except Exception as exc:
            self._logger.error("msf", "MSF 扫描异常", exception=exc)
            result = ScanResult(
                status=ScanStatus.FAILED,
                target=target,
                error=f"MSF 扫描异常: {exc}",
                duration_seconds=time.monotonic() - started_at,
            )
            self._log_scan_end(f"MSF-{int(started_at)}", result)
            return result

    def is_module_allowed(self, module_path: str) -> bool:
        """R5 白名单校验：先检查黑名单，再检查白名单，黑名单优先。"""
        normalized = self._normalize_module_path(module_path)
        if not normalized:
            return False
        if not self._is_safe_module_path(normalized):
            self._logger.warning("msf", f"拦截非法 MSF 模块路径: {normalized}")
            return False

        if any(normalized.startswith(prefix) for prefix in self._blocked_prefixes):
            self._logger.warning("msf", f"拦截黑名单 MSF 模块: {normalized}")
            return False

        if any(normalized.startswith(prefix) for prefix in self._allowed_prefixes):
            return True

        self._logger.warning("msf", f"拦截非白名单 MSF 模块: {normalized}")
        return False

    def list_allowed_modules(self) -> list[str]:
        """列出允许的 MSF 模块路径前缀。"""
        return list(self._allowed_prefixes)

    def exec_msf_module(
        self,
        module_path: str,
        target: str,
        options: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """安全执行 MSF 模块，带完整审计日志。

        流程：
        1. R5 模块白名单校验
        2. R2/R4 目标校验
        3. 记录审计日志
        4. subprocess.run(timeout=60) 执行 msfconsole
        5. 解析输出为结构化字典
        """
        normalized_module = self._normalize_module_path(module_path)
        if not self.is_module_allowed(normalized_module):
            raise SecurityViolationError(normalized_module or "<empty>", "模块不在 MSF scanner 白名单内或命中黑名单")

        is_valid, reason = TargetValidator.validate(target)
        if not is_valid:
            raise InvalidTargetError(target, reason)

        safe_options = self._safe_options(options or {})
        safe_options["RHOSTS"] = target
        started_at = time.monotonic()
        audit_entry = self._new_audit_entry(normalized_module, target, safe_options)
        self._audit_log.append(audit_entry)

        cmd = [
            self._msf_path,
            "-q",
            "-x",
            self._build_msf_command(normalized_module, safe_options),
        ]

        try:
            completed = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60,
            )
            duration = time.monotonic() - started_at
            result_status = "completed" if completed.returncode == 0 else "failed"
            audit_entry["result"] = result_status
            audit_entry["duration_seconds"] = round(duration, 3)
            self._logger.audit_msf_call(normalized_module, target, completed.returncode == 0, duration)

            return {
                "module": normalized_module,
                "target": target,
                "options": dict(safe_options),
                "returncode": completed.returncode,
                "stdout": completed.stdout or "",
                "stderr": completed.stderr or "",
                "duration_seconds": duration,
                "result": result_status,
            }
        except subprocess.TimeoutExpired as exc:
            duration = time.monotonic() - started_at
            audit_entry["result"] = "timeout"
            audit_entry["duration_seconds"] = round(duration, 3)
            self._logger.audit_msf_call(normalized_module, target, False, duration)
            return {
                "module": normalized_module,
                "target": target,
                "options": dict(safe_options),
                "returncode": -1,
                "stdout": exc.stdout or "",
                "stderr": f"MSF 模块执行超时: {exc}",
                "duration_seconds": duration,
                "result": "timeout",
            }
        except FileNotFoundError:
            duration = time.monotonic() - started_at
            audit_entry["result"] = "failed"
            audit_entry["duration_seconds"] = round(duration, 3)
            self._logger.audit_msf_call(normalized_module, target, False, duration)
            return {
                "module": normalized_module,
                "target": target,
                "options": dict(safe_options),
                "returncode": -1,
                "stdout": "",
                "stderr": f"msfconsole 未安装或路径错误: {self._msf_path}",
                "duration_seconds": duration,
                "result": "failed",
            }

    def get_audit_log(self, limit: int = 50) -> list[dict[str, Any]]:
        """获取最近的 MSF 调用审计日志。"""
        if limit <= 0:
            return []
        return [dict(item) for item in self._audit_log[-limit:]]

    def _normalize_module_path(self, module_path: str | None) -> str:
        """规范化模块路径，禁止通过反斜杠或首尾空白绕过前缀校验。"""
        if not isinstance(module_path, str):
            return ""
        return module_path.strip().replace("\\", "/").lstrip("/")

    def _is_safe_module_path(self, module_path: str) -> bool:
        """限制模块路径字符，避免分号、空格等进入 msfconsole -x 脚本。"""
        return bool(re.fullmatch(r"[A-Za-z0-9_./-]+", module_path))

    def _safe_options(self, options: dict[str, Any]) -> dict[str, str]:
        """过滤 MSF option，避免分号、换行等命令串联字符进入 -x 脚本。"""
        safe: dict[str, str] = {}
        for key, value in options.items():
            option_key = str(key).strip().upper()
            option_value = str(value).strip()
            if not option_key or option_key == "RHOSTS":
                continue
            if not re.fullmatch(r"[A-Z0-9_]+", option_key):
                self._logger.warning("msf", f"忽略非法 MSF 参数名: {key}")
                continue
            if any(marker in option_value for marker in (";", "\n", "\r")):
                self._logger.warning("msf", f"忽略包含危险字符的 MSF 参数: {option_key}")
                continue
            safe[option_key] = option_value
        return safe

    def _build_msf_command(self, module_path: str, options: dict[str, str]) -> str:
        """构造 msfconsole -x 脚本；模块与参数均已提前校验。"""
        commands = [f"use {module_path}"]
        for key, value in options.items():
            commands.append(f"set {key} {value}")
        commands.extend(["run", "exit"])
        return "; ".join(commands)

    def _new_audit_entry(self, module_path: str, target: str, options: dict[str, str]) -> dict[str, Any]:
        """创建审计日志条目。"""
        return {
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "module": module_path,
            "target": target,
            "options": dict(options),
            "result": "running",
            "duration_seconds": 0.0,
        }

    def _findings_from_output(self, stdout: str, target: str, module_path: str) -> list[VulnFinding]:
        """从 MSF scanner 输出中提取保守的提示型发现。"""
        findings: list[VulnFinding] = []
        for line in stdout.splitlines():
            lowered = line.lower()
            if "[+]" not in line and "found" not in lowered and "vulnerable" not in lowered:
                continue
            findings.append(
                VulnFinding(
                    vuln_type="msf_scanner_finding",
                    severity=RiskLevel.MEDIUM,
                    title="MSF 扫描器发现可疑结果",
                    description="白名单 MSF scanner 模块返回了可疑发现，建议结合上下文人工复核。",
                    remediation="确认服务配置、版本与认证策略；仅在授权范围内继续验证和加固。",
                    evidence=line[:500],
                    url=None,
                    parameter=None,
                )
            )
        if findings:
            self._logger.info("msf", f"{module_path} 在 {target} 返回 {len(findings)} 条可疑发现")
        return findings


if __name__ == "__main__":
    adapter = MsfScannerAdapter(msf_path="msfconsole")

    assert adapter.capabilities() == ["msf_scan"]
    assert adapter.is_module_allowed("auxiliary/scanner/ssh/ssh_version") is True
    assert adapter.is_module_allowed("auxiliary/scanner/http/title") is True
    assert adapter.is_module_allowed("exploit/windows/smb/example") is False
    assert adapter.is_module_allowed("payload/windows/meterpreter/example") is False
    assert adapter.is_module_allowed("auxiliary/dos/http/example") is False
    assert adapter.is_module_allowed("") is False

    try:
        adapter.exec_msf_module("exploit/windows/smb/example", "127.0.0.1")
    except SecurityViolationError:
        print("SecurityViolationError 抛出测试通过")
    else:
        raise AssertionError("黑名单模块未抛出 SecurityViolationError")

    print("msf_adapter.py 自检通过")
