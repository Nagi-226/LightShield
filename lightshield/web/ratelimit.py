"""LightShield Web API — IP 速率限制器。

基于滑动窗口的请求频率限制，从 config.rate_limit_per_hour 读取阈值。
v0.3.1: 内存储存，单进程有效。v2.0.0 可迁移至 Redis。
"""

from __future__ import annotations

import time
from collections import defaultdict


class RateLimiter:
    """滑动窗口 IP 速率限制器。

    每个 IP 在 window_seconds 内最多允许 max_requests 次请求。
    超限后 is_allowed() 返回 False，调用方应返回 429。
    """

    def __init__(self, max_requests: int = 100, window_seconds: int = 3600):
        """初始化限制器。

        Args:
            max_requests: 窗口内最大请求次数（默认 100）
            window_seconds: 滑动窗口秒数（默认 3600 = 1 小时）
        """
        self._max = max_requests
        self._window = window_seconds
        self._store: dict[str, list[float]] = defaultdict(list)

    # ------------------------------------------------------------------
    # 公共接口
    # ------------------------------------------------------------------

    def is_allowed(self, ip: str) -> bool:
        """检查指定 IP 是否允许本次请求。

        此方法有副作用——允许的请求会被记录到窗口中。

        Args:
            ip: 客户端 IP 地址

        Returns:
            True 表示未超限，False 表示已超限
        """
        now = time.time()
        cutoff = now - self._window

        # 清理过期记录
        self._store[ip] = [t for t in self._store[ip] if t > cutoff]

        if len(self._store[ip]) >= self._max:
            return False

        self._store[ip].append(now)
        return True

    def remaining(self, ip: str) -> int:
        """返回指定 IP 在窗口内的剩余请求次数。

        Args:
            ip: 客户端 IP 地址

        Returns:
            剩余次数（≥0）
        """
        return max(0, self._max - len(self._store.get(ip, [])))


# ------------------------------------------------------------------
# 模块级单例——由 app.py 在 create_app() 中初始化
# ------------------------------------------------------------------

_limiter: RateLimiter | None = None


def get_limiter(max_requests: int = 100, window_seconds: int = 3600) -> RateLimiter:
    """获取或创建模块级 RateLimiter 单例。

    首次调用创建实例，后续调用返回同一实例（忽略参数）。

    Args:
        max_requests: 每小时最大请求次数（仅首次调用生效）
        window_seconds: 窗口秒数（仅首次调用生效）

    Returns:
        RateLimiter 实例
    """
    global _limiter
    if _limiter is None:
        _limiter = RateLimiter(max_requests=max_requests, window_seconds=window_seconds)
    return _limiter
