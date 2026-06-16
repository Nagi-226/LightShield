"""沙箱执行器单元测试（v0.0.38）。

覆盖 LightShield R1 + R4 合规防线：
- execute() 危险操作闸门：未确认 → REJECTED。
- 脚本安全校验：不存在 / 非文件 / 超体积 → REJECTED。
- 沙箱不可用 → SANDBOX_UNAVAILABLE。
- Docker 命令隔离参数齐全（--network none / --rm / 资源限制 / 只读挂载）。
- _run_script mock subprocess 验证 SUCCESS / FAILED / TIMEOUT / 异常分支。
- 工厂 get_executor 与 core.execute_hardening 钩子。

全部通过 mock，不依赖真实 Docker。
"""

from __future__ import annotations

import os
import subprocess
import sys
from types import SimpleNamespace
from unittest.mock import patch

import pytest

# Allow pytest from tests/ directory.
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from lightshield.sandbox import DockerSandboxExecutor, get_executor
from lightshield.sandbox.base import (
    ExecutionResult,
    ExecutionStatus,
    SandboxExecutor,
    SandboxSecurityError,
)
from lightshield.sandbox.docker_executor import _SANDBOX_STDIN, _as_text
from lightshield.utils.constants import SANDBOX_CONTAINER_SCRIPT_PATH, SANDBOX_MAX_SCRIPT_BYTES

DOCKER_RUN = "lightshield.sandbox.docker_executor.subprocess.run"


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def script(tmp_path) -> str:
    """创建一个真实的临时加固脚本文件。"""
    path = tmp_path / "harden_test.sh"
    path.write_text("#!/bin/bash\necho 'hardening...'\n", encoding="utf-8")
    return str(path)


@pytest.fixture
def executor() -> DockerSandboxExecutor:
    """创建 Docker 执行器（不依赖真实 docker）。"""
    return DockerSandboxExecutor()


def _fake_proc(returncode: int = 0, stdout: str = "", stderr: str = "") -> SimpleNamespace:
    """构造一个假的 subprocess.run 返回对象。"""
    return SimpleNamespace(returncode=returncode, stdout=stdout, stderr=stderr)


# =============================================================================
# 数据结构
# =============================================================================


class TestExecutionResult:
    """ExecutionResult / ExecutionStatus 测试。"""

    def test_to_dict_round_trip(self) -> None:
        """to_dict 应包含全部关键字段。"""
        result = ExecutionResult(
            status=ExecutionStatus.SUCCESS,
            script_path="x.sh",
            sandbox="docker:ubuntu:22.04",
            exit_code=0,
            stdout="ok",
            duration_seconds=1.5,
        )
        d = result.to_dict()
        assert d["status"] == "success"
        assert d["exit_code"] == 0
        assert d["stdout"] == "ok"
        assert d["sandbox"] == "docker:ubuntu:22.04"
        assert d["duration_seconds"] == 1.5

    def test_status_values(self) -> None:
        """状态枚举值稳定（被 to_dict / Web API 依赖）。"""
        assert ExecutionStatus.SUCCESS.value == "success"
        assert ExecutionStatus.FAILED.value == "failed"
        assert ExecutionStatus.TIMEOUT.value == "timeout"
        assert ExecutionStatus.SANDBOX_UNAVAILABLE.value == "sandbox_unavailable"
        assert ExecutionStatus.REJECTED.value == "rejected"
        assert ExecutionStatus.ERROR.value == "error"


# =============================================================================
# 抽象基类 / 模板方法 execute()
# =============================================================================


