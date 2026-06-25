"""LightShield 加固适配器抽象基类

与 adapters/base.py 对称——前者定义“扫描”接口，这里定义“系统加固”接口。
所有加固能力（Linux / Windows / 等）只需实现此基类。

设计原则：
  - 默认生成脚本，不自动执行（安全第一）
  - 每条操作必须审计留痕（合规 R4）
  - 预留 execute() / rollback() 扩展位

用法：
    from lightshield.harden.base import HardenBase, HardenResult, HardenStatus
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum

from lightshield.utils.constants import OSPlatform

# =============================================================================
# 数据结构
# =============================================================================


class HardenStatus(Enum):
    """加固执行状态"""

    GENERATED = "generated"  # 已生成脚本（未执行）
    NO_ACTION = "no_action"  # 无推荐项，无需操作
    FAILED = "failed"  # 生成/执行失败
    EXECUTED = "executed"  # v0.0.40: 脚本已执行（不代表已验证）
    VERIFIED = "verified"  # v0.0.40: 复扫确认风险已消除
    REGRESSED = "regressed"  # v0.0.40: 复扫发现仍存在 / 引入新风险


@dataclass
class HardenResult:
    """加固结果统一数据结构 —— 所有 HardenBase 子类返回此格式

    Attributes:
        status: 加固状态
        target: 加固目标
        os_platform: 目标操作系统
        recommendations: 来自规则引擎的加固建议列表
        script_path: 生成的加固脚本路径
        rollback_path: 回滚脚本路径
        action_count: 实际建议的操作数
        audit_id: 关联审计日志的 ID
        error: 错误信息（status=FAILED 时填充）
    """

    status: HardenStatus
    target: str
    os_platform: OSPlatform
    recommendations: list[dict] = field(default_factory=list)
    script_path: str | None = None
    rollback_path: str | None = None
    action_count: int = 0
    audit_id: str = ""
    error: str | None = None

    def to_dict(self) -> dict:
        """导出为字典"""
        return {
            "status": self.status.value,
            "target": self.target,
            "os_platform": self.os_platform.value,
            "recommendations": self.recommendations,
            "script_path": self.script_path,
            "rollback_path": self.rollback_path,
            "action_count": self.action_count,
            "audit_id": self.audit_id,
            "error": self.error,
        }


# =============================================================================
# 抽象基类
# =============================================================================


class HardenBase(ABC):
    """所有加固适配器的抽象基类

    新增加固能力只需：
    1. 继承 HardenBase
    2. 实现 generate() 抽象方法
    3. 在 LightShieldCore / CLI 中注册

    已为未来 execute() / rollback() 预留签名空间。
    """

    def __init__(self, name: str = ""):
        """初始化加固适配器。

        Args:
        name: 适配器名称（用于日志和审计）
        """
        self.name = name or self.__class__.__name__

    @abstractmethod
    def generate(
        self,
        target: str,
        recommendations: list[dict],
        output_dir: str | None = None,
    ) -> HardenResult:
        """生成加固脚本（默认不自动执行）

        Args:
            target: 加固目标（IP/域名）
            recommendations: 规则引擎的 recommend_hardening() 输出
            output_dir: 脚本输出目录，默认读取配置

        Returns:
            HardenResult 结构化结果
        """
        ...

    # ---- 共享 helper ----

    @staticmethod
    def _substitute(command: str, port: str, target: str) -> str:
        """替换命令模板中的变量占位符

        支持的占位符：
          {port} → 端口号
          {target} → 扫描目标

        <service> 等未实现变量保留原样（注释引导操作员填写）。
        """
        cmd = command.replace("{port}", port).replace("{target}", target)
        return cmd

    @staticmethod
    def _audit_action(target: str, action: str, result: str) -> None:
        """记录加固操作到审计日志"""
        from lightshield.utils.logger import get_logger

        get_logger().audit_harden_action(target, action, result)
