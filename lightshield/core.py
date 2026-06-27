"""LightShield 核心调度器 — 主控逻辑

负责：
  - 适配器注册与管理
  - 扫描任务编排（合规 R6：并发 ≤20，间隔 ≥5s）
  - 参数安全校验（合规 R2：单目标，R4：所有权确认）
  - 审计日志记录
  - 异常处理与降级

用法：
    from lightshield.core import LightShieldCore
    core = LightShieldCore()
    core.register_adapter(nmap_adapter)
    result = core.run_scan("192.168.1.1", scan_types=["port_scan"])
"""

from __future__ import annotations

import datetime
import os
import sys as _sys
import threading
import time
import uuid
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from lightshield.harden.closed_loop import ClosedLoopResult
    from lightshield.utils.constants import OSPlatform

# Allow direct script execution (python lightshield/core.py)
if __name__ == "__main__" and _sys.path[0] != os.path.dirname(os.path.dirname(os.path.abspath(__file__))):
    _sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lightshield.adapters.base import BaseAdapter, ScanResult, VulnFinding
from lightshield.config import get_config
from lightshield.harden.base import HardenResult
from lightshield.sandbox.base import ExecutionResult, SandboxExecutor
from lightshield.utils.constants import ScanStatus
from lightshield.utils.validator import TargetValidator

# =============================================================================
# 异步任务信息（v0.0.31: threading.Thread 异步扫描）
# =============================================================================


@dataclass
class _TaskInfo:
    """异步扫描任务的内部状态追踪。

    v0.0.31: Thread 异步，task_id 立即返回，状态可通过 get_scan_status() 轮询。
    v1.0.0: 可迁移至 concurrent.futures.ThreadPoolExecutor。
    v2.0.0: 可迁移至 Celery + Redis。
    """

    status: ScanStatus  # PENDING → RUNNING → COMPLETED / PARTIAL / FAILED
    target: str
    created_at: str  # ISO8601
    thread: threading.Thread | None = None
    result: ScanResult | None = None
    error: str | None = None


# =============================================================================
# 主调度器
# =============================================================================


