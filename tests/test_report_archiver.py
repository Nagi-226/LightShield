"""Report Archiver 单元测试 — v0.0.45 T2 边界路径覆盖。"""

import os

from lightshield.utils.report_archiver import _safe_dirname, archive_report


class TestSafeDirname:
    """_safe_dirname 边界输入。"""

    def test_normal_target(self):
        assert _safe_dirname("example.com") == "example.com"

    def test_ip_with_dots(self):
        assert _safe_dirname("192.168.1.1") == "192.168.1.1"

    def test_strips_whitespace(self):
        result = _safe_dirname("  target  ")
        assert not result.startswith(" ")
        assert not result.endswith(" ")

    def test_slash_replaced(self):
        assert "/" not in _safe_dirname("evil/path")

    def test_backslash_replaced(self):
        assert "\\" not in _safe_dirname("evil\\path")

    def test_colon_replaced(self):
        assert ":" not in _safe_dirname("host:80")

    def test_special_chars_replaced(self):
        result = _safe_dirname("a<b>c|d?e*f")
        assert "<" not in result
        assert ">" not in result
        assert "|" not in result
        assert "?" not in result
        assert "*" not in result

    def test_dot_directory_filtered(self):
        """M-016: . 目录名被替换。"""
        result = _safe_dirname(".")
        assert result != "."
        assert "_" in result

    def test_dotdot_directory_filtered(self):
        """M-016: .. 目录名被替换。"""
        result = _safe_dirname("..")
        assert result != ".."
        assert "_" in result

    def test_long_target_truncated(self):
        result = _safe_dirname("a" * 200)
        assert len(result) <= 80


class TestArchiveReport:
    """archive_report 核心路径。"""

    def test_nonexistent_file_returns_none(self):
        result = archive_report("/nonexistent/report.md", "test")
        assert result is None

    def test_existing_file_archived(self, tmp_path):
        report = tmp_path / "report.md"
        report.write_text("# Test Report")
        result = archive_report(str(report), "127.0.0.1", base_dir=str(tmp_path / "archive"))
        assert result is not None
        assert os.path.exists(result)

    def test_archived_path_contains_date_structure(self, tmp_path):
        report = tmp_path / "scan.md"
        report.write_text("# Scan")
        dest = archive_report(str(report), "10.0.0.1", base_dir=str(tmp_path / "archive"))
        assert dest is not None
        # 路径包含 YYYY-MM 目录结构
        assert os.path.sep + "20" in dest

    def test_script_archiving(self, tmp_path):
        script = tmp_path / "harden.sh"
        script.write_text("#!/bin/bash\necho hardened")
        from lightshield.utils.report_archiver import archive_harden_scripts

        result = archive_harden_scripts(str(script), None, base_dir=str(tmp_path / "archive"))
        assert result is not None

    def test_script_archiving_with_rollback(self, tmp_path):
        harden = tmp_path / "harden.sh"
        rollback = tmp_path / "rollback.sh"
        harden.write_text("#!/bin/bash\necho ok")
        rollback.write_text("#!/bin/bash\necho rollback")
        from lightshield.utils.report_archiver import archive_harden_scripts

        archived, archived_rb = archive_harden_scripts(str(harden), str(rollback), base_dir=str(tmp_path / "archive"))
        assert archived is not None
        assert archived_rb is not None
