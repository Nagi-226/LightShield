"""LightShield Web API — 路由蓝图。

所有 API 端点注册在 /api 前缀下：
- POST /api/login          — 用户登录（公开）
- POST /api/logout         — 用户登出（公开）
- POST /api/scan           — 提交扫描任务（需登录）
- GET  /api/scan/<task_id> — 查询任务状态（需登录）
- GET  /api/report/<scan_id> — 获取扫描报告（需登录）

响应格式统一为 JSON 信封：
  成功: {"success": true, ...}
  失败: {"error": true, "message": "...", "code": N}
"""

from __future__ import annotations

from datetime import datetime, timezone

from flask import Blueprint, current_app, jsonify, request, session

from lightshield.adapters.base import ScanResult, VulnFinding
from lightshield.config import LightShieldConfig
from lightshield.report.reporter import ReportGenerator
from lightshield.repository.base import get_repository
from lightshield.rules.engine import RuleEngine
from lightshield.utils.constants import RiskLevel, ScanStatus
from lightshield.utils.validator import TargetValidator
from lightshield.web.auth import login, login_required, logout
from lightshield.web.csrf import csrf_exempt

# ---------------------------------------------------------------------------
# 蓝图
# ---------------------------------------------------------------------------

api_bp = Blueprint("api", __name__, url_prefix="/api")


# =============================================================================
# 鉴权端点（公开）
# =============================================================================


@api_bp.route("/login", methods=["POST"])
@csrf_exempt
def api_login():
    """用户登录。

    Request JSON:
        {"username": "admin", "password": "lightshield"}

    Response 200:
        {"success": true, "message": "登录成功"}
    Response 400:
        {"error": true, "message": "请提供用户名和密码", "code": 400}
    Response 401:
        {"error": true, "message": "用户名或密码错误", "code": 401}
    """
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": True, "message": "请求体不能为空，需要 JSON", "code": 400}), 400

    username = data.get("username", "")
    password = data.get("password", "")

    if not username or not password:
        return jsonify({"error": True, "message": "请提供用户名和密码", "code": 400}), 400

    if login(username, password):
        return jsonify({"success": True, "message": "登录成功"}), 200

    return jsonify({"error": True, "message": "用户名或密码错误", "code": 401}), 401


@api_bp.route("/logout", methods=["POST"])
@csrf_exempt
def api_logout():
    """用户登出。

    Response 200:
        {"success": true, "message": "已登出"}
    """
    logout()
    return jsonify({"success": True, "message": "已登出"}), 200


# =============================================================================
# 扫描端点（需登录）
# =============================================================================


@api_bp.route("/scan", methods=["POST"])
@login_required
def api_submit_scan():
    """提交扫描任务。

    Request JSON:
        {
            "target": "192.168.1.1",          // 必填：目标 IP/域名
            "scan_types": ["port_scan", ...],  // 可选：扫描类型列表，默认全部
            "confirm_ownership": true          // 可选：所有权确认，默认 false
        }

    Response 202:
        {"task_id": "LS-20260614-...", "status": "accepted", "target": "..."}
    Response 400:
        {"error": true, "message": "...", "code": 400}
    """
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": True, "message": "请求体不能为空，需要 JSON", "code": 400}), 400

    target = (data.get("target") or "").strip()
    if not target:
        return jsonify({"error": True, "message": "请提供扫描目标 (target)", "code": 400}), 400

    # R2 合规：双层校验（API 层 + core.submit_scan 内部再校验）
    is_valid, reason = TargetValidator.validate(target)
    if not is_valid:
        return jsonify({"error": True, "message": f"[R2 违规] {reason}", "code": 400}), 400

    scan_types: list[str] | None = data.get("scan_types")
    confirm_ownership: bool = data.get("confirm_ownership", False)

    core = current_app.config["LIGHTSHIELD_CORE"]
    try:
        task_id = core.submit_scan(
            target=target,
            scan_types=scan_types,
            confirm_ownership=confirm_ownership,
        )
    except Exception as exc:
        return jsonify({"error": True, "message": f"扫描提交失败：{exc}", "code": 500}), 500

    return jsonify({"task_id": task_id, "status": "accepted", "target": target}), 202


