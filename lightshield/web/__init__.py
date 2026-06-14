"""LightShield Web API 模块。

提供 Flask REST API 骨架，将 core.py 的扫描能力暴露为 HTTP 端点。
v0.0.27: Session 鉴权 + 扫描提交/状态查询/报告获取。
"""

from __future__ import annotations

from lightshield.web.app import create_app

__all__ = ["create_app"]
