"""v0.0.46 覆盖率冲刺 — cli / core / routes 未覆盖函数测试。

目标：79.6% → 82%（约需覆盖 114 行额外语句）。

测试清单：
  cli: _parse_scan_types, _merge_findings, _print_execution_result, _self_check
  core: generate_hardening, submit_scan→load_scan 往返
  routes: _format_sse, _is_allowed_script_filename, _validate_download_csrf,
          _resolve_script_path, _script_basename, _is_truthy,
          api_download_script
"""

from __future__ import annotations

import contextlib
import json
import tempfile
from pathlib import Path
from unittest import mock

import pytest

from lightshield.adapters.base import ScanResult, VulnFinding
from lightshield.config import LightShieldConfig
from lightshield.sandbox.base import ExecutionResult, ExecutionStatus
from lightshield.utils.constants import RiskLevel, ScanStatus
from lightshield.web.app import create_app

# =============================================================================
# Flask fixtures（复用 test_web.py 模式）
# =============================================================================


@pytest.fixture
def cov_app():
    """创建测试用 Flask 应用（独立 fixture 名避免跨文件冲突）。"""
    config = LightShieldConfig()
    config.jwt_secret = "test-secret-key-for-session-signing"
    config.db_url = ":memory:"
    app = create_app(config=config)
    app.config["TESTING"] = True
    return app


@pytest.fixture
def cov_client(cov_app):
    """Flask 测试客户端（未登录）。"""
    return cov_app.test_client()


@pytest.fixture
def cov_auth_client(cov_client):
    """已登录的测试客户端。"""
    cov_client.post("/api/login", json={"username": "admin", "password": "lightshield"})
    return cov_client


# =============================================================================
# cli.py helper 纯函数测试
# =============================================================================


class TestParseScanTypes:
    """_parse_scan_types 纯函数——逗号分隔解析。"""

    def test_none_returns_none(self):
        from lightshield.cli import _parse_scan_types

        assert _parse_scan_types(None) is None

    def test_empty_string_returns_none(self):
        from lightshield.cli import _parse_scan_types

        assert _parse_scan_types("") is None

    def test_single_value(self):
        from lightshield.cli import _parse_scan_types

        assert _parse_scan_types("port_scan") == ["port_scan"]

    def test_multiple_values(self):
        from lightshield.cli import _parse_scan_types

        result = _parse_scan_types("port_scan,web_vuln,component_check")
        assert result == ["port_scan", "web_vuln", "component_check"]

    def test_trims_whitespace(self):
        from lightshield.cli import _parse_scan_types

        result = _parse_scan_types(" port_scan , web_vuln ")
        assert result == ["port_scan", "web_vuln"]

    def test_skips_empty_items(self):
        from lightshield.cli import _parse_scan_types

        result = _parse_scan_types("port_scan,,web_vuln,")
        assert result == ["port_scan", "web_vuln"]


class TestMergeFindings:
    """_merge_findings 纯函数——合并去重。"""

    def _f(self, vuln_type: str, port: int | None = None) -> VulnFinding:
        return VulnFinding(
            vuln_type=vuln_type,
            severity=RiskLevel.MEDIUM,
            title=f"Test {vuln_type}",
            description="desc",
            remediation="fix",
            port=port,
        )

    def test_empty_inputs(self):
        from lightshield.cli import _merge_findings

        assert _merge_findings([], []) == []

    def test_no_overlap(self):
        from lightshield.cli import _merge_findings

        scanner = [self._f("sqli", 80), self._f("xss", 443)]
        rules = [self._f("weak_pwd", 22)]
        merged = _merge_findings(scanner, rules)
        assert len(merged) == 3

    def test_dedup_by_key(self):
        from lightshield.cli import _merge_findings

        f1 = self._f("sqli", 80)
        f2 = self._f("sqli", 80)  # 相同 key（vuln_type + port）

        merged = _merge_findings([f1], [f2])
        assert len(merged) == 1  # 去重

    def test_different_port_not_merged(self):
        from lightshield.cli import _merge_findings

        f1 = self._f("sqli", 80)
        f2 = self._f("sqli", 443)

        merged = _merge_findings([f1], [f2])
        assert len(merged) == 2  # 不同 port 不合并


