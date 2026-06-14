"""CSRF protection helpers for the Flask Web UI."""

from __future__ import annotations

import secrets
from collections.abc import Callable
from functools import wraps
from typing import Any

from flask import current_app, jsonify, request, session

UNSAFE_METHODS = {"POST", "PUT", "DELETE", "PATCH"}


def generate_csrf_token() -> str:
    """Return the current session CSRF token, creating it when needed."""
    token = session.get("_csrf_token")
    if not isinstance(token, str) or not token:
        token = secrets.token_hex(32)
        session["_csrf_token"] = token
    return token


def validate_csrf() -> bool:
    """Validate a CSRF token from an AJAX header or submitted form field."""
    expected = session.get("_csrf_token")
    supplied = request.headers.get("X-CSRF-Token") or request.form.get("_csrf_token")
    return bool(expected and supplied and secrets.compare_digest(str(expected), str(supplied)))


def csrf_exempt(view: Callable[..., Any]) -> Callable[..., Any]:
    """Mark a view as exempt from global CSRF checks."""
    view._csrf_exempt = True  # type: ignore[attr-defined]
    return view


def is_csrf_exempt() -> bool:
    """Return True when the current endpoint opted out of CSRF protection."""
    if request.endpoint is None:
        return False
    view = current_app.view_functions.get(request.endpoint)
    return bool(view and getattr(view, "_csrf_exempt", False))


def csrf_failure_response():
    """Build the shared JSON response for CSRF failures."""
    return jsonify({"error": True, "message": "CSRF 校验失败，请刷新页面后重试", "code": 403}), 403


def csrf_protect(view: Callable[..., Any]) -> Callable[..., Any]:
    """Decorator form for views that need an explicit CSRF guard."""

    @wraps(view)
    def decorated(*args: Any, **kwargs: Any):
        if request.method in UNSAFE_METHODS and not validate_csrf():
            return csrf_failure_response()
        return view(*args, **kwargs)

    return decorated