class TestExecuteGate:
    """execute() 危险操作闸门 + 前置校验测试。"""

    def test_cannot_instantiate_abstract(self) -> None:
        """SandboxExecutor 是抽象类，不可直接实例化。"""
        with pytest.raises(TypeError):
            SandboxExecutor()  # type: ignore[abstract]

    def test_reject_without_confirm(self, executor: DockerSandboxExecutor, script: str) -> None:
        """未传 confirm_execute=True → REJECTED，且不触碰 subprocess。"""
        with patch(DOCKER_RUN) as mocked:
            result = executor.execute(script)
        assert result.status == ExecutionStatus.REJECTED
        assert result.error and "confirm_execute" in result.error
        assert mocked.called is False, "未确认不得触发任何 subprocess"

    def test_reject_nonexistent_script(self, executor: DockerSandboxExecutor) -> None:
        """脚本不存在 → REJECTED。"""
        result = executor.execute("/no/such/file.sh", confirm_execute=True)
        assert result.status == ExecutionStatus.REJECTED
        assert result.error and "不存在" in result.error

    def test_reject_directory(self, executor: DockerSandboxExecutor, tmp_path) -> None:
        """目标是目录而非文件 → REJECTED。"""
        result = executor.execute(str(tmp_path), confirm_execute=True)
        assert result.status == ExecutionStatus.REJECTED
        assert result.error and "不是文件" in result.error

    def test_reject_empty_path(self, executor: DockerSandboxExecutor) -> None:
        """空路径 → REJECTED。"""
        result = executor.execute("   ", confirm_execute=True)
        assert result.status == ExecutionStatus.REJECTED

    def test_reject_oversized_script(self, executor: DockerSandboxExecutor, tmp_path) -> None:
        """脚本体积超限 → REJECTED。"""
        big = tmp_path / "big.sh"
        big.write_text("#\n" + "x" * (SANDBOX_MAX_SCRIPT_BYTES + 100), encoding="utf-8")
        result = executor.execute(str(big), confirm_execute=True)
        assert result.status == ExecutionStatus.REJECTED
        assert result.error and "超过上限" in result.error

    def test_sandbox_unavailable(self, executor: DockerSandboxExecutor, script: str) -> None:
        """Docker 不可用 → SANDBOX_UNAVAILABLE（校验通过但后端缺失）。"""
        with patch(DOCKER_RUN, side_effect=FileNotFoundError):
            result = executor.execute(script, confirm_execute=True)
        assert result.status == ExecutionStatus.SANDBOX_UNAVAILABLE

    def test_validate_script_raises(self) -> None:
        """_validate_script 对非法输入抛 SandboxSecurityError。"""
        with pytest.raises(SandboxSecurityError):
            SandboxExecutor._validate_script("")
        with pytest.raises(SandboxSecurityError):
            SandboxExecutor._validate_script("/definitely/not/here.sh")


# =============================================================================
# DockerSandboxExecutor.is_available
# =============================================================================


class TestIsAvailable:
    """Docker 可用性探测测试。"""

    def test_available_when_docker_present(self, executor: DockerSandboxExecutor) -> None:
        """Docker --version 返回 0 → 可用。"""
        with patch(DOCKER_RUN, return_value=_fake_proc(returncode=0, stdout="Docker version 25")):
            assert executor.is_available() is True

    def test_unavailable_when_not_installed(self, executor: DockerSandboxExecutor) -> None:
        """Docker 未安装（FileNotFoundError）→ 不可用。"""
        with patch(DOCKER_RUN, side_effect=FileNotFoundError):
            assert executor.is_available() is False

    def test_unavailable_on_timeout(self, executor: DockerSandboxExecutor) -> None:
        """Docker --version 超时 → 不可用（不崩溃）。"""
        with patch(DOCKER_RUN, side_effect=subprocess.TimeoutExpired(cmd=["docker"], timeout=10)):
            assert executor.is_available() is False

    def test_unavailable_on_nonzero(self, executor: DockerSandboxExecutor) -> None:
        """Docker --version 非 0 → 不可用。"""
        with patch(DOCKER_RUN, return_value=_fake_proc(returncode=1)):
            assert executor.is_available() is False


# =============================================================================
# 命令构造（隔离参数）
# =============================================================================