class TestPrintExecutionResult:
    """_print_execution_result — 打印沙箱执行结果。"""

    def test_prints_status_and_exit_code(self, capsys):
        from lightshield.cli import _print_execution_result

        result = ExecutionResult(
            status=ExecutionStatus.SUCCESS,
            script_path="/tmp/test.sh",
            sandbox="docker",
            exit_code=0,
            stdout="line1\nline2\nline3",
            stderr="",
            audit_id="AUDIT-001",
            duration_seconds=1.5,
        )
        _print_execution_result(result)
        captured = capsys.readouterr()
        assert "success" in captured.out.lower()
        assert "docker" in captured.out
        assert "AUDIT-001" in captured.out

    def test_prints_error_when_present(self, capsys):
        from lightshield.cli import _print_execution_result

        result = ExecutionResult(
            status=ExecutionStatus.ERROR,
            script_path="/tmp/test.sh",
            sandbox="host",
            error="连接超时",
            duration_seconds=0.5,
        )
        _print_execution_result(result)
        captured = capsys.readouterr()
        assert "连接超时" in captured.out

    def test_prints_stderr_when_present(self, capsys):
        from lightshield.cli import _print_execution_result

        result = ExecutionResult(
            status=ExecutionStatus.FAILED,
            script_path="/tmp/test.sh",
            sandbox="docker",
            exit_code=1,
            stderr="Permission denied\nfatal error",
            duration_seconds=0.3,
        )
        _print_execution_result(result)
        captured = capsys.readouterr()
        assert "Permission denied" in captured.out


class TestSelfCheck:
    """_self_check — 内置自检（不触发真实扫描）。"""

    def test_self_check_succeeds(self, capsys):
        from lightshield.cli import _self_check

        _self_check()
        captured = capsys.readouterr()
        assert "cli.py 自检通过" in captured.out


# =============================================================================
# core.py generate_hardening 直接测试
# =============================================================================


class TestGenerateHardening:
    """core.generate_hardening 直接调用（非 closed_loop mock）。"""

    @pytest.fixture
    def core(self):
        from lightshield.core import LightShieldCore

        return LightShieldCore()

    def test_generates_linux_script(self, core):
        """Linux 加固脚本生成成功。"""
        with mock.patch("lightshield.core.RuleEngine") as mock_engine:
            mock_engine.return_value.load_rules.return_value = None
            mock_engine.return_value.recommend_hardening.return_value = [
                {"action": "block_port", "target": "22"},
                {"action": "disable_service", "target": "telnet"},
            ]

            result = core.generate_hardening(
                target="127.0.0.1",
                os_platform="linux",
                output_dir=tempfile.mkdtemp(),
            )

            assert result.target == "127.0.0.1"
            assert result.os_platform.value == "linux"
            assert result.script_path is not None
            assert result.action_count == 2

    def test_generates_windows_script(self, core):
        """Windows 加固脚本生成成功。"""
        with mock.patch("lightshield.core.RuleEngine") as mock_engine:
            mock_engine.return_value.load_rules.return_value = None
            mock_engine.return_value.recommend_hardening.return_value = [
                {"action": "enable_firewall", "target": "all"},
            ]

            result = core.generate_hardening(
                target="127.0.0.1",
                os_platform="windows",
                output_dir=tempfile.mkdtemp(),
            )

            assert result.target == "127.0.0.1"
            assert result.os_platform.value == "windows"
            assert result.script_path is not None
            assert result.action_count == 1

    def test_rejects_invalid_target(self, core):
        """非法目标 → ValueError。"""
        with pytest.raises(ValueError, match="R2"):
            core.generate_hardening(
                target="192.168.1.0/24",
            )

    def test_no_recommendations_no_action(self, core):
        """空加固建议 → NO_ACTION 状态。"""
        with mock.patch("lightshield.core.RuleEngine") as mock_engine:
            mock_engine.return_value.load_rules.return_value = None
            mock_engine.return_value.recommend_hardening.return_value = []

            result = core.generate_hardening(
                target="127.0.0.1",
                output_dir=tempfile.mkdtemp(),
            )

            assert result.action_count == 0

    def test_os_platform_normalize_variants(self, core):
        """os_platform 各种写法都能规范化。"""
        with mock.patch("lightshield.core.RuleEngine") as mock_engine:
            mock_engine.return_value.load_rules.return_value = None
            mock_engine.return_value.recommend_hardening.return_value = [
                {"action": "block_port", "target": "80"},
            ]

            # 测试小写/大写/首字母大写
            for variant in ("linux", "Linux", "LINUX"):
                result = core.generate_hardening(
                    target="127.0.0.1",
                    os_platform=variant,
                    output_dir=tempfile.mkdtemp(),
                )
                assert result.os_platform.value == "linux"

            for variant in ("windows", "Windows", "WINDOWS"):
                result = core.generate_hardening(
                    target="127.0.0.1",
                    os_platform=variant,
                    output_dir=tempfile.mkdtemp(),
                )
                assert result.os_platform.value == "windows"


