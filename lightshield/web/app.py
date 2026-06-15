"""LightShield Web API — Flask 应用工厂。

提供 create_app(config) 工厂函数，创建并配置 Flask 实例：
- Session 签名密钥 + 安全 cookie 标志（HttpOnly/SameSite/v0.0.32）
- 注册 API + Pages Blueprint
- JSON 错误处理器（400/401/403/404/405/429/500）
- 安全响应头（CSP/X-Frame-Options/X-Content-Type-Options/v0.0.32）
- CORS 头（默认本地开发宽松，可配置白名单 v0.0.32）
- CSRF 防护 + 速率限制
- 注入 LightShieldCore 实例到 app.config
"""

from __future__ import annotations

import os
from datetime import timedelta

from flask import Flask, jsonify, request, session

from lightshield.config import LightShieldConfig
from lightshield.core import LightShieldCore
from lightshield.web.csrf import (
    UNSAFE_METHODS,
    csrf_failure_response,
    generate_csrf_token,
    is_csrf_exempt,
    validate_csrf,
)
from lightshield.web.pages import pages_bp
from lightshield.web.ratelimit import get_limiter
from lightshield.web.routes import api_bp


def _register_error_handlers(app: Flask) -> None:
    """注册统一 JSON 格式的 HTTP 错误处理器。"""
    _messages = {
        400: "请求格式错误",
        401: "请先登录",
        403: "禁止访问",
        404: "接口不存在",
        405: "不支持的请求方法",
        429: "请求过于频繁",
        500: "服务器内部错误",
    }

    def _make_handler(code: int, msg: str):
        def _handler(_e):
            return jsonify({"error": True, "message": msg, "code": code}), code

        return _handler

    for code, msg in _messages.items():
        app.register_error_handler(code, _make_handler(code, msg))


def _configure_session(app: Flask, config: LightShieldConfig) -> None:
    """配置 Session 安全参数（v0.0.32）。"""
    secret_key = config.jwt_secret or os.urandom(24).hex()
    app.secret_key = secret_key
    app.config["SESSION_COOKIE_HTTPONLY"] = True
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
    app.config["SESSION_COOKIE_SECURE"] = False
    app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(hours=8)


def create_app(config: LightShieldConfig | None = None) -> Flask:
    """创建并配置 Flask 应用。

    Args:
        config: LightShield 配置对象。为 None 时使用默认配置。

    Returns:
        配置完毕的 Flask 应用实例
    """
    app = Flask(__name__)

    # -----------------------------------------------------------------------
    # 配置
    # -----------------------------------------------------------------------
    if config is None:
        config = LightShieldConfig()

    # Session 安全配置（v0.0.32: HttpOnly + SameSite + 8h 超时）
    _configure_session(app, config)

    # 注入配置和核心实例到 app.config，供路由通过 current_app 访问
    app.config["LIGHTSHIELD_CONFIG"] = config
    app.config["LIGHTSHIELD_CORE"] = LightShieldCore(config=config)

    # 注册 Blueprint + 统一 JSON 错误处理器
    app.register_blueprint(api_bp)
    app.register_blueprint(pages_bp)
    _register_error_handlers(app)

    # -----------------------------------------------------------------------
    # 请求钩子
    # -----------------------------------------------------------------------

    @app.before_request
    def _protect_csrf():
        """Validate CSRF tokens for authenticated unsafe requests."""
        if request.method not in UNSAFE_METHODS:
            return None
        if is_csrf_exempt() or "user" not in session:
            return None
        if not validate_csrf():
            return csrf_failure_response()
        return None

    @app.before_request
    def _rate_limit():
        """Apply rate limiting to API endpoints (v0.0.31)."""
        if request.endpoint and request.endpoint.startswith("api."):
            limiter = get_limiter(max_requests=config.rate_limit_per_hour, window_seconds=3600)
            ip = request.remote_addr or "127.0.0.1"
            if not limiter.is_allowed(ip):
                return jsonify(
                    {
                        "error": True,
                        "message": f"请求过于频繁，每小时限制 {config.rate_limit_per_hour} 次",
                        "code": 429,
                    }
                ), 429

    @app.after_request
    def _add_security_headers(response):
        """添加安全响应头（v0.0.32: CSP + X-Frame + X-Content-Type + Referrer-Policy）。

        CSP 允许：
          - 本域脚本和样式（HTML 内联 + static/）
          - marked.js CDN（用于报告页 Markdown 渲染）
          - 本域 API 调用（connect-src 'self'）
        """
        # ---- CSP（内容安全策略）----
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data:; "
            "connect-src 'self'; "
            "frame-ancestors 'none';"
        )

        # ---- 其他安全头 ----
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

        return response

    @app.after_request
    def _add_cors_headers(response):
        """CORS 头（v0.0.32: 收紧为可配置，默认仅本地开发宽松）。

        生产部署在反向代理后时，CORS 由反向代理统一处理。
        如需跨域 API 访问，设置环境变量 LS_CORS_ORIGINS 为逗号分隔的域名列表。
        """
        cors_origins = os.environ.get("LS_CORS_ORIGINS", "")
        if cors_origins:
            # 白名单模式
            origin = request.headers.get("Origin", "")
            allowed = [o.strip() for o in cors_origins.split(",") if o.strip()]
            if origin in allowed:
                response.headers["Access-Control-Allow-Origin"] = origin
                response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization, X-CSRF-Token"
                response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
                response.headers["Vary"] = "Origin"
        else:
            # 本地开发模式（仅本机访问）
            response.headers["Access-Control-Allow-Origin"] = "*"
            response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization, X-CSRF-Token"
            response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"

        return response

    @app.context_processor
    def _inject_csrf():
        """Expose csrf_token() to all Jinja templates."""
        return {"csrf_token": generate_csrf_token}

    return app
