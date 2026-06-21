"""LightShield Web — 国际化 (i18n) 支持模块。

提供中英双语 locale 加载、翻译查找与当前语言解析：
- locale JSON 位于 ``web/locales/``（``zh-CN.json`` / ``en-US.json``）。
- :func:`translate` 按点号键查找，缺失时回退默认语言、再回退键名本身。
- :func:`resolve_locale` 按 session → cookie → Accept-Language → 默认 解析语言。
- :func:`flatten_for_js` 输出扁平字典，供前端 JS 桥（``window.LS_I18N``）使用。

v0.0.39：Web 仪表板中英切换。本模块为纯表现层逻辑，不涉及任何扫描能力。
"""

from __future__ import annotations

import json
from functools import cache
from pathlib import Path

from flask import has_request_context, request, session

# ---------------------------------------------------------------------------
# 常量
# ---------------------------------------------------------------------------

DEFAULT_LOCALE = "zh-CN"
SUPPORTED_LOCALES: tuple[str, ...] = ("zh-CN", "en-US")

LANG_SESSION_KEY = "lang"  # session 中记录用户显式选择的语言
LANG_COOKIE_KEY = "ls_lang"  # cookie 中持久化的语言偏好

LOCALE_DIR = Path(__file__).parent / "locales"


# ---------------------------------------------------------------------------
# locale 加载与扁平化（带缓存）
# ---------------------------------------------------------------------------


@cache
def _load_locale(code: str) -> dict:
    """加载并缓存指定语言的 locale 字典（嵌套结构）。

    Args:
        code: 语言代码，如 ``"zh-CN"``。

    Returns:
        locale 嵌套字典；文件缺失或解析失败时返回空字典（不抛错）。
    """
    path = LOCALE_DIR / f"{code}.json"
    try:
        with path.open(encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


@cache
def _flatten_locale(code: str) -> dict[str, str]:
    """返回扁平化（点号键）的 locale 字典。

    跳过 ``_meta`` 段与非字符串值，仅保留可直接展示的文案。

    Args:
        code: 语言代码。

    Returns:
        形如 ``{"login.title": "...", ...}`` 的扁平字典。
    """
    flat: dict[str, str] = {}

    def _walk(prefix: str, node: dict) -> None:
        for key, value in node.items():
            if key == "_meta":
                continue
            dotted = f"{prefix}.{key}" if prefix else key
            if isinstance(value, dict):
                _walk(dotted, value)
            elif isinstance(value, str):
                flat[dotted] = value

    _walk("", _load_locale(code))
    return flat


# ---------------------------------------------------------------------------
# 公共 API
# ---------------------------------------------------------------------------


def normalize_locale(code: str | None) -> str | None:
    """把任意输入规整为受支持的语言代码。

    支持精确匹配、忽略大小写，以及仅语言段（``zh`` → ``zh-CN``）的容错。

    Args:
        code: 待规整的语言代码，可为 None。

    Returns:
        受支持的语言代码；无法匹配时返回 None。
    """
    if not code:
        return None
    code = code.strip()
    if code in SUPPORTED_LOCALES:
        return code
    lowered = code.lower()
    for supported in SUPPORTED_LOCALES:
        if supported.lower() == lowered or supported.lower().split("-")[0] == lowered:
            return supported
    return None


def resolve_locale() -> str:
    """解析当前请求应使用的语言代码。

    优先级：``session["lang"]`` → cookie ``ls_lang`` → ``Accept-Language`` 协商 →
    默认语言。无请求上下文（如 CLI 或测试直接调用）时返回默认语言。

    Returns:
        受支持的语言代码。
    """
    if not has_request_context():
        return DEFAULT_LOCALE

    # 1) 会话内的显式选择（语言选择器写入）
    chosen = normalize_locale(session.get(LANG_SESSION_KEY))
    if chosen:
        return chosen

    # 2) cookie 持久化偏好
    chosen = normalize_locale(request.cookies.get(LANG_COOKIE_KEY))
    if chosen:
        return chosen

    # 3) 浏览器 Accept-Language 协商
    chosen = normalize_locale(request.accept_languages.best_match(SUPPORTED_LOCALES))
    if chosen:
        return chosen

    return DEFAULT_LOCALE


def translate(key: str, lang: str | None = None) -> str:
    """翻译一个点号键。

    查找顺序：目标语言 → 默认语言 → 键名本身，保证永不抛错、永不返回空白。

    Args:
        key: 点号键，如 ``"dashboard.title"``。
        lang: 目标语言代码；None 时用 :func:`resolve_locale`。

    Returns:
        翻译后的文案；目标与默认语言均缺失时返回 ``key`` 本身。
    """
    lang = normalize_locale(lang) or resolve_locale()
    value = _flatten_locale(lang).get(key)
    if value is None and lang != DEFAULT_LOCALE:
        value = _flatten_locale(DEFAULT_LOCALE).get(key)
    return value if value is not None else key


def locale_meta(lang: str | None = None) -> dict:
    """返回语言的 ``_meta``（code/name/dir），缺失时给出合理默认。

    Args:
        lang: 目标语言代码；None 时用 :func:`resolve_locale`。

    Returns:
        含 ``code`` / ``name`` / ``dir`` 的字典。
    """
    lang = normalize_locale(lang) or resolve_locale()
    meta = _load_locale(lang).get("_meta")
    if isinstance(meta, dict):
        return meta
    return {"code": lang, "name": lang, "dir": "ltr"}


def flatten_for_js(lang: str | None = None) -> dict[str, str]:
    """返回供前端 JS 桥使用的扁平字典。

    以默认语言为底、目标语言覆盖，保证目标语言缺失的键回退到默认语言文案，
    前端永不出现裸键名。

    Args:
        lang: 目标语言代码；None 时用 :func:`resolve_locale`。

    Returns:
        合并后的扁平字典（默认语言 ∪ 目标语言）。
    """
    lang = normalize_locale(lang) or resolve_locale()
    merged = dict(_flatten_locale(DEFAULT_LOCALE))
    merged.update(_flatten_locale(lang))
    return merged
