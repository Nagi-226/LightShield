"""LightShield 全局配置管理

支持：
  - YAML 配置文件加载
  - 环境变量覆盖（LS_ 前缀）
  - 单例模式
  - MSF 白名单/黑名单校验

用法：
    from lightshield.config import get_config
    cfg = get_config()
    cfg.load("lightshield.yaml")
"""

import json
import os
import sys as _sys
from dataclasses import dataclass, field

# Allow direct script execution (python lightshield/config.py)
if __name__ == "__main__" and _sys.path[0] != os.path.dirname(os.path.dirname(os.path.abspath(__file__))):
    _sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lightshield.utils.constants import (
    ALLOWED_MSF_PREFIXES,
    BLOCKED_MSF_PREFIXES,
    MAX_CONCURRENT_SCANS,
    MIN_SCAN_INTERVAL,
)

# =============================================================================
# 配置数据类
# =============================================================================


@dataclass
class LightShieldConfig:
    """LightShield 全局配置——单例模式

    优先级：环境变量 LS_xxx > 配置文件 > 默认值
    """

    # ---- 扫描配置 ----
    scan_timeout: int = 30
    max_concurrent_scans: int = MAX_CONCURRENT_SCANS
    scan_interval: float = MIN_SCAN_INTERVAL

    # ---- MSF 配置 ----
    msf_path: str = ""
    msf_whitelist: list[str] = field(default_factory=lambda: list(ALLOWED_MSF_PREFIXES))
    msf_blacklist: list[str] = field(default_factory=lambda: list(BLOCKED_MSF_PREFIXES))

    # ---- Nmap 配置 ----
    nmap_path: str = "nmap"
    nmap_args: str = "-sV -O --top-ports 1000"

    # ---- 报告配置 ----
    report_output_dir: str = "./reports"
    report_format: str = "markdown"
    report_lang: str = "zh-CN"

    # ---- 日志配置 ----
    log_dir: str = "./logs"
    log_level: str = "INFO"

    # ---- 加固配置 ----
    harden_dry_run: bool = True
    harden_backup: bool = True

    # =========================================================================
    # 未来扩展（v1.0.0 — v2.0.0 预留，当前不生效）
    # =========================================================================

    # ---- Web Panel (v1.0.0) ----
    web_host: str = "127.0.0.1"  # Flask 监听地址
    web_port: int = 5000  # Flask 监听端口
    auth_enabled: bool = False  # v1.0.0: 启用 Session 鉴权
    scan_queue_backend: str = "memory"  # v1.0.0: memory, v2.0.0: redis

    # ---- 存储后端 (v1.0.0) ----
    repository_backend: str = "json"  # v0.0.20: json, v1.0.0: sqlite, v2.0.0: postgres
    db_url: str = ""  # v1.0.0: sqlite:///data/lightshield.db
    # v2.0.0: postgresql://user:pass@host/lightshield

    # ---- 缓存 & 消息队列 (v2.0.0) ----
    redis_url: str = ""  # redis://localhost:6379/0
    celery_broker_url: str = ""  # redis://localhost:6379/1（或 RabbitMQ）
    cache_ttl_seconds: int = 3600  # 扫描结果缓存有效期

    # ---- API 鉴权 (v2.0.0) ----
    jwt_secret: str = ""  # JWT 签名密钥
    token_expire_hours: int = 24  # Token 有效期
    rate_limit_per_hour: int = 100  # API 每 IP 每小时限制

    # ---- 内部状态 ----
    _loaded: bool = field(default=False, init=False, repr=False)

    # =========================================================================
    # 配置加载
    # =========================================================================

    def load(self, path: str = "lightshield.yaml") -> None:
        """从 YAML 或 JSON 文件加载配置

        自动检测格式（.yaml / .json），然后应用环境变量覆盖。

        Args:
            path: 配置文件路径

        Raises:
            FileNotFoundError: 配置文件不存在
            ValueError: 配置格式错误
        """
        if not os.path.exists(path):
            self._loaded = True
            self._apply_env_overrides()
            return  # 配置文件不存在时使用默认值

        try:
            if path.endswith(".yaml") or path.endswith(".yml"):
                self._load_yaml(path)
            elif path.endswith(".json"):
                self._load_json(path)
            else:
                raise ValueError(f"不支持的配置文件格式: {path}（仅支持 .yaml / .json）")
        except Exception as e:
            raise ValueError(f"加载配置文件失败 [{path}]: {e}") from e

        self._apply_env_overrides()
        self._loaded = True

    def _load_yaml(self, path: str) -> None:
        """从 YAML 文件加载"""
        try:
            import yaml

            with open(path, encoding="utf-8") as f:
                data = yaml.safe_load(f)
        except ImportError as err:
            raise ImportError("需要安装 PyYAML 来读取 .yaml 配置文件：pip install PyYAML") from err

        if not isinstance(data, dict):
            raise ValueError(f"YAML 文件格式错误：期望顶层为字典，实际为 {type(data).__name__}")

        self._update_from_dict(data)

    def _load_json(self, path: str) -> None:
        """从 JSON 文件加载"""
        with open(path, encoding="utf-8") as f:
            data = json.load(f)

        if not isinstance(data, dict):
            raise ValueError(f"JSON 文件格式错误：期望顶层为字典，实际为 {type(data).__name__}")

        self._update_from_dict(data)

    def _update_from_dict(self, data: dict) -> None:
        """从字典批量更新配置字段

        使用 dataclasses.fields() 自动发现所有配置字段，
        新增字段无需手动维护映射表。
        跳过以 _ 开头的内部字段。
        """
        from dataclasses import fields

        valid_keys = {f.name for f in fields(self) if not f.name.startswith("_")}
        for key in valid_keys:
            if key in data:
                setattr(self, key, data[key])

    # =========================================================================
    # 环境变量覆盖
    # =========================================================================

    def _apply_env_overrides(self) -> None:
        """应用 LS_ 前缀的环境变量覆盖

        环境变量映射：
          LS_SCAN_TIMEOUT → scan_timeout
          LS_MAX_CONCURRENT_SCANS → max_concurrent_scans
          LS_SCAN_INTERVAL → scan_interval
          LS_MSF_PATH → msf_path
          LS_REPORT_OUTPUT_DIR → report_output_dir
          LS_LOG_DIR → log_dir
          LS_LOG_LEVEL → log_level
        """
        overrides = {
            "LS_SCAN_TIMEOUT": ("scan_timeout", int),
            "LS_MAX_CONCURRENT_SCANS": ("max_concurrent_scans", int),
            "LS_SCAN_INTERVAL": ("scan_interval", float),
            "LS_MSF_PATH": ("msf_path", str),
            "LS_NMAP_PATH": ("nmap_path", str),
            "LS_REPORT_OUTPUT_DIR": ("report_output_dir", str),
            "LS_REPORT_FORMAT": ("report_format", str),
            "LS_LOG_DIR": ("log_dir", str),
            "LS_LOG_LEVEL": ("log_level", str),
            "LS_HARDEN_DRY_RUN": ("harden_dry_run", lambda v: v.lower() in ("true", "1", "yes")),
            "LS_HARDEN_BACKUP": ("harden_backup", lambda v: v.lower() in ("true", "1", "yes")),
        }

        for env_var, (attr, converter) in overrides.items():
            value = os.environ.get(env_var)
            if value is not None:
                try:
                    setattr(self, attr, converter(value))  # type: ignore[operator]  # converter 类型为 Callable，通过 dict 推导无法表达
                except (ValueError, TypeError) as e:
                    # 使用项目统一日志（走审计与敏感信息脱敏），
                    # 惰性导入避免模块加载期就创建日志目录。
                    from lightshield.utils.logger import get_logger

                    get_logger().warning(
                        "config",
                        f"环境变量 {env_var}={value!r} 转换失败"
                        f"（{type(e).__name__}: {e}），保留默认值 {getattr(self, attr)!r}",
                    )

    # =========================================================================
    # 校验
    # =========================================================================

    def validate_msf_config(self) -> bool:
        """校验 MSF 白名单/黑名单配置（合规 R5）

        确保白名单中不包含黑名单路径前缀。

        Returns:
            True 表示配置合法

        Raises:
            ValueError: 检测到白名单与黑名单冲突
        """
        for blocked in self.msf_blacklist:
            for allowed in self.msf_whitelist:
                # 双向检查：黑名单不应是白名单的前缀，反之亦然
                if blocked.startswith(allowed) or allowed.startswith(blocked):
                    raise ValueError(f"MSF 配置冲突：白名单 [{allowed}] 与黑名单 [{blocked}] 重叠")
        return True

    def validate(self) -> tuple[bool, list[str]]:
        """校验全部配置的合法性

        Returns:
            (是否合法, 警告列表)
        """
        warnings = []

        # R6 校验
        if self.max_concurrent_scans > MAX_CONCURRENT_SCANS:
            warnings.append(f"并发数 {self.max_concurrent_scans} 超过合规上限 {MAX_CONCURRENT_SCANS}")
        if self.scan_interval < MIN_SCAN_INTERVAL:
            warnings.append(f"扫描间隔 {self.scan_interval}s 低于合规要求 {MIN_SCAN_INTERVAL}s")

        # MSF 配置
        try:
            self.validate_msf_config()
        except ValueError as e:
            warnings.append(str(e))

        # 路径校验
        if self.msf_path and not os.path.exists(self.msf_path):
            warnings.append(f"MSF 路径不存在: {self.msf_path}")

        return len(warnings) == 0, warnings

    # =========================================================================
    # 导出
    # =========================================================================

    def to_dict(self) -> dict:
        """导出为字典，方便传递给其他模块"""
        return {
            "scan_timeout": self.scan_timeout,
            "max_concurrent_scans": self.max_concurrent_scans,
            "scan_interval": self.scan_interval,
            "msf_path": self.msf_path,
            "msf_whitelist": self.msf_whitelist,
            "msf_blacklist": self.msf_blacklist,
            "nmap_path": self.nmap_path,
            "nmap_args": self.nmap_args,
            "report_output_dir": self.report_output_dir,
            "report_format": self.report_format,
            "report_lang": self.report_lang,
            "log_dir": self.log_dir,
            "log_level": self.log_level,
            "harden_dry_run": self.harden_dry_run,
            "harden_backup": self.harden_backup,
        }


