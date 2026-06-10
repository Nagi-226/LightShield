"""TargetValidator 单元测试。

覆盖 LightShield 合规防线：
- R2：拒绝 CIDR、IP 范围、通配符、URL 等批量或非单目标输入。
- R4：生成所有权确认提示。
- R6：限制扫描并发和扫描间隔。
"""

from __future__ import annotations

import os
import sys

import pytest


# 允许直接执行本文件或从 tests/ 目录运行 pytest。
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from lightshield.utils.constants import MAX_CONCURRENT_SCANS, MIN_SCAN_INTERVAL
from lightshield.utils.validator import TargetValidator


@pytest.mark.parametrize(
    ("target", "expected_reason"),
    [
        ("192.168.1.1", "合法单 IPv4"),
        ("8.8.8.8", "合法单 IPv4"),
        ("10.0.0.1", "合法单 IPv4"),
        ("::1", "合法单 IPv6"),
        ("2001:4860:4860::8888", "合法单 IPv6"),
        ("example.com", "合法单域名"),
        ("sub.example.cn", "合法单域名"),
        ("localhost", "合法 localhost"),
    ],
)
def test_validate_accepts_single_targets(target: str, expected_reason: str) -> None:
    """合法单目标应通过：单 IPv4、单 IPv6、域名、localhost。"""
    ok, reason = TargetValidator.validate(target)

    assert ok is True, f"{target!r} 应被接受，实际被拒绝：{reason}"
    assert reason == expected_reason, f"{target!r} 返回原因不符合预期"


@pytest.mark.parametrize(
    ("target", "expected_reason"),
    [
        ("", "拒绝空地址"),
        ("   ", "拒绝空地址"),
        ("192.168.1.0/24", "拒绝 CIDR 网段"),
        ("10.0.0.1/8", "拒绝 CIDR 网段"),
        ("192.168.1.1-192.168.1.10", "拒绝 IP 范围"),
        ("192.168.1.1-10", "拒绝 IP 范围"),
        ("*.example.com", "拒绝通配符域名"),
        ("http://example.com", "拒绝 URL"),
        ("https://example.com/path", "拒绝 URL"),
        ("example.com:443", "拒绝 URL"),
        ("example.com/admin", "拒绝 URL"),
        ("example.com?debug=true", "拒绝 URL"),
    ],
)
def test_validate_rejects_batch_or_non_single_targets(target: str, expected_reason: str) -> None:
    """非法目标必须拒绝，宁可误拒不可漏过批量或 URL 形式。"""
    ok, reason = TargetValidator.validate(target)

    assert ok is False, f"{target!r} 应被拒绝，实际通过：{reason}"
    assert reason == expected_reason, f"{target!r} 拒绝原因不符合预期"


@pytest.mark.parametrize(
    "target",
    [
        None,
        "a" * 250 + ".com",
        "exa mple.com",
        "例子.com",
        "example.公司",
        "bad_domain.com",
        "example.com.",
    ],
)
def test_validate_rejects_boundary_invalid_values(target: object) -> None:
    """边界非法输入：None、超长域名、空格、Unicode 域名等都应拒绝。"""
    ok, reason = TargetValidator.validate(target)  # type: ignore[arg-type]

    assert ok is False, f"{target!r} 是边界非法输入，应被拒绝"
    assert reason, f"{target!r} 被拒绝时应返回中文原因"


@pytest.mark.parametrize(
    ("target", "expected"),
    [
        ("192.168.1.1", True),
        ("::1", True),
        ("fe80::1", True),
        ("192.168.1.0/24", False),
        ("example.com", False),
        ("192.168.1.1-10", False),
    ],
)
def test_is_valid_ip_accepts_only_single_ip(target: str, expected: bool) -> None:
    """is_valid_ip 只接受单个 IPv4/IPv6，拒绝网段和范围。"""
    assert TargetValidator.is_valid_ip(target) is expected, f"{target!r} IP 判断错误"


@pytest.mark.parametrize(
    ("target", "expected"),
    [
        ("192.168.1.0/24", True),
        ("10.0.0.0/8", True),
        ("2001:db8::/32", True),
        ("192.168.1.1", False),
        ("example.com", False),
        ("bad/target", False),
    ],
)
def test_is_cidr_detects_network_ranges(target: str, expected: bool) -> None:
    """CIDR 检测用于 R2 批量扫描拦截。"""
    assert TargetValidator.is_cidr(target) is expected, f"{target!r} CIDR 判断错误"


