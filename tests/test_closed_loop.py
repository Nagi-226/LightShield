"""LightShield v0.0.40 — run_harden_closed_loop 单元测试

测试目标：
  - DRY_RUN 路径：扫描→推荐→生成→预检（R1 + 容器烟测）→ overall="generated_only"
  - DRY_RUN R1 关键字拒绝
  - APPLY 路径：双确认闸门（缺一被拒）
  - APPLY 路径：DRY_RUN-first / rollback 就绪 前置检查
  - APPLY 路径：完整 ①-⑦ 闭环（mock subprocess）
  - 无加固建议场景（闭环提前终止）
  - 异常转 ClosedLoopResult（不抛异常）

所有测试 mock 外部依赖（扫描/规则引擎/Docker/子进程），
verify_hardening 用真实实现（纯函数无需 mock）。
"""

from __future__ import annotations

import os
import tempfile
from unittest import mock

from lightshield.adapters.base import ScanResult, VulnFinding
from lightshield.core import LightShieldCore
from lightshield.harden.base import HardenResult, HardenStatus
from lightshield.harden.closed_loop import ClosedLoopResult
from lightshield.sandbox.base import ExecutionResult, ExecutionStatus
from lightshield.utils.constants import OSPlatform, RiskLevel, ScanStatus

# =============================================================================
# 测试辅助
# =============================================================================


def _finding(vuln_type: str, port: int | None = None) -> VulnFinding:
    """快速构造一个 VulnFinding。"""
    return VulnFinding(
        vuln_type=vuln_type,
        severity=RiskLevel.HIGH,
        title=f"风险 {vuln_type}",
        description="测试",
        remediation="修复",
        port=port,
    )


def _scan_result(target: str, findings: list[VulnFinding]) -> ScanResult:
    """构造 ScanResult。"""
    return ScanResult(
        status=ScanStatus.COMPLETED,
        target=target,
        findings=findings,
        duration_seconds=1.0,
    )


def _harden_result(
    script_path: str | None = "/tmp/harden.sh",
    rollback_path: str | None = "/tmp/rollback.sh",
    status: HardenStatus = HardenStatus.GENERATED,
) -> HardenResult:
    """构造 HardenResult。"""
    return HardenResult(
        status=status,
        target="127.0.0.1",
        os_platform=OSPlatform.LINUX,
        script_path=script_path,
        rollback_path=rollback_path,
        action_count=2,
    )


def _exec_result_success() -> ExecutionResult:
    """构造成功的 ExecutionResult。"""
    return ExecutionResult(
        status=ExecutionStatus.SUCCESS,
        script_path="/tmp/harden.sh",
        sandbox="host",
        exit_code=0,
        stdout="ok",
    )


# =============================================================================
# DRY_RUN 路径
# =============================================================================


