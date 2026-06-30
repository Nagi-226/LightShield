"""Tests for Web 国际化（i18n）、/docs 路由与中英双语页面渲染。

覆盖三层：
1. i18n 纯函数（normalize/translate/flatten/meta）—— 无请求上下文，回退默认语言。
2. /lang/<code> 语言切换路由 —— 白名单校验 + 同源重定向防护。
3. /docs 自托管 Swagger UI + 各页面双语渲染（session/Accept-Language 协商）。
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from lightshield.config import LightShieldConfig
from lightshield.web.app import create_app
from lightshield.web.i18n import (
    DEFAULT_LOCALE,
    SUPPORTED_LOCALES,
    flatten_for_js,
    locale_meta,
    normalize_locale,
    translate,
)

# ---------------------------------------------------------------------------
# 1) i18n 纯函数单元测试（无请求上下文 → 回退 DEFAULT_LOCALE）
# ---------------------------------------------------------------------------


def test_normalize_locale_exact_match():
    """精确的受支持语言代码原样返回。"""
    assert normalize_locale("zh-CN") == "zh-CN"
    assert normalize_locale("en-US") == "en-US"


def test_normalize_locale_case_insensitive():
    """大小写不敏感地匹配受支持语言。"""
    assert normalize_locale("ZH-cn") == "zh-CN"
    assert normalize_locale("en-us") == "en-US"


def test_normalize_locale_language_segment_only():
    """仅语言段（zh / en）容错补全到完整代码。"""
    assert normalize_locale("zh") == "zh-CN"
    assert normalize_locale("en") == "en-US"


def test_normalize_locale_invalid_returns_none():
    """非受支持输入返回 None（空串 / None / 未知语言）。"""
    assert normalize_locale("fr") is None
    assert normalize_locale("") is None
    assert normalize_locale(None) is None


def test_translate_defaults_to_chinese_without_request_context():
    """无请求上下文时按默认语言（zh-CN）翻译。"""
    assert translate("common.brand") == "LightShield 轻盾"
    assert translate("login.submit") == "登录"


def test_translate_explicit_english_locale():
    """显式指定 en-US 返回英文文案。"""
    assert translate("common.brand", "en-US") == "LightShield"
    assert translate("login.submit", "en-US") == "Log in"
    assert translate("harden.title", "en-US") == "Hardening recommendations"


def test_translate_missing_key_returns_key_name():
    """缺失键最终回退键名本身，保证永不返回空白。"""
    assert translate("does.not.exist") == "does.not.exist"
    assert translate("does.not.exist", "en-US") == "does.not.exist"


def test_translate_unsupported_locale_falls_back_to_default():
    """未知目标语言被规整失败后退回默认语言翻译。"""
    assert translate("common.brand", "fr-FR") == "LightShield 轻盾"


def test_flatten_for_js_has_dotted_keys_and_skips_meta():
    """扁平字典使用点号键、跳过 _meta、值均为字符串。"""
    flat = flatten_for_js("en-US")
    assert flat["dashboard.title"] == "Scan panel"
    assert flat["common.brand"] == "LightShield"
    assert "_meta" not in flat
    assert not any(key.startswith("_meta") for key in flat)
    assert all(isinstance(value, str) for value in flat.values())


def test_flatten_for_js_merges_default_under_target():
    """目标语言扁平字典以默认语言为底，键集覆盖默认语言（fallback 保证）。"""
    merged = flatten_for_js("en-US")
    zh_keys = set(flatten_for_js("zh-CN").keys())
    assert zh_keys <= set(merged.keys())


def test_locale_meta_exposes_name_and_dir():
    """locale_meta 暴露 name / dir 元信息。"""
    assert locale_meta("zh-CN")["name"] == "简体中文"
    assert locale_meta("en-US")["name"] == "English"
    assert locale_meta("zh-CN")["dir"] == "ltr"


def test_supported_locales_and_default_constants():
    """常量声明：默认 zh-CN，受支持含中英。"""
    assert DEFAULT_LOCALE == "zh-CN"
    assert "zh-CN" in SUPPORTED_LOCALES
    assert "en-US" in SUPPORTED_LOCALES


# ---------------------------------------------------------------------------
# Flask fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def app():
    """Create a Flask app configured for i18n page tests."""
    config = LightShieldConfig()
    config.jwt_secret = "test-secret-key-for-i18n"
    config.db_url = "data/test-lightshield.db"
    flask_app = create_app(config=config)
    flask_app.config["TESTING"] = True
    return flask_app


@pytest.fixture
def client(app):
    """Return an unauthenticated Flask test client."""
    return app.test_client()


@pytest.fixture
def auth_client(client):
    """Return a client with a valid session cookie."""
    client.post("/api/login", json={"username": "admin", "password": "lightshield"})
    return client


# ---------------------------------------------------------------------------
# 2) /lang/<code> 语言切换路由
# ---------------------------------------------------------------------------


def test_set_language_valid_sets_session_and_redirects_to_referrer(client):
    """合法语言写入 session 并重定向回同源来源页。"""
    response = client.get("/lang/en-US", headers={"Referer": "http://localhost/dashboard"})

    assert response.status_code == 302
    assert response.headers["Location"] == "http://localhost/dashboard"

    # 后续请求应使用刚切换的英文（session 持久化于 test client cookie）
    follow = client.get("/")
    html = follow.get_data(as_text=True)
    assert 'lang="en-US"' in html
    assert "Log in" in html


def test_set_language_invalid_code_is_ignored(client):
    """非白名单语言静默忽略，不改变默认语言。"""
    response = client.get("/lang/fr-FR")

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/")

    follow = client.get("/")
    assert 'lang="zh-CN"' in follow.get_data(as_text=True)


def test_set_language_blocks_open_redirect(client):
    """跨源 Referer 被拒绝，回退到登录页（防开放重定向）。"""
    response = client.get("/lang/zh-CN", headers={"Referer": "http://evil.example.com/x"})

    assert response.status_code == 302
    assert "evil.example.com" not in response.headers["Location"]


# ---------------------------------------------------------------------------
# 3) /docs 路由 + 双语页面渲染
# ---------------------------------------------------------------------------


def test_docs_route_is_public_and_renders_swagger(client):
    """/docs 为公开页，渲染自托管 Swagger UI 并指向 openapi.json。"""
    response = client.get("/docs")

    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "swagger-ui" in html
    assert "/static/openapi.json" in html
    assert "API 文档" in html  # docs.title zh（默认语言）


def test_docs_route_renders_english_via_accept_language(client):
    """/docs 按 Accept-Language 协商渲染英文标题。"""
    response = client.get("/docs", headers={"Accept-Language": "en-US"})

    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert 'lang="en-US"' in html
    assert "API Documentation" in html  # docs.title en


def test_login_page_defaults_to_chinese(client):
    """默认（无协商）渲染中文登录页。"""
    response = client.get("/")

    html = response.get_data(as_text=True)
    assert 'lang="zh-CN"' in html
    assert "登录" in html


def test_login_page_negotiates_english_via_accept_language(client):
    """Accept-Language: en-US 协商出英文登录页。"""
    response = client.get("/", headers={"Accept-Language": "en-US"})

    html = response.get_data(as_text=True)
    assert 'lang="en-US"' in html
    assert "Log in" in html


def test_i18n_js_bridge_is_injected(client):
    """每个页面注入前端 JS i18n 桥（window.LS_I18N / window.t）。"""
    html = client.get("/").get_data(as_text=True)

    assert "window.LS_I18N" in html
    assert "window.t" in html
    assert "window.LS_LANG" in html


def test_dashboard_renders_english_after_language_switch(auth_client):
    """登录用户切换英文后，仪表板以英文渲染。"""
    auth_client.get("/lang/en-US")

    with patch("lightshield.core.get_repository") as get_repo:
        get_repo.return_value.list_recent.return_value = []
        response = auth_client.get("/dashboard")

    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert 'lang="en-US"' in html
    assert "Scan panel" in html  # dashboard.title en
    assert "Start scan" in html  # dashboard.start en


def test_harden_page_renders_english_including_not_found_error(auth_client):
    """英文模式下 harden 页渲染，且服务端 not-found 错误也走 i18n（pages.translate）。"""
    auth_client.get("/lang/en-US")

    repo = MagicMock()
    repo.get.return_value = None  # 触发 scan_data is None 错误分支
    with patch("lightshield.core.get_repository", return_value=repo):
        response = auth_client.get("/harden/LS-20260620-000000-deadbe")

    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert 'lang="en-US"' in html
    assert "Hardening recommendations" in html  # harden.title en
    assert "Scan record not found" in html  # harden.err_not_found en（服务端翻译）


def test_harden_page_not_found_error_is_chinese_by_default(auth_client):
    """默认语言下 harden not-found 错误为中文（服务端 translate 回退默认）。"""
    repo = MagicMock()
    repo.get.return_value = None
    with patch("lightshield.core.get_repository", return_value=repo):
        response = auth_client.get("/harden/LS-20260620-000000-deadbe")

    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "扫描记录不存在" in html  # harden.err_not_found zh