@pytest.mark.parametrize(
    ("target", "expected"),
    [
        ("example.com", True),
        ("sub.example.cn", True),
        ("localhost", True),
        ("*.example.com", False),
        ("http://example.com", False),
        ("example.com:443", False),
        ("bad_domain.com", False),
    ],
)
def test_is_valid_domain(target: str, expected: bool) -> None:
    """域名校验应接受单域名，拒绝通配符、URL、带端口和非法字符。"""
    assert TargetValidator.is_valid_domain(target) is expected, f"{target!r} 域名判断错误"


@pytest.mark.parametrize(
    ("target", "expected"),
    [
        ("*.example.com", True),
        ("api.*.example.com", True),
        ("example.com", False),
        ("", False),
    ],
)
def test_is_wildcard_domain(target: str, expected: bool) -> None:
    """通配符域名必须被识别并拒绝。"""
    assert TargetValidator.is_wildcard_domain(target) is expected, f"{target!r} 通配符判断错误"


@pytest.mark.parametrize(
    "target",
    [
        "10.0.0.1",
        "172.16.0.1",
        "172.31.255.255",
        "192.168.1.1",
        "127.0.0.1",
    ],
)
def test_is_private_ip_accepts_private_and_loopback_ranges(target: str) -> None:
    """内网和回环地址应返回 True。"""
    assert TargetValidator.is_private_ip(target) is True, f"{target!r} 应识别为内网/回环地址"


def test_is_private_ip_rejects_public_ip() -> None:
    """公网地址 8.8.8.8 应返回 False。"""
    assert TargetValidator.is_private_ip("8.8.8.8") is False, "8.8.8.8 不应识别为内网地址"


def test_confirm_ownership_returns_non_empty_chinese_text() -> None:
    """R4：所有权确认提示必须非空，并包含目标和所有权说明。"""
    message = TargetValidator.confirm_ownership("192.168.1.1")

    assert message.strip(), "所有权确认提示不能为空"
    assert "192.168.1.1" in message, "所有权确认提示应包含目标地址"
    assert "所有权" in message, "所有权确认提示应明确所有权要求"
    assert "自有资产" in message, "所有权确认提示应强调仅限自有资产"


@pytest.mark.parametrize(
    ("concurrency", "interval"),
    [
        (1, MIN_SCAN_INTERVAL),
        (MAX_CONCURRENT_SCANS, MIN_SCAN_INTERVAL),
        ("1", str(MIN_SCAN_INTERVAL)),
    ],
)
def test_validate_scan_params_accepts_valid_boundaries(concurrency: object, interval: object) -> None:
    """R6：并发和间隔在上下限边界内应通过。"""
    ok, reason = TargetValidator.validate_scan_params(concurrency, interval)  # type: ignore[arg-type]

    assert ok is True, f"合法扫描参数应通过，实际失败：{reason}"
    assert reason == "扫描参数合法"


@pytest.mark.parametrize(
    ("concurrency", "interval", "expected_reason"),
    [
        (0, MIN_SCAN_INTERVAL, "扫描并发必须 ≥1"),
        (-1, MIN_SCAN_INTERVAL, "扫描并发必须 ≥1"),
        (MAX_CONCURRENT_SCANS + 1, MIN_SCAN_INTERVAL, f"扫描并发不得超过 {MAX_CONCURRENT_SCANS}"),
        (1, MIN_SCAN_INTERVAL - 0.1, f"扫描间隔不得小于 {MIN_SCAN_INTERVAL} 秒"),
        ("bad", MIN_SCAN_INTERVAL, "扫描参数必须为数字"),
        (1, "bad", "扫描参数必须为数字"),
    ],
)
def test_validate_scan_params_rejects_invalid_boundaries(
    concurrency: object,
    interval: object,
    expected_reason: str,
) -> None:
    """R6：并发越界、间隔不足、非数字参数必须拒绝。"""
    ok, reason = TargetValidator.validate_scan_params(concurrency, interval)  # type: ignore[arg-type]

    assert ok is False, f"非法扫描参数应拒绝：concurrency={concurrency!r}, interval={interval!r}"
    assert reason == expected_reason, "扫描参数拒绝原因不符合预期"


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