class TestDryRun:
    """DRY_RUN 模式测试——不改系统，overall="generated_only"。"""

    @mock.patch.object(LightShieldCore, "run_vuln_scan")
    @mock.patch("lightshield.rules.engine.RuleEngine.load_rules")
    @mock.patch("lightshield.rules.engine.RuleEngine.recommend_hardening")
    @mock.patch.object(LightShieldCore, "generate_hardening")
    @mock.patch("lightshield.sandbox.docker_executor.DockerSandboxExecutor.is_available")
    @mock.patch("lightshield.sandbox.docker_executor.DockerSandboxExecutor.execute")
    def test_dry_run_complete(
        self,
        mock_docker_exec,
        mock_docker_avail,
        mock_gen,
        mock_recommend,
        mock_load,
        mock_scan,
    ):
        """DRY_RUN 完整流程 → overall="generated_only"。"""
        core = LightShieldCore()

        # Mock ① 扫描
        mock_scan.return_value = _scan_result(
            "127.0.0.1",
            [
                _finding("high_risk_port", 22),
            ],
        )
        # Mock ② 规则推荐
        mock_load.return_value = None
        mock_recommend.return_value = [{"action": "block_port", "target": "22"}]
        # Mock ③ 脚本生成
        mock_gen.return_value = _harden_result()
        # Mock ④ Docker 可用 + 执行成功
        mock_docker_avail.return_value = True
        mock_docker_exec.return_value = _exec_result_success()

        result = core.run_harden_closed_loop(
            target="127.0.0.1",
            os_platform=OSPlatform.LINUX,
            mode="dry_run",
        )

        assert isinstance(result, ClosedLoopResult)
        assert result.mode == "dry_run"
        assert result.overall == "generated_only"
        assert result.before_scan["status"] == "completed"
        assert result.harden["action_count"] == 2
        assert result.execution is not None
        assert result.execution["status"] == "success"
        # DRY_RUN 不复扫、不验证
        assert result.after_scan is None
        assert result.verification is None

    @mock.patch.object(LightShieldCore, "run_vuln_scan")
    @mock.patch("lightshield.rules.engine.RuleEngine.load_rules")
    @mock.patch("lightshield.rules.engine.RuleEngine.recommend_hardening")
    @mock.patch.object(LightShieldCore, "generate_hardening")
    def test_dry_run_no_recommendations(
        self,
        mock_gen,
        mock_recommend,
        mock_load,
        mock_scan,
    ):
        """无加固建议 → 闭环终止，overall="failed"（有 finding）或 "verified"（无 finding）。"""
        core = LightShieldCore()
        mock_scan.return_value = _scan_result("127.0.0.1", [_finding("sqli")])
        mock_load.return_value = None
        mock_recommend.return_value = []  # 无加固建议
        mock_gen.return_value = _harden_result(status=HardenStatus.NO_ACTION)

        result = core.run_harden_closed_loop(
            target="127.0.0.1",
            os_platform=OSPlatform.LINUX,
            mode="dry_run",
        )

        assert result.overall == "failed"  # 有 finding 但无加固建议
        assert result.harden["action_count"] == 0

    @mock.patch.object(LightShieldCore, "run_vuln_scan")
    @mock.patch("lightshield.rules.engine.RuleEngine.load_rules")
    @mock.patch("lightshield.rules.engine.RuleEngine.recommend_hardening")
    @mock.patch.object(LightShieldCore, "generate_hardening")
    def test_dry_run_r1_keyword_rejected(
        self,
        mock_gen,
        mock_recommend,
        mock_load,
        mock_scan,
    ):
        """加固脚本含 R1 攻击关键字 → DRY_RUN 拒绝。"""
        core = LightShieldCore()
        mock_scan.return_value = _scan_result("127.0.0.1", [_finding("high_risk_port", 22)])
        mock_load.return_value = None
        mock_recommend.return_value = [{"action": "block_port", "target": "22"}]

        # 生成含 exploit 关键字的脚本
        with tempfile.NamedTemporaryFile("w", suffix=".sh", delete=False, encoding="utf-8") as tf:
            tf.write("#!/bin/bash\n# exploit target\niptables -A INPUT -p tcp --dport 22 -j DROP\n")
            evil_script = tf.name

        mock_gen.return_value = _harden_result(script_path=evil_script)

        try:
            result = core.run_harden_closed_loop(
                target="127.0.0.1",
                os_platform=OSPlatform.LINUX,
                mode="dry_run",
            )

            assert result.overall == "failed"
            assert result.execution is not None
            assert result.execution["status"] == "rejected"
            assert "R1" in result.execution["error"]
        finally:
            os.remove(evil_script)


# =============================================================================
# APPLY 路径——闸门测试
# =============================================================================


