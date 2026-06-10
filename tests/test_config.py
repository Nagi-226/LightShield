"""测试模块：lightshield/config.py

覆盖内容：
  - get_config() 单例行为与默认值
  - reset_config() 后返回新实例
  - load() 无文件不抛异常（使用默认值）
  - load() 加载 JSON 文件正确覆盖字段
  - _apply_env_overrides 环境变量覆盖（LS_SCAN_TIMEOUT / LS_HARDEN_DRY_RUN 等）
  - validate_msf_config() 白名单无冲突 / 检测冲突抛 ValueError
  - validate() 返回 (bool, list) 元组
  - to_dict() 包含所有公开字段
  - MSF 白名单/黑名单默认值来自 constants

注意：
  - 环境变量测试需要保存/恢复 os.environ，避免污染其他测试
  - 单例测试需要使用 reset_config() 隔离
"""

import json
import os
import tempfile

import pytest

from lightshield.config import get_config, reset_config, LightShieldConfig
from lightshield.utils.constants import (
    ALLOWED_MSF_PREFIXES,
    BLOCKED_MSF_PREFIXES,
    MAX_CONCURRENT_SCANS,
    MIN_SCAN_INTERVAL,
)


# =============================================================================
# 辅助函数
# =============================================================================

def _set_env(key: str, value: str) -> str | None:
    """设置环境变量并返回旧值，方便测试后恢复"""
    old = os.environ.get(key)
    os.environ[key] = value
    return old


def _del_env(key: str) -> str | None:
    """删除环境变量并返回旧值"""
    old = os.environ.get(key)
    os.environ.pop(key, None)
    return old


# =============================================================================
# 单例与默认值
# =============================================================================

class TestConfigSingleton:
    """get_config() 单例行为与默认值"""

    def setup_method(self):
        """每个测试前重置单例"""
        reset_config()

    def test_get_config_returns_lighthield_config(self):
        """get_config() 返回 LightShieldConfig 实例"""
        cfg = get_config()
        assert isinstance(cfg, LightShieldConfig)

    def test_same_instance_on_multiple_calls(self):
        """多次调用返回同一实例"""
        a = get_config()
        b = get_config()
        assert a is b

    def test_default_scan_timeout(self):
        """默认 scan_timeout == 30"""
        cfg = get_config()
        assert cfg.scan_timeout == 30

    def test_default_max_concurrent_scans(self):
        """默认 max_concurrent_scans == MAX_CONCURRENT_SCANS (20)"""
        cfg = get_config()
        assert cfg.max_concurrent_scans == MAX_CONCURRENT_SCANS
        assert cfg.max_concurrent_scans == 20

    def test_default_scan_interval(self):
        """默认 scan_interval == MIN_SCAN_INTERVAL (5.0)"""
        cfg = get_config()
        assert cfg.scan_interval == MIN_SCAN_INTERVAL
        assert cfg.scan_interval == 5.0

    def test_default_msf_path_empty(self):
        """默认 msf_path 为空字符串"""
        cfg = get_config()
        assert cfg.msf_path == ""

    def test_default_nmap_path(self):
        """默认 nmap_path == 'nmap'"""
        cfg = get_config()
        assert cfg.nmap_path == "nmap"

    def test_default_report_format(self):
        """默认 report_format == 'markdown'"""
        cfg = get_config()
        assert cfg.report_format == "markdown"

    def test_default_report_lang(self):
        """默认 report_lang == 'zh-CN'"""
        cfg = get_config()
        assert cfg.report_lang == "zh-CN"

    def test_default_log_level(self):
        """默认 log_level == 'INFO'"""
        cfg = get_config()
        assert cfg.log_level == "INFO"

    def test_default_harden_dry_run(self):
        """默认 harden_dry_run == True"""
        cfg = get_config()
        assert cfg.harden_dry_run is True

    def test_default_harden_backup(self):
        """默认 harden_backup == True"""
        cfg = get_config()
        assert cfg.harden_backup is True

    def test_default_msf_whitelist_from_constants(self):
        """默认 msf_whitelist 来自 constants.ALLOWED_MSF_PREFIXES"""
        cfg = get_config()
        assert cfg.msf_whitelist == list(ALLOWED_MSF_PREFIXES)

    def test_default_msf_blacklist_from_constants(self):
        """默认 msf_blacklist 来自 constants.BLOCKED_MSF_PREFIXES"""
        cfg = get_config()
        assert cfg.msf_blacklist == list(BLOCKED_MSF_PREFIXES)


