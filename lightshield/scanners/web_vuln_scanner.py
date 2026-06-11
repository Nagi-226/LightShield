"""LightShield Web 漏洞检测模块。

本模块只做安全自检：通过低强度测试字符串观察响应差异，帮助用户发现
自有 Web 服务中的基础风险。不提取数据、不执行脚本、不做递归或暴力枚举。
"""

from __future__ import annotations

import html
import os
import re
import sys
import time
from dataclasses import dataclass
from typing import Any
from urllib.parse import parse_qs, urljoin, urlparse

import requests

if __package__ in {None, ""}:  # 允许直接执行本文件进行自检。
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from lightshield.adapters.base import BaseAdapter, ScanResult, VulnFinding
from lightshield.utils.constants import RiskLevel, ScanStatus, ScanType
from lightshield.utils.logger import get_logger
from lightshield.utils.validator import TargetValidator

try:
    from bs4 import BeautifulSoup
except ImportError:  # 运行环境未安装 bs4 时仍保持核心检测可用。
    BeautifulSoup = None  # type: ignore[assignment,misc]  # bs4 未安装时的回退


SQLI_TEST_PAYLOADS: list[tuple[str, str]] = [
    ("'", "单引号闭合"),
    ('"', "双引号闭合"),
    ("' OR '1'='1", "OR 永真（仅检测响应差异）"),
    ("' AND '1'='2", "AND 永假"),
    ("'; WAITFOR DELAY '0:0:3'--", "时间盲注（3秒）"),
]

XSS_TEST_PAYLOADS: list[tuple[str, str]] = [
    ("<script>alert(1)</script>", "基础 script"),
    ('"><script>alert(1)</script>', "属性闭合"),
    ("<img src=x onerror=alert(1)>", "img onerror"),
]

SENSITIVE_DIRS: list[str] = [
    "/admin",
    "/login",
    "/wp-admin",
    "/phpmyadmin",
    "/.git",
    "/.env",
    "/backup",
    "/config",
    "/api",
    "/debug",
    "/test",
    "/upload",
    "/robots.txt",
    "/sitemap.xml",
    "/readme.html",
    "/server-status",
    "/.htaccess",
    "/console",
    "/swagger",
    "/graphql",
    "/actuator",
]


@dataclass(frozen=True)
class _ResponseSnapshot:
    """用于比较响应差异的最小快照。"""

    status_code: int
    text: str
    elapsed_seconds: float
    content_length: int


