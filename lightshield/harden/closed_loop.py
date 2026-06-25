"""LightShield v0.0.40 加固闭环 — 闭环汇总数据结构

本模块仅定义 ClosedLoopResult 数据类与其 to_dict() 方法。
闭环编排逻辑（扫描→推荐→生成→执行→复扫→验证→汇总）由 Codex 实现，
不在此处；此文件是其他 Agent（Codex / QoderWork / Qoder Web）的公共 import。

接口契约来源：docs/design-v040-closed-loop.md §5.3
决策背景：docs/adr-v040-execution-substrate.md

用法：
    from lightshield.harden.closed_loop import ClosedLoopResult
"""

from __future__ import annotations

from dataclasses import dataclass, field

from lightshield.utils.constants import OSPlatform


# =============================================================================
# 数据结构
# =============================================================================


@dataclass
class ClosedLoopResult:
    """加固闭环全链路汇总结果——贯穿 ①-⑦ 七个环节。

    Attributes:
        target: 加固目标（IP/域名）
        os_platform: 目标操作系统平台
        mode: 执行模式 "dry_run" | "apply"
        before_scan: 加固前扫描结果（ScanResult.to_dict()）
        harden: 加固脚本生成结果（HardenResult.to_dict()）
        execution: 执行结果（ExecutionResult.to_dict()），DRY_RUN 跳过执行为 None
        after_scan: 复扫结果（ScanResult.to_dict()），DRY_RUN 无复扫为 None
        verification: 验证比对结果（VerificationResult.to_dict()），未执行比对为 None
        overall: 总判定 "verified" | "partial" | "failed" | "generated_only"
        audit_id: 贯穿全链路的审计 ID
    """

    target: str
    os_platform: OSPlatform
    mode: str  # "dry_run" | "apply"
    before_scan: dict = field(default_factory=dict)
    harden: dict = field(default_factory=dict)
    execution: dict | None = None
    after_scan: dict | None = None
    verification: dict | None = None
    overall: str = "generated_only"
    audit_id: str = ""

    def to_dict(self) -> dict:
        """导出为字典，Web/报告直接消费。

        所有 Enum 值已通过上游 to_dict() 转为字符串值，
        此处直接透传即可。单纯 JSON 序列化可跨进程消费。
        """
        return {
            "target": self.target,
            "os_platform": self.os_platform.value,
            "mode": self.mode,
            "before_scan": self.before_scan,
            "harden": self.harden,
            "execution": self.execution,
            "after_scan": self.after_scan,
            "verification": self.verification,
            "overall": self.overall,
            "audit_id": self.audit_id,
        }


# =============================================================================
# 自检
# =============================================================================

if __name__ == "__main__":
    print("=== ClosedLoopResult 自检 ===")

    # 构造一个典型 DRY_RUN 模式结果
    result = ClosedLoopResult(
        target="127.0.0.1",
        os_platform=OSPlatform.LINUX,
        mode="dry_run",
        before_scan={"status": "completed", "target": "127.0.0.1", "findings": []},
        harden={"status": "generated", "target": "127.0.0.1", "action_count": 3},
        execution=None,  # DRY_RUN 不执行
        after_scan=None,  # DRY_RUN 不复扫
        verification=None,  # DRY_RUN 不比对
        overall="generated_only",
        audit_id="LS-20260625-000000-test01",
    )

    d = result.to_dict()
    assert d["target"] == "127.0.0.1"
    assert d["os_platform"] == "linux"
    assert d["mode"] == "dry_run"
    assert d["execution"] is None
    assert d["overall"] == "generated_only"
    print("  [OK] DRY_RUN 模式 ClosedLoopResult.to_dict()")

    # 构造一个典型 APPLY 模式结果
    apply_result = ClosedLoopResult(
        target="127.0.0.1",
        os_platform=OSPlatform.LINUX,
        mode="apply",
        before_scan={
            "status": "completed",
            "target": "127.0.0.1",
            "findings": [
                {
                    "vuln_type": "high_risk_port",
                    "port": 22,
                    "severity": "high",
                    "title": "高危端口开放: 22",
                }
            ],
        },
        harden={"status": "executed", "target": "127.0.0.1", "action_count": 1},
        execution={"status": "completed", "exit_code": 0, "duration_seconds": 2.1},
        after_scan={
            "status": "completed",
            "target": "127.0.0.1",
            "findings": [],  # 风险消除
        },
        verification={
            "target": "127.0.0.1",
            "verdict": "verified",
            "resolved": [{"vuln_type": "high_risk_port", "port": 22}],
            "remaining": [],
            "regressed": [],
        },
        overall="verified",
        audit_id="LS-20260625-000000-test02",
    )

    d2 = apply_result.to_dict()
    assert d2["overall"] == "verified"
    assert d2["verification"]["verdict"] == "verified"
    print("  [OK] APPLY 模式 ClosedLoopResult.to_dict()")

    print("=== ClosedLoopResult 自检全部通过 ===")
