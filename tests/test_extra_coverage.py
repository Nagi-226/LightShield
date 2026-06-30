"""批量边界/异常路径补测试 — v0.0.45 T2 最终冲刺。"""

import os
import tempfile
from unittest.mock import patch

import pytest

from lightshield.utils.constants import RiskLevel

# =============================================================================
# pdf_writer
# =============================================================================


class TestPdfWriter:
    """pdf_writer 辅助函数测试。"""

    def test_severity_colors_present(self):
        from lightshield.report.pdf_writer import SEVERITY_COLORS

        for level in ("critical", "high", "medium", "low", "info"):
            assert level in SEVERITY_COLORS

    def test_find_chinese_font_returns_none_or_path(self):
        from lightshield.report.pdf_writer import PdfReportWriter

        writer = PdfReportWriter()
        result = writer._find_chinese_font()
        assert result is None or os.path.exists(result)


# =============================================================================
# nuclei_adapter
# =============================================================================


class TestNucleiAdapter:
    """NucleiAdapter 边界路径测试。"""

    def test_severity_map_complete(self):
        from lightshield.adapters.nuclei_adapter import NucleiAdapter

        adapter = NucleiAdapter()
        assert RiskLevel.CRITICAL in adapter.SEVERITY_MAP.values()

    def test_empty_template_dir_handled(self):
        from lightshield.adapters.nuclei_adapter import NucleiAdapter

        with tempfile.TemporaryDirectory() as td:
            adapter = NucleiAdapter(templates_dir=td)
            caps = adapter.capabilities()
            assert isinstance(caps, list)

    def test_validate_target_delegates(self):
        from lightshield.adapters.nuclei_adapter import NucleiAdapter

        adapter = NucleiAdapter()
        assert adapter.validate_target("127.0.0.1") is True
        assert adapter.validate_target("192.168.1.0/24") is False


# =============================================================================
# nmap_adapter
# =============================================================================


class TestNmapAdapter:
    """NmapAdapter 边界路径测试。"""

    def test_adapter_name_is_nmap(self):
        from lightshield.adapters.nmap_adapter import NmapAdapter

        adapter = NmapAdapter()
        assert "nmap" in adapter.name.lower()

    def test_validate_target(self):
        from lightshield.adapters.nmap_adapter import NmapAdapter

        adapter = NmapAdapter()
        assert adapter.validate_target("127.0.0.1") is True
        assert adapter.validate_target("") is False


# =============================================================================
# core facade extra
# =============================================================================


class TestCoreFacadeExtra:
    """core 门面方法补充测试（异常路径）。"""

    @pytest.fixture
    def core(self):
        """返回 LightShieldCore 实例。"""
        from lightshield.core import LightShieldCore

        return LightShieldCore()

    def test_load_scan_repo_error_returns_none(self, core):
        with patch("lightshield.core.get_repository", side_effect=OSError("db down")):
            result = core.load_scan("LS-test")
            assert result is None

    def test_get_recommendations_empty_for_missing_scan(self, core):
        recs = core.get_recommendations("LS-nonexistent-999")
        assert recs == []

    def test_get_scan_history_repo_error_returns_empty(self, core):
        with patch("lightshield.core.get_repository", side_effect=OSError("db down")):
            result = core.get_scan_history()
            assert result == []
