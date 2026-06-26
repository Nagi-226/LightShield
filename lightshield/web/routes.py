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

import json
import secrets
import time
from datetime import datetime, timezone
from fnmatch import fnmatchcase
from pathlib import Path

from flask import Blueprint, Response, current_app, jsonify, request, send_from_directory, session, stream_with_context

from lightshield.adapters.base import ScanResult, VulnFinding
from lightshield.config import LightShieldConfig
from lightshield.report.reporter import ReportGenerator
from lightshield.repository.base import get_repository
from lightshield.rules.engine import RuleEngine
from lightshield.utils.constants import RiskLevel, ScanStatus
from lightshield.utils.logger import get_logger
from lightshield.utils.validator import TargetValidator
from lightshield.web.auth import login, login_required, logout
from lightshield.web.csrf import csrf_exempt, csrf_protect

# ---------------------------------------------------------------------------
# 蓝图
# ---------------------------------------------------------------------------

api_bp = Blueprint("api", __name__, url_prefix="/api")

SCRIPT_FILENAME_PATTERNS = ("harden_*.sh", "harden_*.ps1", "rollback_*.sh", "rollback_*.ps1")
SSE_FINAL_STATUSES = {ScanStatus.COMPLETED.value, ScanStatus.PARTIAL.value, ScanStatus.FAILED.value}
SSE_INTERVAL_SECONDS = 0.5
SSE_TIMEOUT_SECONDS = 20.0


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


