"""Flask page routes for the LightShield Web dashboard."""

from __future__ import annotations

from urllib.parse import urlparse

from flask import Blueprint, current_app, redirect, render_template, request, session, url_for

from lightshield.web.i18n import LANG_SESSION_KEY, normalize_locale, translate

pages_bp = Blueprint("pages", __name__)


@pages_bp.route("/")
def index():
    """Render the login page, or redirect authenticated users to the dashboard."""
    if "user" in session:
        return redirect(url_for("pages.dashboard"))
    return render_template("login.html")


@pages_bp.route("/lang/<code>")
def set_language(code: str):
    """切换界面语言：合法语言写入 session，随后重定向回来源页。

    仅接受白名单语言代码；非法值静默忽略（不报错）。重定向目标经同源校验，
    防止借 Referer 头实施开放重定向（R 红线之外的通用安全加固）。
    """
    normalized = normalize_locale(code)
    if normalized:
        session[LANG_SESSION_KEY] = normalized
    return redirect(_safe_referrer())


def _safe_referrer() -> str:
    """返回安全的重定向目标：仅允许同源 Referer，否则回登录页。"""
    referrer = request.referrer or ""
    if referrer:
        ref = urlparse(referrer)
        if not ref.netloc or ref.netloc == urlparse(request.host_url).netloc:
            return referrer
    return url_for("pages.index")


@pages_bp.route("/docs")
def api_docs():
    """渲染应用内 Swagger UI（自托管资产），可视化 /static/openapi.json。

    公开页面（与已公开的 openapi.json 一致）；登录用户额外显示顶栏便于返回。
    Try-it-out 调用走既有鉴权/CSRF/限流，未登录时对应 API 返回 401。
    """
    return render_template("docs.html", show_nav=("user" in session))


@pages_bp.route("/dashboard")
def dashboard():
    """Render the authenticated scan dashboard with recent scan history."""
    if "user" not in session:
        return redirect(url_for("pages.index"))

    core = current_app.config["LIGHTSHIELD_CORE"]
    history = core.get_scan_history(limit=20)

    return render_template(
        "dashboard.html",
        history=history,
        show_nav=True,
        username=session.get("user", "?"),
    )


@pages_bp.route("/report/<scan_id>")
def view_report(scan_id: str):
    """Render the authenticated Markdown report viewer."""
    if "user" not in session:
        return redirect(url_for("pages.index"))

    return render_template(
        "report.html",
        scan_id=scan_id,
        show_nav=True,
        username=session.get("user", "?"),
    )


@pages_bp.route("/harden/<scan_id>")
def harden_page(scan_id: str):
    """Render the authenticated hardening recommendation page."""
    if "user" not in session:
        return redirect(url_for("pages.index"))

    core = current_app.config["LIGHTSHIELD_CORE"]
    scan = core.load_scan(scan_id)

    if scan is None:
        return render_template(
            "harden.html",
            scan_id=scan_id,
            scan_data={},
            target=translate("common.unknown"),
            error=translate("harden.err_not_found"),
            recommendations=[],
            show_nav=True,
            username=session.get("user", "?"),
        )

    recommendations = core.get_recommendations(scan_id)

    return render_template(
        "harden.html",
        scan_id=scan_id,
        scan_data={"status": scan.status.value, "target": scan.target},
        target=scan.target,
        recommendations=recommendations,
        findings_count=len(scan.findings),
        show_nav=True,
        username=session.get("user", "?"),
    )


@pages_bp.route("/harden/<scan_id>/verify")
def harden_verify_page(scan_id: str):
    """Render the hardening closed-loop verification page."""
    if "user" not in session:
        return redirect(url_for("pages.index"))

    core = current_app.config["LIGHTSHIELD_CORE"]
    scan = core.load_scan(scan_id)

    target = translate("common.unknown")
    if scan is not None:
        target = scan.target or translate("common.unknown")

    return render_template(
        "harden_verify.html",
        scan_id=scan_id,
        target=target,
        show_nav=True,
        username=session.get("user", "?"),
    )