class TestBuildCommand:
    """docker run 命令隔离参数测试（R1 防线）。"""

    def test_isolation_flags_present(self, executor: DockerSandboxExecutor) -> None:
        """命令必须包含所有隔离参数。"""
        cmd = executor._build_command("/abs/harden.sh", "ctr-name")
        # R1：无网络
        assert "--network" in cmd
        assert cmd[cmd.index("--network") + 1] == "none"
        # 即用即销毁
        assert "--rm" in cmd
        # stdin 保持（自动应答脚本内确认）
        assert "-i" in cmd
        # 资源限制
        assert "--memory" in cmd
        assert "--cpus" in cmd
        assert "--pids-limit" in cmd
        # 禁止提权
        assert "no-new-privileges" in cmd
        # 脚本只读挂载
        assert f"/abs/harden.sh:{SANDBOX_CONTAINER_SCRIPT_PATH}:ro" in cmd
        # 容器名（超时清理用）
        assert "ctr-name" in cmd
        # 入口：bash 执行容器内脚本
        assert cmd[-2:] == ["bash", SANDBOX_CONTAINER_SCRIPT_PATH]

    def test_custom_image_and_limits(self) -> None:
        """自定义镜像 / 资源限制应反映在命令中。"""
        ex = DockerSandboxExecutor(image="debian:slim", memory="128m", cpus="0.5", network="none")
        cmd = ex._build_command("/x.sh", "c1")
        assert "debian:slim" in cmd
        assert "128m" in cmd
        assert "0.5" in cmd


# =============================================================================
# _run_script 执行分支
# =============================================================================


class TestRunScript:
    """_run_script mock subprocess 分支测试。"""

    def test_success(self, executor: DockerSandboxExecutor) -> None:
        """退出码 0 → SUCCESS，捕获 stdout。"""
        with patch(DOCKER_RUN, return_value=_fake_proc(returncode=0, stdout="加固完成")) as mocked:
            result = executor._run_script("/abs/x.sh", timeout=60)
        assert result.status == ExecutionStatus.SUCCESS
        assert result.exit_code == 0
        assert result.stdout == "加固完成"
        assert result.sandbox.startswith("docker:")
        # 验证自动应答 stdin 被喂入
        assert mocked.call_args.kwargs["input"] == _SANDBOX_STDIN
        assert "yes" in _SANDBOX_STDIN

    def test_nonzero_exit_failed(self, executor: DockerSandboxExecutor) -> None:
        """退出码非 0 → FAILED，记录退出码。"""
        with patch(DOCKER_RUN, return_value=_fake_proc(returncode=2, stderr="boom")):
            result = executor._run_script("/abs/x.sh", timeout=60)
        assert result.status == ExecutionStatus.FAILED
        assert result.exit_code == 2
        assert result.error and "2" in result.error
        assert result.stderr == "boom"

    def test_timeout(self, executor: DockerSandboxExecutor) -> None:
        """超时 → TIMEOUT，timed_out=True，并尝试清理容器。"""
        timeout_exc = subprocess.TimeoutExpired(cmd=["docker"], timeout=30, output="部分输出", stderr="")
        # 第一次调用（docker run）抛超时；第二次调用（docker kill）正常返回。
        with patch(DOCKER_RUN, side_effect=[timeout_exc, _fake_proc(returncode=0)]) as mocked:
            result = executor._run_script("/abs/x.sh", timeout=30)
        assert result.status == ExecutionStatus.TIMEOUT
        assert result.timed_out is True
        assert result.error and "超时" in result.error
        assert result.stdout == "部分输出"
        # 验证触发了容器清理（docker kill）
        assert any("kill" in str(call) for call in mocked.call_args_list), "超时应触发容器清理"

    def test_docker_missing_midway(self, executor: DockerSandboxExecutor) -> None:
        """执行时 docker 缺失 → SANDBOX_UNAVAILABLE。"""
        with patch(DOCKER_RUN, side_effect=FileNotFoundError):
            result = executor._run_script("/abs/x.sh", timeout=60)
        assert result.status == ExecutionStatus.SANDBOX_UNAVAILABLE

    def test_generic_exception_error(self, executor: DockerSandboxExecutor) -> None:
        """其他异常 → ERROR（不向上抛）。"""
        with patch(DOCKER_RUN, side_effect=RuntimeError("weird")):
            result = executor._run_script("/abs/x.sh", timeout=60)
        assert result.status == ExecutionStatus.ERROR
        assert result.error and "weird" in result.error


