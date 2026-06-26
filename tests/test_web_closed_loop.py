"""LightShield v0.0.40 — Web 闭环路由单元测试

测试 POST /api/harden/<scan_id>/verify：
  - 未登录 → 302
  - 无效 mode / os_platform → 400
  - APPLY 缺双确认 → 400
  - DRY_RUN 成功 → 200 + overall="generated_only"
  - APPLY 成功 → 200 + verified
  - APPLY 失败 → 422
  - 不存在 scan_id → 404
"""

from __future__ import annotations

from unittest import mock

import pytest

from lightshield.config import LightShieldConfig
from lightshield.web.app import create_app


@pytest.fixture
def app():
    """创建测试 Flask 应用（mock core + 测试密钥）。"""
    config = LightShieldConfig()
    config.jwt_secret = "test-secret-key"
    config.web_username = "admin"
    config.web_password = "lightshield"
    app = create_app(config=config)
    app.config["TESTING"] = True
    return app


@pytest.fixture
def client(app):
    """未登录客户端。"""
    return app.test_client()


@pytest.fixture
def auth_client(app):
    """已登录客户端。"""
    c = app.test_client()
    c.post("/api/login", json={"username": "admin", "password": "lightshield"})
    return c


@pytest.fixture
def csrf_header(auth_client, token: str = "test-csrf-token") -> dict[str, str]:
    """Seed CSRF token 并返回匹配 header。"""
    with auth_client.session_transaction() as sess:
        sess["_csrf_token"] = token
    return {"X-CSRF-Token": token}


@pytest.fixture
def mock_repo(app):
    """Mock get_repository 返回有效扫描记录。"""
    with mock.patch("lightshield.web.routes.get_repository") as m:
        repo = mock.Mock()
        repo.get.return_value = {
            "scan_id": "LS-test",
            "target": "127.0.0.1",
            "status": "completed",
            "raw_result": {"target": "127.0.0.1", "findings": []},
        }
        m.return_value = repo
        yield m


@pytest.fixture
def mock_closed_loop(app):
    """Mock core.run_harden_closed_loop。"""
    with mock.patch.object(app.config["LIGHTSHIELD_CORE"], "run_harden_closed_loop") as m:
        yield m


# =============================================================================
# 鉴权
# =============================================================================


class TestAuth:
    """鉴权：未登录拒绝。"""

    def test_unauthenticated_returns_redirect(self, client):
        """未登录 → 302。"""
        resp = client.post("/api/harden/LS-test/verify", json={"mode": "dry_run"})
        assert resp.status_code in (302, 401)


# =============================================================================
# 参数校验
# =============================================================================


class TestValidation:
    """参数校验：mode / os_platform / 双确认闸门。"""

    def test_invalid_mode_rejected(self, auth_client, csrf_header):
        resp = auth_client.post(
            "/api/harden/LS-test/verify",
            json={"mode": "dangerous"},
            headers=csrf_header,
        )
        assert resp.status_code == 400

    def test_invalid_os_platform_rejected(self, auth_client, csrf_header):
        resp = auth_client.post(
            "/api/harden/LS-test/verify",
            json={"mode": "dry_run", "os_platform": "macos"},
            headers=csrf_header,
        )
        assert resp.status_code == 400

    def test_apply_missing_confirm_ownership(self, auth_client, csrf_header):
        resp = auth_client.post(
            "/api/harden/LS-test/verify",
            json={"mode": "apply", "confirm_ownership": False, "confirm_execute": True},
            headers=csrf_header,
        )
        assert resp.status_code == 400
        data = resp.get_json()
        assert data["error"] is True
        assert "R4" in data.get("message", "")

    def test_apply_missing_confirm_execute(self, auth_client, csrf_header):
        resp = auth_client.post(
            "/api/harden/LS-test/verify",
            json={"mode": "apply", "confirm_ownership": True, "confirm_execute": False},
            headers=csrf_header,
        )
        assert resp.status_code == 400


