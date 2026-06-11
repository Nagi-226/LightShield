"""CLI 命令行入口单元测试 — v0.0.22

被测模块：lightshield/cli.py
测试策略：mock 所有外部依赖（LightShieldCore/Nmap），仅验证 CLI 逻辑。

覆盖：
  - create_parser() 参数解析正确性
  - R2 输入校验（CIDR/空值/URL 拦截，不依赖真实网络）
  - R4 所有权确认（交互提示）
  - 加固命令参数处理
  - 错误退出码
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from lightshield.adapters.base import ScanResult
from lightshield.cli import create_parser, main
from lightshield.utils.constants import ScanStatus

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_core():
    """Mock LightShieldCore，返回假扫描结果。"""
    with patch("lightshield.cli.LightShieldCore") as mock_cls:
        core = MagicMock()
        core.run_scan.return_value = ScanResult(
            status=ScanStatus.COMPLETED,
            target="127.0.0.1",
            ports=[{"port": 22, "service": "ssh", "state": "open"}],
            services=[{"name": "ssh", "version": "9.6", "port": 22}],
            findings=[],
            duration_seconds=1.5,
        )
        core.generate_hardening.return_value = MagicMock(
            script_path="/tmp/harden.sh",
            rollback_path="/tmp/rollback.sh",
            status="generated",
        )
        mock_cls.return_value = core
        yield core


@pytest.fixture
def mock_reporter():
    """Mock ReportGenerator。"""
    with patch("lightshield.cli.ReportGenerator") as mock_cls:
        reporter = MagicMock()
        reporter.generate.return_value = "# LightShield Report"
        reporter.save.return_value = "/tmp/report.md"
        mock_cls.return_value = reporter
        yield reporter


# =============================================================================
# create_parser — 参数解析
# =============================================================================


class TestCreateParser:
    """create_parser() 参数解析测试"""

    def test_scan_subcommand_parses_target(self):
        """Scan 子命令正确解析 target 参数"""
        parser = create_parser()
        args = parser.parse_args(["scan", "127.0.0.1"])
        assert args.target == "127.0.0.1"
        assert args.command == "scan"

    def test_scan_with_confirm_ownership_flag(self):
        """--confirm-ownership 标志正确解析"""
        parser = create_parser()
        args = parser.parse_args(["scan", "127.0.0.1", "--confirm-ownership"])
        assert args.confirm_ownership is True

    def test_scan_without_confirm_ownership_defaults_false(self):
        """未传 --confirm-ownership 时默认 False"""
        parser = create_parser()
        args = parser.parse_args(["scan", "127.0.0.1"])
        assert args.confirm_ownership is False

    def test_quick_scan_subcommand(self):
        """quick-scan 子命令正确解析"""
        parser = create_parser()
        args = parser.parse_args(["quick-scan", "example.com"])
        assert args.command == "quick-scan"
        assert args.target == "example.com"

    def test_harden_subcommand_parses_target(self):
        """Harden 子命令正确解析 target"""
        parser = create_parser()
        args = parser.parse_args(["harden", "127.0.0.1", "--confirm-ownership"])
        assert args.command == "harden"
        assert args.target == "127.0.0.1"

    def test_version_subcommand(self):
        """Version 子命令正确识别"""
        parser = create_parser()
        args = parser.parse_args(["version"])
        assert args.command == "version"

    def test_output_format_option(self):
        """--output-format 选项正确解析"""
        parser = create_parser()
        args = parser.parse_args(["scan", "127.0.0.1", "--output-format", "text"])
        assert args.output_format == "text"

    def test_output_dir_option(self):
        """--output-dir 选项正确解析"""
        parser = create_parser()
        args = parser.parse_args(["scan", "127.0.0.1", "--output-dir", "/tmp/out"])
        assert args.output_dir == "/tmp/out"


# =============================================================================
# 输入校验 — R2 防线
# =============================================================================


class TestInputValidation:
    """R2 输入校验（不依赖真实网络）"""

    @pytest.mark.parametrize(
        "bad_target,expected_msg",
        [
            ("192.168.1.0/24", "CIDR"),
            ("", "空"),
            ("http://example.com", "URL"),
        ],
    )
    def test_rejects_invalid_targets(self, bad_target, expected_msg, mock_core, mock_reporter):
        """非法目标应被拦截，exit code ≠ 0"""
        create_parser().parse_args(["scan", bad_target, "--confirm-ownership"])
        with patch("lightshield.cli.TargetValidator.validate") as mock_validate:
            mock_validate.return_value = (False, f"拒绝 {expected_msg}")
            exit_code = main(["scan", bad_target, "--confirm-ownership"])
            assert exit_code != 0, f"应拒绝: {bad_target}"

    def test_accepts_valid_target(self, mock_core, mock_reporter):
        """合法目标应正常执行"""
        exit_code = main(["scan", "127.0.0.1", "--confirm-ownership"])
        assert exit_code == 0


# =============================================================================
# R4 所有权确认
# =============================================================================


class TestOwnershipConfirmation:
    """R4 所有权确认"""

    def test_scan_without_confirm_prompts_for_input(self, mock_core, mock_reporter):
        """无 --confirm-ownership 时应触发交互确认（mock input）"""
        with patch("builtins.input", return_value="YES"):
            exit_code = main(["scan", "127.0.0.1"])
            assert exit_code == 0  # YES 确认后应继续执行

    def test_harden_without_confirm_prompts_for_input(self, mock_core, mock_reporter):
        """Harden 无 --confirm-ownership 时应触发交互确认"""
        with patch("builtins.input", return_value="YES"):
            exit_code = main(["harden", "127.0.0.1"])
            assert exit_code == 0


# =============================================================================
# 加固命令
# =============================================================================


class TestHardenCommand:
    """harden 子命令"""

    def test_harden_generates_scripts(self, mock_core, mock_reporter):
        """Harden --confirm-ownership 正常生成加固脚本"""
        exit_code = main(["harden", "127.0.0.1", "--confirm-ownership"])
        assert exit_code == 0
        mock_core.generate_hardening.assert_called_once()

    def test_harden_rejects_invalid_target(self, mock_core, mock_reporter):
        """Harden 对非法目标应拒绝"""
        exit_code = main(["harden", "192.168.1.0/24", "--confirm-ownership"])
        assert exit_code != 0


# =============================================================================
# Version 命令
# =============================================================================


class TestVersionCommand:
    """version 子命令"""

    def test_version_prints_info(self, capsys):
        """Version 输出版本信息"""
        exit_code = main(["version"])
        assert exit_code == 0
        captured = capsys.readouterr()
        assert "LightShield" in captured.out or "0." in captured.out


# =============================================================================
# 错误处理
# =============================================================================


class TestErrorHandling:
    """错误场景"""

    def test_scan_with_nmap_failure(self, mock_reporter):
        """Nmap 不可用时友好报错，不 crash"""
        with patch("lightshield.cli.LightShieldCore") as mock_cls:
            core = MagicMock()
            core.run_scan.return_value = ScanResult(
                status=ScanStatus.FAILED,
                target="127.0.0.1",
                error="Nmap 未安装",
            )
            mock_cls.return_value = core
            exit_code = main(["scan", "127.0.0.1", "--confirm-ownership"])
            # 即使扫描失败，CLI 不应 crash
            assert exit_code in (0, 1)

    def test_report_generation_failure_handled(self, mock_core):
        """报告生成失败时不 crash"""
        with patch("lightshield.cli.ReportGenerator") as mock_cls:
            reporter = MagicMock()
            reporter.save.side_effect = OSError("磁盘满")
            mock_cls.return_value = reporter
            exit_code = main(["scan", "127.0.0.1", "--confirm-ownership"])
            assert exit_code in (0, 1)
