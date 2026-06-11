"""核心调度器单元测试 — v0.0.22

被测模块：lightshield/core.py
测试策略：mock NmapAdapter 等外部依赖，仅验证调度逻辑。

覆盖：
  - 适配器注册与管理
  - _validate_request R2 防线
  - submit_scan / get_scan_status v0.2.0 异步接口
  - 合规确认 _confirm_ownership
  - 无适配器时优雅降级
"""

from __future__ import annotations

from unittest.mock import MagicMock

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
# submit_scan + get_scan_status — v0.2.0 异步接口
# =============================================================================


class TestAsyncInterface:
    """v0.2.0 新增 submit_scan / get_scan_status"""

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
