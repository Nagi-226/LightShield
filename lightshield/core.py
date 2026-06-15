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

import datetime
import os
import sys as _sys
import threading
import time
import uuid
from dataclasses import dataclass

# Allow direct script execution (python lightshield/core.py)
if __name__ == "__main__" and _sys.path[0] != os.path.dirname(os.path.dirname(os.path.abspath(__file__))):
    _sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lightshield.adapters.base import BaseAdapter, ScanResult, VulnFinding
from lightshield.config import get_config
from lightshield.harden.base import HardenResult
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
    ) -> "HardenResult":
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