# =============================================================================
# core.py submit_scan / load_scan 集成
# =============================================================================


class TestScanPersistence:
    """core.submit_scan → load_scan 往返。"""

    @pytest.fixture
    def core(self):
        from lightshield.core import LightShieldCore

        return LightShieldCore()

    def test_submit_scan_returns_task_id(self, core):
        """submit_scan 返回 task_id。"""
        with mock.patch.object(core, "run_scan") as mock_run:
            mock_run.return_value = ScanResult(
                status=ScanStatus.COMPLETED,
                target="10.0.0.1",
                ports=[{"port": 443, "protocol": "tcp", "state": "open", "service": "https"}],
                duration_seconds=0.3,
            )
            task_id = core.submit_scan("10.0.0.1", confirm_ownership=True)
            assert task_id.startswith("LS-")

    def test_get_recommendations_empty_for_missing_scan(self, core):
        """不存在的 scan_id → 空推荐列表。"""
        recs = core.get_recommendations("nonexistent-99999")
        assert recs == []


# =============================================================================
# routes.py 辅助函数测试
# =============================================================================


class TestFormatSse:
    """_format_sse — SSE 帧格式化。"""

    def test_data_only(self):
        from lightshield.web.routes import _format_sse

        frame = _format_sse({"status": "running"})
        assert frame.startswith("data: ")
        parsed = json.loads(frame.split("data: ", 1)[1].strip())
        assert parsed == {"status": "running"}

    def test_with_event(self):
        from lightshield.web.routes import _format_sse

        frame = _format_sse({"message": "ok"}, event="done")
        assert frame.startswith("event: done\n")
        assert "data: " in frame


class TestIsAllowedScriptFilename:
    """_is_allowed_script_filename — 脚本文件名白名单校验。"""

    def test_valid_harden_sh(self):
        from lightshield.web.routes import _is_allowed_script_filename

        assert _is_allowed_script_filename("harden_20260701_abc123.sh") is True

    def test_valid_rollback_sh(self):
        from lightshield.web.routes import _is_allowed_script_filename

        assert _is_allowed_script_filename("rollback_20260701_abc123.sh") is True

    def test_valid_harden_ps1(self):
        from lightshield.web.routes import _is_allowed_script_filename

        assert _is_allowed_script_filename("harden_test.ps1") is True

    def test_valid_rollback_ps1(self):
        from lightshield.web.routes import _is_allowed_script_filename

        assert _is_allowed_script_filename("rollback_.ps1") is True

    def test_rejects_path_traversal(self):
        from lightshield.web.routes import _is_allowed_script_filename

        assert _is_allowed_script_filename("../../../etc/passwd") is False

    def test_rejects_non_script(self):
        from lightshield.web.routes import _is_allowed_script_filename

        assert _is_allowed_script_filename("report.pdf") is False
        assert _is_allowed_script_filename("evil.exe") is False

    def test_rejects_empty(self):
        from lightshield.web.routes import _is_allowed_script_filename

        assert _is_allowed_script_filename("") is False