# =============================================================================
# 成功 / 失败路径
# =============================================================================


class TestClosedLoop:
    """闭环成功/失败路径：DRY_RUN / APPLY verified / APPLY failed。"""

    def test_dry_run_success(self, auth_client, csrf_header, mock_repo, mock_closed_loop):
        """DRY_RUN → 200 + overall="generated_only"。"""
        from lightshield.harden.closed_loop import ClosedLoopResult
        from lightshield.utils.constants import OSPlatform

        mock_closed_loop.return_value = ClosedLoopResult(
            target="127.0.0.1",
            os_platform=OSPlatform.LINUX,
            mode="dry_run",
            before_scan={"status": "completed", "findings": []},
            harden={"action_count": 1},
            overall="generated_only",
            audit_id="CL-test",
        )

        resp = auth_client.post(
            "/api/harden/LS-test/verify",
            json={"mode": "dry_run"},
            headers=csrf_header,
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["overall"] == "generated_only"
        assert data["scan_id"] == "LS-test"

    def test_apply_verified(self, auth_client, csrf_header, mock_repo, mock_closed_loop):
        """APPLY 双确认 + 加固成功 → 200 + verified。"""
        from lightshield.harden.closed_loop import ClosedLoopResult
        from lightshield.utils.constants import OSPlatform

        mock_closed_loop.return_value = ClosedLoopResult(
            target="127.0.0.1",
            os_platform=OSPlatform.LINUX,
            mode="apply",
            execution={"status": "success"},
            verification={"verdict": "verified", "resolved": [], "remaining": [], "regressed": []},
            overall="verified",
            audit_id="CL-test",
        )

        resp = auth_client.post(
            "/api/harden/LS-test/verify",
            json={"mode": "apply", "confirm_ownership": True, "confirm_execute": True},
            headers=csrf_header,
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["overall"] == "verified"

    def test_apply_failed_returns_422(self, auth_client, csrf_header, mock_repo, mock_closed_loop):
        """APPLY 加固失败 → 422。"""
        from lightshield.harden.closed_loop import ClosedLoopResult
        from lightshield.utils.constants import OSPlatform

        mock_closed_loop.return_value = ClosedLoopResult(
            target="127.0.0.1",
            os_platform=OSPlatform.LINUX,
            mode="apply",
            overall="failed",
            audit_id="CL-test",
        )

        resp = auth_client.post(
            "/api/harden/LS-test/verify",
            json={"mode": "apply", "confirm_ownership": True, "confirm_execute": True},
            headers=csrf_header,
        )
        assert resp.status_code == 422

    def test_defaults_dry_run(self, auth_client, csrf_header, mock_repo, mock_closed_loop):
        """空请求体 → 默认 dry_run。"""
        from lightshield.harden.closed_loop import ClosedLoopResult
        from lightshield.utils.constants import OSPlatform

        mock_closed_loop.return_value = ClosedLoopResult(
            target="127.0.0.1",
            os_platform=OSPlatform.LINUX,
            mode="dry_run",
            overall="generated_only",
            audit_id="CL-test",
        )

        auth_client.post("/api/harden/LS-test/verify", json={}, headers=csrf_header)
        assert mock_closed_loop.call_args.kwargs["mode"] == "dry_run"


# =============================================================================
# 边界
# =============================================================================


class TestEdgeCases:
    """边界：不存在 scan_id → 404。"""

    def test_nonexistent_scan_returns_404(self, auth_client, csrf_header):
        """不存在的 scan_id → 404。"""
        with mock.patch("lightshield.web.routes.get_repository") as m:
            repo = mock.Mock()
            repo.get.return_value = None
            m.return_value = repo

            resp = auth_client.post(
                "/api/harden/LS-nonexistent/verify",
                json={"mode": "dry_run"},
                headers=csrf_header,
            )
            assert resp.status_code == 404