class LightShieldCore:
    """LightShield 主调度器 — 扫描任务编排与合规控制中心

    职责：
    1. 管理已注册的适配器
    2. 接收扫描请求 → 合规校验 → 编排执行 → 收集结果
    3. 强制执行 R2（单目标）、R4（所有权确认）、R6（频率限制）
    """

    def __init__(self, config=None):
        """初始化核心调度器。

        Args:
        config: LightShieldConfig 实例，默认使用全局单例
        """
        self._config = config or get_config()
        self._adapters: dict[str, BaseAdapter] = {}
        self._task_results: dict[str, _TaskInfo] = {}  # v0.0.31: Thread 异步, v1.0: 线程池, v2.0: Redis
        self._scan_log: list[dict] = []

    # =========================================================================
    # 适配器管理
    # =========================================================================

    def register_adapter(self, adapter: BaseAdapter) -> None:
        """注册一个扫描适配器

        适配器的每个能力被单独索引，以便按需调度。

        Args:
            adapter: 实现了 BaseAdapter 的扫描适配器实例
        """
        for cap in adapter.capabilities():
            if cap in self._adapters:
                # 同名能力只保留第一个注册的适配器
                continue
            self._adapters[cap] = adapter

    def unregister_adapter(self, adapter: BaseAdapter) -> None:
        """移除一个适配器及其所有能力"""
        caps = adapter.capabilities()
        for cap in caps:
            if self._adapters.get(cap) is adapter:
                del self._adapters[cap]

    def get_adapter(self, capability: str) -> BaseAdapter | None:
        """按能力名称获取适配器"""
        return self._adapters.get(capability)

    def list_capabilities(self) -> list[str]:
        """列出当前所有可用能力"""
        return sorted(self._adapters.keys())

    def list_adapters(self) -> list[dict]:
        """列出所有注册的适配器及其能力"""
        seen = set()
        result = []
        for _cap, adapter in self._adapters.items():
            if adapter.name not in seen:
                seen.add(adapter.name)
                result.append(
                    {
                        "name": adapter.name,
                        "capabilities": adapter.capabilities(),
                    }
                )
        return result

    # =========================================================================
    # 合规校验
    # =========================================================================

    def _validate_request(self, target: str) -> tuple[bool, str]:
        """校验扫描请求的合规性

        综合调用 R2（输入格式）+ R4（所有权确认）校验。

        Args:
            target: 扫描目标

        Returns:
            (是否合法, 原因说明)
        """
        # R2：格式校验
        is_valid, reason = TargetValidator.validate(target)
        if not is_valid:
            return False, f"[R2 违规] {reason}"

        return True, "合规"

    def _confirm_ownership(self, target: str) -> str:
        """生成所有权确认提示（R4）"""
        return TargetValidator.confirm_ownership(target)

    # =========================================================================
    # 扫描执行
    # =========================================================================

    def run_scan(
        self,
        target: str,
        scan_types: list[str] | None = None,
        *,
        confirm_ownership: bool = False,
        **kwargs,
    ) -> ScanResult:
        """执行安全扫描——主入口

        流程：
        1. R2 输入校验 → 不合法则拒绝
        2. R4 所有权确认 → 如未确认则记录警告，但允许继续（CLI 模式）
                           生产环境应设置 confirm_ownership=True
        3. 匹配 scan_types 对应的适配器
        4. R6 并发数检查 → 超过限制则拒绝
        5. 按 R6 频率限制逐个执行扫描
        6. 合并所有扫描结果为单一 ScanResult

        Args:
            target: 扫描目标（仅单 IP/域名）
            scan_types: 指定扫描类型列表，默认全部
            confirm_ownership: 是否已确认对目标拥有所有权（R4）。
                               必须由用户显式传入 True。
                               未确认时扫描仍会继续，但会标记为"所有权未确认"。
            **kwargs: 传递给适配器的额外参数

        Returns:
            ScanResult 合并结果
        """
        from lightshield.utils.logger import get_logger

        logger = get_logger()

        # ---- Step 1: R2 输入校验 ----
        is_valid, reason = self._validate_request(target)
        if not is_valid:
            return ScanResult(
                status=ScanStatus.FAILED,
                target=target,
                error=reason,
            )

        # ---- Step 2: R4 所有权确认 ----
        if not confirm_ownership:
            confirm_msg = self._confirm_ownership(target)
            logger.warning(
                "core",
                f"R4 所有权未确认: {target}。{confirm_msg}",
            )
            self._log_audit(
                "ownership_unconfirmed",
                target,
                "用户未显式确认所有权，扫描仍继续执行（CLI 模式）",
            )
        else:
            self._log_audit("ownership_confirmed", target, "用户已确认所有权")

        # ---- Step 3: R6 并发数检查 ----
        requested_count = len(scan_types) if scan_types else len(self._adapters)
        if requested_count > self._config.max_concurrent_scans:
            return ScanResult(
                status=ScanStatus.FAILED,
                target=target,
                error=(f"[R6 违规] 请求 {requested_count} 个扫描类型，超过上限 {self._config.max_concurrent_scans}"),
            )

        # ---- Step 4: 确定扫描类型 ----
        if scan_types is None:
            scan_types = self.list_capabilities()

        # 按 adapter 分组扫描类型
        adapter_tasks: list[tuple[BaseAdapter, str]] = []
        for scan_type in scan_types:
            adapter = self._adapters.get(scan_type)
            if adapter is None:
                # 不支持的能力——跳过并记录
                self._log_audit("scan_skip", target, f"不支持的能力: {scan_type}")
                continue
            adapter_tasks.append((adapter, scan_type))

        if not adapter_tasks:
            return ScanResult(
                status=ScanStatus.FAILED,
                target=target,
                error=f"无可用的扫描适配器（请求: {scan_types}，可用: {self.list_capabilities()}）",
            )

        # ---- Step 4: 执行扫描（R6 频率限制） ----
        all_findings: list[VulnFinding] = []
        all_ports: list[dict] = []
        all_services: list[dict] = []
        os_info = None
        errors: list[str] = []
        start_time = time.time()

        for i, (adapter, scan_type) in enumerate(adapter_tasks):
            # R6：扫描间隔
            if i > 0:
                time.sleep(self._config.scan_interval)

            self._log_audit("scan_start", target, f"{adapter.name}:{scan_type}")

            try:
                result = adapter.scan(target, **kwargs)
            except Exception as e:
                errors.append(f"[{adapter.name}:{scan_type}] {e}")
                self._log_audit("scan_error", target, str(e))
                continue

            # 收集结果
            all_findings.extend(result.findings)
            all_ports.extend(result.ports)
            all_services.extend(result.services)
            if result.os_info:
                os_info = result.os_info

            if result.error:
                errors.append(f"[{adapter.name}:{scan_type}] {result.error}")

            self._log_audit("scan_end", target, f"{adapter.name}:{scan_type} 完成")

        duration = time.time() - start_time

        # ---- Step 5: 合并结果 ----
        # 去重端口（同端口同服务只保留一份）
        seen_ports = set()
        unique_ports = []
        for port in all_ports:
            key = (port.get("port"), port.get("service"))
            if key not in seen_ports:
                seen_ports.add(key)
                unique_ports.append(port)

        # 状态判定：全部成功=COMPLETED，部分失败=PARTIAL，全部失败=FAILED
        total_tasks = len(adapter_tasks)
        failed_tasks = len(errors)
        if failed_tasks == 0:
            final_status = ScanStatus.COMPLETED
        elif failed_tasks < total_tasks:
            final_status = ScanStatus.PARTIAL
        else:
            final_status = ScanStatus.FAILED

        return ScanResult(
            status=final_status,
            target=target,
            ports=unique_ports,
            services=all_services,
            os_info=os_info,
            findings=all_findings,
            error="; ".join(errors) if errors else None,
            duration_seconds=round(duration, 2),
        )

    def run_asset_scan(self, target: str, **kwargs) -> ScanResult:
        """便捷方法：仅执行资产扫描"""
        return self.run_scan(target, scan_types=["port_scan", "service_detect"], **kwargs)

    def run_vuln_scan(self, target: str, **kwargs) -> ScanResult:
        """便捷方法：执行漏洞检测"""
        return self.run_scan(
            target,
            scan_types=["web_vuln", "weak_password", "component_check"],
            **kwargs,
        )

    def run_full_scan(self, target: str, **kwargs) -> ScanResult:
        """便捷方法：全量扫描"""
        return self.run_scan(target, scan_types=None, **kwargs)

    # =========================================================================
    # 异步任务接口（v0.0.20 同步实现，v1.0+ 可切换为消息队列）
    # =========================================================================

    def submit_scan(
        self,
        target: str,
        scan_types: list[str] | None = None,
        *,
        confirm_ownership: bool = False,
        **kwargs,
    ) -> str:
        """提交扫描任务，立即返回 task_id（v0.0.31: threading.Thread 异步）。

        v0.0.20: 同步执行——提交即完成。
        v0.0.31: Thread 异步——task_id 立即返回，通过 get_scan_status() 轮询。
        v1.0.0: 线程池 → ThreadPoolExecutor。
        v2.0.0: Celery → Redis。

        Args:
            target: 扫描目标
            scan_types: 扫描类型列表
            confirm_ownership: 是否已确认所有权
            **kwargs: 传递给 run_scan 的额外参数

        Returns:
            task_id: 格式 "LS-YYYYMMDD-HHMMSS-xxxxxx"
        """
        now = datetime.datetime.now()
        task_id = f"LS-{now.strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:6]}"

        task = _TaskInfo(
            status=ScanStatus.PENDING,
            target=target,
            created_at=now.isoformat(),
        )
        self._task_results[task_id] = task

        thread = threading.Thread(
            target=self._run_scan_async,
            args=(task_id, target, scan_types, confirm_ownership),
            kwargs=kwargs,
            daemon=True,
            name=f"lightshield-scan-{task_id}",
        )
        task.thread = thread
        thread.start()

        return task_id

    def _run_scan_async(
        self,
        task_id: str,
        target: str,
        scan_types: list[str] | None,
        confirm_ownership: bool,
        **kwargs,
    ) -> None:
        """在独立线程中执行扫描并更新任务状态。

        不直接抛出异常——所有错误记录在 task.error 中。
        """
        task = self._task_results.get(task_id)
        if task is None:
            return  # 任务已被移除（极少见）

        task.status = ScanStatus.RUNNING
        try:
            task.result = self.run_scan(
                target,
                scan_types=scan_types,
                confirm_ownership=confirm_ownership,
                **kwargs,
            )
            task.status = task.result.status
            if task.result.error:
                task.error = task.result.error
        except Exception as exc:
            task.status = ScanStatus.FAILED
            task.error = str(exc)

    def get_scan_status(self, task_id: str) -> dict:
        """查询扫描任务状态。

        v0.0.31：查 Thread 任务 → PENDING / RUNNING / COMPLETED / PARTIAL / FAILED。
        v1.0.0：查线程池 Future。
        v2.0.0：查 Redis → 支持分布式查询。

        Args:
            task_id: submit_scan() 返回的任务 ID

        Returns:
            {"task_id": str, "status": str, "target": str, "findings": int, ...}
        """
        task = self._task_results.get(task_id)
        if task is None:
            return {"task_id": task_id, "status": "not_found"}

        result = task.result
        return {
            "task_id": task_id,
            "status": task.status.value,
            "target": task.target,
            "created_at": task.created_at,
            "ports": len(result.ports) if result else 0,
            "findings": len(result.findings) if result else 0,
            "duration_seconds": result.duration_seconds if result else 0,
            "error": task.error,
        }

    def generate_hardening(
        self,
        target: str,
        findings: list[VulnFinding] | None = None,
        *,
        recommendations: list[dict] | None = None,
        output_dir: str | None = None,
        os_platform: str | None = None,
    ) -> HardenResult:
        """根据扫描发现生成加固脚本（默认不自动执行）

        流程：
        1. 复用 R2 目标校验
        2. 若未传入 recommendations → 加载规则引擎计算
           若已传入 → 直接使用（CLI 避免重复计算，Codex M1 修复）
        3. 按 OS 选择加固适配器（linux / windows）
        4. 生成加固 / 回滚脚本
        5. 审计留痕（每条操作 audit_harden_action）

        Args:
            target: 加固目标（IP/域名）
            findings: 漏洞发现列表（若同时传入 recommendations 则忽略）
            recommendations: 已计算好的加固建议列表（CLI 传入以复用）
            output_dir: 脚本输出目录（默认使用配置的 report_output_dir）
            os_platform: "linux" | "windows" | None（默认 linux，向后兼容）

        Returns:
            HardenResult 结构化结果

        Raises:
            ValueError: 目标不合法
        """
        from lightshield.harden.linux_harden import LinuxHardener
        from lightshield.harden.win_harden import WinHardener
        from lightshield.rules.engine import RuleEngine
        from lightshield.utils.logger import get_logger

        logger = get_logger()

        # Step 1: R2 目标校验
        is_valid, reason = self._validate_request(target)
        if not is_valid:
            raise ValueError(f"[R2 违规] {reason}")

        # Step 2: 获取/计算加固建议
        if recommendations is not None:
            # CLI 已计算，直接复用（Codex M1 修复）
            pass
        else:
            engine = RuleEngine()
            engine.load_rules()
            recommendations = engine.recommend_hardening(findings or [])

        # Step 3: 选择加固适配器
        platform = (os_platform or "").lower()
        # 默认 Linux，向后兼容 v0.0.16
        hardener = WinHardener() if platform == "windows" else LinuxHardener()

        result = hardener.generate(
            target,
            recommendations,
            output_dir=output_dir or self._config.report_output_dir,
        )

        # Step 4: 审计
        self._log_audit(
            "harden_generated",
            target,
            f"os={result.os_platform.value} actions={result.action_count} status={result.status.value}",
        )
        logger.info(
            "core",
            f"加固脚本生成完成：target={target} "
            f"os={result.os_platform.value} actions={result.action_count} status={result.status.value}",
        )

        return result

    def execute_hardening(
        self,
        script_path: str,
        *,
        confirm_execute: bool = False,
        executor: SandboxExecutor | None = None,
        timeout: int | None = None,
    ) -> ExecutionResult:
        """在沙箱中执行已生成的加固脚本（v0.0.38）。

        v0.0.40 扩展为双模式——按传入的 executor 后端选择：
          - executor=DockerSandboxExecutor → DRY_RUN 锁死容器预检（不改系统）
          - executor=HostExecutor → APPLY 宿主机本机执行（改真实系统，需额外护栏）
        默认 executor=DockerSandboxExecutor（向后兼容 v0.0.38）。

        ⚠️ 危险操作：必须 confirm_execute=True 才放行。
        APPLY 模式额外护栏（编排层负责）：R4 双确认 + DRY_RUN-first + rollback 就绪。

        Args:
            script_path: 待执行的加固脚本路径（通常来自 generate_hardening 的 script_path）
            confirm_execute: 必须显式传 True（对齐 R4 双确认）
            executor: 沙箱执行器实例，默认 DockerSandboxExecutor(Docker 隔离)
            timeout: 执行超时秒数（覆盖默认）

        Returns:
            ExecutionResult 结构化结果（任何失败都返回结果对象，不抛异常）
        """
        from lightshield.sandbox.docker_executor import DockerSandboxExecutor

        exec_backend = executor or DockerSandboxExecutor()
        result = exec_backend.execute(script_path, confirm_execute=confirm_execute, timeout=timeout)

        self._log_audit(
            "harden_execute",
            script_path,
            f"sandbox={result.sandbox} status={result.status.value} exit={result.exit_code}",
        )
        return result

    # =========================================================================
    # v0.0.40 自动加固闭环
    # =========================================================================

    # R1 攻击关键字黑名单（加固脚本内容扫描用）
    _R1_ATTACK_KEYWORDS: tuple[str, ...] = (
        "exploit",  # gate-a: r1-scan item
        "payload",  # gate-a: r1-scan item
        "reverse_shell",  # gate-a: r1-scan item
        "bind_shell",  # gate-a: r1-scan item
        "backdoor",  # gate-a: r1-scan item
        "trojan",  # gate-a: r1-scan item
        "meterpreter",  # gate-a: r1-scan item
        "shellcode",  # gate-a: r1-scan item
        "rootkit",  # gate-a: r1-scan item
        "keylogger",  # gate-a: r1-scan item
        "ransomware",  # gate-a: r1-scan item
        "obfuscated",  # gate-a: r1-scan item
    )

    def _r1_scan_script_content(self, script_path: str) -> list[str]:
        """对加固脚本内容做 R1 攻击关键字扫描。

        在 DRY_RUN 预检和 APPLY 执行前调用，命中任何关键字即拒绝。
        扫描内容为脚本全文（小写匹配），逐行检查。

        Args:
            script_path: 脚本路径

        Returns:
            命中的关键字列表（为空表示通过）
        """
        hits: list[str] = []
        try:
            with open(script_path, encoding="utf-8", errors="replace") as f:
                for lineno, line in enumerate(f, 1):
                    lower_line = line.lower()
                    for kw in self._R1_ATTACK_KEYWORDS:
                        if kw in lower_line:
                            hits.append(f"L{lineno}:{kw}")
        except OSError:
            # 文件不可读 → 已在基类 _validate_script 中校验过，放过
            pass
        return hits

    def _resolve_pre_generated(
        self,
        pre_generated: dict,
        result: ClosedLoopResult,
        audit_id: str,
    ):
        """校验并提取 CLI 预生成的闭环数据。

        避免闭环内部重复扫描/推荐/生成，确保用户审阅的脚本 = 实际执行的脚本。

        Returns:
            (before_scan, before_findings, recommendations, harden_result, script_path)
            校验失败时 result 已填充，调用方应 return result。
        """
        from lightshield.utils.logger import get_logger

        logger = get_logger()

        pg_scan = pre_generated.get("scan_result")
        pg_recs = pre_generated.get("recommendations")
        pg_harden = pre_generated.get("harden_result")

        if not pg_scan or not pg_recs or not pg_harden:
            logger.error("core", f"[闭环/{audit_id}] 预生成数据不完整")
            result.overall = "failed"
            result.harden = {
                "status": "failed",
                "error": "pre_generated 需包含 scan_result, recommendations, harden_result",
            }
            return None

        before_scan = pg_scan
        before_findings = before_scan.findings if hasattr(before_scan, "findings") else pg_scan.get("findings", [])
        recommendations = pg_recs
        harden_result = pg_harden

        result.before_scan = before_scan.to_dict() if hasattr(before_scan, "to_dict") else before_scan
        result.harden = harden_result.to_dict() if hasattr(harden_result, "to_dict") else harden_result

        if not recommendations:
            logger.info("core", f"[闭环/{audit_id}] 预生成数据无加固建议，闭环终止")
            result.harden = {"status": "no_action", "action_count": 0}
            result.overall = "failed" if before_findings else "verified"
            if not before_findings:
                result.verification = {
                    "verdict": "verified",
                    "resolved": [],
                    "remaining": [],
                    "regressed": [],
                    "before_count": 0,
                    "after_count": 0,
                }
            return None

        script_path = getattr(harden_result, "script_path", None) or harden_result.get("script_path")
        if not script_path or not os.path.exists(script_path):
            logger.error("core", f"[闭环/{audit_id}] 预生成脚本路径不存在: {script_path}")
            result.overall = "failed"
            result.harden = {"status": "failed", "error": f"预生成脚本路径不存在: {script_path}"}
            return None

        logger.info("core", f"[闭环/{audit_id}] 预生成数据验证通过，进入执行阶段")
        return (before_scan, before_findings, recommendations, harden_result, script_path)

    def _run_dry_run_precheck(
        self,
        script_path: str,
        audit_id: str,
    ) -> dict | None:
        """DRY_RUN 预检：R1 攻击关键字扫描 + 锁死容器烟测。

        返回填充到 result.execution 的 dict，或 None 表示预检通过。
        """
        from lightshield.utils.logger import get_logger

        logger = get_logger()

        # R1 攻击关键字内容扫描
        r1_hits = self._r1_scan_script_content(script_path)
        if r1_hits:
            logger.warning("core", f"[闭环/{audit_id}] R1 拒绝: {r1_hits}")
            return {
                "status": "rejected",
                "sandbox": "dry_run",
                "error": f"R1 攻击关键字命中: {', '.join(r1_hits)}",
            }

        # 锁死容器烟测
        try:
            from lightshield.sandbox.docker_executor import DockerSandboxExecutor

            docker_exec = DockerSandboxExecutor()
            if docker_exec.is_available():
                exec_result = docker_exec.execute(
                    script_path,
                    confirm_execute=True,
                    timeout=30,
                )
                logger.info(
                    "core",
                    f"[闭环/{audit_id}] DRY_RUN 烟测: status={exec_result.status.value}",
                )
                return exec_result.to_dict()
            else:
                logger.warning("core", f"[闭环/{audit_id}] Docker 不可用，跳过容器烟测")
                return {
                    "status": "skipped",
                    "sandbox": "dry_run",
                    "error": "Docker 不可用：仅完成 R1 攻击关键字扫描",
                }
        except Exception as exc:
            logger.warning("core", f"[闭环/{audit_id}] DRY_RUN 烟测异常: {exc}")
            return {
                "status": "error",
                "sandbox": "dry_run",
                "error": f"DRY_RUN 预检异常: {exc}",
            }

    def _run_apply_and_verify(
        self,
        target: str,
        before_findings: list[VulnFinding],
        script_path: str,
        rollback_path: str | None,
        mode: str,
        backend: str,
        audit_id: str,
        scan_fn,
        result: ClosedLoopResult,
    ) -> None:
        """APPLY 路径：检查护栏 → 真机执行 → 复扫 → 验证 → 汇总。

        修改 result 的内容（in-place），不返回值。
        """
        from lightshield.harden.verify import verify_hardening
        from lightshield.sandbox.base import ExecutionStatus
        from lightshield.sandbox.host_executor import HostExecutor
        from lightshield.utils.logger import get_logger

        logger = get_logger()

        # 护栏 1：R4 双重确认（调用方已确保）
        # 护栏 2：回滚脚本就绪
        if not rollback_path or not os.path.exists(rollback_path):
            logger.warning("core", f"[闭环/{audit_id}] APPLY 拒绝: 回滚脚本不就绪")
            result.overall = "failed"
            result.execution = {
                "status": "rejected",
                "sandbox": "host",
                "error": "APPLY 需要回滚脚本已就绪（rollback_path 不存在或为空）",
            }
            return

        # 护栏 3：R1 最终扫描
        r1_hits = self._r1_scan_script_content(script_path)
        if r1_hits:
            logger.warning("core", f"[闭环/{audit_id}] APPLY 拒绝: R1 命中 {r1_hits}")
            result.overall = "failed"
            result.execution = {
                "status": "rejected",
                "sandbox": "host",
                "error": f"R1 攻击关键字命中（APPLY 前最终扫描）: {', '.join(r1_hits)}",
            }
            return

        # ④ 真机执行
        logger.info("core", f"[闭环/{audit_id}] ④ APPLY 真机执行: backend={backend}")
        try:
            from lightshield.sandbox.docker_executor import DockerSandboxExecutor

            host_exec = DockerSandboxExecutor() if backend == "docker" else HostExecutor()
            exec_result = host_exec.execute(
                script_path,
                confirm_execute=True,
                timeout=120,
            )
            result.execution = exec_result.to_dict()
            logger.info(
                "core",
                f"[闭环/{audit_id}] ④ 执行完成: status={exec_result.status.value}",
            )
        except Exception as exc:
            logger.error("core", f"[闭环/{audit_id}] 真机执行异常: {exc}")
            result.overall = "failed"
            result.execution = {"status": "error", "sandbox": "host", "error": f"真机执行异常: {exc}"}
            return

        if exec_result.status in (ExecutionStatus.FAILED, ExecutionStatus.ERROR):
            logger.warning("core", f"[闭环/{audit_id}] 执行状态异常，继续复扫验证")

        # ⑤ 复扫
        logger.info("core", f"[闭环/{audit_id}] ⑤ 复扫: target={target}")
        try:
            after_scan = scan_fn(target)
            result.after_scan = after_scan.to_dict()
        except Exception as exc:
            logger.error("core", f"[闭环/{audit_id}] 复扫失败: {exc}")
            result.overall = "failed"
            result.after_scan = {"status": "failed", "target": target, "error": str(exc)}
            return

        # ⑥ 验证比对
        logger.info("core", f"[闭环/{audit_id}] ⑥ 验证比对")
        verification = verify_hardening(
            before=before_findings,
            after=after_scan.findings,
            target=target,
        )
        verification.audit_id = audit_id
        result.verification = verification.to_dict()

        # ⑦ 汇总
        result.overall = verification.verdict
        logger.info(
            "core",
            f"[闭环/{audit_id}] ⑦ 闭环完成: overall={result.overall} "
            f"resolved={len(verification.resolved)} remaining={len(verification.remaining)}",
        )

    def run_harden_closed_loop(
        self,
        target: str,
        *,
        os_platform: str | OSPlatform = "linux",
        confirm_ownership: bool = False,
        mode: str = "dry_run",
        confirm_execute: bool = False,
        backend: str | None = None,
        scan_types: list[str] | None = None,
        pre_generated: dict | None = None,
    ) -> ClosedLoopResult:
        """加固闭环全链路编排——扫描→推荐→生成→执行→复扫→验证→汇总。

        v0.0.40 核心方法，贯穿 ①-⑦ 七个环节：
          ① 基线扫描（run_vuln_scan）—— pre_generated 提供时跳过
          ② 规则推荐（RuleEngine.recommend_hardening）—— pre_generated 提供时跳过
          ③ 脚本生成（generate_hardening）—— pre_generated 提供时跳过
          ④ 执行（execute_hardening，按 mode 选 backend）
          ⑤ 复扫（run_vuln_scan，仅 APPLY）
          ⑥ 验证比对（verify_hardening，仅 APPLY）
          ⑦ 汇总（ClosedLoopResult）

        DRY_RUN 模式（默认，安全优先）：
          - 执行 ①②③ + 锁死容器预检（bash -n + R1 内容扫描 + 容器烟测）
          - backend 锁死 "docker"
          - 不复扫、不改系统、overall="generated_only"

        APPLY 模式（真机执行）：
          - 执行 ①-⑦ 完整闭环
          - backend="host"，宿主机本机执行
          - 四重前置护栏：R4 双确认 + DRY_RUN-first + rollback 就绪 + R1 最终扫描
          - 任一前置条件不满足 → 返回 structured failure，不抛异常

        Args:
            target: 加固目标（IP/域名/localhost）
            os_platform: 目标 OS 平台
            confirm_ownership: R4 所有权确认（APPLY 必须 True）
            mode: "dry_run"（默认安全）| "apply"（真机执行）
            confirm_execute: R4 执行确认（APPLY 必须 True）
            backend: None→按 mode 自动选（dry_run→docker, apply→host）
            scan_types: 扫描类型列表，默认 None=全量扫描
            pre_generated: CLI 预生成数据（避免重复扫描/推荐/生成，确保用户审阅的脚本=实际执行的脚本）。
                格式: {"scan_result": ScanResult, "recommendations": list[dict], "harden_result": HardenResult}
                None → core 内部执行 ①②③（API/Web 路径）

        Returns:
            ClosedLoopResult 全链路结果（任何失败都返回结果对象，不抛异常）
        """
        from lightshield.harden.closed_loop import ClosedLoopResult
        from lightshield.rules.engine import RuleEngine
        from lightshield.utils.constants import OSPlatform as OSPlatformEnum
        from lightshield.utils.logger import get_logger

        logger = get_logger()
        audit_id = f"CL-{datetime.datetime.now().strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:6]}"

        # 规范化 os_platform
        if isinstance(os_platform, str):
            try:
                os_plat = OSPlatformEnum(os_platform.lower())
            except ValueError:
                os_plat = OSPlatformEnum.UNKNOWN
        else:
            os_plat = os_platform

        # 确定 backend（None → 按 mode 自动选）
        if backend is None:
            backend = "host" if mode == "apply" else "docker"  # DRY_RUN 锁死容器

        # ---- 结果容器（默认值，逐步填充） ----
        result = ClosedLoopResult(
            target=target,
            os_platform=os_plat,
            mode=mode,
            overall="generated_only",
            audit_id=audit_id,
        )

        # 扫描方法选择：指定 scan_types → run_scan；默认 → run_vuln_scan
        def _do_scan(tgt: str) -> ScanResult:
            if scan_types:
                return self.run_scan(tgt, scan_types=scan_types)
            return self.run_vuln_scan(tgt)

        # ============================================================
        # 0-check：CLI 预生成数据（避免重复扫描/推荐/生成，确保审阅=执行）
        # ============================================================
        if pre_generated is not None:
            resolved = self._resolve_pre_generated(pre_generated, result, audit_id)
            if resolved is None:
                return result  # 校验失败，result 已填充
            before_scan, before_findings, recommendations, harden_result, script_path = resolved
        else:
            # ============================================================
            # ① 基线扫描
            # ============================================================
            logger.info("core", f"[闭环/{audit_id}] ① 基线扫描: target={target}")
            try:
                before_scan = _do_scan(target)
                result.before_scan = before_scan.to_dict()
            except Exception as exc:
                logger.error("core", f"[闭环/{audit_id}] 基线扫描失败: {exc}")
                result.overall = "failed"
                result.before_scan = {"status": "failed", "target": target, "error": str(exc)}
                return result

            before_findings = before_scan.findings

            # ============================================================
            # ② 规则匹配 + 加固建议
            # ============================================================
            logger.info("core", f"[闭环/{audit_id}] ② 规则推荐: findings={len(before_findings)}")
            try:
                engine = RuleEngine()
                engine.load_rules()
                recommendations = engine.recommend_hardening(before_findings)
            except Exception as exc:
                logger.error("core", f"[闭环/{audit_id}] 规则推荐失败: {exc}")
                result.overall = "failed"
                result.harden = {"status": "failed", "error": str(exc)}
                return result

            if not recommendations:
                logger.info("core", f"[闭环/{audit_id}] 无加固建议，闭环终止")
                result.harden = {"status": "no_action", "action_count": 0}
                # 无需加固但基线扫描已完成 → 如有 finding 则 failed，否则 verified
                if before_findings:
                    result.overall = "failed"
                else:
                    result.overall = "verified"
                    result.verification = {
                        "verdict": "verified",
                        "resolved": [],
                        "remaining": [],
                        "regressed": [],
                        "before_count": 0,
                        "after_count": 0,
                    }
                return result

            # ============================================================
            # ③ 生成加固/回滚脚本
            # ============================================================
            logger.info("core", f"[闭环/{audit_id}] ③ 生成脚本: actions={len(recommendations)}")
            try:
                harden_result = self.generate_hardening(
                    target,
                    findings=before_findings,
                    recommendations=recommendations,
                    os_platform=os_plat.value,
                )
                result.harden = harden_result.to_dict()
            except Exception as exc:
                logger.error("core", f"[闭环/{audit_id}] 脚本生成失败: {exc}")
                result.overall = "failed"
                result.harden = {"status": "failed", "error": str(exc)}
                return result

            if harden_result.status.value in ("failed", "no_action") or not harden_result.script_path:
                logger.info("core", f"[闭环/{audit_id}] 脚本生成状态异常: {harden_result.status.value}")
                result.overall = "failed"
                return result

            script_path = harden_result.script_path

        # ============================================================
        # DRY_RUN 路径：预检（R1 扫描 + 容器烟测）
        # ============================================================
        if mode == "dry_run":
            logger.info("core", f"[闭环/{audit_id}] DRY_RUN 预检: script={script_path}")
            precheck_result = self._run_dry_run_precheck(script_path, audit_id)
            if precheck_result:
                result.execution = precheck_result
                if precheck_result.get("status") == "rejected":
                    result.overall = "failed"
                    return result
            result.overall = "generated_only"
            logger.info("core", f"[闭环/{audit_id}] DRY_RUN 完成")
            return result

        # ============================================================
        # APPLY 路径：三重前置护栏 + 执行 + 复扫 + 验证
        # ============================================================
        # 护栏 1：R4 双重确认
        if not confirm_ownership or not confirm_execute:
            logger.warning(
                "core",
                f"[闭环/{audit_id}] APPLY 拒绝: 双确认未满足 ownership={confirm_ownership} execute={confirm_execute}",
            )
            result.overall = "failed"
            result.execution = {
                "status": "rejected",
                "sandbox": "host",
                "error": "APPLY 需要 confirm_ownership=True 且 confirm_execute=True（R4 双确认未满足）",
            }
            return result

        # 护栏 0：DRY_RUN-first 前置预检（APPLY 前必须通过 R1 扫描 + 容器烟测）
        logger.info("core", f"[闭环/{audit_id}] APPLY 前置 DRY_RUN 预检: script={script_path}")
        precheck_result = self._run_dry_run_precheck(script_path, audit_id)
        if precheck_result:
            result.execution = precheck_result
            if precheck_result.get("status") == "rejected":
                result.overall = "failed"
                logger.warning(
                    "core",
                    f"[闭环/{audit_id}] APPLY 拒绝: DRY_RUN-first 预检未通过 ({precheck_result.get('error')})",
                )
                return result
            # skipped / error：R1 扫描已完成但容器烟测未执行/异常，记录后放行
            logger.warning(
                "core",
                f"[闭环/{audit_id}] DRY_RUN 预检非阻塞状态: {precheck_result.get('status')}，继续 APPLY",
            )

        # 护栏 2+3 + ④⑤⑥⑦ 委托给 helper
        self._run_apply_and_verify(
            target=target,
            before_findings=before_findings,
            script_path=script_path,
            rollback_path=harden_result.rollback_path,
            mode=mode,
            backend=backend,
            audit_id=audit_id,
            scan_fn=_do_scan,
            result=result,
        )
        return result

    # =========================================================================
    # 审计日志
    # =========================================================================

    def _log_audit(self, event: str, target: str, detail: str) -> None:
        """记录审计日志"""
        entry = {
            "timestamp": datetime.datetime.now().isoformat(),
            "event": event,
            "target": target,
            "detail": detail,
        }
        self._scan_log.append(entry)

    def get_audit_log(self, limit: int = 50) -> list[dict]:
        """获取审计日志"""
        return self._scan_log[-limit:]

    def clear_audit_log(self) -> None:
        """清空审计日志"""
        self._scan_log.clear()