# =============================================================================
# 单例
# =============================================================================

_config_instance: LightShieldConfig | None = None


def get_config() -> LightShieldConfig:
    """获取全局配置单例

    首次调用时创建默认实例，后续调用返回同一实例。

    Returns:
        LightShieldConfig 单例
    """
    global _config_instance
    if _config_instance is None:
        _config_instance = LightShieldConfig()
    return _config_instance


def reset_config() -> None:
    """重置配置单例（主要用于测试）"""
    global _config_instance
    _config_instance = None


# =============================================================================
# 自检
# =============================================================================

if __name__ == "__main__":
    cfg = get_config()
    print("[OK] 默认配置加载成功")
    print(f"   扫描超时: {cfg.scan_timeout}s")
    print(f"   并发上限: {cfg.max_concurrent_scans}")
    print(f"   扫描间隔: {cfg.scan_interval}s")
    print(f"   Nmap 路径: {cfg.nmap_path}")
    print(f"   报告目录: {cfg.report_output_dir}")
    print(f"   日志目录: {cfg.log_dir}")

    is_valid, warnings = cfg.validate()
    if is_valid:
        print("[OK] 配置校验通过")
    else:
        for w in warnings:
            print(f"[WARN]  {w}")

    cfg.validate_msf_config()
    print("[OK] MSF 白名单/黑名单无冲突")
