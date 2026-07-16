"""核心调度器单元测试 — v0.0.22

被测模块：lightshield/core.py
测试策略：mock NmapAdapter 等外部依赖，仅验证调度逻辑。

覆盖：
  - 适配器注册与管理
  - _validate_request R2 防线
  - submit_scan / get_scan_status v0.0.20 异步接口
  - 合规确认 _confirm_ownership
  - 无适配器时优雅降级
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from lightshield.adapters.base import BaseAdapter, ScanResult
from lightshield.config import LightShieldConfig
from lightshield.core import LightShieldCore
from lightshield.utils.constants import ScanStatus

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def core():
    """创建独立的 LightShieldCore 实例（不依赖全局单例）。"""
    config = LightShieldConfig()
    config.log_dir = "/tmp/test_logs"
    return LightShieldCore(config=config)


@pytest.fixture
def mock_adapter():
    """创建一个可用的 mock Adapter。"""
    adapter = MagicMock(spec=BaseAdapter)
    adapter.name = "MockAdapter"
    adapter.capabilities.return_value = ["mock_scan"]
    adapter.validate_target.return_value = True
    adapter.scan.return_value = ScanResult(
        status=ScanStatus.COMPLETED,
        target="127.0.0.1",
        ports=[{"port": 80, "service": "http", "state": "open"}],
        services=[{"name": "http", "version": "nginx", "port": 80}],
        findings=[],
        duration_seconds=0.5,
    )
    return adapter


# =============================================================================
# 适配器管理
# =============================================================================


class TestAdapterManagement:
    """适配器注册与管理"""

    def test_register_adapter_adds_to_list(self, core, mock_adapter):
        """注册后 list_adapters() 可见"""
        core.register_adapter(mock_adapter)
        adapters = core.list_adapters()
        assert len(adapters) >= 1
        names = [a["name"] for a in adapters]
        assert "MockAdapter" in names

    def test_register_duplicate_name_no_duplicate(self, core, mock_adapter):
        """重复注册同名 adapter 应去重"""
        core.register_adapter(mock_adapter)
        core.register_adapter(mock_adapter)
        adapters = core.list_adapters()
        names = [a["name"] for a in adapters]
        assert names.count("MockAdapter") == 1

    def test_list_adapters_empty_initially(self, core):
        """初始状态 list_adapters() 返回空"""
        assert core.list_adapters() == []

    def test_list_capabilities(self, core, mock_adapter):
        """list_capabilities() 返回所有已注册能力"""
        core.register_adapter(mock_adapter)
        caps = core.list_capabilities()
        assert "mock_scan" in caps


# =============================================================================
# _validate_request — R2 防线
# =============================================================================


class TestValidateRequest:
    """_validate_request R2 输入校验"""

    @pytest.mark.parametrize(
        "target",
        [
            "127.0.0.1",
            "192.168.1.1",
            "10.0.0.1",
            "example.com",
            "localhost",
        ],
    )
    def test_accepts_valid_targets(self, core, target):
        """合法目标应通过校验"""
        is_valid, reason = core._validate_request(target)
        assert is_valid, f"应接受 {target}，但被拒绝: {reason}"

    @pytest.mark.parametrize(
        "target",
        [
            "192.168.1.0/24",
            "10.0.0.0/8",
        ],
    )
    def test_rejects_cidr(self, core, target):
        """CIDR 网段应被拒绝"""
        is_valid, reason = core._validate_request(target)
        assert not is_valid, f"应拒绝 CIDR: {target}"

    def test_rejects_empty_string(self, core):
        """空字符串应被拒绝"""
        is_valid, _ = core._validate_request("")
        assert not is_valid

    def test_rejects_wildcard_domain(self, core):
        """通配符域名应被拒绝"""
        is_valid, _ = core._validate_request("*.example.com")
        assert not is_valid


# =============================================================================
# submit_scan + get_scan_status — v0.0.20 异步接口
# =============================================================================


class TestAsyncInterface:
    """v0.0.20 新增 submit_scan / get_scan_status"""

    def test_submit_scan_returns_task_id(self, core, mock_adapter):
        """submit_scan 返回格式正确的 task_id"""
        core.register_adapter(mock_adapter)
        task_id = core.submit_scan("127.0.0.1", confirm_ownership=True)
        assert task_id.startswith("LS-"), f"task_id 应以 'LS-' 开头: {task_id}"
        assert len(task_id) > 20, "task_id 应包含时间戳和随机后缀"

    def test_get_scan_status_returns_completed(self, core, mock_adapter):
        """扫描完成后 get_scan_status 返回 COMPLETED"""
        core.register_adapter(mock_adapter)
        task_id = core.submit_scan("127.0.0.1", confirm_ownership=True)
        status = core.get_scan_status(task_id)
        assert status["task_id"] == task_id
        assert status["status"] == "completed"
        assert status["target"] == "127.0.0.1"
        assert isinstance(status["ports"], int)
        assert isinstance(status["findings"], int)

    def test_get_scan_status_not_found(self, core):
        """查询不存在的 task_id 返回 not_found"""
        status = core.get_scan_status("nonexistent-id")
        assert status["status"] == "not_found"

    def test_submit_scan_rejects_invalid_target(self, core, mock_adapter):
        """submit_scan 对非法目标返回 FAILED 状态"""
        core.register_adapter(mock_adapter)
        task_id = core.submit_scan("192.168.1.0/24", confirm_ownership=True)
        status = core.get_scan_status(task_id)
        assert status["status"] == "failed"

    def test_submit_scan_rejects_unconfirmed_without_starting_thread(self, core, mock_adapter):
        """Unconfirmed async scans fail immediately without creating a worker."""
        core.register_adapter(mock_adapter)

        with patch("lightshield.core.threading.Thread") as thread_cls:
            task_id = core.submit_scan("127.0.0.1")

        thread_cls.assert_not_called()
        status = core.get_scan_status(task_id)
        assert status["status"] == "failed"
        assert "confirm_ownership=True" in status["error"]
        mock_adapter.scan.assert_not_called()


# =============================================================================
# 合规确认
# =============================================================================


class TestComplianceConfirmation:
    """R4 所有权确认"""

    def test_confirm_ownership_returns_prompt(self, core):
        """_confirm_ownership 返回非空提示文本"""
        prompt = core._confirm_ownership("192.168.1.1")
        assert isinstance(prompt, str)
        assert len(prompt) > 0

    def test_run_scan_rejects_unconfirmed_before_adapter(self, core, mock_adapter):
        """Unconfirmed direct calls fail closed before adapter execution."""
        core.register_adapter(mock_adapter)

        result = core.run_scan("127.0.0.1")

        assert result.status == ScanStatus.FAILED
        assert result.error is not None
        assert "confirm_ownership=True" in result.error
        mock_adapter.scan.assert_not_called()


# =============================================================================
# 无适配器降级
# =============================================================================


class TestNoAdapterDegradation:
    """无适配器时的优雅降级"""

    def test_run_scan_without_adapters_returns_failed(self, core):
        """未注册适配器时 run_scan 返回 FAILED（不 crash）"""
        result = core.run_scan("127.0.0.1", confirm_ownership=True)
        assert result.status == ScanStatus.FAILED
        assert result.error

    def test_run_asset_scan_without_adapters(self, core):
        """run_asset_scan 无适配器时不 crash"""
        result = core.run_asset_scan("127.0.0.1")
        assert result.status == ScanStatus.FAILED

    def test_run_full_scan_without_adapters(self, core):
        """run_full_scan 无适配器时不 crash"""
        result = core.run_full_scan("127.0.0.1")
        assert result.status == ScanStatus.FAILED


# =============================================================================
# R2 拒绝后的行为
# =============================================================================


class TestR2RejectionBehavior:
    """R2 拒绝后各方法的行为一致性"""

    def test_run_scan_rejects_cidr_even_with_adapter(self, core, mock_adapter):
        """即使注册了 adapter，CIDR 输入仍被拒绝"""
        core.register_adapter(mock_adapter)
        result = core.run_scan("192.168.1.0/24", confirm_ownership=True)
        assert result.status == ScanStatus.FAILED
        assert "CIDR" in result.error or "拒绝" in result.error


# =============================================================================
# v0.0.44 Web-Core 门面方法
# =============================================================================


class TestFacadeLoadScan:
    """load_scan 门面：从仓库加载扫描并返回 ScanResult。"""

    def test_load_scan_success(self, core):
        """正常加载应返回 ScanResult（含 findings）。"""
        from unittest.mock import patch

        repo = MagicMock()
        repo.get.return_value = {
            "scan_id": "LS-test",
            "target": "127.0.0.1",
            "status": "completed",
            "raw_result": {
                "target": "127.0.0.1",
                "status": "completed",
                "ports": [{"port": 22, "service": "ssh"}],
                "findings": [
                    {
                        "vuln_type": "high_risk_port",
                        "severity": "high",
                        "title": "SSH 暴露",
                        "description": "SSH 端口对外开放",
                        "remediation": "限制访问",
                        "port": 22,
                    }
                ],
                "duration_seconds": 5.0,
            },
        }

        with patch("lightshield.core.get_repository", return_value=repo):
            result = core.load_scan("LS-test")

        assert result is not None
        assert result.target == "127.0.0.1"
        assert result.status == ScanStatus.COMPLETED
        assert len(result.findings) == 1
        assert result.findings[0].vuln_type == "high_risk_port"
        assert len(result.ports) == 1

    def test_load_scan_not_found(self, core):
        """scan_id 不存在 → 返回 None。"""
        from unittest.mock import patch

        repo = MagicMock()
        repo.get.return_value = None

        with patch("lightshield.core.get_repository", return_value=repo):
            result = core.load_scan("LS-nonexistent")

        assert result is None

    def test_load_scan_repo_exception(self, core):
        """仓库异常 → 返回 None（不抛异常）。"""
        from unittest.mock import patch

        with patch("lightshield.core.get_repository", side_effect=RuntimeError("db error")):
            result = core.load_scan("LS-test")

        assert result is None


class TestFacadeGetRecommendations:
    """get_recommendations 门面：加载扫描 → 规则引擎 → 加固建议。"""

    def test_get_recommendations_success(self, core):
        """正常流程返回加固建议列表。"""
        from unittest.mock import patch

        repo = MagicMock()
        repo.get.return_value = {
            "scan_id": "LS-test",
            "target": "127.0.0.1",
            "status": "completed",
            "raw_result": {
                "target": "127.0.0.1",
                "status": "completed",
                "findings": [
                    {
                        "vuln_type": "high_risk_port",
                        "severity": "high",
                        "title": "Telnet",
                        "description": "Telnet 暴露",
                        "remediation": "关闭",
                        "port": 23,
                    }
                ],
            },
        }

        mock_engine = MagicMock()
        mock_engine.recommend_hardening.return_value = [{"action": "关闭端口", "target": "23", "severity": "high"}]

        with (
            patch("lightshield.core.get_repository", return_value=repo),
            patch("lightshield.core.RuleEngine", return_value=mock_engine),
        ):
            recs = core.get_recommendations("LS-test")

        assert len(recs) == 1
        assert recs[0]["action"] == "关闭端口"

    def test_get_recommendations_scan_not_found(self, core):
        """扫描不存在 → 返回空列表。"""
        from unittest.mock import patch

        repo = MagicMock()
        repo.get.return_value = None

        with patch("lightshield.core.get_repository", return_value=repo):
            recs = core.get_recommendations("LS-missing")

        assert recs == []

    def test_get_recommendations_engine_exception(self, core):
        """RuleEngine 异常 → 返回空列表（不抛异常）。"""
        from unittest.mock import patch

        repo = MagicMock()
        repo.get.return_value = {
            "scan_id": "LS-test",
            "target": "127.0.0.1",
            "status": "completed",
            "raw_result": {
                "target": "127.0.0.1",
                "status": "completed",
                "findings": [],
            },
        }

        mock_engine = MagicMock()
        mock_engine.recommend_hardening.side_effect = RuntimeError("engine error")

        with (
            patch("lightshield.core.get_repository", return_value=repo),
            patch("lightshield.core.RuleEngine", return_value=mock_engine),
        ):
            recs = core.get_recommendations("LS-test")

        assert recs == []


class TestFacadeGetScanHistory:
    """get_scan_history 门面：获取最近扫描历史。"""

    def test_get_scan_history_success(self, core):
        """正常返回历史列表。"""
        from unittest.mock import patch

        history = [{"scan_id": "LS-1", "target": "10.0.0.1"}]
        repo = MagicMock()
        repo.list_recent.return_value = history

        with patch("lightshield.core.get_repository", return_value=repo):
            result = core.get_scan_history(limit=10)

        assert result == history
        repo.list_recent.assert_called_once_with(limit=10)

    def test_get_scan_history_repo_exception(self, core):
        """仓库异常 → 返回空列表（不抛异常）。"""
        from unittest.mock import patch

        with patch("lightshield.core.get_repository", side_effect=RuntimeError("db error")):
            result = core.get_scan_history()

        assert result == []


class TestOsPlatformNormalize:
    """os_platform_normalize 静态方法：规范化 OS 平台输入。"""

    def test_none_defaults_to_linux(self):
        assert LightShieldCore.os_platform_normalize(None) == "linux"

    def test_string_linux(self):
        assert LightShieldCore.os_platform_normalize("linux") == "linux"

    def test_string_windows(self):
        assert LightShieldCore.os_platform_normalize("windows") == "windows"

    def test_string_case_insensitive(self):
        assert LightShieldCore.os_platform_normalize("Windows") == "windows"
        assert LightShieldCore.os_platform_normalize("LINUX") == "linux"

    def test_empty_string_defaults_to_linux(self):
        assert LightShieldCore.os_platform_normalize("") == "linux"

    def test_enum_input(self):
        from lightshield.utils.constants import OSPlatform

        assert LightShieldCore.os_platform_normalize(OSPlatform.LINUX) == "linux"
        assert LightShieldCore.os_platform_normalize(OSPlatform.WINDOWS) == "windows"
