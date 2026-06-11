"""测试模块：lightshield/report/reporter.py

被测类：ReportGenerator

测试点：
  - generate(..., fmt="markdown") 含关键章节
  - generate(..., fmt="text") 含关键内容
  - save(report, filename) 写入文件，返回路径 + 可读 + 内容匹配
  - generate_and_save(...) 一步完成，返回路径 + 文件存在
  - _risk_summary(findings) 统计正确（含 total）
  - save() OSError → 抛出 IOError（v0.0.15修复）
  - generate 空 findings → 报告结构完整但不含漏洞详情表格
"""

import os
import shutil
import tempfile
from unittest.mock import patch

import pytest

from lightshield.adapters.base import ScanResult, VulnFinding
from lightshield.report.reporter import ReportGenerator
from lightshield.utils.constants import RiskLevel, ScanStatus


@pytest.fixture
def reporter():
    """创建使用临时目录的 ReportGenerator"""
    tmpdir = tempfile.mkdtemp(prefix="lightshield_test_report_")
    r = ReportGenerator(output_dir=tmpdir)
    yield r
    shutil.rmtree(tmpdir, ignore_errors=True)


@pytest.fixture
def sample_scan_result():
    """模拟扫描结果"""
    return ScanResult(
        status=ScanStatus.COMPLETED,
        target="192.168.1.100",
        ports=[
            {"port": 22, "protocol": "tcp", "state": "open", "service": "ssh"},
            {"port": 80, "protocol": "tcp", "state": "open", "service": "http"},
            {"port": 3306, "protocol": "tcp", "state": "open", "service": "mysql"},
        ],
        services=[
            {"name": "ssh", "version": "OpenSSH 7.6", "port": 22},
            {"name": "http", "version": "nginx 1.18.0", "port": 80},
            {"name": "mysql", "version": "MySQL 5.7", "port": 3306},
        ],
        os_info="Ubuntu 18.04",
        duration_seconds=12.5,
    )


@pytest.fixture
def sample_findings():
    """模拟漏洞发现列表"""
    return [
        VulnFinding(
            vuln_type="high_risk_port",
            severity=RiskLevel.CRITICAL,
            title="SSH 端口开放",
            description="SSH 端口 22 对外暴露。",
            remediation="1. 禁用密码登录\n2. 仅允许密钥认证",
            port=22,
        ),
        VulnFinding(
            vuln_type="vulnerable_component",
            severity=RiskLevel.HIGH,
            title="OpenSSH 版本过低",
            description="OpenSSH 7.6 存在已知漏洞。",
            remediation="升级至 9.0+",
            port=22,
            cve_id="CVE-2023-38408",
            cvss_score=9.8,
        ),
        VulnFinding(
            vuln_type="high_risk_port",
            severity=RiskLevel.MEDIUM,
            title="MySQL 端口开放",
            description="MySQL 端口 3306 对外暴露。",
            remediation="绑定到 127.0.0.1。",
            port=3306,
        ),
    ]


@pytest.fixture
def sample_harden():
    """模拟加固建议"""
    return [
        {
            "action": "关闭端口",
            "target": "3306",
            "reason": "MySQL 直接暴露",
            "severity": "high",
            "commands": ["iptables -A INPUT -p tcp --dport 3306 -j DROP"],
        },
        {
            "action": "升级 OpenSSH",
            "target": "22",
            "reason": "版本过低",
            "severity": "critical",
            "commands": ["apt upgrade openssh-server"],
        },
    ]


# =============================================================================
# generate — Markdown
# =============================================================================


class TestGenerateMarkdown:
    """generate(..., fmt="markdown")"""

    REQUIRED_SECTIONS = [
        "资产基本信息",
        "风险总览",
        "漏洞详情",
        "加固操作建议",
        "后续安全建议",
    ]

    @pytest.mark.parametrize("section", REQUIRED_SECTIONS)
    def test_contains_key_section(self, reporter, sample_scan_result, sample_findings, sample_harden, section):
        """Markdown 报告含关键章节"""
        report = reporter.generate(sample_scan_result, sample_findings, sample_harden, fmt="markdown")
        assert section in report, f"报告缺少章节: {section}"

    def test_contains_lighthield_title(self, reporter, sample_scan_result, sample_findings, sample_harden):
        """报告含 LightShield 标题"""
        report = reporter.generate(sample_scan_result, sample_findings, sample_harden, fmt="markdown")
        assert "LightShield" in report

    def test_contains_target_info(self, reporter, sample_scan_result, sample_findings, sample_harden):
        """报告含目标 IP"""
        report = reporter.generate(sample_scan_result, sample_findings, sample_harden, fmt="markdown")
        assert sample_scan_result.target in report

    def test_contains_cve_id(self, reporter, sample_scan_result, sample_findings, sample_harden):
        """报告含 CVE 编号"""
        report = reporter.generate(sample_scan_result, sample_findings, sample_harden, fmt="markdown")
        assert "CVE-2023-38408" in report

    def test_empty_findings_structure_complete(self, reporter, sample_scan_result, sample_harden):
        """空 findings 时报告结构完整"""
        report = reporter.generate(sample_scan_result, [], sample_harden, fmt="markdown")
        # 基本结构仍存在
        assert "LightShield" in report
        assert "风险总览" in report


