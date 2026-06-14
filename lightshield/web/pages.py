"""Flask page routes for the LightShield Web dashboard."""

from __future__ import annotations

from flask import Blueprint, current_app, redirect, render_template, session, url_for

from lightshield.adapters.base import VulnFinding
from lightshield.repository.base import get_repository
from lightshield.rules.engine import RuleEngine
from lightshield.utils.constants import RiskLevel

pages_bp = Blueprint("pages", __name__)


@pages_bp.route("/")
def index():
    """Render the login page, or redirect authenticated users to the dashboard."""
    if "user" in session:
        return redirect(url_for("pages.dashboard"))
    return render_template("login.html")


@pages_bp.route("/dashboard")
def dashboard():
    """Render the authenticated scan dashboard with recent scan history."""
    if "user" not in session:
        return redirect(url_for("pages.index"))

    config = current_app.config.get("LIGHTSHIELD_CONFIG")
    db_url = getattr(config, "db_url", "") or "data/lightshield.db"

    try:
        repo = get_repository("sqlite", db_url=db_url)
        history = repo.list_recent(limit=20)
    except Exception:
        history = []

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

    config = current_app.config.get("LIGHTSHIELD_CONFIG")
    db_url = getattr(config, "db_url", "") or "data/lightshield.db"

    try:
        repo = get_repository("sqlite", db_url=db_url)
        scan_data = repo.get(scan_id)
    except Exception:
        scan_data = None

    if scan_data is None:
        return render_template(
            "harden.html",
            scan_id=scan_id,
            scan_data={},
            target="未知",
            error="扫描记录不存在",
            recommendations=[],
            show_nav=True,
            username=session.get("user", "?"),
        )

    raw = scan_data.get("raw_result", scan_data)
    findings = _reconstruct_findings(raw.get("findings", []))
    engine = RuleEngine()
    engine.load_rules()
    recommendations = engine.recommend_hardening(findings)

    return render_template(
        "harden.html",
        scan_id=scan_id,
        scan_data=scan_data,
        target=scan_data.get("target") or raw.get("target", "unknown"),
        recommendations=recommendations,
        findings_count=len(findings),
        show_nav=True,
        username=session.get("user", "?"),
    )


def _reconstruct_findings(findings_data: list[dict]) -> list[VulnFinding]:
    """Rebuild VulnFinding instances from repository dictionaries."""
    findings: list[VulnFinding] = []
    for item in findings_data:
        try:
            severity = RiskLevel(item.get("severity", "info"))
        except ValueError:
            severity = RiskLevel.INFO

        findings.append(
            VulnFinding(
                vuln_type=item.get("vuln_type", "unknown"),
                severity=severity,
                title=item.get("title", ""),
                description=item.get("description", ""),
                remediation=item.get("remediation", ""),
                url=item.get("url"),
                parameter=item.get("parameter"),
                port=item.get("port"),
                cve_id=item.get("cve_id"),
                cvss_score=item.get("cvss_score"),
                evidence=item.get("evidence"),
            )
        )
    return findings
