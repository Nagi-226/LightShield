"""LightShield Web API — Session 鉴权模块。

提供 Flask 原生 session（签名 cookie）鉴权：
- 凭证从环境变量 LS_WEB_USERNAME / LS_WEB_PASSWORD 读取，默认 admin/lightshield
- login(username, password) → 校验通过设置 session["user"]
- logout() → 清除 session
- @login_required 装饰器 → 未登录返回 401 JSON
- v0.0.31: 登录暴力破解防护（IP 失败计数 + 指数退避锁定期）

JWT 鉴权留给 v2.0.0，当前 MVP 使用最简单的 session 方案。
"""

from __future__ import annotations

import os
import secrets
import time
from collections.abc import Callable
from functools import wraps

from flask import jsonify, request, session

# ---------------------------------------------------------------------------
# 默认凭证（可被环境变量覆盖）
# ---------------------------------------------------------------------------

DEFAULT_USERNAME = "admin"
DEFAULT_PASSWORD = "lightshield"


def _get_credentials() -> tuple[str, str]:
    """从环境变量读取 Web 登录凭证，不存在时使用默认值。

    Returns:
        (username, password) 元组
    """
    username = os.environ.get("LS_WEB_USERNAME", DEFAULT_USERNAME)
    password = os.environ.get("LS_WEB_PASSWORD", DEFAULT_PASSWORD)
    return username, password


# ---------------------------------------------------------------------------
# 登录暴力破解防护（v0.0.31）
# ---------------------------------------------------------------------------

_login_failures: dict[str, dict] = {}
MAX_FAILURES = 5
BASE_DELAY_SECONDS = 2  # 第 1 次锁定期 2s，第 2 次 4s，... 最大 64s
MAX_DELAY_EXPONENT = 6  # 2^6 = 64s


def _is_login_blocked(ip: str) -> bool:
    """检查指定 IP 是否在登录锁定期内。"""
    record = _login_failures.get(ip)
    if record is None:
        return False
    blocked_until = record.get("blocked_until", 0)
    if blocked_until and time.time() < blocked_until:
        return True
    # 锁定期已过，清除
    if blocked_until:
        record["blocked_until"] = 0
    return False


# ---------------------------------------------------------------------------
# 鉴权操作
# ---------------------------------------------------------------------------


def login(username: str, password: str) -> bool:
    """校验用户名密码，成功则设置 session。

    v0.0.31: 暴力破解防护——每个 IP 最多 5 次连续失败，超过后进入指数退避锁定期。

    Args:
        username: 登录用户名
        password: 登录密码

    Returns:
        True 表示登录成功，False 表示凭证错误或已被锁定
    """
    ip = request.remote_addr or "127.0.0.1"

    # 已被锁定则直接拒绝
    if _is_login_blocked(ip):
        return False

    valid_user, valid_pass = _get_credentials()
    if secrets.compare_digest(username, valid_user) and secrets.compare_digest(password, valid_pass):
        # 成功：清除该 IP 的失败记录
        _login_failures.pop(ip, None)
        session["user"] = username
        return True

    # 失败：记录并计算延时
    record = _login_failures.get(ip)
    if record is None:
        record = _login_failures[ip] = {"failures": 0}
    record["failures"] += 1

    if record["failures"] >= MAX_FAILURES:
        exponent = min(record["failures"] - MAX_FAILURES + 1, MAX_DELAY_EXPONENT)
        delay = BASE_DELAY_SECONDS**exponent
        record["blocked_until"] = time.time() + delay

    return False


def logout() -> None:
    """清除 session 中的用户信息。"""
    session.pop("user", None)


def is_authenticated() -> bool:
    """检查当前请求是否已通过鉴权。

    Returns:
        True 表示已登录
    """
    return "user" in session


# ---------------------------------------------------------------------------
# 装饰器
# ---------------------------------------------------------------------------


def login_required(f: Callable) -> Callable:
    """装饰器：要求请求已通过 Session 鉴权，否则返回 401 JSON。

    用法：
        @login_required
        def protected_endpoint():
            ...
    """

    @wraps(f)
    def decorated(*args, **kwargs):
        if not is_authenticated():
            return jsonify({"error": True, "message": "请先登录", "code": 401}), 401
        return f(*args, **kwargs)

    return decorated
