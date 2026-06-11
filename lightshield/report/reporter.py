"""LightShield 中文安全报告生成器

基于扫描结果和规则引擎输出，生成面向非专业用户的中文安全报告。
支持 Markdown 和纯文本两种格式。

用法：
    from lightshield.report.reporter import ReportGenerator
    reporter = ReportGenerator()
    report = reporter.generate(scan_result, findings, format="markdown")
    reporter.save(report, "report.md")
"""

import os
from datetime import datetime

from lightshield.adapters.base import ScanResult, VulnFinding
from lightshield.utils.constants import RiskLevel
from lightshield.utils.logger import get_logger


class ReportGenerator:
    """中文安全报告生成器

    设计原则：
    - 面向非安全专业用户：通俗语言，避免晦涩术语
    - 结构清晰：资产概况 → 风险总览 → 漏洞详情 → 加固建议
    - 可操作：每个漏洞附带具体的修复步骤
    """

    def __init__(self, output_dir: str = "./reports"):
        self._output_dir = output_dir
        self._logger = get_logger()
        try:
            os.makedirs(output_dir, exist_ok=True)
        except OSError as e:
            # 目录创建失败不阻断构造，延后到 save() 再尝试
            self._logger.error("report", f"报告目录创建失败：{output_dir}", exception=e)

    # =========================================================================
    # 生成
    # =========================================================================

    def generate(
        self,
        scan_result: ScanResult,
        findings: list[VulnFinding] | None = None,
        harden_recommendations: list[dict] | None = None,
        fmt: str = "markdown",
    ) -> str:
        """生成安全报告

        Args:
            scan_result: 扫描结果
            findings: 所有漏洞发现（扫描器 + 规则引擎的汇总）
            harden_recommendations: 加固策略推荐
            fmt: 输出格式 "markdown" 或 "text"

        Returns:
            报告全文
        """
        if fmt == "text":
            report = self._generate_text(scan_result, findings, harden_recommendations)
        else:
            report = self._generate_markdown(scan_result, findings, harden_recommendations)
        self._logger.info(
            "report",
            f"报告已生成：target={scan_result.target} 格式={fmt} 长度={len(report)} 字",
        )
        return report

    def _generate_markdown(
        self,
        result: ScanResult,
        findings: list[VulnFinding] | None,
        harden: list[dict] | None,
    ) -> str:
        """生成 Markdown 格式报告"""
        findings = findings or result.findings or []
        risk_summary = self._risk_summary(findings)
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        lines = [
            "# LightShield 轻盾 — 安全自检报告",
            "",
            f"**生成时间**：{now}",
            f"**扫描目标**：{result.target}",
            f"**扫描耗时**：{result.duration_seconds}s",
            f"**操作系统**：{result.os_info or '未知'}",
            "",
            "---",
            "",
            "## 一、资产基本信息",
            "",
            "| 项目 | 详情 |",
            "|------|------|",
            f"| 目标地址 | {result.target} |",
            f"| 操作系统 | {result.os_info or '未识别'} |",
            f"| 开放端口数 | {len(result.ports)} |",
            f"| 识别服务数 | {len(result.services)} |",
            f"| 发现漏洞数 | {len(findings)} |",
        ]

        # 端口清单
        if result.ports:
            lines += [
                "",
                "### 开放端口清单",
                "",
                "| 端口 | 协议 | 状态 | 服务 |",
                "|------|------|------|------|",
            ]
            for p in result.ports:
                lines.append(
                    f"| {p.get('port', '?')} | {p.get('protocol', '?')} "
                    f"| {p.get('state', '?')} | {p.get('service', '-')} |"
                )

        lines += [
            "",
            "---",
            "",
            "## 二、风险总览",
            "",
            "| 风险等级 | 数量 | 说明 |",
            "|----------|------|------|",
            f"| 🔴 严重 | {risk_summary['critical']} | 需立即处理：远程代码执行、数据泄露风险 |",
            f"| 🟠 高危 | {risk_summary['high']} | 建议 24 小时内处理：弱口令、高危端口开放 |",
            f"| 🟡 中危 | {risk_summary['medium']} | 建议本周内处理：配置问题、老旧组件 |",
            f"| 🟢 低危 | {risk_summary['low']} | 建议择期处理：最佳实践偏离 |",
            f"| **合计** | **{risk_summary['total']}** | |",
        ]

        # 漏洞详情
        if findings:
            lines += [
                "",
                "---",
                "",
                "## 三、漏洞详情",
            ]
            for i, f in enumerate(findings, 1):
                sev_label = {
                    "critical": "🔴 严重",
                    "high": "🟠 高危",
                    "medium": "🟡 中危",
                    "low": "🟢 低危",
                    "info": "💭 提示",
                }.get(f.severity.value, "⚪ 未知")

                lines += [
                    f"### {i}. {sev_label} — {f.title}",
                    "",
                    f"**风险等级**：{f.severity.value.upper()}",
                ]
                if f.port:
                    lines.append(f"**受影响端口**：{f.port}")
                if f.url:
                    lines.append(f"**受影响 URL**：{f.url}")
                if f.parameter:
                    lines.append(f"**受影响参数**：{f.parameter}")
                if f.cve_id:
                    lines.append(f"**关联 CVE**：{f.cve_id} (CVSS: {f.cvss_score or 'N/A'})")

                lines += [
                    "",
                    f"**问题描述**：{f.description}",
                    "",
                ]
                if f.evidence:
                    lines.append(f"**检测证据**：{f.evidence}")
                    lines.append("")

                lines += [
                    "**修复建议**：",
                    "",
                ]
                for step in f.remediation.split("\n"):
                    if step.strip():
                        lines.append(f"{step.strip()}  ")
                lines.append("")

        # 加固建议
        if harden:
            lines += [
                "---",
                "",
                "## 四、加固操作建议",
                "",
                "> ⚠️ 执行加固操作前建议备份重要数据。以下操作按风险优先级排序。",
                "",
                "| 优先级 | 操作 | 目标 | 原因 |",
                "|--------|------|------|------|",
            ]
            for h in harden:
                lines.append(
                    f"| {h.get('severity', '?')} | {h.get('action', '?')} "
                    f"| {h.get('target', '?')} | {h.get('reason', '?')} |"
                )

        # 安全建议
        lines += [
            "",
            "---",
            "",
            "## 五、后续安全建议",
            "",
            "1. **定期扫描**：建议每月至少执行一次安全自检，及时发现新风险。",
            "2. **保持更新**：及时更新操作系统和所有服务组件到最新安全版本。",
            "3. **日志监控**：配置日志审计和异常告警，及时发现入侵行为。",
            "4. **备份策略**：实施 3-2-1 备份策略（3 份副本、2 种介质、1 份异地）。",
            "5. **最小权限**：遵循最小权限原则，每个服务仅授予必需的访问权限。",
            "",
            "---",
            "",
            "*本报告由 LightShield 轻盾 v0.1.0 自动生成。仅供自有资产安全自查使用。*",
        ]

        return "\n".join(lines)

    def _generate_text(
        self,
        result: ScanResult,
        findings: list[VulnFinding] | None,
        harden: list[dict] | None,
    ) -> str:
        """生成纯文本格式报告"""
        findings = findings or result.findings or []
        risk_summary = self._risk_summary(findings)
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        lines = [
            "=" * 60,
            "  LightShield 轻盾 — 安全自检报告",
            "=" * 60,
            "",
            f"生成时间: {now}",
            f"扫描目标: {result.target}",
            f"扫描耗时: {result.duration_seconds}s",
            f"操作系统: {result.os_info or '未知'}",
            "",
            "-" * 60,
            "一、资产基本信息",
            "-" * 60,
            f"开放端口: {len(result.ports)} 个",
        ]
        for p in result.ports:
            lines.append(
                f"  端口 {p.get('port', '?')}/{p.get('protocol', '?')} "
                f"— {p.get('state', '?')} ({p.get('service', '-')})"
            )

        lines += [
            "",
            "-" * 60,
            "二、风险总览",
            "-" * 60,
            f"严重: {risk_summary['critical']} | 高危: {risk_summary['high']} "
            f"| 中危: {risk_summary['medium']} | 低危: {risk_summary['low']}",
        ]

        if findings:
            lines += [
                "",
                "-" * 60,
                "三、漏洞详情",
                "-" * 60,
            ]
            for i, f in enumerate(findings, 1):
                lines += [
                    f"{i}. [{f.severity.value.upper()}] {f.title}",
                    f"   问题: {f.description}",
                    f"   修复: {f.remediation.replace(chr(10), ' ')}",
                    "",
                ]

        lines += [
            "",
            "-" * 60,
            "* 本报告由 LightShield 轻盾自动生成",
            "* 仅供自有资产安全自查使用",
        ]

        return "\n".join(lines)

    # =========================================================================
    # 工具
    # =========================================================================

    @staticmethod
    def _risk_summary(findings: list[VulnFinding]) -> dict:
        """风险统计"""
        summary = {"critical": 0, "high": 0, "medium": 0, "low": 0, "info": 0}
        for f in findings:
            sev = f.severity.value
            if sev in summary:
                summary[sev] += 1
        summary["total"] = sum(summary.values())
        return summary

    def save(self, report: str, filename: str = None) -> str:
        """保存报告到文件

        Args:
            report: 报告全文
            filename: 文件名，默认 report-{timestamp}.md

        Returns:
            保存的文件路径
        """
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
            filename = f"report-{timestamp}.md"

        filepath = os.path.join(self._output_dir, filename)
        try:
            # 兜底：构造时若目录创建失败，这里再尝试一次
            os.makedirs(self._output_dir, exist_ok=True)
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(report)
        except OSError as e:
            self._logger.error("report", f"报告保存失败：{filepath}", exception=e)
            raise OSError(f"报告保存失败：{filepath}（{e}）") from e

        self._logger.info("report", f"报告已保存：{filepath}")
        return filepath

    def generate_and_save(
        self,
        scan_result: ScanResult,
        findings: list[VulnFinding] = None,
        harden: list[dict] = None,
        fmt: str = "markdown",
    ) -> str:
        """生成并保存报告

        Returns:
            报告文件路径
        """
        report = self.generate(scan_result, findings, harden, fmt)
        ext = ".md" if fmt == "markdown" else ".txt"
        return self.save(report, f"report-{datetime.now().strftime('%Y%m%d-%H%M%S')}{ext}")