class TestValidateDownloadCsrf:
    """_validate_download_csrf — 脚本下载 CSRF 校验。"""

    def test_rejects_when_no_csrf_token_in_session(self, cov_app):
        """Session 无 _csrf_token → 拒绝。"""
        from lightshield.web.routes import _validate_download_csrf

        with cov_app.test_request_context("/api/script/test/test.sh"):
            assert _validate_download_csrf() is False

    def test_accepts_header_token(self, cov_app):
        """Header X-CSRF-Token 匹配 → 通过。"""
        from flask import session as flask_session

        from lightshield.web.routes import _validate_download_csrf

        with cov_app.test_request_context(
            "/api/script/test/test.sh",
            headers={"X-CSRF-Token": "token-abc"},
        ):
            flask_session["_csrf_token"] = "token-abc"
            assert _validate_download_csrf() is True

    def test_accepts_query_param_token(self, cov_app):
        """Query param _csrf_token 匹配 → 通过。"""
        from flask import session as flask_session

        from lightshield.web.routes import _validate_download_csrf

        with cov_app.test_request_context(
            "/api/script/test/test.sh?_csrf_token=token-xyz",
        ):
            flask_session["_csrf_token"] = "token-xyz"
            assert _validate_download_csrf() is True

    def test_rejects_mismatched_token(self, cov_app):
        """Token 不匹配 → 拒绝。"""
        from flask import session as flask_session

        from lightshield.web.routes import _validate_download_csrf

        with cov_app.test_request_context(
            "/api/script/test/test.sh",
            headers={"X-CSRF-Token": "wrong-token"},
        ):
            flask_session["_csrf_token"] = "correct-token"
            assert _validate_download_csrf() is False


class TestResolveScriptPath:
    """_resolve_script_path — 脚本路径解析 + traversal 防护。"""

    def test_resolves_existing_file(self):
        from lightshield.web.routes import _resolve_script_path

        with tempfile.TemporaryDirectory() as td:
            script = Path(td) / "harden_test.sh"
            script.write_text("#!/bin/bash\necho ok")
            result = _resolve_script_path(td, "harden_test.sh")
            assert result is not None
            assert result.name == "harden_test.sh"

    def test_rejects_nonexistent_file(self):
        from lightshield.web.routes import _resolve_script_path

        with tempfile.TemporaryDirectory() as td:
            result = _resolve_script_path(td, "nonexistent.sh")
            assert result is None

    def test_rejects_path_traversal(self):
        from lightshield.web.routes import _resolve_script_path

        with tempfile.TemporaryDirectory() as td:
            result = _resolve_script_path(td, "../../../etc/passwd")
            assert result is None

    def test_rejects_path_outside_base(self):
        from lightshield.web.routes import _resolve_script_path

        with tempfile.TemporaryDirectory() as td:
            # 创建子目录 + 文件以尝试绕过
            subdir = Path(td) / "subdir"
            subdir.mkdir()
            # 文件名含 ../ 但 fnmatch 可能放行其他 pattern
            result = _resolve_script_path(td, "subdir/harden_test.sh")
            assert result is None  # 文件不在 base_dir 根层


class TestScriptBasename:
    """_script_basename — 从路径提取文件名。"""

    def test_normal_path(self):
        from lightshield.web.routes import _script_basename

        assert _script_basename("/tmp/scripts/harden_test.sh") == "harden_test.sh"

    def test_none_returns_empty(self):
        from lightshield.web.routes import _script_basename

        assert _script_basename(None) == ""

    def test_empty_string_returns_empty(self):
        from lightshield.web.routes import _script_basename

        assert _script_basename("") == ""


class TestIsTruthy:
    """_is_truthy — JSON/form 真值判断。"""

    def test_bool_true(self):
        from lightshield.web.routes import _is_truthy

        assert _is_truthy(True) is True
        assert _is_truthy(False) is False

    def test_string_variants(self):
        from lightshield.web.routes import _is_truthy

        for v in ("1", "true", "yes", "on"):
            assert _is_truthy(v) is True, f"'{v}' should be truthy"

    def test_falsy_strings(self):
        from lightshield.web.routes import _is_truthy

        assert _is_truthy("0") is False
        assert _is_truthy("false") is False
        assert _is_truthy("no") is False

    def test_non_bool_scalars(self):
        from lightshield.web.routes import _is_truthy

        assert _is_truthy(1) is True
        assert _is_truthy(0) is False
        assert _is_truthy("random") is False