@api_bp.route("/scan/<task_id>/stream", methods=["GET"])
@login_required
def api_scan_stream(task_id: str):
    """SSE 实时推送扫描进度。"""
    core = current_app.config["LIGHTSHIELD_CORE"]
    logger = get_logger()

    def _events():
        started_at = time.monotonic()
        logger.info("web", f"SSE 扫描进度连接已建立：task_id={task_id}")

        while True:
            try:
                status = core.get_scan_status(task_id)
            except Exception as exc:
                logger.error("web", f"SSE 扫描状态读取失败：task_id={task_id}", exception=exc)
                yield _format_sse({"message": "扫描状态读取失败", "code": 500}, event="error")
                return

            state = str(status.get("status", "unknown"))
            if state == "not_found":
                logger.warning("web", f"SSE 任务不存在：task_id={task_id}")
                yield _format_sse({"message": f"任务不存在: {task_id}", "code": 404}, event="error")
                return

            yield _format_sse(status)

            if state in SSE_FINAL_STATUSES:
                logger.info("web", f"SSE 扫描进度完成：task_id={task_id} status={state}")
                yield _format_sse(status, event="done")
                return

            if time.monotonic() - started_at >= SSE_TIMEOUT_SECONDS:
                logger.warning("web", f"SSE 扫描进度超时：task_id={task_id} status={state}")
                yield _format_sse(
                    {
                        "task_id": task_id,
                        "status": state,
                        "message": "扫描进度监听超时，请稍后刷新或查看历史记录",
                    },
                    event="timeout",
                )
                return

            time.sleep(SSE_INTERVAL_SECONDS)

    return Response(
        stream_with_context(_events()),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


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
    script_filename = _script_basename(result.script_path)
    rollback_filename = _script_basename(result.rollback_path)
    return jsonify(
        {
            "success": True,
            "generated": True,
            "action_count": result.action_count,
            "script_path": result.script_path,
            "rollback_path": result.rollback_path,
            "script_filename": script_filename,
            "rollback_filename": rollback_filename,
            "status": status,
            "message": f"已生成 {result.action_count} 条加固操作",
        }
    ), 200


@api_bp.route("/harden/<scan_id>/verify", methods=["POST"])
@login_required
@csrf_protect
def api_harden_closed_loop(scan_id: str):
    """v0.0.40 加固闭环——触发 run_harden_closed_loop，返回全链路结果。

    请求体（JSON）：
        mode: "dry_run" | "apply"（默认 dry_run）
        os_platform: "linux" | "windows"（默认 linux）
        confirm_ownership: bool（APPLY 必须 true）
        confirm_execute: bool（APPLY 必须 true）

    APPLY 模式缺双确认 → 400 + 错误文案。
    DRY_RUN 模式 → overall="generated_only"，不改系统。
    """
    from lightshield.utils.constants import OSPlatform

    logger = get_logger()
    data = request.get_json(silent=True) or request.form.to_dict() or {}

    # ---- 参数解析 + 校验 ----
    mode = str(data.get("mode", "dry_run")).lower()
    if mode not in ("dry_run", "apply"):
        return jsonify({"error": True, "message": "mode 必须是 dry_run 或 apply", "code": 400}), 400

    os_platform_str = str(data.get("os_platform", "linux")).lower()
    try:
        os_platform = OSPlatform(os_platform_str)
    except ValueError:
        return jsonify({"error": True, "message": "不支持的操作系统，请选择 linux 或 windows", "code": 400}), 400

    confirm_ownership = _is_truthy(data.get("confirm_ownership"))
    confirm_execute = _is_truthy(data.get("confirm_execute"))

    # APPLY 双确认闸门（前端已拦，后端二次校验——R4 防线不可绕过）
    if mode == "apply" and (not confirm_ownership or not confirm_execute):
        return jsonify(
            {
                "error": True,
                "message": "[R4] APPLY 真机执行需要同时确认所有权和执行授权。"
                "请勾选「我确认拥有该资产」和「确认在真机执行加固」。",
                "code": 400,
            }
        ), 400

    # ---- 加载扫描记录 → 获取 target ----
    config: LightShieldConfig = current_app.config["LIGHTSHIELD_CONFIG"]
    db_url = config.db_url or "data/lightshield.db"
    try:
        repo = get_repository("sqlite", db_url=db_url)
        scan_data = repo.get(scan_id)
    except Exception as exc:
        return jsonify({"error": True, "message": f"扫描记录读取失败：{exc}", "code": 500}), 500

    if scan_data is None:
        return jsonify({"error": True, "message": f"扫描记录不存在: {scan_id}", "code": 404}), 404

    target = scan_data.get("target") or scan_data.get("raw_result", {}).get("target", "unknown")

    # ---- 执行闭环 ----
    core = current_app.config["LIGHTSHIELD_CORE"]
    session["harden_confirmed_at"] = datetime.now(timezone.utc).isoformat()

    logger.info("web", f"闭环启动: scan_id={scan_id} target={target} mode={mode}")

    try:
        result = core.run_harden_closed_loop(
            target=target,
            os_platform=os_platform,
            confirm_ownership=confirm_ownership,
            mode=mode,
            confirm_execute=confirm_execute,
        )
    except Exception as exc:
        logger.error("web", f"闭环执行异常: scan_id={scan_id} {exc}")
        return jsonify({"error": True, "message": f"闭环执行失败：{exc}", "code": 500}), 500

    # ---- 构造响应 ----
    response_data = result.to_dict()
    response_data["success"] = result.overall in ("verified", "partial", "generated_only")
    response_data["scan_id"] = scan_id

    status_code = 200 if result.overall != "failed" else 422  # 422 Unprocessable Entity → 前端展示失败但不崩

    logger.info(
        "web",
        f"闭环完成: scan_id={scan_id} overall={result.overall} "
        f"resolved={len(result.verification.get('resolved', [])) if result.verification else 0}",
    )
    return jsonify(response_data), status_code


@api_bp.route("/script/<scan_id>/<path:filename>", methods=["GET"])
@login_required
def api_download_script(scan_id: str, filename: str):
    """下载生成的加固 / 回滚脚本。"""
    logger = get_logger()

    if not _is_allowed_script_filename(filename):
        logger.warning("web", f"拒绝脚本下载：非法文件名 scan_id={scan_id} filename={filename}")
        return jsonify({"error": True, "message": "脚本文件名不在下载白名单内", "code": 400}), 400

    if not _validate_download_csrf():
        logger.warning("web", f"拒绝脚本下载：CSRF 校验失败 scan_id={scan_id} filename={filename}")
        return jsonify({"error": True, "message": "CSRF 校验失败，请刷新页面后重试", "code": 403}), 403

    if not session.get("harden_confirmed_at"):
        logger.warning("web", f"拒绝脚本下载：未确认 R4 所有权 scan_id={scan_id} filename={filename}")
        return jsonify({"error": True, "message": "[R4] 下载脚本前请先确认目标所有权或授权范围", "code": 403}), 403

    config: LightShieldConfig = current_app.config["LIGHTSHIELD_CONFIG"]
    script_path = _resolve_script_path(config.report_output_dir, filename)
    if script_path is None:
        logger.warning("web", f"脚本文件不存在：scan_id={scan_id} filename={filename}")
        return jsonify({"error": True, "message": "脚本文件不存在", "code": 404}), 404

    logger.info("web", f"脚本下载：scan_id={scan_id} filename={filename}")
    return send_from_directory(
        directory=script_path.parent,
        path=script_path.name,
        as_attachment=True,
        download_name=script_path.name,
        mimetype="application/octet-stream",
        max_age=0,
    )


# =============================================================================
# 辅助函数：从仓库数据重建领域对象
# =============================================================================


def _format_sse(data: dict, event: str | None = None) -> str:
    """Format one Server-Sent Event frame."""
    prefix = f"event: {event}\n" if event else ""
    return f"{prefix}data: {json.dumps(data, ensure_ascii=False)}\n\n"


def _is_allowed_script_filename(filename: str) -> bool:
    """Return True when filename matches the hardening script whitelist."""
    if not filename or "/" in filename or "\\" in filename:
        return False
    if Path(filename).name != filename:
        return False
    return any(fnmatchcase(filename, pattern) for pattern in SCRIPT_FILENAME_PATTERNS)


def _validate_download_csrf() -> bool:
    """Validate CSRF for GET-based script downloads."""
    expected = session.get("_csrf_token")
    supplied = (
        request.headers.get("X-CSRF-Token")
        or request.args.get("_csrf_token")
        or request.args.get("csrf_token")
        or request.form.get("_csrf_token")
    )
    return bool(expected and supplied and secrets.compare_digest(str(expected), str(supplied)))


def _resolve_script_path(output_dir: str, filename: str) -> Path | None:
    """Resolve a script path under report_output_dir without allowing traversal."""
    base_dir = Path(output_dir).expanduser().resolve(strict=False)
    script_path = (base_dir / filename).resolve(strict=False)
    if script_path.parent != base_dir or not script_path.is_file():
        return None
    return script_path


def _script_basename(path: str | None) -> str:
    """Return a generated script basename suitable for download URL construction."""
    if not path:
        return ""
    return Path(path).name


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