# =============================================================================
# execute() 端到端（mock）
# =============================================================================


class TestExecuteEndToEnd:
    """execute() 完整流程（版本探测 + 执行）测试。"""

    def test_full_success_path(self, executor: DockerSandboxExecutor, script: str) -> None:
        """可用 + 执行成功 → SUCCESS，审计 ID 被填充。"""
        # 第一次 subprocess.run = is_available (docker --version)
        # 第二次 subprocess.run = _run_script (docker run)
        with patch(
            DOCKER_RUN,
            side_effect=[_fake_proc(returncode=0, stdout="Docker version 25"), _fake_proc(returncode=0, stdout="done")],
        ):
            result = executor.execute(script, confirm_execute=True, timeout=30)
        assert result.status == ExecutionStatus.SUCCESS
        assert result.audit_id.startswith("EXEC-")
        assert result.stdout == "done"


# =============================================================================
# 工厂
# =============================================================================


class TestFactory:
    """get_executor 工厂测试。"""

    def test_docker_backend(self) -> None:
        """backend='docker' → DockerSandboxExecutor。"""
        ex = get_executor("docker")
        assert isinstance(ex, DockerSandboxExecutor)

    def test_case_insensitive(self) -> None:
        """后端名大小写不敏感。"""
        assert isinstance(get_executor("Docker"), DockerSandboxExecutor)

    def test_unknown_backend_raises(self) -> None:
        """未知后端 → ValueError。"""
        with pytest.raises(ValueError, match="不支持的沙箱后端"):
            get_executor("qemu")

    def test_kwargs_passthrough(self) -> None:
        """构造参数透传。"""
        ex = get_executor("docker", image="alpine:bash")
        assert isinstance(ex, DockerSandboxExecutor)
        assert ex._image == "alpine:bash"


# =============================================================================
# _as_text helper
# =============================================================================


class TestAsText:
    """_as_text 输出归一化测试。"""

    def test_bytes(self) -> None:
        assert _as_text(b"hello") == "hello"

    def test_str(self) -> None:
        assert _as_text("world") == "world"

    def test_none(self) -> None:
        assert _as_text(None) == ""

    def test_invalid_bytes_replaced(self) -> None:
        """非法字节序列应以替换字符兜底，不抛异常。"""
        assert _as_text(b"\xff\xfe") != ""


# =============================================================================
# core.execute_hardening 钩子
# =============================================================================


class TestCoreHook:
    """LightShieldCore.execute_hardening 集成测试。"""

    def test_reject_without_confirm(self) -> None:
        """Core 钩子未确认 → REJECTED（默认 Docker 执行器，闸门先拦截）。"""
        from lightshield.core import LightShieldCore

        core = LightShieldCore()
        result = core.execute_hardening("/whatever.sh", confirm_execute=False)
        assert result.status == ExecutionStatus.REJECTED

    def test_delegates_and_audits(self, script: str) -> None:
        """Core 钩子委托给注入的执行器，并写审计日志。"""
        from lightshield.core import LightShieldCore

        canned = ExecutionResult(
            status=ExecutionStatus.SUCCESS,
            script_path=script,
            sandbox="fake",
            exit_code=0,
            stdout="ok",
        )

        class _Recording(SandboxExecutor):
            def __init__(self):
                super().__init__(name="Recording")
                self.calls: list[str] = []

            def is_available(self) -> bool:
                return True

            def _run_script(self, abs_script_path: str, *, timeout: int) -> ExecutionResult:
                self.calls.append(abs_script_path)
                return canned

        fake = _Recording()
        core = LightShieldCore()
        result = core.execute_hardening(script, confirm_execute=True, executor=fake)

        assert result.status == ExecutionStatus.SUCCESS
        assert len(fake.calls) == 1, "应委托给注入的执行器"
        # 审计日志含 harden_execute 事件
        audit = core.get_audit_log()
        assert any(entry["event"] == "harden_execute" for entry in audit), "应记录 harden_execute 审计"


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
