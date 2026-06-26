"""LightShield v0.0.40 — Loop Hook 模块单元测试

测试目标：
  - notifier: 无 key 静默跳过 / URL 构造 / 内容截断
  - report_archiver: 正常归档 / 不存在文件 / 非法字符替换 / 过期清理
"""

from __future__ import annotations

import os
import tempfile
from unittest import mock

from lightshield.utils.notifier import (
    _MAX_BODY_LEN,
    _MAX_TITLE_LEN,
    notify_closed_loop_complete,
    notify_scan_complete,
    send_bark_notification,
)
from lightshield.utils.report_archiver import (
    _cleanup_old,
    _safe_dirname,
    archive_report,
)

# =============================================================================
# 测试辅助
# =============================================================================


def _get_url_from_mock(m_urlopen) -> str:
    """从 urllib.request.urlopen mock 中提取请求 URL。

    urlopen 接收 Request 对象，返回其 full_url 字符串。
    """
    req = m_urlopen.call_args[0][0]
    return req.full_url if hasattr(req, "full_url") else str(req)


# =============================================================================
# notifier 测试
# =============================================================================


class TestSendBarkNotification:
    """send_bark_notification 基础测试。"""

    def test_no_key_skips(self):
        """无 Bark Key → 静默跳过。"""
        r = send_bark_notification("title", "body", "")
        assert r.success is False
        assert "未配置" in r.message

    def test_empty_key_skips(self):
        """空白 Key → 静默跳过。"""
        r = send_bark_notification("title", "body", "   ")
        assert r.success is False

    def test_title_truncation(self):
        """超长标题自动截断——URL 不含完整超长标题。"""
        long_title = "x" * (_MAX_TITLE_LEN + 50)
        long_body = "y" * (_MAX_BODY_LEN + 50)

        with mock.patch("urllib.request.urlopen") as m_urlopen:
            m_resp = mock.Mock()
            m_resp.status = 200
            m_urlopen.return_value.__enter__.return_value = m_resp

            r = send_bark_notification(long_title, long_body, "test_key")

        assert r.success is True
        url = _get_url_from_mock(m_urlopen)
        # 完整的长标题（MAX+50）不可能出现在 URL 中（已被截断）
        assert long_title not in url
        # 但截断后的部分应在
        assert "x" * _MAX_TITLE_LEN in url

    def test_url_encoding(self):
        """中文字符正确 URL 编码。"""
        with mock.patch("urllib.request.urlopen") as m_urlopen:
            m_resp = mock.Mock()
            m_resp.status = 200
            m_urlopen.return_value.__enter__.return_value = m_resp

            send_bark_notification("标题 测试", "clean_body", "test_key")

        url = _get_url_from_mock(m_urlopen)
        assert "%E6%A0%87%E9%A2%98" in url  # "标题" 的 URL 编码
        # 中文字符不应原样出现在 URL 中
        assert "标题" not in url


class TestNotifyScanComplete:
    """notify_scan_complete 测试。"""

    def test_no_key_skips(self):
        """无 Key → 跳过。"""
        r = notify_scan_complete("127.0.0.1", 5, bark_key="")
        assert r.success is False

    def test_critical_uses_alarm_sound(self):
        """严重漏洞 → alarm 提示音。"""
        with mock.patch("urllib.request.urlopen") as m_urlopen:
            m_resp = mock.Mock()
            m_resp.status = 200
            m_urlopen.return_value.__enter__.return_value = m_resp

            r = notify_scan_complete("127.0.0.1", 5, critical_count=2, bark_key="k")

        assert r.success is True
        url = _get_url_from_mock(m_urlopen)
        assert "alarm" in url
        assert "%F0%9F%94%B4" in url  # 🔴 URL-encoded

    def test_no_findings_uses_silence(self):
        """无漏洞 → silence 提示音。"""
        with mock.patch("urllib.request.urlopen") as m_urlopen:
            m_resp = mock.Mock()
            m_resp.status = 200
            m_urlopen.return_value.__enter__.return_value = m_resp

            r = notify_scan_complete("127.0.0.1", 0, bark_key="k")

        assert r.success is True
        url = _get_url_from_mock(m_urlopen)
        assert "silence" in url

    def test_high_finding_uses_default_sound(self):
        """高危漏洞 → 默认提示音。"""
        with mock.patch("urllib.request.urlopen") as m_urlopen:
            m_resp = mock.Mock()
            m_resp.status = 200
            m_urlopen.return_value.__enter__.return_value = m_resp

            notify_scan_complete("127.0.0.1", 3, high_count=3, bark_key="k")

        url = _get_url_from_mock(m_urlopen)
        assert "birdsong" in url