@api_bp.route("/scan/<task_id>", methods=["GET"])
@login_required
def api_get_scan_status(task_id: str):
    """查询扫描任务状态。

    Response 200:
        {"task_id": "...", "status": "completed", "target": "...", ...}
    Response 404:
        {"error": true, "message": "任务不存在: LS-xxx", "code": 404}
    """
    core = current_app.config["LIGHTSHIELD_CORE"]
    status = core.get_scan_status(task_id)

    if status.get("status") == "not_found":
        return jsonify({"error": True, "message": f"任务不存在: {task_id}", "code": 404}), 404

    return jsonify(status), 200


# =============================================================================
# 报告端点（需登录）
# =============================================================================


@api_bp.route("/report/<scan_id>", methods=["GET"])
@login_required
def api_get_report(scan_id: str):
    """获取扫描报告。

    Query params:
        format: "markdown"（默认）、"text" 或 "pdf"

    Response 200:
        报告内容 (Markdown/Text: text/plain; PDF: application/pdf)
    Response 404:
        {"error": true, "message": "扫描记录不存在: LS-xxx", "code": 404}
    Response 409:
        {"error": true, "message": "扫描尚未完成，无法生成报告。当前状态: failed", "code": 409}
    """
    config: LightShieldConfig = current_app.config["LIGHTSHIELD_CONFIG"]

    # 从仓库加载扫描数据
    db_url = config.db_url or "data/lightshield.db"
    try:
        repo = get_repository("sqlite", db_url=db_url)
    except Exception as exc:
        return jsonify({"error": True, "message": f"数据仓库初始化失败：{exc}", "code": 500}), 500

    scan_data = repo.get(scan_id)
    if scan_data is None:
        return jsonify({"error": True, "message": f"扫描记录不存在: {scan_id}", "code": 404}), 404

    # 仅允许已完成或部分完成的扫描生成报告
    scan_status = scan_data.get("status", "")
    if scan_status not in (ScanStatus.COMPLETED.value, ScanStatus.PARTIAL.value):
        return jsonify(
            {
                "error": True,
                "message": f"扫描尚未完成，无法生成报告。当前状态: {scan_status}",
                "code": 409,
            }
        ), 409

    # 从 raw_result 中提取完整数据
    raw = scan_data.get("raw_result", scan_data)

    try:
        scan_result = _reconstruct_scan_result(raw)
        findings = _reconstruct_findings(raw.get("findings", []))
    except Exception as exc:
        return jsonify({"error": True, "message": f"数据解析失败：{exc}", "code": 500}), 500

    # 生成报告
    fmt = request.args.get("format", "markdown")
    if fmt not in ("markdown", "text", "pdf"):
        fmt = "markdown"

    reporter = ReportGenerator(output_dir=config.report_output_dir)
    try:
        report = reporter.generate(scan_result, findings=findings, fmt=fmt)
    except Exception as exc:
        return jsonify({"error": True, "message": f"报告生成失败：{exc}", "code": 500}), 500

    if fmt == "pdf":
        return (
            report,
            200,
            {
                "Content-Type": "application/pdf",
                "Content-Disposition": f'attachment; filename="lightshield-{scan_id}.pdf"',
            },
        )

    return report, 200, {"Content-Type": "text/plain; charset=utf-8"}


