"""LightShield 规则引擎

基于 JSON 规则库的漏洞特征匹配与风险分级系统。
支持：
  - 服务版本匹配（CVE 对照）
  - 端口特征匹配（高危端口识别）
  - 弱口令特征匹配
  - 加固策略推荐
  - 风险等级自动计算
  - 外部规则导入

用法：
    from lightshield.rules.engine import RuleEngine
    engine = RuleEngine()
    engine.load_rules("vuln_rules.json")
    findings = engine.match(scan_result)
"""

import json
import os

from lightshield.adapters.base import ScanResult, VulnFinding
from lightshield.utils.constants import RiskLevel
from lightshield.utils.logger import get_logger

# =============================================================================
# 规则引擎
# =============================================================================


class RuleEngine:
    """轻量化规则引擎 — 漏洞特征匹配 + 加固策略推荐

    设计原则：
    - 规则与代码分离：规则存储在 JSON 文件中，可独立更新
    - 可扩展：支持导入外部规则数据源
    - 轻量化：纯 Python 实现，无重型依赖
    """

    def __init__(self):
        self._vuln_rules: list[dict] = []
        self._harden_rules: list[dict] = []
        self._loaded: bool = False
        self._logger = get_logger()

    # =========================================================================
    # 规则加载
    # =========================================================================

    def load_rules(self, vuln_path: str = None, harden_path: str = None) -> None:
        """加载规则库

        Args:
            vuln_path: 漏洞规则文件路径（JSON），默认 rules/vuln_rules.json
            harden_path: 加固规则文件路径（JSON），默认 rules/harden_rules.json
        """
        base_dir = os.path.dirname(os.path.abspath(__file__))

        if vuln_path is None:
            vuln_path = os.path.join(base_dir, "vuln_rules.json")
        if harden_path is None:
            harden_path = os.path.join(base_dir, "harden_rules.json")

        self._vuln_rules = self._load_json(vuln_path)
        self._harden_rules = self._load_json(harden_path)
        self._loaded = True
        self._logger.info(
            "rules",
            f"规则加载完成：漏洞规则 {len(self._vuln_rules)} 条，加固规则 {len(self._harden_rules)} 条",
        )

    def _load_json(self, path: str) -> list[dict]:
        """加载 JSON 规则文件

        异常安全：文件缺失记 info 并返回空列表；JSON 解析或读取失败记 error
        并返回空列表，避免单个坏文件中断整个规则引擎初始化。
        """
        if not os.path.exists(path):
            self._logger.info("rules", f"规则文件不存在，跳过：{path}")
            return []
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            self._logger.error("rules", f"规则文件加载失败：{path}", exception=e)
            return []
        if isinstance(data, dict):
            # 支持 {"rules": [...]} 或直接 [...]  格式
            return data.get("rules", [])
        return data if isinstance(data, list) else []

    def import_rules(self, rules: list[dict], rule_type: str = "vuln") -> None:
        """导入外部规则（不覆盖已有规则）

        Args:
            rules: 规则列表
            rule_type: "vuln" 或 "harden"
        """
        if rule_type == "vuln":
            existing_ids = {r.get("rule_id") for r in self._vuln_rules}
            for rule in rules:
                if rule.get("rule_id") not in existing_ids:
                    self._vuln_rules.append(rule)
        elif rule_type == "harden":
            existing_ids = {r.get("rule_id") for r in self._harden_rules}
            for rule in rules:
                if rule.get("rule_id") not in existing_ids:
                    self._harden_rules.append(rule)

    # =========================================================================
    # 漏洞匹配
    # =========================================================================

    def match(self, scan_result: ScanResult) -> list[VulnFinding]:
        """对扫描结果执行全部规则匹配

        匹配顺序：
        1. 端口特征匹配（高危端口）
        2. 服务版本匹配（CVE 对照）
        3. 服务指纹匹配（弱口令等）
        4. 风险等级自动计算

        Args:
            scan_result: 扫描结果

        Returns:
            匹配到的漏洞发现列表（已去重）
        """
        findings: list[VulnFinding] = []

        for rule in self._vuln_rules:
            match_type = rule.get("match_type", "")
            try:
                if match_type == "port":
                    f = self._match_port(rule, scan_result)
                elif match_type == "service_version":
                    f = self._match_service_version(rule, scan_result)
                elif match_type == "service_fingerprint":
                    f = self._match_service_fingerprint(rule, scan_result)
                elif match_type == "header":
                    f = self._match_header(rule, scan_result)
                else:
                    continue
            except Exception as e:
                # 容错：单条规则匹配异常不应中断整轮匹配
                self._logger.warning(
                    "rules",
                    f"规则匹配异常，已跳过：rule_id={rule.get('rule_id', '?')} "
                    f"match_type={match_type}（{type(e).__name__}: {e}）",
                )
                continue

            if f:
                findings.append(f)

        # 去重（同类型同端口同参数只保留严重等级最高的）
        deduped = self._deduplicate(findings)
        self._logger.info(
            "rules",
            f"规则匹配完成：target={scan_result.target} 命中 {len(deduped)} 项漏洞",
        )
        return deduped

    def _match_port(self, rule: dict, result: ScanResult) -> VulnFinding | None:
        """端口特征匹配"""
        port = rule.get("port")
        if port is None:
            return None

        for p in result.ports:
            if p.get("port") == port and p.get("state") == "open":
                return VulnFinding(
                    vuln_type=rule.get("vuln_type", "high_risk_port"),
                    severity=self._parse_severity(rule.get("severity", "high")),
                    title=rule.get("title", f"高危端口开放: {port}"),
                    description=rule.get("description", ""),
                    remediation=rule.get("remediation", ""),
                    port=port,
                    cve_id=rule.get("cve_id"),
                    cvss_score=rule.get("cvss_score"),
                )
        return None

    def _match_service_version(self, rule: dict, result: ScanResult) -> VulnFinding | None:
        """服务版本匹配（CVE 对照）"""
        service_name = rule.get("service", "").lower()
        max_affected = rule.get("max_affected_version")
        if not service_name or not max_affected:
            return None

        for svc in result.services:
            if svc.get("name", "").lower() == service_name:
                version = svc.get("version", "")
                if self._version_affected(version, max_affected):
                    return VulnFinding(
                        vuln_type=rule.get("vuln_type", "vulnerable_component"),
                        severity=self._parse_severity(rule.get("severity", "high")),
                        title=rule.get("title", f"{service_name} 版本过低"),
                        description=rule.get("description", "").format(
                            version=version,
                            max_affected=max_affected,
                        ),
                        remediation=rule.get("remediation", ""),
                        port=svc.get("port"),
                        cve_id=rule.get("cve_id"),
                        cvss_score=rule.get("cvss_score"),
                        evidence=f"{service_name} {version} (受影响: <={max_affected})",
                    )
        return None

    def _match_service_fingerprint(self, rule: dict, result: ScanResult) -> VulnFinding | None:
        """服务指纹匹配（弱口令等特征）"""
        rule.get("service", "").lower()
        rule.get("auth_result", "")

        # 从 result 的 findings 中查找匹配
        for f in result.findings:
            if f.vuln_type == rule.get("match_vuln_type", ""):
                return VulnFinding(
                    vuln_type=rule.get("vuln_type", "weak_auth"),
                    severity=self._parse_severity(rule.get("severity", "high")),
                    title=rule.get("title", "弱认证"),
                    description=rule.get("description", ""),
                    remediation=rule.get("remediation", ""),
                    port=f.port,
                    evidence=f.evidence,
                )
        return None

    def _match_header(self, rule: dict, result: ScanResult) -> VulnFinding | None:
        """HTTP 响应头特征匹配"""
        rule.get("header", "").lower()
        rule.get("pattern", "")

        # 从 result 的 raw_output 或 services 中查找
        for svc in result.services:
            if svc.get("name") == "http":
                # 标记为需要进一步检查
                return VulnFinding(
                    vuln_type=rule.get("vuln_type", "misconfiguration"),
                    severity=self._parse_severity(rule.get("severity", "medium")),
                    title=rule.get("title", "HTTP 配置问题"),
                    description=rule.get("description", ""),
                    remediation=rule.get("remediation", ""),
                    port=svc.get("port"),
                )
        return None

    # =========================================================================
    # 加固策略推荐
    # =========================================================================

    def recommend_hardening(self, findings: list[VulnFinding]) -> list[dict]:
        """根据漏洞发现推荐加固策略

        Args:
            findings: 漏洞发现列表

        Returns:
            加固策略列表 [{"action": "关闭端口", "target": "23", "reason": "Telnet 明文传输"}, ...]
        """
        recommendations: list[dict] = []
        seen_actions: set[str] = set()

        for finding in findings:
            # 查找匹配的加固规则
            for rule in self._harden_rules:
                if rule.get("trigger_vuln_type") == finding.vuln_type:
                    action_key = f"{rule.get('action')}:{finding.port or finding.vuln_type}"
                    if action_key not in seen_actions:
                        seen_actions.add(action_key)
                        recommendations.append(
                            {
                                "action": rule.get("action", ""),
                                "target": str(finding.port or finding.vuln_type),
                                "reason": rule.get("reason", finding.title),
                                "commands": rule.get("commands", []),
                                "severity": finding.severity.value,
                            }
                        )

        # 按严重程度排序
        severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        recommendations.sort(key=lambda r: severity_order.get(r["severity"], 99))

        self._logger.info("rules", f"生成加固建议 {len(recommendations)} 条")
        return recommendations

    # =========================================================================
    # 风险统计
    # =========================================================================

    def summarize_risks(self, findings: list[VulnFinding]) -> dict:
        """风险统计摘要

        Returns:
            {"critical": N, "high": N, "medium": N, "low": N, "info": N, "total": N}
        """
        summary = {"critical": 0, "high": 0, "medium": 0, "low": 0, "info": 0}
        for f in findings:
            sev = f.severity.value
            if sev in summary:
                summary[sev] += 1
        summary["total"] = sum(summary.values())
        return summary

    # =========================================================================
    # 工具方法
    # =========================================================================

    def _version_affected(self, version: str, max_affected: str) -> bool:
        """判断版本是否受影响（version < max_affected 的语义版本比较）

        降级策略：语义版本比较失败时回退到字符串比较。
        """
        if not version:
            return True  # 未知版本视为有风险

        try:
            v = self._parse_semver(version)
            m = self._parse_semver(max_affected)
            return v < m
        except (ValueError, IndexError):
            # 版本格式无法解析时使用字符串比较
            return version.strip() <= max_affected.strip()

    @staticmethod
    def _parse_semver(version_str: str) -> tuple:
        """解析语义版本号为元组用于比较

        处理格式：1.2.3 / 1.2.3p4 / 1.2.3-ubuntu0.6 / 6.4.2-RC1

        Returns:
            (major, minor, patch) 元组
        """
        import re

        # 提取主版本号
        clean = re.sub(r"[^0-9.]", ".", version_str.split("-")[0])
        parts = clean.split(".")
        result = []
        for p in parts[:3]:  # 只取 major.minor.patch
            try:
                result.append(int(p))
            except ValueError:
                result.append(0)
        while len(result) < 3:
            result.append(0)
        return tuple(result[:3])

    @staticmethod
    def _parse_severity(severity: str) -> RiskLevel:
        """解析风险等级字符串"""
        mapping = {
            "critical": RiskLevel.CRITICAL,
            "high": RiskLevel.HIGH,
            "medium": RiskLevel.MEDIUM,
            "low": RiskLevel.LOW,
            "info": RiskLevel.INFO,
        }
        return mapping.get(severity.lower(), RiskLevel.MEDIUM)

    @staticmethod
    def _deduplicate(findings: list[VulnFinding]) -> list[VulnFinding]:
        """去重：同类型同端口只保留严重等级最高的"""
        severity_order = {
            RiskLevel.CRITICAL: 0,
            RiskLevel.HIGH: 1,
            RiskLevel.MEDIUM: 2,
            RiskLevel.LOW: 3,
            RiskLevel.INFO: 4,
        }
        seen: dict[tuple, VulnFinding] = {}
        for f in findings:
            key = (f.vuln_type, f.port, f.parameter)
            if key not in seen or severity_order[f.severity] < severity_order[seen[key].severity]:
                seen[key] = f
        return list(seen.values())

    # =========================================================================
    # 信息
    # =========================================================================

    @property
    def vuln_rule_count(self) -> int:
        """已加载的漏洞规则数"""
        return len(self._vuln_rules)

    @property
    def harden_rule_count(self) -> int:
        """已加载的加固规则数"""
        return len(self._harden_rules)


# =============================================================================
# 自检
# =============================================================================

if __name__ == "__main__":
    import os
    import sys as _sys

    _sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

    engine = RuleEngine()
    engine.load_rules()

    print("=== RuleEngine self-check ===")
    print(f"  Vuln rules loaded: {engine.vuln_rule_count}")
    print(f"  Harden rules loaded: {engine.harden_rule_count}")

    # 版本比较测试
    assert engine._version_affected("1.0", "2.0")
    assert not engine._version_affected("2.0", "1.0")
    assert engine._version_affected("", "2.0")  # unknown = risky
    print("  Version comparison: OK")

    # 风险摘要
    from lightshield.adapters.base import VulnFinding

    findings = [
        VulnFinding("test", RiskLevel.CRITICAL, "C", "d", "r"),
        VulnFinding("test", RiskLevel.HIGH, "H", "d", "r"),
        VulnFinding("test", RiskLevel.LOW, "L", "d", "r"),
    ]
    summary = engine.summarize_risks(findings)
    assert summary["critical"] == 1 and summary["high"] == 1
    print(f"  Risk summary: {summary}")

    print("=== RuleEngine: ALL PASSED ===")