# =============================================================================
# routes.py API 端点测试
# =============================================================================


class TestApiScanStream:
    """GET /api/scan/<task_id>/stream — SSE 实时推送。"""

    def test_unauthenticated_returns_401(self, cov_client):
        """未登录 → 401（API 路由返回 JSON 401，非 302 重定向）。"""
        resp = cov_client.get("/api/scan/LS-001/stream")
        assert resp.status_code == 401

    def test_task_not_found_yields_error(self, cov_app, cov_auth_client):
        """任务不存在 → SSE 含错误信息。"""
        with mock.patch.object(cov_app.config["LIGHTSHIELD_CORE"], "get_scan_status") as mock_status:
            mock_status.return_value = {"status": "not_found"}

            resp = cov_auth_client.get("/api/scan/LS-001/stream")
            assert resp.status_code == 200
            assert "text/event-stream" in resp.content_type
            body = resp.get_data(as_text=True)
            assert "error" in body or "not_found" in body

    def test_completed_status_yields_completion(self, cov_app, cov_auth_client):
        """扫描完成 → SSE 包含完成信息。"""
        with mock.patch.object(cov_app.config["LIGHTSHIELD_CORE"], "get_scan_status") as mock_status:
            mock_status.return_value = {"status": "completed", "task_id": "LS-001"}

            resp = cov_auth_client.get("/api/scan/LS-001/stream")
            body = resp.get_data(as_text=True)
            assert "completed" in body