class TestApplyGates:
    """APPLY 模式三重前置护栏测试。"""

    def test_apply_rejected_no_confirm_ownership(self):
        """APPLY 缺少 confirm_ownership → rejected（在护栏阶段被拦截）。"""
        core = LightShieldCore()
        with (
            mock.patch.object(core, "run_vuln_scan") as mock_scan,
            mock.patch("lightshield.rules.engine.RuleEngine.load_rules"),
            mock.patch("lightshield.rules.engine.RuleEngine.recommend_hardening") as m_rec,
            mock.patch.object(core, "generate_hardening") as m_gen,
        ):
            mock_scan.return_value = _scan_result("127.0.0.1", [_finding("high_risk_port", 22)])
            m_rec.return_value = [{"action": "block_port", "target": "22"}]
            m_gen.return_value = _harden_result()

            result = core.run_harden_closed_loop(
                target="127.0.0.1",
                os_platform=OSPlatform.LINUX,
                mode="apply",
                confirm_ownership=False,
                confirm_execute=True,
            )

        assert result.overall == "failed"
        assert result.execution is not None
        assert result.execution["status"] == "rejected"
        assert "confirm_ownership" in result.execution["error"]

    def test_apply_rejected_no_confirm_execute(self):
        """APPLY 缺少 confirm_execute → rejected。"""
        core = LightShieldCore()
        with (
            mock.patch.object(core, "run_vuln_scan") as mock_scan,
            mock.patch("lightshield.rules.engine.RuleEngine.load_rules"),
            mock.patch("lightshield.rules.engine.RuleEngine.recommend_hardening") as m_rec,
            mock.patch.object(core, "generate_hardening") as m_gen,
        ):
            mock_scan.return_value = _scan_result("127.0.0.1", [_finding("high_risk_port", 22)])
            m_rec.return_value = [{"action": "block_port", "target": "22"}]
            m_gen.return_value = _harden_result()

            result = core.run_harden_closed_loop(
                target="127.0.0.1",
                os_platform=OSPlatform.LINUX,
                mode="apply",
                confirm_ownership=True,
                confirm_execute=False,
            )

        assert result.overall == "failed"
        assert result.execution is not None
        assert result.execution["status"] == "rejected"

    @mock.patch.object(LightShieldCore, "run_vuln_scan")
    @mock.patch("lightshield.rules.engine.RuleEngine.load_rules")
    @mock.patch("lightshield.rules.engine.RuleEngine.recommend_hardening")
    @mock.patch.object(LightShieldCore, "generate_hardening")
    def test_apply_rejected_no_rollback(
        self,
        mock_gen,
        mock_recommend,
        mock_load,
        mock_scan,
    ):
        """APPLY 缺少回滚脚本 → rejected。"""
        core = LightShieldCore()
        mock_scan.return_value = _scan_result("127.0.0.1", [_finding("high_risk_port", 22)])
        mock_load.return_value = None
        mock_recommend.return_value = [{"action": "block_port", "target": "22"}]
        # 回滚路径设为 None
        mock_gen.return_value = _harden_result(rollback_path=None)

        result = core.run_harden_closed_loop(
            target="127.0.0.1",
            os_platform=OSPlatform.LINUX,
            mode="apply",
            confirm_ownership=True,
            confirm_execute=True,
        )

        assert result.overall == "failed"
        assert result.execution["status"] == "rejected"
        assert "回滚" in result.execution["error"]


# =============================================================================
# APPLY 路径——完整闭环
# =============================================================================