# =============================================================================
# reset_config
# =============================================================================

class TestResetConfig:
    """reset_config() 行为验证"""

    def setup_method(self):
        reset_config()

    def test_reset_creates_new_instance(self):
        """reset_config() 后 get_config() 返回新实例"""
        old = get_config()
        reset_config()
        new = get_config()
        assert old is not new, "reset_config 后应返回新实例"

    def test_reset_then_same_defaults(self):
        """reset 后新实例仍使用默认值"""
        cfg1 = get_config()
        cfg1.scan_timeout = 999  # 修改当前实例
        reset_config()
        cfg2 = get_config()
        assert cfg2.scan_timeout == 30, "新实例应恢复默认值"


# =============================================================================
# load() — 无文件 / JSON 加载
# =============================================================================

class TestConfigLoad:
    """load() 方法验证"""

    def setup_method(self):
        reset_config()

    def test_load_no_file_no_exception(self):
        """不存在的配置文件不抛异常，使用默认值"""
        cfg = get_config()
        cfg.load("/nonexistent/path/lightshield.yaml")
        assert cfg.scan_timeout == 30, "应保持默认值"

    def test_load_json_file_overrides_field(self):
        """加载 JSON 配置文件覆盖对应字段"""
        cfg = get_config()

        json_data = {
            "scan_timeout": 60,
            "nmap_path": "/usr/bin/nmap",
            "report_lang": "en-US",
        }

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False, encoding="utf-8"
        ) as f:
            json.dump(json_data, f)
            json_path = f.name

        try:
            cfg.load(json_path)
            assert cfg.scan_timeout == 60, f"期望 60，实际 {cfg.scan_timeout}"
            assert cfg.nmap_path == "/usr/bin/nmap"
            assert cfg.report_lang == "en-US"
        finally:
            os.unlink(json_path)

    def test_load_json_does_not_alter_unrelated_fields(self):
        """加载 JSON 不覆盖未在 JSON 中出现的字段"""
        cfg = get_config()
        original_nmap_args = cfg.nmap_args

        json_data = {"scan_timeout": 45}

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False, encoding="utf-8"
        ) as f:
            json.dump(json_data, f)
            json_path = f.name

        try:
            cfg.load(json_path)
            assert cfg.nmap_args == original_nmap_args, "未在 JSON 中的字段应保持默认值"
        finally:
            os.unlink(json_path)

    def test_load_unsupported_format_raises_value_error(self):
        """不支持的配置文件格式抛出 ValueError"""
        cfg = get_config()
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".txt", delete=False, encoding="utf-8"
        ) as f:
            f.write("some text")
            txt_path = f.name

        try:
            with pytest.raises(ValueError, match="不支持的配置文件格式"):
                cfg.load(txt_path)
        finally:
            os.unlink(txt_path)


# =============================================================================
# 环境变量覆盖
# =============================================================================