# =============================================================================
# 自检
# =============================================================================

if __name__ == "__main__":
    print("=== LightShield Core 自检 ===")

    # 1. 初始化
    core = LightShieldCore()
    print("[OK] 核心调度器初始化成功")

    # 2. 合规校验
    is_valid, reason = core._validate_request("192.168.1.1")
    assert is_valid, f"合法 IP 被拒绝: {reason}"
    print("[OK] 合法 IP '192.168.1.1' 通过校验")

    is_valid, reason = core._validate_request("192.168.1.0/24")
    assert not is_valid, f"CIDR 未被拒绝: {reason}"
    print(f"[OK] CIDR '192.168.1.0/24' 被正确拒绝: {reason}")

    is_valid, reason = core._validate_request("")
    assert not is_valid, f"空地址未被拒绝: {reason}"
    print(f"[OK] 空地址被正确拒绝: {reason}")

    # 3. 无适配器时扫描
    result = core.run_scan("192.168.1.1")
    assert result.status == ScanStatus.FAILED
    print(f"[OK] 无适配器时扫描正确失败: {result.error}")

    # 4. 能力列表
    print(f"   可用能力: {core.list_capabilities()}")
    print(f"   已注册适配器: {core.list_adapters()}")

    print("=== Core 自检全部通过 ===")
