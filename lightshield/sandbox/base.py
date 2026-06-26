"""LightShield 沙箱执行器抽象基类

v0.0.38：为"自动加固"（v0.0.40）铺路——提供在隔离环境中安全执行加固脚本的统一接口。
v0.0.40：扩展为双模式——隔离预检执行（Docker 后端）与真机应用执行（Host 后端）。

与 harden/base.py 的分工：
  - HardenBase.generate() 负责"生成"加固脚本（默认不执行）。
  - SandboxExecutor.execute() 负责执行这些脚本——
    · DRY_RUN 模式：隔离容器中预检（DockerSandboxExecutor，backend="docker"）
    · APPLY 模式：宿主机本机执行（HostExecutor，backend="host"，v0.0.40 新增）
  二者解耦，构成闭环：生成 → 审阅 → DRY_RUN 预检 → APPLY 真机执行 → 复扫验证。

设计原则（合规）：
  - DRY_RUN（backend="docker"）：锁死容器（--network none）中预检，不改系统（R1）。
  - APPLY（backend="host"）：宿主机本机执行防御命令，以用户当前权限运行（R1/R4）。
  - 执行是危险操作，必须显式 confirm_execute=True 才放行（防误执行，对齐 R4 双确认）。
  - 每次执行审计留痕（logger.audit_harden_action）。
  - 超时强制终止 + 完整输出捕获。

新增沙箱后端只需：
  1. 继承 SandboxExecutor
  2. 实现 is_available() 与 _run_script() 两个抽象方法
  3. 在 sandbox/__init__.py 的 get_executor() 工厂中注册

用法：
    from lightshield.sandbox import get_executor
    # DRY_RUN（预检）
    executor = get_executor("docker")
    # APPLY（真机执行）
    executor = get_executor("host")
    result = executor.execute("reports/harden_x.sh", confirm_execute=True)
    print(result.status, result.exit_code)
"""

from __future__ import annotations

import os
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from lightshield.utils.constants import (
    SANDBOX_DEFAULT_TIMEOUT,
    SANDBOX_MAX_SCRIPT_BYTES,
)

# =============================================================================
# 数据结构
# =============================================================================


class ExecutionStatus(Enum):
    """沙箱执行状态。"""

    SUCCESS = "success"  # 脚本执行完成，退出码 0
    FAILED = "failed"  # 脚本执行完成，退出码非 0
    TIMEOUT = "timeout"  # 超时被强制终止
    SANDBOX_UNAVAILABLE = "sandbox_unavailable"  # 沙箱后端不可用（如 Docker 未安装）
    REJECTED = "rejected"  # 前置安全校验拒绝（未确认/脚本非法）
    ERROR = "error"  # 执行器内部错误


class SandboxSecurityError(Exception):
    """沙箱安全校验失败异常——脚本路径非法或体积超限时抛出。"""

    def __init__(self, reason: str):
        """初始化异常。

        Args:
            reason: 拒绝原因（中文）
        """
        self.reason = reason
        super().__init__(f"沙箱安全校验失败: {reason}")


@dataclass
class ExecutionResult:
    """沙箱执行结果统一数据结构——所有 SandboxExecutor 子类返回此格式。

    Attributes:
        status: 执行状态
        script_path: 被执行的脚本路径
        sandbox: 使用的沙箱后端标识（如 "docker:ubuntu:22.04"）
        exit_code: 脚本退出码（未执行时为 None）
        stdout: 标准输出（可能被截断）
        stderr: 标准错误（可能被截断）
        duration_seconds: 执行耗时
        timed_out: 是否因超时被终止
        audit_id: 关联审计日志的 ID
        error: 错误信息（status 非 SUCCESS 时填充）
    """

    status: ExecutionStatus
    script_path: str
    sandbox: str = ""
    exit_code: int | None = None
    stdout: str = ""
    stderr: str = ""
    duration_seconds: float = 0.0
    timed_out: bool = False
    audit_id: str = ""
    error: str | None = None

    def to_dict(self) -> dict:
        """导出为字典，方便报告 / Web API 消费。"""
        return {
            "status": self.status.value,
            "script_path": self.script_path,
            "sandbox": self.sandbox,
            "exit_code": self.exit_code,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "duration_seconds": self.duration_seconds,
            "timed_out": self.timed_out,
            "audit_id": self.audit_id,
            "error": self.error,
        }


# =============================================================================
# 抽象基类
# =============================================================================


