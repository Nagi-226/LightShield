"""LightShield 命令行入口。

CLI 是用户侧 R4 所有权确认防线：任何扫描命令都必须先通过目标格式校验，
并在未传入 --confirm-ownership 时进行交互确认。
"""

from __future__ import annotations

import argparse
import os
import sys
from typing import Any

if __package__ in {None, ""}:  # 允许 python lightshield/cli.py 直接自检。
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from lightshield import __version__
from lightshield.adapters.base import ScanResult, VulnFinding
from lightshield.adapters.nmap_adapter import NmapAdapter
from lightshield.core import LightShieldCore
from lightshield.report.reporter import ReportGenerator
from lightshield.rules.engine import RuleEngine
from lightshield.utils.constants import ScanStatus
from lightshield.utils.logger import get_logger
from lightshield.utils.validator import TargetValidator

DEFAULT_OUTPUT_DIR = "./reports"
DEFAULT_SCAN_TYPES = "port_scan,service_detect"


def create_parser() -> argparse.ArgumentParser:
    """创建命令行参数解析器。"""
    parser = argparse.ArgumentParser(
        prog="lightshield",
        description="LightShield 轻盾 — 开源轻量化安全自检 + 防御加固工具",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    scan_parser = subparsers.add_parser("scan", help="全量扫描（资产 + 漏洞 + 报告）")
    _add_scan_arguments(scan_parser, default_scan_types=DEFAULT_SCAN_TYPES)

    quick_parser = subparsers.add_parser("quick-scan", help="快速扫描（Top 100 端口）")
    _add_scan_arguments(quick_parser, default_scan_types="port_scan,service_detect")

    harden_parser = subparsers.add_parser("harden", help="生成加固脚本（扫描 + 规则匹配 + 加固建议 + 脚本输出）")
    _add_harden_arguments(harden_parser)

    history_parser = subparsers.add_parser("history", help="查看扫描历史记录")
    history_parser.add_argument("target", nargs="?", help="按目标 IP/域名过滤（可选）")
    history_parser.add_argument("--scan-id", help="查看指定扫描的详细信息")
    history_parser.add_argument("--limit", type=int, default=20, help="最大显示条数，默认 20")
    history_parser.add_argument("--format", choices=["table", "json"], default="table", help="输出格式，默认 table")

    subparsers.add_parser("version", help="显示版本号")
    return parser


def main(argv: list[str] | None = None) -> int:
    """CLI 主入口——由 console_scripts 调用。"""
    parser = create_parser()
    args = parser.parse_args(argv)

    if args.command == "version":
        print(f"LightShield 轻盾 v{__version__}")
        return 0

    if args.command in {"scan", "quick-scan"}:
        return run_scan_command(args)

    if args.command == "harden":
        return run_harden_command(args)

    if args.command == "history":
        return run_history_command(args)

    parser.print_help()
    return 1


def run_scan_command(args: argparse.Namespace) -> int:
    """执行 scan / quick-scan 命令。"""
    target = args.target
    is_valid, reason = TargetValidator.validate(target)
    if not is_valid:
        print(f"[错误] 目标地址不合法：{reason}")
        print("LightShield 仅允许扫描单个自有 IP、域名或 localhost，禁止 CIDR/网段/通配符。")
        return 1

    if not _ensure_ownership(target, args.confirm_ownership):
        print("已取消扫描：未确认目标所有权。")
        return 1

    logger = get_logger(level="DEBUG" if args.verbose else "INFO")
    logger.info("cli", f"启动 {args.command}: target={target}")

    print(f"LightShield 轻盾 v{__version__}")
    print("[1/4] 正在扫描端口... (NmapAdapter)")

    try:
        core = LightShieldCore()
        _register_adapters(core, quick=args.command == "quick-scan")
        scan_types = _parse_scan_types(args.scan_types)
        scan_kwargs: dict[str, Any] = {
            "confirm_ownership": True,
            "timeout": args.timeout,
        }
        if args.command == "quick-scan":
            scan_kwargs["ports"] = "1-100"

        scan_result = core.run_scan(target, scan_types=scan_types, **scan_kwargs)
        if scan_result.status == ScanStatus.FAILED:
            print(f"[错误] 扫描失败：{scan_result.error or '未获得有效扫描结果'}")
            return 1

        print("[2/4] 正在检测漏洞... (扫描器结果汇总)")
        print("[3/4] 正在匹配规则... (RuleEngine)")
        rule_engine = RuleEngine()
        rule_engine.load_rules()

        # v0.0.26: 远程规则导入
        if getattr(args, "rules_url", None):
            try:
                imported = rule_engine.import_rules_from_url(args.rules_url)
                print(f"[规则] 从远程导入 {imported} 条规则")
            except Exception as exc:
                print(f"[警告] 远程规则导入失败：{exc}，继续使用内置规则")
        rule_findings = rule_engine.match(scan_result)
        all_findings = _merge_findings(scan_result.findings, rule_findings)
        harden_recommendations = rule_engine.recommend_hardening(all_findings)

        print("[4/4] 正在生成报告... (ReportGenerator)")
        reporter = ReportGenerator(output_dir=args.output_dir)
        report_path = reporter.generate_and_save(
            scan_result,
            findings=all_findings,
            harden=harden_recommendations,
            fmt=args.output_format,
        )

        print(f"[完成] 报告已保存: {report_path}")

        # 保存扫描结果到 SQLite 历史
        try:
            from lightshield.repository.base import get_repository

            repo = get_repository("sqlite", db_url="data/lightshield.db")
            scan_dict = {
                "scan_id": getattr(scan_result, "scan_id", None),
                "target": scan_result.target,
                "status": scan_result.status.value,
                "ports": scan_result.ports,
                "services": scan_result.services,
                "os_info": scan_result.os_info,
                "findings": [
                    {
                        "vuln_type": f.vuln_type,
                        "severity": f.severity.value,
                        "title": f.title,
                        "description": f.description,
                        "remediation": f.remediation,
                        "port": f.port,
                        "cve_id": f.cve_id,
                        "cvss_score": f.cvss_score,
                        "evidence": f.evidence,
                    }
                    for f in all_findings
                ],
                "error": scan_result.error,
                "duration_seconds": scan_result.duration_seconds,
            }
            scan_id = repo.save(scan_dict)
            print(f"[历史] 扫描已保存：{scan_id}")
        except Exception:
            pass  # 历史保存失败不阻断主流程

        if scan_result.error:
            print(f"[警告] 部分扫描提示：{scan_result.error}")
        return 0
    except KeyboardInterrupt:
        print("\n已取消扫描。")
        return 1
    except Exception as exc:
        print(f"[错误] 执行失败：{exc}")
        if args.verbose:
            raise
        return 1


def run_harden_command(args: argparse.Namespace) -> int:
    """执行 harden 命令：扫描 → 规则匹配 → 加固建议 → 生成加固/回滚脚本"""
    target = args.target
    is_valid, reason = TargetValidator.validate(target)
    if not is_valid:
        print(f"[错误] 目标地址不合法：{reason}")
        print("LightShield 仅允许扫描单个自有 IP、域名或 localhost，禁止 CIDR/网段/通配符。")
        return 1

    if not _ensure_ownership(target, args.confirm_ownership):
        print("已取消：未确认目标所有权。")
        return 1

    logger = get_logger(level="DEBUG" if args.verbose else "INFO")
    logger.info("cli", f"启动 harden: target={target}")

    print(f"LightShield 轻盾 v{__version__}")
    print("[1/3] 正在扫描端口... (NmapAdapter)")

    try:
        # 扫描
        core = LightShieldCore()
        _register_adapters(core)
        scan_result = core.run_scan(
            target,
            scan_types=["port_scan", "service_detect"],
            confirm_ownership=True,
            timeout=args.timeout,
        )
        if scan_result.status == ScanStatus.FAILED:
            print(f"[错误] 扫描失败：{scan_result.error or '未获得有效扫描结果'}")
            return 1

        # 规则匹配
        print("[2/3] 正在匹配规则 + 生成加固建议...")
        rule_engine = RuleEngine()
        rule_engine.load_rules()

        # v0.0.26: 远程规则导入
        if getattr(args, "rules_url", None):
            try:
                imported = rule_engine.import_rules_from_url(args.rules_url)
                print(f"[规则] 从远程导入 {imported} 条规则")
            except Exception as exc:
                print(f"[警告] 远程规则导入失败：{exc}，继续使用内置规则")
        rule_findings = rule_engine.match(scan_result)
        all_findings = _merge_findings(scan_result.findings, rule_findings)
        recommendations = rule_engine.recommend_hardening(all_findings)

        if not recommendations:
            print("[完成] 未发现需要加固的风险项。目标当前状态良好。")
            logger.info("cli", f"harden 无加固项：target={target}")
            return 0

        # 生成加固脚本
        print("[3/3] 正在生成加固/回滚脚本...")
        harden_result = core.generate_hardening(
            target,
            findings=all_findings,
            recommendations=recommendations,  # 复用，避免 Core 重复计算（Codex M1 修复）
            output_dir=args.output_dir,
        )

        # 报告（含加固建议段）
        reporter = ReportGenerator(output_dir=args.output_dir)
        report_path = reporter.generate_and_save(
            scan_result,
            findings=all_findings,
            harden=recommendations,
            fmt=args.output_format,
        )

        # 输出结果
        print(f"[完成] 加固建议 {harden_result.action_count} 条")
        for i, rec in enumerate(recommendations, 1):
            sev = rec.get("severity", "?")
            action = rec.get("action", "?")
            tgt = rec.get("target", "?")
            reason = rec.get("reason", "")
            print(f"  {i}. [{sev}] {action} → {tgt}（{reason}）")

        print("")
        print(f" 加固脚本：{harden_result.script_path}")
        print(f" 回滚脚本：{harden_result.rollback_path}")
        print(f" 安全报告：{report_path}")
        print("")
        print(" ⚠️  请审阅加固脚本后再手动执行。脚本运行时会再次确认所有权。")
        return 0

    except KeyboardInterrupt:
        print("\n已取消。")
        return 1
    except Exception as exc:
        print(f"[错误] 执行失败：{exc}")
        if args.verbose:
            raise
        return 1


def run_history_command(args: argparse.Namespace) -> int:
    """执行 history 命令：查看扫描历史记录。"""
    from lightshield.repository.base import get_repository

    db_url = "data/lightshield.db"
    try:
        repo = get_repository("sqlite", db_url=db_url)
    except Exception as exc:
        print(f"[错误] 无法打开扫描历史数据库：{exc}")
        return 1

    # ---- 查看单条扫描详情 ----
    if args.scan_id:
        detail = repo.get(args.scan_id)
        if detail is None:
            print(f"[未找到] 扫描记录 {args.scan_id} 不存在。")
            return 1
        if args.format == "json":
            import json

            print(json.dumps(detail, ensure_ascii=False, indent=2))
        else:
            _print_scan_detail(detail)
        return 0

    # ---- 按目标过滤 ----
    if args.target:
        entries = repo.list_by_target(args.target, limit=args.limit)
        title = f"目标 {args.target} 的扫描历史"
    else:
        entries = repo.list_recent(limit=args.limit)
        title = f"最近 {len(entries)} 次扫描"

    if not entries:
        print("暂无扫描历史记录。")
        print("运行 lightshield scan <target> 开始第一次扫描。")
        return 0

    if args.format == "json":
        import json

        print(json.dumps(entries, ensure_ascii=False, indent=2))
    else:
        _print_history_table(entries, title)

    return 0


def _print_history_table(entries: list[dict], title: str) -> None:
    """以表格形式打印扫描历史列表。"""
    print(f"\n{'=' * 80}")
    print(f"  {title}")
    print(f"{'=' * 80}")
    print(
        f"{'扫描 ID':<34s} {'目标':<20s} {'状态':<10s} {'端口':>4s} {'服务':>4s} {'漏洞':>4s} {'CVE':>4s} {'耗时':>6s}"
    )
    print("-" * 80)
    for entry in entries:
        sid = entry.get("scan_id", "?")
        target = entry.get("target", "?")
        status = entry.get("status", "?")
        ports = entry.get("ports_count", 0)
        services = entry.get("services_count", 0)
        findings = entry.get("findings_count", 0)
        cves = entry.get("cve_count", 0)
        duration = entry.get("duration_seconds", 0)
        print(
            f"{sid:<34s} {target:<20s} {status:<10s} {ports:>4d} {services:>4d} {findings:>4d} {cves:>4d} {duration:>5.1f}s"
        )
    print("-" * 80)
    total = len(entries)
    print(f"  共 {total} 条记录")
    if total > 0:
        print("  查看详情：lightshield history --scan-id <扫描ID>")
    print("")


def _print_scan_detail(detail: dict) -> None:
    """打印单条扫描详情。"""
    print(f"\n{'=' * 60}")
    print(f"  扫描详情：{detail.get('scan_id', '?')}")
    print(f"{'=' * 60}")
    print(f"  目标：{detail.get('target', '?')}")
    print(f"  状态：{detail.get('status', '?')}")
    print(f"  时间：{detail.get('created_at', '?')}")
    print(f"  端口：{detail.get('ports_count', 0)}  服务：{detail.get('services_count', 0)}")
    print(f"  漏洞：{detail.get('findings_count', 0)}  CVE：{detail.get('cve_count', 0)}")
    if detail.get("os_info"):
        print(f"  OS  ：{detail['os_info']}")
    if detail.get("duration_seconds"):
        print(f"  耗时：{detail['duration_seconds']}s")
    if detail.get("error"):
        print(f"  错误：{detail['error']}")

    # 展开 findings
    raw = detail.get("raw_result")
    if isinstance(raw, dict):
        findings = raw.get("findings", [])
        if findings:
            print(f"\n  漏洞发现 ({len(findings)} 条):")
            for i, f in enumerate(findings[:10], 1):
                sev = f.get("severity", "?")
                title = f.get("title", "?")
                cve = f.get("cve_id", "")
                cve_str = f" [{cve}]" if cve else ""
                print(f"    {i:>2d}. [{sev:>8s}] {title[:50]}{cve_str}")
            if len(findings) > 10:
                print(f"    ... 还有 {len(findings) - 10} 条，使用 --format json 查看完整数据")
    print("")


def _add_harden_arguments(parser: argparse.ArgumentParser) -> None:
    """为 harden 子命令添加参数。"""
    parser.add_argument("target", help="自有目标 IP、域名或 localhost")
    parser.add_argument(
        "--output-format",
        choices=["markdown", "text"],
        default="markdown",
        help="报告格式，默认 markdown",
    )
    parser.add_argument(
        "--output-dir",
        default=DEFAULT_OUTPUT_DIR,
        help="脚本与报告输出目录，默认 ./reports",
    )
    parser.add_argument(
        "--confirm-ownership",
        action="store_true",
        help="确认你拥有目标所有权或已获得明确授权",
    )
    parser.add_argument("--timeout", type=int, default=60, help="扫描超时时间，默认 60 秒")
    parser.add_argument("--rules-url", help="从远程 URL 导入额外规则（v0.0.26）")
    parser.add_argument("--verbose", action="store_true", help="输出详细日志")


def _add_scan_arguments(parser: argparse.ArgumentParser, default_scan_types: str) -> None:
    """为扫描类子命令添加通用参数。"""
    parser.add_argument("target", help="自有目标 IP、域名或 localhost")
    parser.add_argument(
        "--output-format",
        choices=["markdown", "text"],
        default="markdown",
        help="报告格式，默认 markdown",
    )
    parser.add_argument("--output-dir", default=DEFAULT_OUTPUT_DIR, help="报告输出目录，默认 ./reports")
    parser.add_argument(
        "--confirm-ownership",
        action="store_true",
        help="确认你拥有目标所有权或已获得明确授权",
    )
    parser.add_argument(
        "--scan-types",
        default=default_scan_types,
        help="指定扫描类型，逗号分隔，例如 port_scan,web_vuln",
    )
    parser.add_argument("--timeout", type=int, default=60, help="单个扫描器超时时间，默认 60 秒")
    parser.add_argument("--rules-url", help="从远程 URL 导入额外规则（v0.0.26）")
    parser.add_argument("--verbose", action="store_true", help="输出详细日志")


def _ensure_ownership(target: str, confirmed: bool) -> bool:
    """R4 所有权确认：未传参数时必须交互输入 YES。"""
    if confirmed:
        return True

    print("[警告] 所有权确认")
    print(TargetValidator.confirm_ownership(target))
    answer = input("如确认拥有该目标或已获授权，请输入 YES 继续：").strip()
    return answer == "YES"


def _register_adapters(core: LightShieldCore, quick: bool = False) -> None:
    """注册 CLI 当前可用的扫描适配器。"""
    nmap_args = "-sV --top-ports 100" if quick else "-sV -O --top-ports 1000"
    core.register_adapter(NmapAdapter(nmap_args=nmap_args))

    # 其他扫描器属于可选能力；导入失败时不影响基础资产扫描。
    optional_adapters = [
        ("lightshield.scanners.web_vuln_scanner", "WebVulnScanner"),
        ("lightshield.scanners.weak_password", "WeakPasswordAdapter"),
        ("lightshield.scanners.component_checker", "ComponentCheckerAdapter"),
    ]
    for module_name, class_name in optional_adapters:
        try:
            module = __import__(module_name, fromlist=[class_name])
            adapter_cls = getattr(module, class_name)
            core.register_adapter(adapter_cls())
        except Exception as exc:
            get_logger().warning("cli", f"跳过可选扫描器 {class_name}: {exc}")


def _parse_scan_types(value: str | None) -> list[str] | None:
    """解析逗号分隔的扫描类型。"""
    if not value:
        return None
    scan_types = [item.strip() for item in value.split(",") if item.strip()]
    return scan_types or None


def _merge_findings(
    scanner_findings: list[VulnFinding],
    rule_findings: list[VulnFinding],
) -> list[VulnFinding]:
    """合并扫描器和规则引擎发现，避免重复报告同类同位置风险。"""
    merged: list[VulnFinding] = []
    seen: set[tuple[Any, ...]] = set()
    for finding in [*scanner_findings, *rule_findings]:
        key = (finding.vuln_type, finding.port, finding.url, finding.parameter, finding.title)
        if key in seen:
            continue
        seen.add(key)
        merged.append(finding)
    return merged


def _self_check() -> None:
    """内置自检：验证参数解析和 R4 交互路径，不触发真实扫描。"""
    parser = create_parser()
    args = parser.parse_args(["scan", "127.0.0.1", "--confirm-ownership"])
    assert args.command == "scan"
    assert args.target == "127.0.0.1"
    assert args.confirm_ownership is True
    assert _parse_scan_types("port_scan,web_vuln") == ["port_scan", "web_vuln"]
    assert TargetValidator.validate("192.168.1.0/24")[0] is False

    mock_result = ScanResult(
        status=ScanStatus.COMPLETED,
        target="127.0.0.1",
        ports=[{"port": 80, "protocol": "tcp", "state": "open", "service": "http"}],
        services=[{"name": "http", "version": "mock", "port": 80}],
        duration_seconds=0.1,
    )
    reporter = ReportGenerator(output_dir="./reports")
    path = reporter.generate_and_save(mock_result, findings=[], harden=[], fmt="text")
    assert os.path.exists(path)
    print("cli.py 自检通过")


if __name__ == "__main__":
    if len(sys.argv) == 1:
        _self_check()
    else:
        sys.exit(main())