# =============================================================================
# 自检
# =============================================================================

if __name__ == "__main__":
    import os
    import sys as _sys

    _sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

    from lightshield.adapters.base import ScanResult
    from lightshield.utils.constants import ScanStatus

    reporter = ReportGenerator(output_dir="./reports")

    # 构造模拟扫描结果
    mock_result = ScanResult(
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

    mock_findings = [
        VulnFinding(
            vuln_type="high_risk_port",
            severity=RiskLevel.HIGH,
            title="SSH 端口开放",
            description="SSH 端口 22 处于开放状态。",
            remediation="1. 禁用密码登录\n2. 仅允许密钥认证",
            port=22,
        ),
        VulnFinding(
            vuln_type="vulnerable_component",
            severity=RiskLevel.CRITICAL,
            title="OpenSSH 版本过低",
            description="OpenSSH 7.6 存在已知漏洞 CVE-2023-38408。",
            remediation="升级 OpenSSH 到 9.0+",
            port=22,
            cve_id="CVE-2023-38408",
            cvss_score=9.8,
        ),
        VulnFinding(
            vuln_type="high_risk_port",
            severity=RiskLevel.HIGH,
            title="MySQL 端口对外开放",
            description="MySQL 端口 3306 对外开放。",
            remediation="绑定到 127.0.0.1，使用防火墙阻止外部访问。",
            port=3306,
        ),
    ]

    harden = [
        {"action": "关闭端口", "target": "3306", "reason": "MySQL 直接暴露", "severity": "high"},
        {"action": "升级 OpenSSH", "target": "22", "reason": "版本过低", "severity": "critical"},
    ]

    # Markdown
    md = reporter.generate(mock_result, mock_findings, harden, fmt="markdown")
    assert "LightShield" in md
    assert "风险总览" in md
    assert "修复建议" in md
    print(f"[OK] Markdown report: {len(md)} chars")

    # 纯文本
    txt = reporter.generate(mock_result, mock_findings, harden, fmt="text")
    assert "LightShield" in txt
    print(f"[OK] Text report: {len(txt)} chars")

    # 保存
    path = reporter.save(md)
    assert os.path.exists(path)
    print(f"[OK] Saved to: {path}")

    print("=== Reporter: ALL PASSED ===")
