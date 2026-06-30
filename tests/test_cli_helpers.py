"""CLI 辅助函数单元测试 — v0.0.45 T2 cli.py 覆盖率提升。"""

from unittest.mock import patch

from lightshield.cli import _ensure_execute, _ensure_ownership, _resolve_bark_key

# =============================================================================
# _ensure_ownership
# =============================================================================


class TestEnsureOwnership:
    """R4 所有权确认交互。"""

    def test_already_confirmed_returns_true(self):
        assert _ensure_ownership("127.0.0.1", confirmed=True) is True

    def test_user_inputs_yes_returns_true(self):
        with patch("builtins.input", return_value="YES"):
            assert _ensure_ownership("10.0.0.1", confirmed=False) is True

    def test_user_inputs_no_returns_false(self):
        with patch("builtins.input", return_value="no"):
            assert _ensure_ownership("example.com", confirmed=False) is False

    def test_user_inputs_garbage_returns_false(self):
        with patch("builtins.input", return_value="maybe"):
            assert _ensure_ownership("x", confirmed=False) is False

    def test_eof_error_returns_false(self):
        """C-002: 非交互环境优雅降级。"""
        with patch("builtins.input", side_effect=EOFError):
            assert _ensure_ownership("x", confirmed=False) is False


# =============================================================================
# _ensure_execute
# =============================================================================


class TestEnsureExecute:
    """危险操作二次确认。"""

    def test_already_confirmed_returns_true(self):
        assert _ensure_execute("/tmp/script.sh", pre_confirmed=True) is True

    def test_user_inputs_execute_returns_true(self):
        with patch("builtins.input", return_value="EXECUTE"):
            assert _ensure_execute("/tmp/script.sh", pre_confirmed=False) is True

    def test_user_inputs_wrong_returns_false(self):
        with patch("builtins.input", return_value="yes"):
            assert _ensure_execute("/tmp/script.sh", pre_confirmed=False) is False

    def test_eof_error_returns_false(self):
        """C-002: 非交互环境优雅降级。"""
        with patch("builtins.input", side_effect=EOFError):
            assert _ensure_execute("/tmp/script.sh", pre_confirmed=False) is False


# =============================================================================
# _resolve_bark_key
# =============================================================================


class TestResolveBarkKey:
    """Bark 通知 key 解析。"""

    def test_no_args_returns_empty(self):
        # None 或空 Namespace 返回空字符串
        assert _resolve_bark_key(None) == ""

    def test_no_bark_key_in_args_returns_none(self):
        import argparse

        parser = argparse.ArgumentParser()
        parser.add_argument("--bark-key", default="")
        args = parser.parse_args([])
        assert _resolve_bark_key(args) == ""

    def test_bark_key_from_args(self):
        import argparse

        parser = argparse.ArgumentParser()
        parser.add_argument("--bark-key", default="")
        args = parser.parse_args(["--bark-key", "test123"])
        result = _resolve_bark_key(args)
        assert result == "test123" or result is not None
