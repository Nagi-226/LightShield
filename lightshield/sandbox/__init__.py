"""LightShield 沙箱执行子包（v0.0.38）。

在隔离的 Docker 容器中安全执行加固脚本，为 v0.0.40 自动加固闭环铺路。

公共 API：
    SandboxExecutor      — 抽象基类（模板方法：闸门 + 校验 + 审计 + 委托）
    DockerSandboxExecutor — Docker 容器隔离实现
    ExecutionResult      — 执行结果数据结构
    ExecutionStatus      — 执行状态枚举
    SandboxSecurityError — 安全校验异常
    get_executor()       — 后端工厂
"""

from lightshield.sandbox.base import (
    ExecutionResult,
    ExecutionStatus,
    SandboxExecutor,
    SandboxSecurityError,
)
from lightshield.sandbox.docker_executor import DockerSandboxExecutor
from lightshield.sandbox.host_executor import HostExecutor

__all__ = [
    "DockerSandboxExecutor",
    "ExecutionResult",
    "ExecutionStatus",
    "HostExecutor",
    "SandboxExecutor",
    "SandboxSecurityError",
    "get_executor",
]


def get_executor(backend: str = "docker", **kwargs) -> SandboxExecutor:
    """按后端名返回沙箱执行器实例。

    Args:
        backend: 沙箱后端标识
            - "docker" — Docker 隔离容器（DRY_RUN 预检，v0.0.38）
            - "host"  — 宿主机本机执行（APPLY 真机应用，v0.0.40）
        **kwargs: 透传给具体执行器构造函数（timeout 等）

    Returns:
        对应的 SandboxExecutor 子类实例

    Raises:
        ValueError: 不支持的后端名
    """
    backend_normalized = (backend or "").lower().strip()
    if backend_normalized == "docker":
        return DockerSandboxExecutor(**kwargs)
    if backend_normalized == "host":
        return HostExecutor(**kwargs)
    raise ValueError(f"不支持的沙箱后端: {backend}（支持: docker / host）")