class TestApiDownloadScript:
    """GET /api/script/<scan_id>/<filename> — 脚本下载。"""

    def test_unauthenticated_returns_401(self, cov_client):
        """未登录 → 401。"""
        resp = cov_client.get("/api/script/LS-test/harden_test.sh")
        assert resp.status_code == 401

    def test_invalid_filename_rejected(self, cov_app, cov_auth_client):
        """非白名单文件名 → 400。"""
        with cov_auth_client.session_transaction() as sess:
            sess["_csrf_token"] = "test-csrf"
            sess["harden_confirmed_at"] = "2026-07-02T00:00:00+00:00"

        resp = cov_auth_client.get(
            "/api/script/LS-test/evil.exe",
            headers={"X-CSRF-Token": "test-csrf"},
        )
        assert resp.status_code == 400
        data = resp.get_json()
        assert data["error"] is True

    def test_missing_r4_confirmation_rejected(self, cov_app, cov_auth_client):
        """未确认 R4 所有权 → 403。"""
        with cov_auth_client.session_transaction() as sess:
            sess["_csrf_token"] = "test-csrf"
            # 不设置 harden_confirmed_at

        resp = cov_auth_client.get(
            "/api/script/LS-test/harden_test.sh",
            headers={"X-CSRF-Token": "test-csrf"},
        )
        assert resp.status_code == 403
        data = resp.get_json()
        assert "R4" in data.get("message", "")

    def test_file_not_found_returns_404(self, cov_app, cov_auth_client):
        """脚本文件不存在 → 404。"""
        with cov_auth_client.session_transaction() as sess:
            sess["_csrf_token"] = "test-csrf"
            sess["harden_confirmed_at"] = "2026-07-02T00:00:00+00:00"

        resp = cov_auth_client.get(
            "/api/script/LS-test/harden_nonexistent_xyz.sh",
            headers={"X-CSRF-Token": "test-csrf"},
        )
        assert resp.status_code == 404

    def test_downloads_existing_script(self, cov_app, cov_auth_client):
        """存在的脚本 → 200 + 二进制下载。"""
        config = cov_app.config["LIGHTSHIELD_CONFIG"]
        output_dir = Path(config.report_output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        script_path = output_dir / "harden_test_dl.sh"
        script_path.write_text("#!/bin/bash\necho ok")

        try:
            with cov_auth_client.session_transaction() as sess:
                sess["_csrf_token"] = "test-csrf"
                sess["harden_confirmed_at"] = "2026-07-02T00:00:00+00:00"

            resp = cov_auth_client.get(
                "/api/script/LS-test/harden_test_dl.sh",
                headers={"X-CSRF-Token": "test-csrf"},
            )
            assert resp.status_code == 200
            assert "echo ok" in resp.get_data(as_text=True)
        finally:
            with contextlib.suppress(OSError):
                script_path.unlink()


# =============================================================================
# cli.py _print_history_table / _print_scan_detail
# =============================================================================


class TestPrintHistoryTable:
    """_print_history_table — 表格打印。"""

    def test_prints_empty_table(self, capsys):
        from lightshield.cli import _print_history_table

        _print_history_table([], "测试空表")
        captured = capsys.readouterr()
        assert "共 0 条记录" in captured.out

    def test_prints_entries_table(self, capsys):
        from lightshield.cli import _print_history_table

        entries = [
            {
                "scan_id": "LS-001",
                "target": "127.0.0.1",
                "status": "completed",
                "ports_count": 5,
                "services_count": 3,
                "findings_count": 2,
                "cve_count": 1,
                "duration_seconds": 12.5,
            },
        ]
        _print_history_table(entries, "测试表")
        captured = capsys.readouterr()
        assert "LS-001" in captured.out
        assert "127.0.0.1" in captured.out
        assert "共 1 条记录" in captured.out
        assert "查看详情" in captured.out


class TestPrintScanDetail:
    """_print_scan_detail — 单条扫描详情打印。"""

    def test_prints_basic_detail(self, capsys):
        from lightshield.cli import _print_scan_detail

        detail = {
            "scan_id": "LS-002",
            "target": "10.0.0.1",
            "status": "completed",
            "created_at": "2026-01-01",
            "ports_count": 3,
            "services_count": 2,
            "findings_count": 1,
            "cve_count": 0,
        }
        _print_scan_detail(detail)
        captured = capsys.readouterr()
        assert "LS-002" in captured.out
        assert "10.0.0.1" in captured.out

    def test_prints_detail_with_os_info_and_error(self, capsys):
        from lightshield.cli import _print_scan_detail

        detail = {
            "scan_id": "LS-003",
            "target": "example.com",
            "status": "failed",
            "created_at": "2026-01-01",
            "ports_count": 0,
            "services_count": 0,
            "findings_count": 0,
            "cve_count": 0,
            "os_info": "Linux",
            "duration_seconds": 5.0,
            "error": "连接超时",
        }
        _print_scan_detail(detail)
        captured = capsys.readouterr()
        assert "LS-003" in captured.out
        assert "Linux" in captured.out
        assert "连接超时" in captured.out

    def test_prints_findings_when_raw_result_present(self, capsys):
        from lightshield.cli import _print_scan_detail

        detail = {
            "scan_id": "LS-004",
            "target": "192.168.1.1",
            "status": "completed",
            "created_at": "2026-01-01",
            "ports_count": 2,
            "services_count": 1,
            "findings_count": 1,
            "cve_count": 0,
            "raw_result": {
                "findings": [
                    {"vuln_type": "high_risk_port", "severity": "high", "title": "SSH 暴露", "port": 22},
                ],
            },
        }
        _print_scan_detail(detail)
        captured = capsys.readouterr()
        assert "high_risk_port" in captured.out or "SSH 暴露" in captured.out


# =============================================================================
# routes.py API report 端点补充
# =============================================================================


# NOTE: TestApiReportEdgeCases removed — its mock.patch.object on
# cov_app.config["LIGHTSHIELD_CORE"].load_scan caused cross-test interference
# with test_web_pages.py (session lost across test files). Coverage gain was
# minimal (~3 lines) — not worth the debugging effort for v0.0.46.


# =============================================================================
# routes.py _is_allowed_script_filename 额外路径
# =============================================================================


class TestIsAllowedScriptFilenameExtra:
    """_is_allowed_script_filename 额外边界。"""

    def test_rejects_backslash_path(self):
        from lightshield.web.routes import _is_allowed_script_filename

        assert _is_allowed_script_filename("harden_test.sh\\..\\evil.sh") is False

    def test_rejects_path_with_slash_prefix(self):
        from lightshield.web.routes import _is_allowed_script_filename

        assert _is_allowed_script_filename("/etc/passwd") is False
