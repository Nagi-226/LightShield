"""LightShield Web API 单元测试 — v0.0.27

被测模块：lightshield/web/ (app.py, auth.py, routes.py)
测试策略：使用 Flask test_client，mock LightShieldCore 和 Repository。

覆盖：
  - 登录/登出（成功、失败、缺字段）
  - 会话保护（未登录拦截、已登录放行）
  - 扫描提交（成功、R2 拒绝、缺 target）
  - 扫描状态查询（找到、未找到）
  - 报告获取（markdown/text、扫描不存在、未完成）
  - HTTP 错误处理（404/405/500 JSON 响应）
  - CLI serve 子命令解析
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from lightshield.config import LightShieldConfig
from lightshield.web.app import create_app

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def app():
    """创建测试用 Flask 应用（注入 mock core + 测试密钥）。"""
    config = LightShieldConfig()
    config.jwt_secret = "test-secret-key-for-session-signing"
    app = create_app(config=config)
    app.config["TESTING"] = True
    return app


@pytest.fixture
def client(app):
    """Flask 测试客户端（未登录）。"""
    return app.test_client()


@pytest.fixture
def auth_client(client):
    """已登录的测试客户端。"""
    client.post("/api/login", json={"username": "admin", "password": "lightshield"})
    return client


def csrf_header(client, token: str = "test-csrf-token") -> dict[str, str]:
    """Seed the session with a CSRF token and return the matching AJAX header."""
    with client.session_transaction() as sess:
        sess["_csrf_token"] = token
    return {"X-CSRF-Token": token}


@pytest.fixture
def mock_core(app):
    """替换 app 中的 LightShieldCore 为 mock。"""
    with (
        patch.object(app.config["LIGHTSHIELD_CORE"], "submit_scan") as mock_submit,
        patch.object(app.config["LIGHTSHIELD_CORE"], "get_scan_status") as mock_status,
    ):
        mock_submit.return_value = "LS-20260614-120000-a1b2c3"
        mock_status.return_value = {
            "task_id": "LS-20260614-120000-a1b2c3",
            "status": "completed",
            "target": "127.0.0.1",
            "ports": 5,
            "findings": 2,
            "duration_seconds": 12.5,
            "error": None,
        }
        yield {"submit_scan": mock_submit, "get_scan_status": mock_status}


@pytest.fixture
def mock_repo():
    """Mock get_repository，返回含假数据的仓库。"""
    with patch("lightshield.web.routes.get_repository") as mock_get_repo:
        repo = MagicMock()
        repo.get.return_value = {
            "scan_id": "LS-20260614-120000-a1b2c3",
            "target": "127.0.0.1",
            "status": "completed",
            "ports_count": 5,
            "services_count": 3,
            "findings_count": 2,
            "cve_count": 1,
            "os_info": "Linux",
            "error": None,
            "duration_seconds": 12.5,
            "created_at": "2026-06-14T12:00:00",
            "raw_result": {
                "target": "127.0.0.1",
                "status": "completed",
                "ports": [{"port": 22, "protocol": "tcp", "state": "open", "service": "ssh"}],
                "services": [{"name": "ssh", "version": "OpenSSH 8.9", "port": 22}],
                "os_info": "Linux",
                "findings": [
                    {
                        "vuln_type": "high_risk_port",
                        "severity": "medium",
                        "title": "SSH 端口对外开放",
                        "description": "SSH 服务暴露在公网",
                        "remediation": "限制 SSH 访问来源 IP",
                        "port": 22,
                    },
                ],
                "error": None,
                "duration_seconds": 12.5,
            },
        }
        mock_get_repo.return_value = repo
        yield repo


# =============================================================================
# TestAuth — 登录/登出
# =============================================================================


class TestAuth:
    """登录与登出功能测试。"""

    def test_login_success(self, client):
        """正确的用户名密码应返回 200 并设置 session。"""
        resp = client.post("/api/login", json={"username": "admin", "password": "lightshield"})
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["success"] is True
        assert "登录成功" in data["message"]

    def test_login_wrong_password(self, client):
        """错误的密码应返回 401。"""
        resp = client.post("/api/login", json={"username": "admin", "password": "wrong"})
        assert resp.status_code == 401
        data = resp.get_json()
        assert data["error"] is True

    def test_login_missing_fields(self, client):
        """缺少用户名或密码应返回 400。"""
        resp = client.post("/api/login", json={"username": "admin"})
        assert resp.status_code == 400

        resp = client.post("/api/login", json={"password": "lightshield"})
        assert resp.status_code == 400

        resp = client.post("/api/login", json={})
        assert resp.status_code == 400

    def test_login_empty_body(self, client):
        """空请求体或无 JSON 应返回 400。"""
        resp = client.post("/api/login", data="not json")
        assert resp.status_code == 400

    # ---- C-003: 登录字段类型校验 ----

    def test_login_username_null_rejected(self, client):
        """C-003: username 为 JSON null → 400。"""
        resp = client.post("/api/login", json={"username": None, "password": "lightshield"})
        assert resp.status_code == 400
        data = resp.get_json()
        assert "必须为字符串" in data["message"]

    def test_login_username_number_rejected(self, client):
        """C-003: username 为数字 → 400。"""
        resp = client.post("/api/login", json={"username": 42, "password": "lightshield"})
        assert resp.status_code == 400
        data = resp.get_json()
        assert "必须为字符串" in data["message"]

    def test_login_password_list_rejected(self, client):
        """C-003: password 为数组 → 400。"""
        resp = client.post("/api/login", json={"username": "admin", "password": ["a", "b"]})
        assert resp.status_code == 400
        data = resp.get_json()
        assert "必须为字符串" in data["message"]

    def test_login_both_non_string_rejected(self, client):
        """C-003: 两个字段都是非字符串 → 400。"""
        resp = client.post("/api/login", json={"username": True, "password": 3.14})
        assert resp.status_code == 400

    def test_logout(self, auth_client):
        """登出应返回 200 并清除 session。"""
        resp = auth_client.post("/api/logout")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["success"] is True

    def test_protected_endpoint_without_login(self, client):
        """未登录调用受保护端点应返回 401。"""
        resp = client.post("/api/scan", json={"target": "127.0.0.1"})
        assert resp.status_code == 401
        data = resp.get_json()
        assert data["error"] is True
        assert data["code"] == 401

    def test_protected_endpoint_with_login(self, auth_client, mock_core):
        """已登录调用受保护端点应正常返回。"""
        resp = auth_client.post(
            "/api/scan",
            json={"target": "127.0.0.1"},
            headers=csrf_header(auth_client),
        )
        assert resp.status_code == 202


# =============================================================================
# TestScanAPI — 扫描提交与状态查询
# =============================================================================


class TestScanAPI:
    """扫描 API 端点测试。"""

    def test_submit_scan_success(self, auth_client, mock_core):
        """合法目标应返回 202 和 task_id。"""
        resp = auth_client.post(
            "/api/scan",
            json={"target": "127.0.0.1", "scan_types": ["port_scan"], "confirm_ownership": True},
            headers=csrf_header(auth_client),
        )
        assert resp.status_code == 202
        data = resp.get_json()
        assert "task_id" in data
        assert data["status"] == "accepted"
        assert data["target"] == "127.0.0.1"
        mock_core["submit_scan"].assert_called_once_with(
            target="127.0.0.1", scan_types=["port_scan"], confirm_ownership=True
        )

    def test_submit_scan_rejects_missing_csrf(self, auth_client, mock_core):
        """已登录的 POST /api/scan 缺少 CSRF token 应返回 403。"""
        resp = auth_client.post("/api/scan", json={"target": "127.0.0.1"})
        assert resp.status_code == 403
        data = resp.get_json()
        assert data["error"] is True
        assert data["code"] == 403
        mock_core["submit_scan"].assert_not_called()

    def test_submit_scan_r2_reject_cidr(self, auth_client, mock_core):
        """CIDR 网段应被 R2 校验拒绝（400）。"""
        resp = auth_client.post(
            "/api/scan",
            json={"target": "192.168.1.0/24"},
            headers=csrf_header(auth_client),
        )
        assert resp.status_code == 400
        data = resp.get_json()
        assert data["error"] is True
        assert "R2" in data["message"]
        mock_core["submit_scan"].assert_not_called()

    def test_submit_scan_r2_reject_empty(self, auth_client, mock_core):
        """空字符串目标应被拒绝（400）。"""
        resp = auth_client.post("/api/scan", json={"target": ""}, headers=csrf_header(auth_client))
        assert resp.status_code == 400
        mock_core["submit_scan"].assert_not_called()

    def test_submit_scan_missing_target(self, auth_client, mock_core):
        """缺少 target 字段应返回 400。"""
        resp = auth_client.post(
            "/api/scan",
            json={"scan_types": ["port_scan"]},
            headers=csrf_header(auth_client),
        )
        assert resp.status_code == 400
        mock_core["submit_scan"].assert_not_called()

    def test_submit_scan_empty_body(self, auth_client):
        """空请求体应返回 400。"""
        resp = auth_client.post("/api/scan", data="not json", headers=csrf_header(auth_client))
        assert resp.status_code == 400

    def test_submit_scan_default_scan_types(self, auth_client, mock_core):
        """不传 scan_types 时应传 None 给 core（表示全部）。"""
        resp = auth_client.post(
            "/api/scan",
            json={"target": "127.0.0.1"},
            headers=csrf_header(auth_client),
        )
        assert resp.status_code == 202
        mock_core["submit_scan"].assert_called_once_with(target="127.0.0.1", scan_types=None, confirm_ownership=False)

    def test_get_scan_status_found(self, auth_client, mock_core):
        """存在的 task_id 应返回完整状态。"""
        resp = auth_client.get("/api/scan/LS-20260614-120000-a1b2c3")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["task_id"] == "LS-20260614-120000-a1b2c3"
        assert data["status"] == "completed"
        assert data["ports"] == 5

    def test_get_scan_status_not_found(self, auth_client, mock_core):
        """不存在的 task_id 应返回 404。"""
        mock_core["get_scan_status"].return_value = {"task_id": "LS-bogus", "status": "not_found"}
        resp = auth_client.get("/api/scan/LS-bogus")
        assert resp.status_code == 404
        data = resp.get_json()
        assert data["error"] is True
        assert data["code"] == 404


# =============================================================================
# TestReportAPI — 报告获取
# =============================================================================


class TestReportAPI:
    """报告 API 端点测试。"""

    def test_get_report_markdown(self, auth_client, mock_repo):
        """默认 format=markdown 应返回 markdown 报告文本。"""
        resp = auth_client.get("/api/report/LS-20260614-120000-a1b2c3")
        assert resp.status_code == 200
        assert "text/plain" in resp.content_type
        assert "# LightShield" in resp.get_data(as_text=True)

    def test_get_report_text(self, auth_client, mock_repo):
        """format=text 应返回纯文本报告。"""
        resp = auth_client.get("/api/report/LS-20260614-120000-a1b2c3?format=text")
        assert resp.status_code == 200
        assert "text/plain" in resp.content_type

    def test_get_report_pdf(self, auth_client, mock_repo):
        """format=pdf 应返回 PDF 字节流。"""
        with patch("lightshield.web.routes.ReportGenerator") as mock_reporter_cls:
            reporter = MagicMock()
            reporter.generate.return_value = b"%PDF-1.4\nfake\n%%EOF"
            mock_reporter_cls.return_value = reporter

            resp = auth_client.get("/api/report/LS-20260614-120000-a1b2c3?format=pdf")

        assert resp.status_code == 200
        assert "application/pdf" in resp.content_type
        assert resp.get_data().startswith(b"%PDF")
        reporter.generate.assert_called_once()

    def test_get_report_not_found(self, auth_client, mock_repo):
        """不存在的 scan_id 应返回 404。"""
        mock_repo.get.return_value = None
        resp = auth_client.get("/api/report/LS-bogus")
        assert resp.status_code == 404
        data = resp.get_json()
        assert data["error"] is True
        assert data["code"] == 404

    def test_get_report_scan_incomplete(self, auth_client, mock_repo):
        """未完成的扫描（status=failed）应返回 409。"""
        mock_repo.get.return_value = {
            "scan_id": "LS-20260614-120000-a1b2c3",
            "target": "127.0.0.1",
            "status": "failed",
            "raw_result": {"target": "127.0.0.1", "status": "failed", "findings": [], "ports": [], "services": []},
        }
        resp = auth_client.get("/api/report/LS-20260614-120000-a1b2c3")
        assert resp.status_code == 409
        data = resp.get_json()
        assert data["error"] is True
        assert data["code"] == 409

    def test_get_report_scan_partial_allowed(self, auth_client, mock_repo):
        """部分完成的扫描（partial）应允许生成报告。"""
        mock_repo.get.return_value["status"] = "partial"
        mock_repo.get.return_value["raw_result"]["status"] = "partial"
        resp = auth_client.get("/api/report/LS-20260614-120000-a1b2c3")
        assert resp.status_code == 200


# =============================================================================
# TestHardenAPI — 加固脚本生成
# =============================================================================


class TestHardenAPI:
    """加固 API 端点测试。"""

    def test_generate_harden_requires_login(self, client):
        """未登录调用加固生成端点应返回 401。"""
        resp = client.post("/api/harden/LS-20260614-120000-a1b2c3", json={"confirm_ownership": True})
        assert resp.status_code == 401

    def test_generate_harden_rejects_missing_csrf(self, auth_client):
        """已登录但缺少 CSRF token 时应返回 403。"""
        resp = auth_client.post("/api/harden/LS-20260614-120000-a1b2c3", json={"confirm_ownership": True})
        assert resp.status_code == 403
        data = resp.get_json()
        assert data["code"] == 403

    def test_generate_harden_requires_r4_confirmation(self, auth_client):
        """加固脚本生成前必须再次确认 R4 所有权。"""
        resp = auth_client.post(
            "/api/harden/LS-20260614-120000-a1b2c3",
            json={"os_platform": "linux", "confirm_ownership": False},
            headers=csrf_header(auth_client),
        )
        assert resp.status_code == 400
        data = resp.get_json()
        assert data["error"] is True
        assert "R4" in data["message"]

    def test_generate_harden_rejects_invalid_os(self, auth_client):
        """只允许 linux / windows 两种加固脚本目标平台。"""
        resp = auth_client.post(
            "/api/harden/LS-20260614-120000-a1b2c3",
            json={"os_platform": "macos", "confirm_ownership": True},
            headers=csrf_header(auth_client),
        )
        assert resp.status_code == 400
        data = resp.get_json()
        assert data["error"] is True

    def test_generate_harden_returns_404_for_missing_scan(self, auth_client):
        """扫描记录不存在时不应调用核心加固生成逻辑。"""
        with patch("lightshield.web.routes.get_repository") as mock_get_repo:
            repo = MagicMock()
            repo.get.return_value = None
            mock_get_repo.return_value = repo

            resp = auth_client.post(
                "/api/harden/LS-bogus",
                json={"os_platform": "linux", "confirm_ownership": True},
                headers=csrf_header(auth_client),
            )

        assert resp.status_code == 404
        data = resp.get_json()
        assert data["error"] is True

    def test_generate_harden_success(self, auth_client, mock_repo, app):
        """有效请求应基于扫描 findings 生成加固和回滚脚本路径。"""
        result = MagicMock()
        result.status.value = "generated"
        result.action_count = 2
        result.script_path = "reports/harden-127-0-0-1.sh"
        result.rollback_path = "reports/rollback-127-0-0-1.sh"
        app.config["LIGHTSHIELD_CORE"].generate_hardening = MagicMock(return_value=result)

        with patch("lightshield.web.routes.RuleEngine") as mock_engine_class:
            engine = MagicMock()
            engine.recommend_hardening.return_value = [
                {
                    "action": "关闭高危端口",
                    "target": "22",
                    "severity": "high",
                    "reason": "SSH 暴露",
                    "commands": ["ufw deny 22"],
                }
            ]
            mock_engine_class.return_value = engine

            resp = auth_client.post(
                "/api/harden/LS-20260614-120000-a1b2c3",
                json={"os_platform": "linux", "confirm_ownership": True},
                headers=csrf_header(auth_client),
            )

        assert resp.status_code == 200
        data = resp.get_json()
        assert data["success"] is True
        assert data["generated"] is True
        assert data["script_path"] == "reports/harden-127-0-0-1.sh"
        assert data["rollback_path"] == "reports/rollback-127-0-0-1.sh"
        app.config["LIGHTSHIELD_CORE"].generate_hardening.assert_called_once()
        with auth_client.session_transaction() as sess:
            assert "harden_confirmed_at" in sess


# =============================================================================
# TestErrorHandling — HTTP 错误处理
# =============================================================================


class TestErrorHandling:
    """HTTP 错误响应格式测试。"""

    def test_404_unknown_route(self, client):
        """不存在的路由应返回 JSON 格式的 404。"""
        resp = client.get("/api/nonexistent")
        assert resp.status_code == 404
        data = resp.get_json()
        assert data["error"] is True
        assert data["code"] == 404

    def test_405_wrong_method(self, client):
        """错误的方法应返回 JSON 格式的 405。"""
        resp = client.get("/api/login")  # login 只接受 POST
        assert resp.status_code == 405
        data = resp.get_json()
        assert data["error"] is True
        assert data["code"] == 405


# =============================================================================
# TestCLIServe — CLI serve 子命令
# =============================================================================


class TestCLIServe:
    """CLI serve 子命令解析测试。"""

    def test_serve_subcommand_exists(self):
        """Serve 子命令应在 parser 中注册。"""
        from lightshield.cli import create_parser

        parser = create_parser()
        args = parser.parse_args(["serve"])
        assert args.command == "serve"

    def test_serve_default_host_port(self):
        """不传参数时使用默认值。"""
        from lightshield.cli import create_parser

        parser = create_parser()
        args = parser.parse_args(["serve"])
        assert args.host is None  # 由 config.web_host 提供默认值
        assert args.port is None  # 由 config.web_port 提供默认值
        assert args.debug is False

    def test_serve_custom_host_port(self):
        """--host 和 --port 参数应被正确解析。"""
        from lightshield.cli import create_parser

        parser = create_parser()
        args = parser.parse_args(["serve", "--host", "0.0.0.0", "--port", "8080", "--debug"])
        assert args.host == "0.0.0.0"
        assert args.port == 8080
        assert args.debug is True
