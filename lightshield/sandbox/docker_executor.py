"""LightShield Docker 沙箱执行器

在隔离的 Docker 容器中执行加固脚本，绝不在宿主机直接运行（合规 R1）。

隔离措施（默认即最严格）：
  - --network none：容器内无网络，脚本无法对外发起连接/攻击（R1 核心防线）
  - --memory / --cpus / --pids-limit：资源上限，防内存炸弹 / fork 炸弹拖垮宿主机
  - --rm：容器即用即销毁，不残留状态
  - -v <script>:...:ro：脚本以只读方式挂载，容器内无法篡改
  - --security-opt no-new-privileges：禁止提权
  - 超时强制终止 + best-effort 容器清理

脚本内的 R4 交互式所有权确认（read -r -p ... yes/no）由沙箱自动应答——
操作员已在 CLI 层通过 --execute 二次确认，沙箱内无需重复人工输入。

用法：
    from lightshield.sandbox.docker_executor import DockerSandboxExecutor
    executor = DockerSandboxExecutor()
    if executor.is_available():
        result = executor.execute("reports/harden_x.sh", confirm_execute=True)
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
import uuid

# Allow direct script execution (python lightshield/sandbox/docker_executor.py)
if __package__ in {None, ""}:
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from lightshield.sandbox.base import ExecutionResult, ExecutionStatus, SandboxExecutor
from lightshield.utils.constants import (
    SANDBOX_CONTAINER_SCRIPT_PATH,
    SANDBOX_DEFAULT_CPUS,
    SANDBOX_DEFAULT_IMAGE,
    SANDBOX_DEFAULT_MEMORY,
    SANDBOX_DEFAULT_NETWORK,
    SANDBOX_DEFAULT_PIDS_LIMIT,
    SANDBOX_DEFAULT_TIMEOUT,
)
from lightshield.utils.logger import get_logger

# 自动应答脚本内的交互式确认（read -r -p ...）。
# 加固脚本的所有权阻断门检查 `[ "$_answer" != "yes" ]`，喂入足量 "yes" 行即可放行；
# 操作员已在 CLI 层 --execute 二次确认，此处不重复人工输入。
_SANDBOX_STDIN: str = "yes\n" * 16


class DockerSandboxExecutor(SandboxExecutor):
    """基于 Docker 容器隔离的沙箱执行器。

    能力：在即用即销毁、无网络、资源受限的容器中执行加固脚本并捕获输出。
    """

    def __init__(
        self,
        image: str = SANDBOX_DEFAULT_IMAGE,
        docker_path: str = "docker",
        timeout: int = SANDBOX_DEFAULT_TIMEOUT,
        memory: str = SANDBOX_DEFAULT_MEMORY,
        cpus: str = SANDBOX_DEFAULT_CPUS,
        pids_limit: int = SANDBOX_DEFAULT_PIDS_LIMIT,
        network: str = SANDBOX_DEFAULT_NETWORK,
    ):
        """初始化 Docker 沙箱执行器。

        Args:
            image: 容器镜像（需含 bash；默认 ubuntu:22.04）
            docker_path: docker 可执行文件路径
            timeout: 默认执行超时秒数
            memory: 容器内存上限（如 "256m"）
            cpus: 容器 CPU 上限（如 "1.0"）
            pids_limit: 容器进程数上限
            network: 容器网络模式（默认 "none"，R1 防线）
        """
        super().__init__(name="DockerSandboxExecutor", timeout=timeout)
        self._image = image
        self._docker_path = docker_path
        self._memory = memory
        self._cpus = cpus
        self._pids_limit = pids_limit
        self._network = network
        self._logger = get_logger()

    # =========================================================================
    # SandboxExecutor 实现
    # =========================================================================

    def is_available(self) -> bool:
        """检查 Docker 是否可用（docker --version 返回 0）。"""
        try:
            completed = subprocess.run(
                [self._docker_path, "--version"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            return completed.returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired, PermissionError, OSError):
            return False

    def _run_script(self, abs_script_path: str, *, timeout: int) -> ExecutionResult:
        """在 Docker 容器中执行脚本并捕获输出。"""
        container_name = f"lightshield-sandbox-{uuid.uuid4().hex[:12]}"
        cmd = self._build_command(abs_script_path, container_name)
        self._logger.info("sandbox", f"docker 执行: {' '.join(cmd)}")

        start = time.monotonic()
        try:
            completed = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                input=_SANDBOX_STDIN,
            )
            duration = round(time.monotonic() - start, 2)
        except subprocess.TimeoutExpired as exc:
            self._kill_container(container_name)
            return ExecutionResult(
                status=ExecutionStatus.TIMEOUT,
                script_path=abs_script_path,
                sandbox=f"docker:{self._image}",
                stdout=_as_text(exc.stdout),
                stderr=_as_text(exc.stderr),
                duration_seconds=float(timeout),
                timed_out=True,
                error=f"沙箱执行超时（{timeout}s），已强制终止容器",
            )
        except FileNotFoundError:
            return ExecutionResult(
                status=ExecutionStatus.SANDBOX_UNAVAILABLE,
                script_path=abs_script_path,
                sandbox=f"docker:{self._image}",
                error=f"Docker 未安装或路径错误: {self._docker_path}",
            )
        except Exception as exc:  # noqa: BLE001 — 兜底：任何执行异常都转为结构化结果，不向上抛
            self._logger.error("sandbox", "docker 执行异常", exception=exc)
            return ExecutionResult(
                status=ExecutionStatus.ERROR,
                script_path=abs_script_path,
                sandbox=f"docker:{self._image}",
                duration_seconds=round(time.monotonic() - start, 2),
                error=f"沙箱执行异常: {exc}",
            )

        status = ExecutionStatus.SUCCESS if completed.returncode == 0 else ExecutionStatus.FAILED
        return ExecutionResult(
            status=status,
            script_path=abs_script_path,
            sandbox=f"docker:{self._image}",
            exit_code=completed.returncode,
            stdout=completed.stdout or "",
            stderr=completed.stderr or "",
            duration_seconds=duration,
            error=None if status == ExecutionStatus.SUCCESS else f"脚本退出码非 0: {completed.returncode}",
        )

    # =========================================================================
    # 命令构造与清理
    # =========================================================================

    def _build_command(self, abs_script_path: str, container_name: str) -> list[str]:
        """构造 docker run 命令（最严格隔离参数）。

        Args:
            abs_script_path: 脚本绝对路径（execute() 已校验）
            container_name: 容器名（用于超时清理）

        Returns:
            docker run 命令参数列表（通过 subprocess 列表形式调用，无 shell 注入风险）
        """
        return [
            self._docker_path,
            "run",
            "--rm",  # 即用即销毁
            "-i",  # 保持 stdin，供自动应答脚本内交互确认
            "--name",
            container_name,
            "--network",
            self._network,  # R1：默认 none，容器无网络
            "--memory",
            self._memory,  # 内存上限
            "--cpus",
            self._cpus,  # CPU 上限
            "--pids-limit",
            str(self._pids_limit),  # 进程数上限（防 fork 炸弹）
            "--security-opt",
            "no-new-privileges",  # 禁止提权
            "-v",
            f"{abs_script_path}:{SANDBOX_CONTAINER_SCRIPT_PATH}:ro",  # 脚本只读挂载
            "-w",
            "/sandbox",
            self._image,
            "bash",
            SANDBOX_CONTAINER_SCRIPT_PATH,
        ]

    def _kill_container(self, container_name: str) -> None:
        """超时后 best-effort 强制终止容器（--rm 会随之清理）。"""
        try:
            subprocess.run(
                [self._docker_path, "kill", container_name],
                capture_output=True,
                text=True,
                timeout=10,
            )
        except Exception:  # noqa: BLE001 — 清理失败不影响主流程，仅记录
            self._logger.warning("sandbox", f"超时容器清理失败（可能已退出）: {container_name}")


def _as_text(value: str | bytes | None) -> str:
    """将 subprocess 捕获的输出统一为文本（超时分支可能返回 bytes）。"""
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value


# =============================================================================
# 自检
# =============================================================================

if __name__ == "__main__":
    from unittest.mock import patch

    print("=== DockerSandboxExecutor 自检 ===")

    executor = DockerSandboxExecutor()
    assert executor.name == "DockerSandboxExecutor"
    print(f"[OK] 名称: {executor.name}")

    # 1. 命令构造——验证隔离参数齐全
    cmd = executor._build_command("/abs/harden.sh", "test-container")
    assert "--network" in cmd and "none" in cmd, "缺少 --network none（R1 防线）"
    assert "--rm" in cmd, "缺少 --rm"
    assert "--memory" in cmd, "缺少内存限制"
    assert "--pids-limit" in cmd, "缺少进程数限制"
    assert "no-new-privileges" in cmd, "缺少提权禁用"
    assert f"/abs/harden.sh:{SANDBOX_CONTAINER_SCRIPT_PATH}:ro" in cmd, "脚本未只读挂载"
    print("[OK] 命令隔离参数齐全: network=none + rm + memory + pids-limit + ro 挂载")

    # 2. is_available —— mock docker --version 成功
    fake_ok = type("R", (), {"returncode": 0, "stdout": "Docker version 25", "stderr": ""})()
    with patch("lightshield.sandbox.docker_executor.subprocess.run", return_value=fake_ok):
        assert executor.is_available() is True
    print("[OK] is_available（docker 存在）→ True")

    # 3. is_available —— docker 未安装
    with patch("lightshield.sandbox.docker_executor.subprocess.run", side_effect=FileNotFoundError):
        assert executor.is_available() is False
    print("[OK] is_available（docker 缺失）→ False")

    # 4. _as_text 兼容 bytes/str/None
    assert _as_text(b"hello") == "hello"
    assert _as_text("world") == "world"
    assert _as_text(None) == ""
    print("[OK] _as_text 兼容 bytes/str/None")

    print("=== DockerSandboxExecutor: ALL PASSED ===")