class WebVulnScanner(BaseAdapter):
    """Web 漏洞检测扫描器 — 自研脚本引擎。"""

    _SQL_ERROR_PATTERNS: tuple[re.Pattern[str], ...] = (
        re.compile(r"sql syntax", re.IGNORECASE),
        re.compile(r"mysql_fetch|mysqli_fetch|mysql error", re.IGNORECASE),
        re.compile(r"you have an error in your sql syntax", re.IGNORECASE),
        re.compile(r"ora-\d{5}|oracle error", re.IGNORECASE),
        re.compile(r"postgresql|pg_query|unterminated quoted string", re.IGNORECASE),
        re.compile(r"sqlite|sqliteexception", re.IGNORECASE),
        re.compile(r"microsoft ole db|odbc sql server|sqlserver", re.IGNORECASE),
        re.compile(r"mariadb", re.IGNORECASE),
    )

    def __init__(
        self,
        timeout: float = 10.0,
        request_interval: float = 1.0,
        session: requests.Session | None = None,
    ) -> None:
        """初始化 Web 检测器。

        Args:
            timeout: HTTP 请求超时，默认 10 秒。
            request_interval: 默认 1 秒，满足低频自检要求。
            session: 可注入 requests.Session，便于测试或复用连接。
        """
        super().__init__(name="WebVulnScanner")
        self.timeout = timeout
        self.request_interval = max(1.0, request_interval)
        self.session = session or requests.Session()
        self._last_request_at = 0.0
        self._logger = get_logger()

    def validate_target(self, target: str) -> bool:
        """委托给 TargetValidator，并允许 Web URL 先抽取主机名后校验。"""
        host = self._extract_host(target)
        if host is None:
            valid, _ = TargetValidator.validate(target)
            return valid

        valid, _ = TargetValidator.validate(host)
        return valid

    def scan(self, target: str, **kwargs: Any) -> ScanResult:
        """主扫描入口：依次执行 SQL 注入、XSS、目录枚举并汇总为 ScanResult。"""
        started_at = time.monotonic()
        scan_id = self._logger.audit_scan_start(target, ScanType.WEB_VULN.value)

        if not self.validate_target(target):
            result = ScanResult(
                status=ScanStatus.FAILED,
                target=target,
                error="目标格式不合法：仅允许单个自有 IP、域名或其 Web URL",
                duration_seconds=time.monotonic() - started_at,
            )
            self._logger.audit_scan_end(scan_id, "failed: invalid target")
            self._log_scan_end(scan_id, result)
            return result

        try:
            url = self._normalize_url(target)
            params = kwargs.get("params")
            findings: list[VulnFinding] = []

            if kwargs.get("check_sqli", True):
                findings.extend(self.detect_sqli(url, params=params))
            if kwargs.get("check_xss", True):
                findings.extend(self.detect_xss(url, params=params))
            if kwargs.get("check_dirs", True):
                findings.extend(self.enumerate_directories(url))

            result = ScanResult(
                status=ScanStatus.COMPLETED,
                target=target,
                findings=findings,
                raw_output=f"web_vuln findings={len(findings)}",
                duration_seconds=time.monotonic() - started_at,
            )
            self._logger.audit_scan_end(scan_id, f"completed: findings={len(findings)}")
            self._log_scan_end(scan_id, result)
            return result
        except Exception as exc:  # 异常安全：扫描失败也返回结构化结果。
            self._logger.error(self.name, "Web 漏洞检测失败", exception=exc)
            result = ScanResult(
                status=ScanStatus.FAILED,
                target=target,
                error=f"Web 漏洞检测失败：{exc}",
                duration_seconds=time.monotonic() - started_at,
            )
            self._logger.audit_scan_end(scan_id, "failed: exception")
            self._log_scan_end(scan_id, result)
            return result

    def capabilities(self) -> list[str]:
        """返回扫描器能力。"""
        return ["web_vuln", "directory_enum"]

    def detect_sqli(self, url: str, params: dict | None = None) -> list[VulnFinding]:
        """基于响应差异的 SQL 注入检测，不做数据提取或写操作。"""
        base_params = self._resolve_params(url, params)
        if not base_params:
            return []

        baseline_response = self._safe_get(url, params=base_params)
        if baseline_response is None:
            return []

        baseline = self._snapshot(baseline_response)
        findings: list[VulnFinding] = []

        for param_name, original_value in base_params.items():
            boolean_snapshots: dict[str, _ResponseSnapshot] = {}

            for payload, label in SQLI_TEST_PAYLOADS:
                test_params = dict(base_params)
                test_params[param_name] = f"{original_value}{payload}"
                response = self._safe_get(url, params=test_params)
                if response is None:
                    continue

                snapshot = self._snapshot(response)
                evidence = self._sqli_evidence(baseline, snapshot, payload, label)
                if label.startswith("OR 永真") or label.startswith("AND 永假"):
                    boolean_snapshots[label] = snapshot

                if evidence:
                    findings.append(
                        VulnFinding(
                            vuln_type="sqli",
                            severity=RiskLevel.HIGH,
                            title="疑似 SQL 注入风险",
                            description=(
                                "目标参数在接收 SQL 特征测试字符串后出现数据库错误、"
                                "明显响应差异或延迟，可能存在 SQL 注入风险。"
                            ),
                            remediation=(
                                "使用参数化查询或 ORM 绑定参数；不要拼接 SQL；"
                                "对输入做白名单校验，并隐藏数据库错误详情。"
                            ),
                            url=url,
                            parameter=param_name,
                            evidence=evidence,
                        )
                    )
                    break

            bool_evidence = self._boolean_sqli_evidence(baseline, boolean_snapshots)
            if bool_evidence and not any(f.parameter == param_name for f in findings):
                findings.append(
                    VulnFinding(
                        vuln_type="sqli",
                        severity=RiskLevel.HIGH,
                        title="疑似 SQL 注入响应差异",
                        description="永真和永假测试字符串触发了可疑响应差异，建议人工复核。",
                        remediation="统一使用参数化查询，并对异常响应进行一致化处理。",
                        url=url,
                        parameter=param_name,
                        evidence=bool_evidence,
                    )
                )

        return findings

    def detect_xss(self, url: str, params: dict | None = None) -> list[VulnFinding]:
        """XSS 检测：只检查字符串是否未转义回显，不在浏览器中执行。"""
        base_params = self._resolve_params(url, params)
        if not base_params:
            return []

        findings: list[VulnFinding] = []
        for param_name, original_value in base_params.items():
            for payload, label in XSS_TEST_PAYLOADS:
                test_params = dict(base_params)
                test_params[param_name] = f"{original_value}{payload}"
                response = self._safe_get(url, params=test_params)
                if response is None:
                    continue

                response_text = response.text or ""
                escaped_payload = html.escape(payload, quote=True)
                if payload in response_text and escaped_payload not in response_text:
                    findings.append(
                        VulnFinding(
                            vuln_type="xss_reflected",
                            severity=RiskLevel.MEDIUM,
                            title="疑似反射型 XSS 风险",
                            description="测试字符串被页面未转义回显，可能存在反射型 XSS 风险。",
                            remediation=(
                                "对所有用户输入进行上下文相关输出编码；启用内容安全策略 CSP；避免直接拼接 HTML。"
                            ),
                            url=url,
                            parameter=param_name,
                            evidence=f"{label} 测试字符串被未转义回显",
                        )
                    )
                    break

                stored_response = self._safe_get(url, params=base_params)
                if stored_response is not None and payload in (stored_response.text or ""):
                    findings.append(
                        VulnFinding(
                            vuln_type="xss_stored",
                            severity=RiskLevel.HIGH,
                            title="疑似存储型 XSS 风险",
                            description="测试字符串在后续页面响应中出现，可能存在存储型 XSS 风险。",
                            remediation=("保存前校验输入，输出时做上下文编码；对富文本内容使用安全白名单清洗。"),
                            url=url,
                            parameter=param_name,
                            evidence=f"{label} 测试字符串在后续响应中出现",
                        )
                    )
                    break

        return findings

    def enumerate_directories(self, base_url: str) -> list[VulnFinding]:
        """基于内置小字典枚举常见敏感路径，无递归、无暴力破解。"""
        root_url = self._site_root(base_url)
        findings: list[VulnFinding] = []

        for path in SENSITIVE_DIRS[:200]:
            target_url = urljoin(root_url, path.lstrip("/"))
            response = self._safe_get(target_url, params=None)
            if response is None or response.status_code not in {200, 401, 403}:
                continue

            severity = self._directory_severity(path, response.status_code)
            evidence = self._directory_evidence(path, response)
            findings.append(
                VulnFinding(
                    vuln_type="sensitive_dir",
                    severity=severity,
                    title="发现敏感路径或管理入口",
                    description=f"目标存在常见敏感路径 {path}，建议确认是否需要公开访问。",
                    remediation=("移除不必要的公开文件；为管理入口配置访问控制；禁止公开配置、备份、版本控制目录。"),
                    url=target_url,
                    evidence=evidence,
                )
            )

        return findings

    def _safe_get(self, url: str, params: dict | None = None) -> requests.Response | None:
        """统一 HTTP GET：限速、超时、异常捕获。"""
        self._rate_limit()
        try:
            self._logger.info(self.name, f"检测请求 {url}")
            response = self.session.get(
                url,
                params=params,
                timeout=self.timeout,
                allow_redirects=True,
                headers={"User-Agent": "LightShield-WebSelfCheck/0.0.06"},
            )
            return response
        except requests.RequestException as exc:
            self._logger.warning(self.name, f"请求失败：{url} | {exc}")
            return None

    def _rate_limit(self) -> None:
        """同一扫描器实例内的请求间隔控制。"""
        now = time.monotonic()
        wait_seconds = self.request_interval - (now - self._last_request_at)
        if wait_seconds > 0:
            time.sleep(wait_seconds)
        self._last_request_at = time.monotonic()

    def _resolve_params(self, url: str, params: dict | None) -> dict[str, str]:
        """优先使用显式参数，否则从 URL 查询串解析参数。"""
        if params:
            return {str(key): str(value) for key, value in params.items()}

        parsed = urlparse(url)
        parsed_params = parse_qs(parsed.query, keep_blank_values=True)
        return {key: values[0] if values else "" for key, values in parsed_params.items()}

    def _sqli_evidence(
        self,
        baseline: _ResponseSnapshot,
        snapshot: _ResponseSnapshot,
        payload: str,
        label: str,
    ) -> str | None:
        """根据错误信息、状态码和延迟生成 SQL 注入证据。"""
        lowered_text = snapshot.text.lower()
        for pattern in self._SQL_ERROR_PATTERNS:
            if pattern.search(lowered_text):
                return f"{label}: 响应中出现数据库错误特征；测试字符串={payload!r}"

        if baseline.status_code < 500 <= snapshot.status_code:
            return f"{label}: 状态码从 {baseline.status_code} 变为 {snapshot.status_code}"

        if "时间盲注" in label and snapshot.elapsed_seconds - baseline.elapsed_seconds >= 2.5:
            return f"{label}: 响应耗时增加 {snapshot.elapsed_seconds - baseline.elapsed_seconds:.2f} 秒"

        return None

    def _boolean_sqli_evidence(
        self,
        baseline: _ResponseSnapshot,
        snapshots: dict[str, _ResponseSnapshot],
    ) -> str | None:
        """比较永真/永假响应差异，降低单一响应误报。"""
        true_snapshot = next((value for key, value in snapshots.items() if key.startswith("OR 永真")), None)
        false_snapshot = next((value for key, value in snapshots.items() if key.startswith("AND 永假")), None)
        if true_snapshot is None or false_snapshot is None:
            return None

        true_like_baseline = self._similar_response(baseline, true_snapshot)
        false_like_baseline = self._similar_response(baseline, false_snapshot)
        true_false_different = not self._similar_response(true_snapshot, false_snapshot)

        if true_like_baseline and not false_like_baseline and true_false_different:
            return "永真响应接近基线，永假响应明显不同，存在可疑布尔响应差异"
        return None

    def _similar_response(self, left: _ResponseSnapshot, right: _ResponseSnapshot) -> bool:
        """粗粒度比较响应是否相似。"""
        if left.status_code != right.status_code:
            return False
        base = max(left.content_length, right.content_length, 1)
        diff_ratio = abs(left.content_length - right.content_length) / base
        return diff_ratio <= 0.15

    def _snapshot(self, response: requests.Response) -> _ResponseSnapshot:
        """把 requests.Response 转为可比较快照。"""
        text = response.text or ""
        elapsed_seconds = 0.0
        elapsed = getattr(response, "elapsed", None)
        if elapsed is not None and hasattr(elapsed, "total_seconds"):
            elapsed_seconds = float(elapsed.total_seconds())

        return _ResponseSnapshot(
            status_code=int(getattr(response, "status_code", 0)),
            text=text,
            elapsed_seconds=elapsed_seconds,
            content_length=len(text.encode("utf-8", errors="ignore")),
        )

    def _directory_evidence(self, path: str, response: requests.Response) -> str:
        """生成敏感路径证据，避免记录过多响应正文。"""
        title = self._html_title(response.text or "")
        title_part = f"，标题={title}" if title else ""
        return f"{path} 返回 HTTP {response.status_code}{title_part}"

    def _directory_severity(self, path: str, status_code: int) -> RiskLevel:
        """根据路径和状态码给出保守风险等级。"""
        high_risk_paths = {"/.git", "/.env", "/backup", "/config", "/phpmyadmin", "/server-status"}
        medium_paths = {"/admin", "/login", "/wp-admin", "/debug", "/console", "/actuator"}
        if status_code in {401, 403}:
            return RiskLevel.LOW
        if path in high_risk_paths:
            return RiskLevel.HIGH
        if path in medium_paths:
            return RiskLevel.MEDIUM
        return RiskLevel.LOW

    def _html_title(self, text: str) -> str | None:
        """提取页面标题；bs4 不可用时使用轻量正则兜底。"""
        if not text:
            return None

        if BeautifulSoup is not None:
            soup = BeautifulSoup(text, "html.parser")
            if soup.title and soup.title.string:
                return soup.title.string.strip()[:80]

        match = re.search(r"<title[^>]*>(.*?)</title>", text, re.IGNORECASE | re.DOTALL)
        if not match:
            return None
        return re.sub(r"\s+", " ", match.group(1)).strip()[:80]

    def _normalize_url(self, target: str) -> str:
        """将域名/IP 转为 URL；已有 http/https URL 时保持原样。"""
        parsed = urlparse(target)
        if parsed.scheme in {"http", "https"} and parsed.netloc:
            return target
        return f"http://{target.strip('/')}"

    def _site_root(self, url: str) -> str:
        """提取站点根 URL，用于敏感路径枚举。"""
        normalized = self._normalize_url(url)
        parsed = urlparse(normalized)
        return f"{parsed.scheme}://{parsed.netloc}/"

    def _extract_host(self, target: str) -> str | None:
        """从 URL 中提取主机名；普通域名/IP 返回 None 交给 TargetValidator。"""
        parsed = urlparse(target)
        if parsed.scheme in {"http", "https"} and parsed.hostname:
            return parsed.hostname
        return None