class TestApplyFullLoop:
    """APPLY 完整 ①-⑦ 闭环 mock 测试。"""

    @mock.patch.object(LightShieldCore, "run_vuln_scan")
    @mock.patch("lightshield.rules.engine.RuleEngine.load_rules")
    @mock.patch("lightshield.rules.engine.RuleEngine.recommend_hardening")
    @mock.patch.object(LightShieldCore, "generate_hardening")
    @mock.patch("lightshield.sandbox.host_executor.HostExecutor._run_script")
    def test_apply_verified(
        self,
        mock_run_script,
        mock_gen,
        mock_recommend,
        mock_load,
        mock_scan,
    ):
        """APPLY 加固成功 → overall="verified"。"""
        core = LightShieldCore()

        # Mock ① 基线扫描：发现端口 22 风险
        before_finding = _finding("high_risk_port", 22)
        # Mock ⑤ 复扫：风险消除（空列表）
        mock_scan.side_effect = [
            _scan_result("127.0.0.1", [before_finding]),  # before
            _scan_result("127.0.0.1", []),  # after
        ]
        mock_load.return_value = None
        mock_recommend.return_value = [{"action": "block_port", "target": "22"}]

        # 生成加固脚本（含回滚路径）
        with tempfile.NamedTemporaryFile("w", suffix=".sh", delete=False, encoding="utf-8") as tf:
            tf.write("#!/bin/bash\niptables -A INPUT -p tcp --dport 22 -j DROP\n")
            script = tf.name
        with tempfile.NamedTemporaryFile("w", suffix=".sh", delete=False, encoding="utf-8") as tf2:
            tf2.write("#!/bin/bash\niptables -D INPUT -p tcp --dport 22 -j DROP\n")
            rollback = tf2.name

        mock_gen.return_value = _harden_result(script_path=script, rollback_path=rollback)

        # Mock ④ HostExecutor 执行成功
        mock_run_script.return_value = _exec_result_success()

        try:
            result = core.run_harden_closed_loop(
                target="127.0.0.1",
                os_platform=OSPlatform.LINUX,
                mode="apply",
                confirm_ownership=True,
                confirm_execute=True,
            )

            assert result.mode == "apply"
            assert result.overall == "verified", f"应 verified，实得 {result.overall}"
            assert result.execution["status"] == "success"
            assert result.verification is not None
            assert result.verification["verdict"] == "verified"
            assert len(result.verification["resolved"]) == 1
            assert result.verification["resolved"][0]["port"] == 22
        finally:
            os.remove(script)
            os.remove(rollback)

    @mock.patch.object(LightShieldCore, "run_vuln_scan")
    @mock.patch("lightshield.rules.engine.RuleEngine.load_rules")
    @mock.patch("lightshield.rules.engine.RuleEngine.recommend_hardening")
    @mock.patch.object(LightShieldCore, "generate_hardening")
    @mock.patch("lightshield.sandbox.host_executor.HostExecutor._run_script")
    def test_apply_partial(
        self,
        mock_run_script,
        mock_gen,
        mock_recommend,
        mock_load,
        mock_scan,
    ):
        """APPLY 部分修复 → overall="partial"。"""
        core = LightShieldCore()

        before = [_finding("high_risk_port", 22), _finding("high_risk_port", 3306)]
        after = [_finding("high_risk_port", 3306)]  # 22 修了，3306 还在

        mock_scan.side_effect = [
            _scan_result("127.0.0.1", before),
            _scan_result("127.0.0.1", after),
        ]
        mock_load.return_value = None
        mock_recommend.return_value = [{"action": "block_port", "target": "22"}]

        with tempfile.NamedTemporaryFile("w", suffix=".sh", delete=False) as tf:
            tf.write("#!/bin/bash\niptables -A INPUT -p tcp --dport 22 -j DROP\n")
            script = tf.name
        with tempfile.NamedTemporaryFile("w", suffix=".sh", delete=False) as tf2:
            tf2.write("#!/bin/bash\niptables -D INPUT -p tcp --dport 22 -j DROP\n")
            rollback = tf2.name

        mock_gen.return_value = _harden_result(script_path=script, rollback_path=rollback)
        mock_run_script.return_value = _exec_result_success()

        try:
            result = core.run_harden_closed_loop(
                target="127.0.0.1",
                os_platform=OSPlatform.LINUX,
                mode="apply",
                confirm_ownership=True,
                confirm_execute=True,
            )

            assert result.overall == "partial"
            assert len(result.verification["resolved"]) == 1
            assert len(result.verification["remaining"]) == 1
        finally:
            os.remove(script)
            os.remove(rollback)


# =============================================================================
# 异常处理
# =============================================================================


class TestExceptionHandling:
    """异常一律转 ClosedLoopResult，不向上抛。"""

    def test_scan_exception_converted(self):
        """基线扫描异常 → ClosedLoopResult（不抛异常）。"""
        core = LightShieldCore()
        with mock.patch.object(core, "run_vuln_scan", side_effect=RuntimeError("网络不可达")):
            result = core.run_harden_closed_loop(
                target="127.0.0.1",
                os_platform=OSPlatform.LINUX,
                mode="dry_run",
            )

            assert isinstance(result, ClosedLoopResult)
            assert result.overall == "failed"
            assert "网络不可达" in result.before_scan.get("error", "")

    @mock.patch.object(LightShieldCore, "run_vuln_scan")
    @mock.patch("lightshield.rules.engine.RuleEngine.load_rules")
    def test_recommendation_exception_converted(self, mock_load, mock_scan):
        """规则推荐异常 → ClosedLoopResult。"""
        core = LightShieldCore()
        mock_scan.return_value = _scan_result("127.0.0.1", [_finding("sqli")])
        mock_load.return_value = None
        with mock.patch(
            "lightshield.rules.engine.RuleEngine.recommend_hardening",
            side_effect=RuntimeError("规则引擎崩溃"),
        ):
            result = core.run_harden_closed_loop(
                target="127.0.0.1",
                os_platform=OSPlatform.LINUX,
                mode="dry_run",
            )

            assert isinstance(result, ClosedLoopResult)
            assert result.overall == "failed"
            assert "规则引擎崩溃" in result.harden.get("error", "")