class SandboxExecutor(ABC):
    """所有沙箱执行器的抽象基类。

    采用模板方法模式：公共的 execute() 负责安全闸门 + 校验 + 审计，
    实际的执行委托给子类实现的 _run_script()。

    v0.0.40 双模式：
      - DockerSandboxExecutor：DRY_RUN 预检，锁死容器（--network none），不改系统
      - HostExecutor：APPLY 真机执行，宿主机 subprocess，改真实系统

    核心调度器只依赖此抽象接口，不直接依赖具体执行技术。
    """

    def __init__(self, name: str = "", timeout: int = SANDBOX_DEFAULT_TIMEOUT):
        """初始化沙箱执行器。

        Args:
            name: 执行器名称（用于日志和审计）
            timeout: 默认执行超时秒数
        """
        self.name = name or self.__class__.__name__
        self._timeout = timeout

    # ---- 子类必须实现 ----

    @abstractmethod
    def is_available(self) -> bool:
        """检查沙箱后端是否可用（如 Docker 守护进程是否运行）。

        Returns:
            True 表示后端就绪，可执行脚本
        """
        ...

    @abstractmethod
    def _run_script(self, abs_script_path: str, *, timeout: int) -> ExecutionResult:
        """在隔离沙箱中执行脚本——子类核心实现。

        execute() 已完成所有前置校验（confirm/存在性/体积/可用性），
        子类只需专注于"如何在隔离环境中运行并捕获输出"。

        Args:
            abs_script_path: 已校验通过的脚本绝对路径
            timeout: 执行超时秒数

        Returns:
            ExecutionResult 结构化结果
        """
        ...

    # ---- 模板方法（公共流程，子类不应重写）----

    def execute(
        self,
        script_path: str,
        *,
        confirm_execute: bool = False,
        timeout: int | None = None,
    ) -> ExecutionResult:
        """在隔离沙箱中执行脚本——主入口。

        流程：
        1. 危险操作闸门：confirm_execute 必须为 True（防误执行）。
        2. 脚本安全校验：存在 + 是文件 + 体积未超限。
        3. 沙箱可用性检查：后端不可用则返回 SANDBOX_UNAVAILABLE。
        4. 审计开始 → 委托 _run_script() → 审计结束。

        Args:
            script_path: 待执行脚本路径
            confirm_execute: 必须显式传 True 才放行（对齐 R4 双确认）
            timeout: 覆盖默认超时（秒）

        Returns:
            ExecutionResult 结构化结果（任何失败都返回结果对象，不抛异常）
        """
        from lightshield.utils.logger import get_logger

        logger = get_logger()
        effective_timeout = timeout or self._timeout

        # ---- Step 1: 危险操作闸门 ----
        if not confirm_execute:
            return ExecutionResult(
                status=ExecutionStatus.REJECTED,
                script_path=script_path,
                sandbox=self.name,
                error="未显式确认执行（需 confirm_execute=True）。沙箱执行属危险操作，已拒绝。",
            )

        # ---- Step 2: 脚本安全校验 ----
        try:
            abs_script = self._validate_script(script_path)
        except SandboxSecurityError as exc:
            logger.warning("sandbox", f"脚本校验拒绝: {exc.reason}")
            return ExecutionResult(
                status=ExecutionStatus.REJECTED,
                script_path=script_path,
                sandbox=self.name,
                error=exc.reason,
            )

        # ---- Step 3: 沙箱可用性 ----
        if not self.is_available():
            error_msg = f"沙箱后端不可用：{self.name}。请确认 Docker 已安装并正在运行。"
            logger.error("sandbox", error_msg)
            return ExecutionResult(
                status=ExecutionStatus.SANDBOX_UNAVAILABLE,
                script_path=script_path,
                sandbox=self.name,
                error=error_msg,
            )

        # ---- Step 4: 审计 + 执行 ----
        audit_id = self._gen_audit_id()
        self._audit(script_path, f"sandbox_execute_start id={audit_id}", "started")
        logger.info("sandbox", f"开始沙箱执行: script={script_path} id={audit_id} timeout={effective_timeout}s")

        result = self._run_script(abs_script, timeout=effective_timeout)
        result.audit_id = audit_id

        self._audit(
            script_path,
            f"sandbox_execute_end id={audit_id}",
            f"status={result.status.value} exit={result.exit_code} duration={result.duration_seconds}s",
        )
        logger.info(
            "sandbox",
            f"沙箱执行结束: id={audit_id} status={result.status.value} "
            f"exit={result.exit_code} duration={result.duration_seconds}s",
        )
        return result

    # ---- 共享 helper ----

    @staticmethod
    def _validate_script(script_path: str) -> str:
        """校验脚本路径合法性，返回绝对路径。

        Args:
            script_path: 待校验路径

        Returns:
            校验通过的绝对路径

        Raises:
            SandboxSecurityError: 路径为空 / 不存在 / 非文件 / 体积超限
        """
        if not script_path or not script_path.strip():
            raise SandboxSecurityError("脚本路径为空")

        abs_path = os.path.abspath(script_path)
        if not os.path.exists(abs_path):
            raise SandboxSecurityError(f"脚本不存在: {script_path}")
        if not os.path.isfile(abs_path):
            raise SandboxSecurityError(f"目标不是文件: {script_path}")

        size = os.path.getsize(abs_path)
        if size > SANDBOX_MAX_SCRIPT_BYTES:
            raise SandboxSecurityError(f"脚本体积 {size} 字节超过上限 {SANDBOX_MAX_SCRIPT_BYTES} 字节")

        return abs_path

    @staticmethod
    def _gen_audit_id() -> str:
        """生成沙箱执行审计 ID：EXEC-YYYYMMDD-HHMMSS-xxxxxx。"""
        return f"EXEC-{datetime.now().strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:6]}"

    @staticmethod
    def _audit(target: str, action: str, result: str) -> None:
        """记录沙箱执行到审计日志（复用加固审计通道，合规 R4）。"""
        from lightshield.utils.logger import get_logger

        get_logger().audit_harden_action(target, action, result)


