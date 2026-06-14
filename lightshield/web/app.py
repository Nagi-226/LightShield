"""LightShield Web API — Flask 应用工厂。

提供 create_app(config) 工厂函数，创建并配置 Flask 实例：
- Session 签名密钥（来自 config.jwt_secret，为空则随机生成）
- 注册 API Blueprint
- JSON 错误处理器（400/401/404/405/500）
- CORS 宽松头（开发友好）
- 注入 LightShieldCore 实例到 app.config
"""

from __future__ import annotations

import os

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
from lightshield.web.routes import api_bp


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

    # Session 签名密钥：优先 config.jwt_secret，为空则随机生成
    # （字段名含 'jwt' 是历史命名，v0.0.27 复用于 session 签名）
    secret_key = config.jwt_secret or os.urandom(24).hex()
    app.secret_key = secret_key

    # 注入配置和核心实例到 app.config，供路由通过 current_app 访问
    app.config["LIGHTSHIELD_CONFIG"] = config
    app.config["LIGHTSHIELD_CORE"] = LightShieldCore(config=config)

    # -----------------------------------------------------------------------
    # 注册 Blueprint
    # -----------------------------------------------------------------------
    app.register_blueprint(api_bp)
    app.register_blueprint(pages_bp)

    # -----------------------------------------------------------------------
    # 错误处理器（统一 JSON 响应）
    # -----------------------------------------------------------------------

    @app.errorhandler(400)
    def _handle_400(e):
        return jsonify({"error": True, "message": "请求格式错误", "code": 400}), 400

    @app.errorhandler(401)
    def _handle_401(e):
        return jsonify({"error": True, "message": "请先登录", "code": 401}), 401

    @app.errorhandler(404)
    def _handle_404(e):
        return jsonify({"error": True, "message": "接口不存在", "code": 404}), 404

    @app.errorhandler(405)
    def _handle_405(e):
        return jsonify({"error": True, "message": "不支持的请求方法", "code": 405}), 405

    @app.errorhandler(500)
    def _handle_500(e):
        return jsonify({"error": True, "message": "服务器内部错误", "code": 500}), 500

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
    def _log_request():
        """记录每个 API 请求的方法和路径。"""
        # 跳过静态文件请求的日志（本项目无静态文件，仅保留扩展点）
        pass

    @app.after_request
    def _add_cors_headers(response):
        """添加宽松 CORS 头，方便开发阶段浏览器调用。

        v1.0.0 应替换为 Flask-CORS 或白名单机制。
        """
        response.headers["Access-Control-Allow-Origin"] = "*"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization, X-CSRF-Token"
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
        return response

    @app.context_processor
    def _inject_csrf():
        """Expose csrf_token() to all Jinja templates."""
        return {"csrf_token": generate_csrf_token}

    return app
