"""PDF report writer for LightShield reports.

The writer uses fpdf2 when available and keeps the dependency optional so the
core package can still run without Web/PDF extras installed.
"""

from __future__ import annotations

import os
import platform
from datetime import datetime
from typing import Any

from lightshield.adapters.base import ScanResult, VulnFinding
from lightshield.utils.logger import get_logger

SEVERITY_COLORS = {
    "critical": (142, 68, 173),
    "high": (231, 76, 60),
    "medium": (243, 156, 18),
    "low": (241, 196, 15),
    "info": (149, 165, 166),
}

SEVERITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}


class PdfReportWriter:
    """Generate a PDF report aligned with the Markdown report structure."""

    def __init__(self) -> None:
        self._logger = get_logger()
        self._font_name = "Helvetica"
        self._unicode_font = False

    def write(
        self,
        scan_result: ScanResult,
        findings: list[VulnFinding] | None = None,
        harden_recommendations: list[dict] | None = None,
    ) -> bytes:
        """Render the report as PDF bytes."""
        fpdf_cls = self._load_fpdf()
        pdf = fpdf_cls()
        pdf.set_auto_page_break(auto=True, margin=18)
        with _IgnoreMissingFakeMethods():
            pdf.alias_nb_pages()

        self._setup_font(pdf)
        self._cover(pdf, scan_result)
        self._asset_overview(pdf, scan_result, findings or scan_result.findings or [])
        self._risk_summary(pdf, findings or scan_result.findings or [])
        self._findings(pdf, findings or scan_result.findings or [])
        self._hardening(pdf, harden_recommendations or [])
        return self._normalize_output(pdf.output(dest="S"))

    @staticmethod
    def _load_fpdf():
        try:
            from fpdf import FPDF
        except ImportError as exc:
            raise RuntimeError("PDF 导出需要安装 fpdf2：pip install 'lightshield[web]'") from exc
        return FPDF

    def _setup_font(self, pdf: Any) -> None:
        font_path = self._find_chinese_font()
        if font_path:
            try:
                pdf.add_font("LightShieldCN", "", font_path)
                self._font_name = "LightShieldCN"
                self._unicode_font = True
                return
            except Exception as exc:  # pragma: no cover - depends on local font/fpdf support
                self._logger.warning("report", f"中文字体加载失败，降级为英文 PDF 字体: {font_path} ({exc})")
        else:
            self._logger.warning("report", "未找到中文字体，PDF 将降级为英文兼容字体")

        self._font_name = "Helvetica"
        self._unicode_font = False

    @staticmethod
    def _find_chinese_font() -> str | None:
        candidates = [
            r"C:\Windows\Fonts\msyh.ttc",
            r"C:\Windows\Fonts\msyh.ttf",
            r"C:\Windows\Fonts\simhei.ttf",
            "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
            "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
            "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
            "/usr/share/fonts/truetype/arphic/ukai.ttc",
        ]
        for path in candidates:
            if os.path.exists(path):
                return path

        if platform.system().lower() == "linux":
            for root, _dirs, files in os.walk("/usr/share/fonts"):
                for name in files:
                    lower = name.lower()
                    if lower.endswith((".ttf", ".ttc", ".otf")) and any(
                        marker in lower for marker in ("noto", "cjk", "wqy", "microhei", "uming", "ukai")
                    ):
                        return os.path.join(root, name)
        return None

    def _cover(self, pdf: Any, result: ScanResult) -> None:
        pdf.add_page()
        self._set_font(pdf, size=24, style="B")
        self._cell(pdf, "LightShield 轻盾", h=16, ln=1, align="C")
        self._cell(pdf, "安全自检报告", h=14, ln=1, align="C")
        pdf.ln(10)
        self._set_font(pdf, size=12)
        rows = [
            ("生成时间", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
            ("扫描目标", result.target),
            ("扫描耗时", f"{result.duration_seconds}s"),
            ("操作系统", result.os_info or "未知"),
            ("开放端口", str(len(result.ports))),
            ("识别服务", str(len(result.services))),
        ]
        self._table(pdf, ["项目", "详情"], rows, [45, 125])
        self._footer(pdf)

    def _asset_overview(self, pdf: Any, result: ScanResult, findings: list[VulnFinding]) -> None:
        pdf.add_page()
        self._heading(pdf, "一、资产概览")
        rows = [
            ("目标地址", result.target),
            ("操作系统", result.os_info or "未识别"),
            ("开放端口数", str(len(result.ports))),
            ("识别服务数", str(len(result.services))),
            ("漏洞发现数", str(len(findings))),
        ]
        self._table(pdf, ["项目", "详情"], rows, [45, 125])
        if result.ports:
            pdf.ln(4)
            self._subheading(pdf, "开放端口清单")
            port_rows = [
                (
                    str(item.get("port", "?")),
                    str(item.get("protocol", "?")),
                    str(item.get("state", "?")),
                    str(item.get("service", "-")),
                )
                for item in result.ports
            ]
            self._table(pdf, ["端口", "协议", "状态", "服务"], port_rows, [28, 32, 35, 75])
        self._footer(pdf)

    def _risk_summary(self, pdf: Any, findings: list[VulnFinding]) -> None:
        self._heading(pdf, "二、风险摘要")
        summary = {"critical": 0, "high": 0, "medium": 0, "low": 0, "info": 0}
        for finding in findings:
            summary[finding.severity.value] = summary.get(finding.severity.value, 0) + 1
        rows = [
            ("CRITICAL", str(summary["critical"]), "需要立即处理"),
            ("HIGH", str(summary["high"]), "建议 24 小时内处理"),
            ("MEDIUM", str(summary["medium"]), "建议本周内处理"),
            ("LOW", str(summary["low"]), "建议择期处理"),
            ("INFO", str(summary["info"]), "提示信息"),
        ]
        self._table(pdf, ["等级", "数量", "说明"], rows, [40, 25, 105], color_first_column=True)
        self._footer(pdf)

    def _findings(self, pdf: Any, findings: list[VulnFinding]) -> None:
        pdf.add_page()
        self._heading(pdf, "三、漏洞详情")
        if not findings:
            self._paragraph(pdf, "未发现漏洞详情。")
            self._footer(pdf)
            return

        ordered = sorted(findings, key=lambda item: SEVERITY_ORDER.get(item.severity.value, 99))
        for index, finding in enumerate(ordered, 1):
            self._subheading(pdf, f"{index}. [{finding.severity.value.upper()}] {finding.title}")
            details = [
                ("风险等级", finding.severity.value.upper()),
                ("影响端口", str(finding.port or "-")),
                ("关联 CVE", finding.cve_id or "-"),
                ("问题描述", finding.description),
                ("修复建议", finding.remediation.replace("\n", " ")),
            ]
            self._table(pdf, ["字段", "内容"], details, [35, 135], color_first_column=False)
            pdf.ln(2)
        self._footer(pdf)

    def _hardening(self, pdf: Any, harden: list[dict]) -> None:
        pdf.add_page()
        self._heading(pdf, "四、加固建议")
        if not harden:
            self._paragraph(pdf, "暂无加固建议。")
            self._footer(pdf)
            return

        rows = [
            (
                str(item.get("severity", "-")).upper(),
                str(item.get("action", "-")),
                str(item.get("target", "-")),
                str(item.get("reason", "-")),
            )
            for item in harden
        ]
        self._table(pdf, ["优先级", "操作", "目标", "原因"], rows, [28, 45, 35, 62], color_first_column=True)
        self._footer(pdf)

    def _heading(self, pdf: Any, text: str) -> None:
        self._set_font(pdf, size=16, style="B")
        pdf.ln(3)
        self._cell(pdf, text, h=10, ln=1)
        self._set_font(pdf, size=10)

    def _subheading(self, pdf: Any, text: str) -> None:
        self._set_font(pdf, size=12, style="B")
        self._cell(pdf, text, h=8, ln=1)
        self._set_font(pdf, size=10)

    def _paragraph(self, pdf: Any, text: str) -> None:
        self._set_font(pdf, size=10)
        self._multi_cell(pdf, 0, 7, text)

    def _table(
        self,
        pdf: Any,
        headers: list[str],
        rows: list[tuple],
        widths: list[int],
        *,
        color_first_column: bool = False,
    ) -> None:
        self._set_font(pdf, size=9, style="B")
        pdf.set_fill_color(22, 37, 52)
        pdf.set_text_color(255, 255, 255)
        for header, width in zip(headers, widths, strict=False):
            self._cell(pdf, header, w=width, h=8, border=1, align="C", fill=True)
        self._cell(pdf, "", w=0, h=8, ln=1)
        pdf.set_text_color(0, 0, 0)
        self._set_font(pdf, size=9)
        for row in rows:
            max_lines = max(self._line_count(str(value), width) for value, width in zip(row, widths, strict=False))
            height = max(8, max_lines * 5)
            for index, (value, width) in enumerate(zip(row, widths, strict=False)):
                if color_first_column and index == 0:
                    color = SEVERITY_COLORS.get(str(value).lower(), SEVERITY_COLORS["info"])
                    pdf.set_fill_color(*color)
                    pdf.set_text_color(255, 255, 255)
                    fill = True
                else:
                    pdf.set_fill_color(255, 255, 255)
                    pdf.set_text_color(0, 0, 0)
                    fill = False
                self._cell(pdf, str(value), w=width, h=height, border=1, fill=fill)
            self._cell(pdf, "", w=0, h=height, ln=1)
        pdf.set_text_color(0, 0, 0)
        pdf.ln(4)

    @staticmethod
    def _line_count(text: str, width: int) -> int:
        chars_per_line = max(8, int(width / 2.8))
        return max(1, (len(text) // chars_per_line) + 1)

    def _set_font(self, pdf: Any, size: int, style: str = "") -> None:
        # 自定义中文字体仅注册了 regular 变体，不支持 bold/italic
        if self._unicode_font and style:
            style = ""
        pdf.set_font(self._font_name, style, size)

    def _cell(self, pdf: Any, text: str, **kwargs: Any) -> None:
        pdf.cell(text=self._safe_text(text), **kwargs)

    def _multi_cell(self, pdf: Any, w: int, h: int, text: str) -> None:
        pdf.multi_cell(w=w, h=h, text=self._safe_text(text))

    def _safe_text(self, text: str) -> str:
        value = str(text)
        if self._unicode_font:
            return value
        return value.encode("latin-1", errors="replace").decode("latin-1")

    def _footer(self, pdf: Any) -> None:
        pdf.set_y(-15)
        self._set_font(pdf, size=8)
        generated_at = datetime.now().strftime("%Y-%m-%d %H:%M")
        self._cell(pdf, f"LightShield - {generated_at} - Page {pdf.page_no()}/{{nb}}", h=8, align="C", ln=1)

    @staticmethod
    def _normalize_output(output: Any) -> bytes:
        if isinstance(output, bytes):
            return output
        if isinstance(output, bytearray):
            return bytes(output)
        if isinstance(output, str):
            return output.encode("latin-1")
        return bytes(output)


class _IgnoreMissingFakeMethods:
    """Context manager used for fake/minimal FPDF compatibility in tests."""

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, _tb):
        return exc_type is AttributeError