# =============================================================================
# 自检
# =============================================================================

if __name__ == "__main__":
    import tempfile

    print("=== SandboxExecutor 自检 ===")

    # 用一个最小可实例化子类验证模板方法逻辑（不依赖真实 Docker）
    class _FakeExecutor(SandboxExecutor):
        """自检用假执行器——_run_script 直接返回成功，不触碰真实沙箱。"""

        def __init__(self, available: bool = True):
            super().__init__(name="FakeExecutor")
            self._available = available

        def is_available(self) -> bool:
            return self._available

        def _run_script(self, abs_script_path: str, *, timeout: int) -> ExecutionResult:
            return ExecutionResult(
                status=ExecutionStatus.SUCCESS,
                script_path=abs_script_path,
                sandbox="fake",
                exit_code=0,
                stdout="ok",
                duration_seconds=0.01,
            )

    # 1. 未确认 → REJECTED
    ex = _FakeExecutor()
    r = ex.execute("whatever.sh")
    assert r.status == ExecutionStatus.REJECTED, f"未确认应拒绝，实得 {r.status}"
    print("[OK] 未确认执行 → REJECTED（危险操作闸门）")

    # 2. 脚本不存在 → REJECTED
    r = ex.execute("/nonexistent/path/x.sh", confirm_execute=True)
    assert r.status == ExecutionStatus.REJECTED
    assert r.error and "不存在" in r.error
    print("[OK] 脚本不存在 → REJECTED")

    # 3. 后端不可用 → SANDBOX_UNAVAILABLE
    with tempfile.NamedTemporaryFile("w", suffix=".sh", delete=False) as tf:
        tf.write("#!/bin/bash\necho hi\n")
        script = tf.name
    try:
        ex_down = _FakeExecutor(available=False)
        r = ex_down.execute(script, confirm_execute=True)
        assert r.status == ExecutionStatus.SANDBOX_UNAVAILABLE, f"后端不可用应返回 UNAVAILABLE，实得 {r.status}"
        print("[OK] 后端不可用 → SANDBOX_UNAVAILABLE")

        # 4. 正常路径 → SUCCESS + 审计 ID 填充
        r = ex.execute(script, confirm_execute=True)
        assert r.status == ExecutionStatus.SUCCESS, f"应成功，实得 {r.status}"
        assert r.audit_id.startswith("EXEC-"), f"审计 ID 未填充: {r.audit_id}"
        print(f"[OK] 正常执行 → SUCCESS，审计 ID={r.audit_id}")

        # 5. to_dict 完整性
        d = r.to_dict()
        assert d["status"] == "success"
        assert d["exit_code"] == 0
        assert "stdout" in d
        print("[OK] ExecutionResult.to_dict 完整")

        # 6. 体积超限 → REJECTED
        big = script + ".big"
        with open(big, "w", encoding="utf-8") as f:
            f.write("#\n" + "x" * (SANDBOX_MAX_SCRIPT_BYTES + 10))
        r = ex.execute(big, confirm_execute=True)
        assert r.status == ExecutionStatus.REJECTED
        assert r.error and "超过上限" in r.error
        print("[OK] 脚本体积超限 → REJECTED")
        os.remove(big)
    finally:
        os.remove(script)

    print("=== SandboxExecutor: ALL PASSED ===")