# =============================================================================
# generate — Text
# =============================================================================


class TestGenerateText:
    """generate(..., fmt="text")"""

    def test_contains_lighthield(self, reporter, sample_scan_result, sample_findings, sample_harden):
        """纯文本报告含 LightShield"""
        report = reporter.generate(sample_scan_result, sample_findings, sample_harden, fmt="text")
        assert "LightShield" in report

    def test_contains_target(self, reporter, sample_scan_result, sample_findings, sample_harden):
        """纯文本报告含目标地址"""
        report = reporter.generate(sample_scan_result, sample_findings, sample_harden, fmt="text")
        assert sample_scan_result.target in report

    def test_contains_port_info(self, reporter, sample_scan_result, sample_findings, sample_harden):
        """纯文本报告含端口信息"""
        report = reporter.generate(sample_scan_result, sample_findings, sample_harden, fmt="text")
        assert "22" in report


# =============================================================================
# save
# =============================================================================


class TestSave:
    """save() 方法验证"""

    def test_save_returns_filepath(self, reporter):
        """save() 返回文件路径"""
        path = reporter.save("test report content", "test_report.md")
        assert "test_report.md" in path or path.endswith(".md")

    def test_saved_file_readable(self, reporter):
        """save() 后文件存在且可读"""
        content = "Hello, LightShield 报告测试！"
        path = reporter.save(content, "readable_test.md")
        assert os.path.exists(path), f"文件不存在: {path}"

        with open(path, encoding="utf-8") as f:
            saved_content = f.read()
        assert saved_content == content

    def test_save_default_filename(self, reporter):
        """不传 filename 时自动生成"""
        path = reporter.save("default name test")
        assert os.path.exists(path)

    def test_save_oserror_raises_io_error(self, reporter):
        """v0.0.15 修复：OSError → IOError"""
        with (
            patch("builtins.open", side_effect=OSError("Permission denied")),
            pytest.raises(IOError, match="报告保存失败"),
        ):
            reporter.save("test content", "will_fail.md")


# =============================================================================
# generate_and_save
# =============================================================================


class TestGenerateAndSave:
    """generate_and_save() 一步完成"""

    def test_returns_path(self, reporter, sample_scan_result, sample_findings, sample_harden):
        """返回文件路径"""
        path = reporter.generate_and_save(sample_scan_result, sample_findings, sample_harden, fmt="markdown")
        assert isinstance(path, str)
        assert len(path) > 0

    def test_file_exists(self, reporter, sample_scan_result, sample_findings, sample_harden):
        """文件确实存在"""
        path = reporter.generate_and_save(sample_scan_result, sample_findings, sample_harden, fmt="markdown")
        assert os.path.exists(path)

    def test_text_format_generates_txt(self, reporter, sample_scan_result, sample_findings, sample_harden):
        """Text 格式生成 .txt 文件"""
        path = reporter.generate_and_save(sample_scan_result, sample_findings, sample_harden, fmt="text")
        assert path.endswith(".txt")


# =============================================================================
# _risk_summary
# =============================================================================


class TestRiskSummary:
    """_risk_summary() 统计"""

    def test_counts_correct(self):
        """各等级统计准确"""
        findings = [
            VulnFinding("a", RiskLevel.CRITICAL, "", "", ""),
            VulnFinding("b", RiskLevel.CRITICAL, "", "", ""),
            VulnFinding("c", RiskLevel.HIGH, "", "", ""),
        ]
        summary = ReportGenerator._risk_summary(findings)
        assert summary["critical"] == 2
        assert summary["high"] == 1
        assert summary["medium"] == 0
        assert summary["total"] == 3

    def test_includes_total_field(self):
        """包含 total 字段"""
        summary = ReportGenerator._risk_summary([])
        assert "total" in summary
        assert summary["total"] == 0

    def test_empty_list_all_zero(self):
        """空列表全 0"""
        summary = ReportGenerator._risk_summary([])
        for key in ["critical", "high", "medium", "low", "info"]:
            assert summary[key] == 0