@api_bp.route("/harden/<scan_id>", methods=["POST"])
@login_required
def api_generate_harden(scan_id: str):
    """生成加固和回滚脚本，返回脚本路径。"""
    data = request.get_json(silent=True) or request.form.to_dict() or {}
    os_platform = str(data.get("os_platform", "linux")).lower()
    if os_platform not in ("linux", "windows"):
        return jsonify({"error": True, "message": "不支持的操作系统，请选择 linux 或 windows", "code": 400}), 400

    if not _is_truthy(data.get("confirm_ownership")):
        return jsonify({"error": True, "message": "[R4] 请先确认目标所有权或授权范围", "code": 400}), 400

    config: LightShieldConfig = current_app.config["LIGHTSHIELD_CONFIG"]
    db_url = config.db_url or "data/lightshield.db"
    try:
        repo = get_repository("sqlite", db_url=db_url)
        scan_data = repo.get(scan_id)
    except Exception as exc:
        return jsonify({"error": True, "message": f"扫描记录读取失败：{exc}", "code": 500}), 500

    if scan_data is None:
        return jsonify({"error": True, "message": f"扫描记录不存在: {scan_id}", "code": 404}), 404

    raw = scan_data.get("raw_result", scan_data)
    findings = _reconstruct_findings(raw.get("findings", []))

    engine = RuleEngine()
    engine.load_rules()
    recommendations = engine.recommend_hardening(findings)
    if not recommendations:
        return jsonify({"success": True, "generated": False, "message": "未发现需要加固的风险项", "code": 200}), 200

    target = scan_data.get("target") or raw.get("target", "unknown")
    core = current_app.config["LIGHTSHIELD_CORE"]
    session["harden_confirmed_at"] = datetime.now(timezone.utc).isoformat()

    try:
        result = core.generate_hardening(
            target,
            findings=findings,
            recommendations=recommendations,
            output_dir=config.report_output_dir,
            os_platform=os_platform,
        )
    except Exception as exc:
        return jsonify({"error": True, "message": f"脚本生成失败：{exc}", "code": 500}), 500

    status = result.status.value if hasattr(result.status, "value") else str(result.status)
    return jsonify(
        {
            "success": True,
            "generated": True,
            "action_count": result.action_count,
            "script_path": result.script_path,
            "rollback_path": result.rollback_path,
            "status": status,
            "message": f"已生成 {result.action_count} 条加固操作",
        }
    ), 200


# =============================================================================
# 辅助函数：从仓库数据重建领域对象
# =============================================================================


def _reconstruct_scan_result(raw: dict) -> ScanResult:
    """从仓库存储的字典重建 ScanResult 对象。

    Args:
        raw: repo.get() 返回的 raw_result 字典（或 scan_data 本身）

    Returns:
        ScanResult 实例
    """
    status_str = raw.get("status", "completed")
    try:
        status = ScanStatus(status_str)
    except ValueError:
        status = ScanStatus.FAILED

    return ScanResult(
        status=status,
        target=raw.get("target", "unknown"),
        ports=raw.get("ports", []),
        services=raw.get("services", []),
        os_info=raw.get("os_info"),
        findings=[],  # findings 由 _reconstruct_findings 单独处理
        error=raw.get("error"),
        duration_seconds=raw.get("duration_seconds", 0.0),
    )


def _reconstruct_findings(findings_data: list[dict]) -> list[VulnFinding]:
    """从字典列表重建 VulnFinding 对象列表。

    Args:
        findings_data: 仓库中序列化的 findings 列表

    Returns:
        VulnFinding 实例列表
    """
    findings: list[VulnFinding] = []
    for f in findings_data:
        severity_str = f.get("severity", "info")
        try:
            severity = RiskLevel(severity_str)
        except ValueError:
            severity = RiskLevel.INFO

        findings.append(
            VulnFinding(
                vuln_type=f.get("vuln_type", "unknown"),
                severity=severity,
                title=f.get("title", ""),
                description=f.get("description", ""),
                remediation=f.get("remediation", ""),
                url=f.get("url"),
                parameter=f.get("parameter"),
                port=f.get("port"),
                cve_id=f.get("cve_id"),
                cvss_score=f.get("cvss_score"),
                evidence=f.get("evidence"),
            )
        )
    return findings


def _is_truthy(value) -> bool:
    """Return True for common JSON/form truthy values."""
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.lower() in {"1", "true", "yes", "on"}
    return bool(value)
