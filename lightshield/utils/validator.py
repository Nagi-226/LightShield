"""LightShield 目标输入校验模块。

本模块是合规红线 R2/R4/R6 的基础防线：
- R2：禁止 CIDR、IP 范围、通配符等批量扫描目标。
- R4：为扫描前的资产所有权确认提供统一提示。
- R6：限制扫描并发和请求间隔。
"""

from __future__ import annotations

import ipaddress
import re

try:
    from lightshield.utils.constants import MAX_CONCURRENT_SCANS, MIN_SCAN_INTERVAL
except ImportError:  # 允许在常量模块尚未合入时独立自检。
    MAX_CONCURRENT_SCANS = 20
    MIN_SCAN_INTERVAL = 5.0


class TargetValidator:
    """目标输入校验器 —— 合规 R2/R4 的核心防线。"""

    _DOMAIN_LABEL_RE = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?$")
    _URL_SCHEME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]*://")
    _IP_RANGE_FULL_RE = re.compile(r"^\s*(?P<start>[^-\s]+)\s*-\s*(?P<end>[^-\s]+)\s*$")
    _IP_RANGE_SHORT_RE = re.compile(r"^\s*(?P<prefix>(?:\d{1,3}\.){3})(?P<start>\d{1,3})\s*-\s*(?P<end>\d{1,3})\s*$")

    @staticmethod
    def _normalize(target: object) -> str:
        """将任意输入安全转换为去首尾空白的字符串。"""
        if not isinstance(target, str):
            return ""
        return target.strip()

    @staticmethod
    def is_valid_ip(target: str) -> bool:
        """验证是否为合法单 IPv4/IPv6 地址（拒绝 CIDR/网段）。"""
        value = TargetValidator._normalize(target)
        if not value or TargetValidator.is_cidr(value) or TargetValidator._is_ip_range(value):
            return False

        try:
            ipaddress.ip_address(value)
            return True
        except ValueError:
            return False

    @staticmethod
    def is_private_ip(target: str) -> bool:
        """验证是否为内网 IP（含私有地址、回环地址和链路本地地址）。"""
        value = TargetValidator._normalize(target)
        try:
            ip_obj = ipaddress.ip_address(value)
        except ValueError:
            return False

        return bool(ip_obj.is_private or ip_obj.is_loopback or ip_obj.is_link_local)

    @staticmethod
    def is_cidr(target: str) -> bool:
        """检测是否为 CIDR 网段格式（需要拦截的格式）。"""
        value = TargetValidator._normalize(target)
        if "/" not in value:
            return False

        try:
            ipaddress.ip_network(value, strict=False)
            return True
        except ValueError:
            return False

    @staticmethod
    def is_valid_domain(target: str) -> bool:
        """验证是否为合法域名（拒绝通配符 *.example.com）。"""
        value = TargetValidator._normalize(target).lower()
        if not value:
            return False
        if value == "localhost":
            return True
        if TargetValidator.is_wildcard_domain(value):
            return False
        if TargetValidator._looks_like_url_or_path(value):
            return False
        if TargetValidator.is_valid_ip(value) or TargetValidator.is_cidr(value):
            return False
        if len(value) > 253 or value.endswith(".") or "." not in value:
            return False
        if re.fullmatch(r"[\d.]+", value):
            return False

        labels = value.split(".")
        return all(TargetValidator._DOMAIN_LABEL_RE.fullmatch(label) for label in labels)

    @staticmethod
    def is_wildcard_domain(target: str) -> bool:
        """检测通配符域名。"""
        value = TargetValidator._normalize(target)
        return "*" in value

    @staticmethod
    def validate(target: str) -> tuple[bool, str]:
        """综合校验入口——所有对外操作的前置关口。

        仅接受单 IPv4、单 IPv6、单域名和 localhost；拒绝 CIDR、IP 范围、
        通配符域名、URL、带路径/端口/查询参数的目标。
        """
        value = TargetValidator._normalize(target)
        if not value:
            return False, "拒绝空地址"

        if TargetValidator.is_cidr(value):
            return False, "拒绝 CIDR 网段"

        if TargetValidator._is_ip_range(value):
            return False, "拒绝 IP 范围"

        if TargetValidator.is_wildcard_domain(value):
            return False, "拒绝通配符域名"

        if TargetValidator._looks_like_url_or_path(value):
            return False, "拒绝 URL"

        if TargetValidator.is_valid_ip(value):
            ip_obj = ipaddress.ip_address(value)
            version = "IPv4" if ip_obj.version == 4 else "IPv6"
            return True, f"合法单 {version}"

        if TargetValidator.is_valid_domain(value):
            if value.lower() == "localhost":
                return True, "合法 localhost"
            return True, "合法单域名"

        return False, "拒绝非法目标格式"

    @staticmethod
    def confirm_ownership(target: str) -> str:
        """生成所有权确认提示信息（合规 R4）。"""
        value = TargetValidator._normalize(target) or "<未填写目标>"
        return (
            f"请确认你拥有目标 {value} 的所有权或已获得明确授权。"
            "LightShield 仅允许扫描和加固自有资产，禁止用于公网陌生资产。"
        )

    @staticmethod
    def validate_scan_params(concurrency: int, interval: float) -> tuple[bool, str]:
        """校验扫描参数（合规 R6：并发 ≤20，间隔 ≥5s）。"""
        try:
            concurrency_value = int(concurrency)
            interval_value = float(interval)
        except (TypeError, ValueError):
            return False, "扫描参数必须为数字"

        if concurrency_value < 1:
            return False, "扫描并发必须 ≥1"
        if concurrency_value > MAX_CONCURRENT_SCANS:
            return False, f"扫描并发不得超过 {MAX_CONCURRENT_SCANS}"
        if interval_value < MIN_SCAN_INTERVAL:
            return False, f"扫描间隔不得小于 {MIN_SCAN_INTERVAL} 秒"
        return True, "扫描参数合法"

    @staticmethod
    def _looks_like_url_or_path(target: str) -> bool:
        """识别 URL、路径、端口和用户信息格式，避免绕过单目标校验。"""
        value = TargetValidator._normalize(target)
        if TargetValidator._URL_SCHEME_RE.match(value):
            return True
        if any(mark in value for mark in ("/", "\\", "?", "#", "@")):
            return True

        # IPv6 合法地址包含冒号，不能按端口格式误拦截。
        return bool(":" in value and not TargetValidator.is_valid_ip(value))

    @staticmethod
    def _is_ip_range(target: str) -> bool:
        """检测 192.168.1.1-192.168.1.10 或 192.168.1.1-10 形式的 IP 范围。"""
        value = TargetValidator._normalize(target)
        short_match = TargetValidator._IP_RANGE_SHORT_RE.fullmatch(value)
        if short_match:
            start_ip = f"{short_match.group('prefix')}{short_match.group('start')}"
            end_ip = f"{short_match.group('prefix')}{short_match.group('end')}"
            return TargetValidator._is_same_version_ip_pair(start_ip, end_ip)

        full_match = TargetValidator._IP_RANGE_FULL_RE.fullmatch(value)
        if full_match:
            start = full_match.group("start")
            end = full_match.group("end")
            return TargetValidator._is_same_version_ip_pair(start, end)

        return False

    @staticmethod
    def _is_same_version_ip_pair(start: str, end: str) -> bool:
        """确认两个字符串是否构成同版本 IP 范围。"""
        try:
            start_ip = ipaddress.ip_address(start)
            end_ip = ipaddress.ip_address(end)
        except ValueError:
            return False
        return start_ip.version == end_ip.version


if __name__ == "__main__":
    cases = {
        "192.168.1.1": (True, "合法单 IPv4"),
        "192.168.1.0/24": (False, "拒绝 CIDR 网段"),
        "::1": (True, "合法单 IPv6"),
        "*.example.com": (False, "拒绝通配符域名"),
        "http://example.com": (False, "拒绝 URL"),
        "": (False, "拒绝空地址"),
    }

    for sample, expected in cases.items():
        actual = TargetValidator.validate(sample)
        print(f"{sample!r}: {actual}")
        assert actual == expected, f"{sample!r} 期望 {expected}，实际 {actual}"

    assert TargetValidator.validate_scan_params(20, 5.0) == (True, "扫描参数合法")
    assert TargetValidator.validate_scan_params(21, 5.0)[0] is False
    assert TargetValidator.validate_scan_params(1, 4.9)[0] is False
    print("validator.py 自检通过")