class TestEnvOverrides:
    """_apply_env_overrides 环境变量覆盖验证"""

    def setup_method(self):
        reset_config()

    def test_ls_scan_timeout_override(self):
        """LS_SCAN_TIMEOUT 环境变量覆盖 scan_timeout"""
        old = _set_env("LS_SCAN_TIMEOUT", "60")
        try:
            cfg = get_config()
            cfg.load("/nonexistent.yaml")  # 触发 _apply_env_overrides
            assert cfg.scan_timeout == 60, f"期望 60，实际 {cfg.scan_timeout}"
        finally:
            if old is None:
                _del_env("LS_SCAN_TIMEOUT")
            else:
                _set_env("LS_SCAN_TIMEOUT", old)

    def test_ls_max_concurrent_scans_override(self):
        """LS_MAX_CONCURRENT_SCANS 环境变量覆盖 max_concurrent_scans"""
        old = _set_env("LS_MAX_CONCURRENT_SCANS", "15")
        try:
            cfg = get_config()
            cfg.load("/nonexistent.yaml")
            assert cfg.max_concurrent_scans == 15
        finally:
            if old is None:
                _del_env("LS_MAX_CONCURRENT_SCANS")
            else:
                _set_env("LS_MAX_CONCURRENT_SCANS", old)

    def test_ls_scan_interval_override(self):
        """LS_SCAN_INTERVAL 环境变量覆盖 scan_interval"""
        old = _set_env("LS_SCAN_INTERVAL", "10.5")
        try:
            cfg = get_config()
            cfg.load("/nonexistent.yaml")
            assert cfg.scan_interval == 10.5
        finally:
            if old is None:
                _del_env("LS_SCAN_INTERVAL")
            else:
                _set_env("LS_SCAN_INTERVAL", old)

    def test_ls_nmap_path_override(self):
        """LS_NMAP_PATH 环境变量覆盖 nmap_path"""
        old = _set_env("LS_NMAP_PATH", "/opt/nmap/bin/nmap")
        try:
            cfg = get_config()
            cfg.load("/nonexistent.yaml")
            assert cfg.nmap_path == "/opt/nmap/bin/nmap"
        finally:
            if old is None:
                _del_env("LS_NMAP_PATH")
            else:
                _set_env("LS_NMAP_PATH", old)

    def test_ls_report_output_dir_override(self):
        """LS_REPORT_OUTPUT_DIR 环境变量覆盖 report_output_dir"""
        old = _set_env("LS_REPORT_OUTPUT_DIR", "/tmp/reports")
        try:
            cfg = get_config()
            cfg.load("/nonexistent.yaml")
            assert cfg.report_output_dir == "/tmp/reports"
        finally:
            if old is None:
                _del_env("LS_REPORT_OUTPUT_DIR")
            else:
                _set_env("LS_REPORT_OUTPUT_DIR", old)

    def test_ls_log_dir_override(self):
        """LS_LOG_DIR 环境变量覆盖 log_dir"""
        old = _set_env("LS_LOG_DIR", "/var/log/lightshield")
        try:
            cfg = get_config()
            cfg.load("/nonexistent.yaml")
            assert cfg.log_dir == "/var/log/lightshield"
        finally:
            if old is None:
                _del_env("LS_LOG_DIR")
            else:
                _set_env("LS_LOG_DIR", old)

    def test_ls_log_level_override(self):
        """LS_LOG_LEVEL 环境变量覆盖 log_level"""
        old = _set_env("LS_LOG_LEVEL", "DEBUG")
        try:
            cfg = get_config()
            cfg.load("/nonexistent.yaml")
            assert cfg.log_level == "DEBUG"
        finally:
            if old is None:
                _del_env("LS_LOG_LEVEL")
            else:
                _set_env("LS_LOG_LEVEL", old)

    # ---- LS_HARDEN_DRY_RUN 布尔转换 ----

    @pytest.mark.parametrize("env_val,expected", [
        ("true", True),
        ("false", False),
        ("1", True),
        ("0", False),
        ("yes", True),
        ("no", False),
        ("TRUE", True),
        ("FALSE", False),
    ])
    def test_harden_dry_run_bool_conversion(self, env_val, expected):
        """LS_HARDEN_DRY_RUN 的 true/false/1/0/yes/no 转换正确"""
        old = _set_env("LS_HARDEN_DRY_RUN", env_val)
        try:
            cfg = get_config()
            cfg.load("/nonexistent.yaml")
            assert cfg.harden_dry_run == expected, (
                f"env={env_val!r} 期望 {expected}，实际 {cfg.harden_dry_run}"
            )
        finally:
            if old is None:
                _del_env("LS_HARDEN_DRY_RUN")
            else:
                _set_env("LS_HARDEN_DRY_RUN", old)

    def test_harden_dry_run_default_is_true(self):
        """未设置 LS_HARDEN_DRY_RUN 时默认 True"""
        _del_env("LS_HARDEN_DRY_RUN")
        cfg = get_config()
        cfg.load("/nonexistent.yaml")
        assert cfg.harden_dry_run is True


