"""LightShield v0.0.40 — HostExecutor 单元测试

测试目标：
  - HostExecutor.is_available() 始终返回 True
  - 未确认执行 → REJECTED（复用基类闸门）
  - 正常执行脚本（跨平台：Windows .bat / Linux .sh）
  - 脚本退出码非零 → FAILED
  - 执行超时 → TIMEOUT
  - 脚本不存在 → REJECTED
  - get_executor("host") 工厂返回 HostExecutor

所有测试使用临时文件 + mock subprocess，不真实修改系统。
"""

from __future__ import annotations

import os
import platform
import tempfile
from unittest import mock

import pytest

from lightshield.sandbox import get_executor
from lightshield.sandbox.base import ExecutionStatus
from lightshield.sandbox.host_executor import HostExecutor

# =============================================================================
# 跨平台测试辅助
# =============================================================================

IS_WINDOWS = platform.system() == "Windows"

if IS_WINDOWS:
    GOOD_SCRIPT = "@echo off\r\necho hello from host\r\nexit /b 0\r\n"
    FAIL_SCRIPT = "@echo off\r\necho about to fail\r\nexit /b 1\r\n"
    SUFFIX = ".bat"
else:
    GOOD_SCRIPT = "#!/bin/bash\necho 'hello from host'\nexit 0\n"
    FAIL_SCRIPT = "#!/bin/bash\necho 'about to fail'\nexit 1\n"
    SUFFIX = ".sh"


# =============================================================================
# 测试类
# =============================================================================


class TestHostExecutorBasic:
    """基本属性与闸门测试。"""

    def test_is_available_always_true(self):
        """HostExecutor 始终可用，不依赖外部运行时。"""
        ex = HostExecutor()
        assert ex.is_available() is True

    def test_name_default(self):
        """默认名称为 HostExecutor。"""
        ex = HostExecutor()
        assert ex.name == "HostExecutor"

    def test_name_custom(self):
        """自定义名称。"""
        ex = HostExecutor()
        ex.name = "CustomHost"
        assert ex.name == "CustomHost"

    def test_unconfirmed_execute_rejected(self):
        """未传 confirm_execute → REJECTED（基类闸门）。"""
        ex = HostExecutor()
        r = ex.execute("whatever.sh")
        assert r.status == ExecutionStatus.REJECTED
        assert r.error and "confirm_execute" in r.error.lower()

    def test_script_not_found_rejected(self):
        """脚本不存在 → REJECTED（基类安全校验）。"""
        ex = HostExecutor()
        r = ex.execute("/nonexistent/path/script.sh", confirm_execute=True)
        assert r.status == ExecutionStatus.REJECTED
        assert r.error and "不存在" in r.error


class TestHostExecutorExecution:
    """真实执行测试（使用临时文件，不 mock）。"""

    def test_execute_success(self):
        """正常脚本 → SUCCESS。"""
        ex = HostExecutor()
        with tempfile.NamedTemporaryFile("w", suffix=SUFFIX, delete=False, encoding="utf-8") as tf:
            tf.write(GOOD_SCRIPT)
            script = tf.name

        try:
            r = ex.execute(script, confirm_execute=True)
            assert r.status == ExecutionStatus.SUCCESS, f"应成功，实得 {r.status}（error={r.error}）"
            assert r.sandbox == "host"
            assert r.exit_code == 0
            assert "hello from host" in r.stdout
            assert r.audit_id.startswith("EXEC-"), f"审计 ID: {r.audit_id}"
        finally:
            os.remove(script)

    def test_execute_failure_non_zero_exit(self):
        """退出码非零 → FAILED。"""
        ex = HostExecutor()
        with tempfile.NamedTemporaryFile("w", suffix=SUFFIX, delete=False, encoding="utf-8") as tf:
            tf.write(FAIL_SCRIPT)
            script = tf.name

        try:
            r = ex.execute(script, confirm_execute=True)
            assert r.status == ExecutionStatus.FAILED, f"应失败，实得 {r.status}"
            assert r.exit_code == 1
            assert r.error and "退出码" in r.error
        finally:
            os.remove(script)

    def test_execute_timeout(self):
        """执行超时 → TIMEOUT。"""
        ex = HostExecutor(timeout=2)
        if IS_WINDOWS:
            # Windows: powershell sleep
            content = '@echo off\r\npowershell.exe -NoProfile -Command "Start-Sleep -Seconds 60"\r\nexit /b 0\r\n'
        else:
            content = "#!/bin/bash\nsleep 60\nexit 0\n"

        with tempfile.NamedTemporaryFile("w", suffix=SUFFIX, delete=False, encoding="utf-8") as tf:
            tf.write(content)
            script = tf.name

        try:
            r = ex.execute(script, confirm_execute=True, timeout=2)
            assert r.status == ExecutionStatus.TIMEOUT, f"应超时，实得 {r.status}"
            assert r.timed_out is True
            assert r.exit_code is None
        finally:
            os.remove(script)

    def test_audit_id_populated(self):
        """成功执行后 audit_id 已填充。"""
        ex = HostExecutor()
        with tempfile.NamedTemporaryFile("w", suffix=SUFFIX, delete=False, encoding="utf-8") as tf:
            tf.write(GOOD_SCRIPT)
            script = tf.name

        try:
            r = ex.execute(script, confirm_execute=True)
            assert r.audit_id, "audit_id 不应为空"
            assert r.audit_id.startswith("EXEC-")
        finally:
            os.remove(script)