if __name__ == "__main__":

    class _FakeElapsed:
        def __init__(self, seconds: float = 0.1) -> None:
            self._seconds = seconds

        def total_seconds(self) -> float:
            return self._seconds

    class _FakeResponse:
        def __init__(self, text: str, status_code: int = 200, elapsed: float = 0.1) -> None:
            self.text = text
            self.status_code = status_code
            self.elapsed = _FakeElapsed(elapsed)

    class _SelfCheckScanner(WebVulnScanner):
        def __init__(self) -> None:
            super().__init__(request_interval=0.0)

        def _safe_get(self, url: str, params: dict | None = None) -> _FakeResponse | None:  # type: ignore[override]
            if url.endswith("/.env"):
                return _FakeResponse("<title>env</title>DB_PASSWORD=redacted")
            if params and any("'" in str(value) for value in params.values()):
                return _FakeResponse("You have an error in your SQL syntax")
            if params and any("<script>" in str(value) for value in params.values()):
                return _FakeResponse(str(next(iter(params.values()))))
            return _FakeResponse("normal page")

    scanner = _SelfCheckScanner()
    assert scanner.capabilities() == ["web_vuln", "directory_enum"]
    assert len(SENSITIVE_DIRS) <= 200
    assert scanner.validate_target("example.com") is True
    assert scanner.validate_target("192.168.1.0/24") is False
    assert scanner.detect_sqli("http://example.com/search", {"q": "test"})
    assert scanner.detect_xss("http://example.com/search", {"q": "test"})
    assert any(f.url and f.url.endswith("/.env") for f in scanner.enumerate_directories("http://example.com"))
    print("web_vuln_scanner.py 自检通过")