# =============================================================================
# validate_msf_config
# =============================================================================

class TestValidateMsfConfig:
    """validate_msf_config() MSF 白名单/黑名单冲突检测"""

    def setup_method(self):
        reset_config()

    def test_no_conflict_returns_true(self):
        """默认配置无冲突时返回 True"""
        cfg = get_config()
        assert cfg.validate_msf_config() is True

    def test_detects_exploit_in_whitelist(self):
        """手动将 'exploit/' 加入白名单应抛出 ValueError"""
        cfg = get_config()
        cfg.msf_whitelist = list(ALLOWED_MSF_PREFIXES) + ["exploit/"]

        with pytest.raises(ValueError, match="MSF 配置冲突"):
            cfg.validate_msf_config()

    def test_detects_payload_in_whitelist(self):
        """手动将 'payload/' 加入白名单应抛出 ValueError"""
        cfg = get_config()
        cfg.msf_whitelist.append("payload/")

        with pytest.raises(ValueError, match="MSF 配置冲突"):
            cfg.validate_msf_config()

    def test_detects_reverse_conflict(self):
        """白名单前缀在黑名单子路径中时也应检测到（双向检查）"""
        cfg = get_config()
        # 模拟：辅助扫描 HTTP 路径片段出现在黑名单中
        cfg.msf_whitelist = list(ALLOWED_MSF_PREFIXES)
        cfg.msf_blacklist = list(BLOCKED_MSF_PREFIXES) + ["auxiliary/scanner/http/dangerous"]

        with pytest.raises(ValueError, match="MSF 配置冲突"):
            cfg.validate_msf_config()


# =============================================================================
# validate
# =============================================================================

class TestValidate:
    """validate() 方法验证"""

    def setup_method(self):
        reset_config()

    def test_returns_bool_and_list(self):
        """validate() 返回 (bool, list) 元组"""
        cfg = get_config()
        is_valid, warnings = cfg.validate()
        assert isinstance(is_valid, bool)
        assert isinstance(warnings, list)

    def test_default_config_is_valid(self):
        """默认配置校验通过（无警告）"""
        cfg = get_config()
        is_valid, warnings = cfg.validate()
        assert is_valid is True
        assert len(warnings) == 0, f"期望 0 条警告，实际: {warnings}"

    def test_warns_on_excessive_concurrency(self):
        """并发数超过合规上限时触发警告"""
        cfg = get_config()
        cfg.max_concurrent_scans = 999
        is_valid, warnings = cfg.validate()
        assert is_valid is False
        assert any("并发数" in w for w in warnings), "应包含并发超标警告"

    def test_warns_on_short_interval(self):
        """扫描间隔低于合规下限时触发警告"""
        cfg = get_config()
        cfg.scan_interval = 0.1
        is_valid, warnings = cfg.validate()
        assert is_valid is False
        assert any("扫描间隔" in w for w in warnings), "应包含间隔超标警告"


# =============================================================================
# to_dict
# =============================================================================

class TestToDict:
    """to_dict() 导出验证"""

    def setup_method(self):
        reset_config()

    def test_returns_dict(self):
        """to_dict() 返回 dict"""
        cfg = get_config()
        result = cfg.to_dict()
        assert isinstance(result, dict)

    def test_contains_all_public_fields(self):
        """to_dict() 包含所有公开配置字段"""
        expected_keys = {
            "scan_timeout", "max_concurrent_scans", "scan_interval",
            "msf_path", "msf_whitelist", "msf_blacklist",
            "nmap_path", "nmap_args",
            "report_output_dir", "report_format", "report_lang",
            "log_dir", "log_level",
            "harden_dry_run", "harden_backup",
        }
        cfg = get_config()
        result = cfg.to_dict()
        actual_keys = set(result.keys())
        missing = expected_keys - actual_keys
        assert not missing, f"to_dict() 缺失字段: {missing}"

    def test_values_match_instance(self):
        """to_dict() 中的值与实例属性一致"""
        cfg = get_config()
        cfg.scan_timeout = 42
        cfg.harden_dry_run = False

        result = cfg.to_dict()
        assert result["scan_timeout"] == 42
        assert result["harden_dry_run"] is False
