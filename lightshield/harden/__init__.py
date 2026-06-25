"""防御加固子包 — 安全加固模板、配置下发与回滚支持

导出：
  - HardenStatus / HardenResult / HardenBase — 加固适配器抽象基类
  - LinuxHardener  — Linux 加固脚本生成器（.sh）
  - WinHardener   — Windows 加固脚本生成器（.ps1）
  - VerificationResult / verify_hardening — v0.0.40 加固前后比对（纯函数）
  - ClosedLoopResult — v0.0.40 闭环全链路汇总数据结构
"""

from lightshield.harden.base import HardenBase, HardenResult, HardenStatus
from lightshield.harden.closed_loop import ClosedLoopResult
from lightshield.harden.linux_harden import LinuxHardener
from lightshield.harden.verify import VerificationResult, verify_hardening
from lightshield.harden.win_harden import WinHardener

__all__ = [
    "ClosedLoopResult",
    "HardenBase",
    "HardenResult",
    "HardenStatus",
    "LinuxHardener",
    "VerificationResult",
    "WinHardener",
    "verify_hardening",
]