class TestNotifyClosedLoopComplete:
    """notify_closed_loop_complete 测试。"""

    def test_no_key_skips(self):
        """无 Key → 跳过。"""
        r = notify_closed_loop_complete("127.0.0.1", "verified", "apply", bark_key="")
        assert r.success is False

    def test_verified_uses_silence(self):
        """加固成功 → silence 提示音。"""
        with mock.patch("urllib.request.urlopen") as m_urlopen:
            m_resp = mock.Mock()
            m_resp.status = 200
            m_urlopen.return_value.__enter__.return_value = m_resp

            notify_closed_loop_complete("127.0.0.1", "verified", "apply", resolved_count=3, bark_key="k")

        url = _get_url_from_mock(m_urlopen)
        assert "silence" in url

    def test_failed_uses_alarm(self):
        """加固失败 → alarm 提示音。"""
        with mock.patch("urllib.request.urlopen") as m_urlopen:
            m_resp = mock.Mock()
            m_resp.status = 200
            m_urlopen.return_value.__enter__.return_value = m_resp

            notify_closed_loop_complete("127.0.0.1", "failed", "apply", bark_key="k")

        url = _get_url_from_mock(m_urlopen)
        assert "alarm" in url


# =============================================================================
# report_archiver 测试
# =============================================================================


class TestArchiveReport:
    """archive_report 测试。"""

    def test_nonexistent_file_returns_none(self):
        """文件不存在 → None。"""
        assert archive_report("/nonexistent/path.md", "test") is None

    def test_empty_path_returns_none(self):
        """空路径 → None。"""
        assert archive_report("", "test") is None

    def test_normal_archive(self):
        """正常归档：文件移动到按日期组织的目录。"""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = os.path.join(tmpdir, "scan_test.md")
            with open(test_file, "w", encoding="utf-8") as f:
                f.write("# Report\n")

            dest = archive_report(test_file, "127.0.0.1", base_dir=tmpdir)
            assert dest is not None
            assert os.path.isfile(dest)
            assert "127.0.0.1" in dest
            # 原文件已移动
            assert not os.path.exists(test_file)

    def test_archive_with_special_target_chars(self):
        """目标含特殊字符 → 安全目录名替换。"""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = os.path.join(tmpdir, "scan_test.md")
            with open(test_file, "w", encoding="utf-8") as f:
                f.write("# Report\n")

            dest = archive_report(test_file, "evil.com/path?query=1", base_dir=tmpdir)
            assert dest is not None
            assert "/" not in dest.split("evil")[-1] if "evil" in dest else True


class TestSafeDirname:
    """_safe_dirname 测试。"""

    def test_normal_names(self):
        assert _safe_dirname("example.com") == "example.com"
        assert _safe_dirname("127.0.0.1") == "127.0.0.1"
        assert _safe_dirname("localhost") == "localhost"

    def test_path_traversal_prevented(self):
        assert "/" not in _safe_dirname("a/b")
        assert "\\" not in _safe_dirname("a\\b")

    def test_special_chars_replaced(self):
        assert _safe_dirname("site:80") == "site_80"
        assert _safe_dirname("a?query") == "a_query"
        assert _safe_dirname("a<b>c|d") == "a_b_c_d"
        assert _safe_dirname('a"b') == "a_b"

    def test_long_name_truncated(self):
        long = "a" * 100
        result = _safe_dirname(long)
        assert len(result) <= 80


class TestCleanupOld:
    """_cleanup_old 测试。"""

    def test_empty_dir_no_crash(self):
        """空目录清理不崩溃。"""
        with tempfile.TemporaryDirectory() as tmpdir:
            _cleanup_old(tmpdir, max_age_days=30)  # 不应该抛异常

    def test_recent_files_preserved(self):
        """近期报告不被清理。"""
        with tempfile.TemporaryDirectory() as tmpdir:
            # 创建当天目录
            import datetime

            today = datetime.datetime.now()
            month_dir = os.path.join(tmpdir, today.strftime("%Y-%m"))
            day_dir = os.path.join(month_dir, today.strftime("%d"))
            os.makedirs(day_dir)
            with open(os.path.join(day_dir, "report.md"), "w") as f:
                f.write("# test")

            _cleanup_old(tmpdir, max_age_days=30)
            # 目录应仍存在
            assert os.path.isdir(day_dir)