class TestHostExecutorWithMock:
    """Mock subprocess 测试——不受平台限制。"""

    def test_run_script_mocked_success(self):
        """Mock subprocess.Popen → SUCCESS。"""
        ex = HostExecutor()
        with mock.patch("subprocess.Popen") as m_popen:
            mock_proc = mock.MagicMock()
            mock_proc.communicate.return_value = ("mocked output", "")
            mock_proc.returncode = 0
            mock_proc.pid = 99999
            m_popen.return_value = mock_proc
            r = ex._run_script("/fake/script.sh", timeout=30)
            assert r.status == ExecutionStatus.SUCCESS
            assert r.exit_code == 0
            assert "mocked output" in r.stdout
            assert r.timed_out is False

    def test_run_script_mocked_failure(self):
        """Mock subprocess.Popen → FAILED。"""
        ex = HostExecutor()
        with mock.patch("subprocess.Popen") as m_popen:
            mock_proc = mock.MagicMock()
            mock_proc.communicate.return_value = ("", "something broke")
            mock_proc.returncode = 42
            mock_proc.pid = 99999
            m_popen.return_value = mock_proc
            r = ex._run_script("/fake/script.sh", timeout=30)
            assert r.status == ExecutionStatus.FAILED
            assert r.exit_code == 42
            assert r.error and "退出码" in r.error

    def test_run_script_mocked_timeout(self):
        """Mock subprocess.Popen + communicate → TimeoutExpired → TIMEOUT。"""
        import subprocess

        ex = HostExecutor()
        with mock.patch("subprocess.Popen") as m_popen:
            mock_proc = mock.MagicMock()
            mock_proc.pid = 99999
            # communicate 第一次抛 TimeoutExpired → 触发超时分支
            mock_proc.communicate.side_effect = [
                subprocess.TimeoutExpired(
                    cmd=["/fake/script.sh"],
                    timeout=5,
                    output="partial output",
                ),
                # 第二次调用（收集已产出）→ 返回部分输出
                ("partial output", ""),
            ]
            m_popen.return_value = mock_proc
            r = ex._run_script("/fake/script.sh", timeout=5)
            assert r.status == ExecutionStatus.TIMEOUT
            assert r.timed_out is True
            assert r.exit_code is None


class TestGetExecutorHost:
    """get_executor 工厂注册测试。"""

    def test_get_executor_host_returns_host_executor(self):
        """get_executor("host") → HostExecutor 实例。"""
        ex = get_executor("host")
        assert isinstance(ex, HostExecutor)
        assert ex.name == "HostExecutor"

    def test_get_executor_docker_still_works(self):
        """get_executor("docker") → DockerSandboxExecutor（不破 v0.0.38）。"""
        ex = get_executor("docker")
        from lightshield.sandbox.docker_executor import DockerSandboxExecutor

        assert isinstance(ex, DockerSandboxExecutor)

    def test_get_executor_invalid_backend_raises(self):
        """不支持的 backend → ValueError。"""
        with pytest.raises(ValueError, match="不支持"):
            get_executor("nonexistent_backend")
