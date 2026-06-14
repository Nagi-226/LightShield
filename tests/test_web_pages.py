"""Tests for the Flask-rendered Web dashboard pages."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from lightshield.config import LightShieldConfig
from lightshield.web.app import create_app


@pytest.fixture
def app():
    """Create a Flask app configured for page tests."""
    config = LightShieldConfig()
    config.jwt_secret = "test-secret-key-for-pages"
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


def test_index_renders_login_page_for_guest(client):
    """Guests should see the login page at the site root."""
    response = client.get("/")

    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "LightShield" in html
    assert "login-form" in html
    assert 'name="_csrf_token"' in html
    assert 'name="csrf-token"' in html
    assert "/api/login" in html


def test_index_redirects_authenticated_user_to_dashboard(auth_client):
    """Authenticated users should not see the login form again."""
    response = auth_client.get("/")

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/dashboard")


def test_dashboard_requires_login(client):
    """The dashboard page should require an authenticated session."""
    response = client.get("/dashboard")

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/")


def test_dashboard_renders_scan_form_and_history(auth_client):
    """The dashboard should render the scan form plus recent SQLite history."""
    repo = MagicMock()
    repo.list_recent.return_value = [
        {
            "scan_id": "LS-20260614-120000-a1b2c3",
            "target": "127.0.0.1",
            "status": "completed",
            "ports_count": 5,
            "findings_count": 2,
            "created_at": "2026-06-14T12:00:00",
        }
    ]

    with patch("lightshield.web.pages.get_repository", return_value=repo) as get_repo:
        response = auth_client.get("/dashboard")

    assert response.status_code == 200
    get_repo.assert_called_once_with("sqlite", db_url="data/test-lightshield.db")
    repo.list_recent.assert_called_once_with(limit=20)
    html = response.get_data(as_text=True)
    assert "scan-form" in html
    assert "confirm-ownership" in html
    assert 'id="confirm-ownership" name="confirm_ownership"' in html
    assert "checked" not in html.split('id="confirm-ownership"', 1)[1].split(">", 1)[0]
    assert "LS-20260614-120000-a1b2c3" in html
    assert "/report/LS-20260614-120000-a1b2c3" in html
    assert "/harden/LS-20260614-120000-a1b2c3" in html
    assert 'name="_csrf_token"' in html


def test_report_page_requires_login(client):
    """The report viewer should require an authenticated session."""
    response = client.get("/report/LS-20260614-120000-a1b2c3")

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/")


def test_report_page_loads_marked_and_fetches_markdown(auth_client):
    """The report viewer should load markdown from the authenticated API endpoint."""
    scan_id = "LS-20260614-120000-a1b2c3"
    response = auth_client.get(f"/report/{scan_id}")

    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "marked.min.js" in html
    assert f"/api/report/{scan_id}?format=markdown" in html
    assert f"/api/report/{scan_id}?format=pdf" in html
    assert "download" in html
    assert f"/harden/{scan_id}" in html
    assert "report-content" in html


def test_harden_page_requires_login(client):
    """The hardening page should require an authenticated session."""
    response = client.get("/harden/LS-20260614-120000-a1b2c3")

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/")


def test_harden_page_renders_recommendations_and_csrf(auth_client):
    """The hardening page should render recommendations and the R4-gated form."""
    repo = MagicMock()
    repo.get.return_value = {
        "scan_id": "LS-20260614-120000-a1b2c3",
        "target": "127.0.0.1",
        "status": "completed",
        "created_at": "2026-06-14T12:00:00",
        "raw_result": {
            "target": "127.0.0.1",
            "status": "completed",
            "findings": [
                {
                    "vuln_type": "high_risk_port",
                    "severity": "high",
                    "title": "Telnet 暴露",
                    "description": "Telnet 明文传输",
                    "remediation": "关闭 Telnet",
                    "port": 23,
                }
            ],
        },
    }

    with (
        patch("lightshield.web.pages.get_repository", return_value=repo),
        patch("lightshield.web.pages.RuleEngine") as mock_engine_class,
    ):
        engine = MagicMock()
        engine.recommend_hardening.return_value = [
            {
                "action": "关闭高危端口",
                "target": "23",
                "severity": "high",
                "reason": "Telnet 明文传输",
                "commands": ["ufw deny 23"],
            }
        ]
        mock_engine_class.return_value = engine

        response = auth_client.get("/harden/LS-20260614-120000-a1b2c3")

    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "harden-form" in html
    assert "/api/harden/LS-20260614-120000-a1b2c3" in html
    assert "关闭高危端口" in html
    assert "Telnet 明文传输" in html
    assert 'id="harden-confirm-ownership" name="confirm_ownership"' in html
    assert "checked" not in html.split('id="harden-confirm-ownership"', 1)[1].split(">", 1)[0]
    assert 'name="_csrf_token"' in html


def test_static_stylesheet_is_served(client):
    """The page stylesheet should be available without a build step."""
    response = client.get("/static/style.css")

    assert response.status_code == 200
    assert "text/css" in response.content_type
    assert "--accent" in response.get_data(as_text=True)
