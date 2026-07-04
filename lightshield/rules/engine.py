"""LightShield 规则引擎

基于 JSON 规则库的漏洞特征匹配与风险分级系统。
支持：
  - 服务版本匹配（CVE 对照）
  - 端口特征匹配（高危端口识别）
  - 弱口令特征匹配
  - 加固策略推荐
  - 风险等级自动计算
  - 外部规则导入（文件/URL）
  - 规则热加载（保留导入规则）
  - 规则版本管理

用法：
    from lightshield.rules.engine import RuleEngine
    engine = RuleEngine()
    engine.load_rules()
    engine.import_rules_from_url("https://example.com/rules.json")
    findings = engine.match(scan_result)
"""

import hashlib
import json
import os
import re
import time

import requests

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

    _REQUIRED_RULE_FIELDS = {"rule_id", "match_type"}  # import 校验
    _IMPORT_TIMEOUT = 15  # URL 导入超时（秒）

    def __init__(self):
        self._vuln_rules: list[dict] = []
        self._harden_rules: list[dict] = []
        self._loaded: bool = False
        self._logger = get_logger()

        # v0.0.26: 追踪导入规则 ID（与内置规则区分，支持热加载）
        self._imported_vuln_ids: set[str] = set()
        self._imported_harden_ids: set[str] = set()

        # v0.0.26: 规则版本元数据
        self._rule_versions: dict[str, str] = {}  # {"vuln": "1.0", "harden": "1.0"}
        self._last_loaded_at: float = 0.0

    # =========================================================================
    # 规则加载
    # =========================================================================

    def load_rules(self, vuln_path: str = None, harden_path: str = None) -> None:
        """加载规则库（v0.0.26：支持热加载时保留已导入的外部规则）

        Args:
            vuln_path: 漏洞规则文件路径（JSON），默认 rules/vuln_rules.json
            harden_path: 加固规则文件路径（JSON），默认 rules/harden_rules.json
        """
        base_dir = os.path.dirname(os.path.abspath(__file__))

        if vuln_path is None:
            vuln_path = os.path.join(base_dir, "vuln_rules.json")
        if harden_path is None:
            harden_path = os.path.join(base_dir, "harden_rules.json")

        self._vuln_path = vuln_path
        self._harden_path = harden_path

        # 记录当前导入规则（将在热加载中保留）
        imported_vuln = [r for r in self._vuln_rules if r.get("rule_id") in self._imported_vuln_ids]
        imported_harden = [r for r in self._harden_rules if r.get("rule_id") in self._imported_harden_ids]

        self._vuln_rules = self._load_json(vuln_path)
        self._harden_rules = self._load_json(harden_path)
        self._loaded = True
        self._last_loaded_at = time.time()

        # 恢复已导入规则（去重追加）
        builtin_vuln = {r.get("rule_id") for r in self._vuln_rules}
        builtin_harden = {r.get("rule_id") for r in self._harden_rules}
        for rule in imported_vuln:
            if rule.get("rule_id") not in builtin_vuln:
                self._vuln_rules.append(rule)
        for rule in imported_harden:
            if rule.get("rule_id") not in builtin_harden:
                self._harden_rules.append(rule)

        # 更新版本元数据
        self._rule_versions["vuln"] = self._compute_version(self._vuln_rules[: len(builtin_vuln)])
        self._rule_versions["harden"] = self._compute_version(self._harden_rules[: len(builtin_harden)])

        self._logger.info(
            "rules",
            f"规则加载完成：漏洞规则 {len(self._vuln_rules)} 条（内置 {len(builtin_vuln)} + 导入 {len(self._imported_vuln_ids)}），"
            f"加固规则 {len(self._harden_rules)} 条（内置 {len(builtin_harden)} + 导入 {len(self._imported_harden_ids)}）",
        )

    def reload_rules(self) -> None:
        """热加载：重新从磁盘加载内置规则，保留已导入的外部规则。

        用途：运维期间更新内置规则文件后无需重启。
        """
        if not self._loaded:
            self.load_rules()
            return

        self._logger.info("rules", "热加载规则（保留已导入的外部规则）")
        self.load_rules(
            vuln_path=getattr(self, "_vuln_path", None),
            harden_path=getattr(self, "_harden_path", None),
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

    def import_rules(self, rules: list[dict], rule_type: str = "vuln") -> int:
        """导入外部规则（不覆盖已有规则，自动校验）

        Args:
            rules: 规则列表
            rule_type: "vuln" 或 "harden"

        Returns:
            成功导入的规则数
        """
        target = self._vuln_rules if rule_type == "vuln" else self._harden_rules
        imported_ids = self._imported_vuln_ids if rule_type == "vuln" else self._imported_harden_ids
        existing_ids = {r.get("rule_id") for r in target}
        count = 0

        for rule in rules:
            rule_id = rule.get("rule_id")
            if not rule_id:
                self._logger.warning("rules", f"跳过无 rule_id 的规则: {rule.get('title', '?')}")
                continue
            if not self._validate_rule(rule):
                self._logger.warning("rules", f"规则校验失败，跳过: {rule_id}")
                continue
            if rule_id not in existing_ids:
                target.append(rule)
                imported_ids.add(rule_id)
                existing_ids.add(rule_id)
                count += 1

        if count > 0:
            self._logger.info("rules", f"导入 {rule_type} 规则 {count} 条")
        return count

    def import_rules_from_file(self, path: str, rule_type: str = "vuln") -> int:
        """从本地文件导入规则

        Args:
            path: JSON 规则文件路径
            rule_type: "vuln" 或 "harden"

        Returns:
            成功导入的规则数
        """
        if not os.path.exists(path):
            self._logger.error("rules", f"规则文件不存在: {path}")
            raise FileNotFoundError(f"规则文件不存在: {path}")
        rules = self._load_json(path)
        if not rules:
            self._logger.warning("rules", f"规则文件为空或格式错误: {path}")
            return 0
        return self.import_rules(rules, rule_type)

    def import_rules_from_url(self, url: str, rule_type: str = "vuln") -> int:
        """从远程 URL 导入规则

        通过 HTTP GET 获取 JSON 规则数据，校验后合并到当前规则集。
        不覆盖已有规则（包括内置和已导入的）。

        Args:
            url: 远程规则 JSON URL（需返回 JSON 数组或 {"rules": [...]}）
            rule_type: "vuln" 或 "harden"

        Returns:
            成功导入的规则数

        Raises:
            requests.RequestException: 网络请求失败
            ValueError: 响应不是有效 JSON
        """
        self._logger.info("rules", f"从远程导入规则: {url}")

        try:
            resp = requests.get(
                url,
                timeout=self._IMPORT_TIMEOUT,
                headers={"Accept": "application/json"},
            )
            resp.raise_for_status()
            data = resp.json()
        except requests.Timeout:
            self._logger.error("rules", f"远程规则导入超时: {url}")
            raise
        except requests.RequestException as e:
            self._logger.error("rules", f"远程规则导入请求失败: {e}")
            raise
        except json.JSONDecodeError as e:
            self._logger.error("rules", f"远程规则 JSON 解析失败: {e}")
            raise ValueError(f"远程响应不是有效 JSON: {e}") from e

        if isinstance(data, dict):
            rules = data.get("rules", [])
        elif isinstance(data, list):
            rules = data
        else:
            raise ValueError(f"不支持的规则格式: {type(data)}")

        count = self.import_rules(rules, rule_type)
        return count

    def _validate_rule(self, rule: dict) -> bool:
        """校验规则是否包含必填字段"""
        return all(field in rule for field in self._REQUIRED_RULE_FIELDS)

    @staticmethod
    def _compute_version(rules: list[dict]) -> str:
        """基于规则内容计算版本指纹（SHA256 前 8 位）"""
        serialized = json.dumps(
            sorted(rules, key=lambda r: r.get("rule_id", "")),
            sort_keys=True,
            ensure_ascii=False,
        )
        return hashlib.sha256(serialized.encode()).hexdigest()[:8]

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
        """服务指纹匹配（弱口令等特征）。

        规则字段说明：
          - service: 目标服务名（如 "ssh"），用于精确匹配扫描结果中的服务
          - match_vuln_type: 匹配的漏洞类型（如 "weak_password"）
          - auth_result: 认证结果标记（如 "weak"），v1.0.0+ 可用于过滤
        """
        target_service = rule.get("service", "").lower()

        # 从 result 的 findings 中查找匹配
        for f in result.findings:
            if f.vuln_type != rule.get("match_vuln_type", ""):
                continue
            # 如果规则指定了 service，进一步过滤：查找该 finding 端口对应的服务名
            if target_service and f.port is not None:
                svc_match = any(
                    svc.get("port") == f.port and str(svc.get("name", "")).lower() == target_service
                    for svc in (result.services or [])
                )
                if not svc_match:
                    continue
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
        """HTTP 响应头特征匹配。

        规则字段：
          - header: 响应头名（大小写不敏感）
          - pattern: 用 re.search 做子串匹配的正则
        """
        header_name = str(rule.get("header", "")).strip().lower()
        pattern = rule.get("pattern", "")
        if not header_name or not isinstance(pattern, str) or not pattern:
            return None

        try:
            compiled_pattern = re.compile(pattern)
        except re.error as exc:
            self._logger.warning(
                "rules",
                f"Header 规则正则无效，已跳过：rule_id={rule.get('rule_id', '?')} pattern={pattern!r} ({exc})",
            )
            return None

        for svc in result.services:
            if not isinstance(svc, dict) or str(svc.get("name", "")).lower() != "http":
                continue
            headers = svc.get("headers", {})
            if not isinstance(headers, dict) or not headers:
                continue

            actual_name = ""
            actual_value = None
            for key, value in headers.items():
                if str(key).lower() == header_name:
                    actual_name = str(key)
                    actual_value = str(value)
                    break
            if actual_value is None:
                continue

            if compiled_pattern.search(actual_value):
                return VulnFinding(
                    vuln_type=rule.get("vuln_type", "misconfiguration"),
                    severity=self._parse_severity(rule.get("severity", "medium")),
                    title=rule.get("title", "HTTP 响应头配置问题"),
                    description=rule.get("description", ""),
                    remediation=rule.get("remediation", ""),
                    port=svc.get("port"),
                    cve_id=rule.get("cve_id"),
                    cvss_score=rule.get("cvss_score"),
                    parameter=actual_name,
                    evidence=f"{actual_name}: {actual_value}",
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

        # 按严重程度排序（使用共享常量，保持跨模块一致）
        from lightshield.utils.constants import SEVERITY_ORDER

        recommendations.sort(key=lambda r: SEVERITY_ORDER.get(r["severity"], 99))

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
        from lightshield.utils.constants import SEVERITY_ORDER

        seen: dict[tuple, VulnFinding] = {}
        for f in findings:
            key = (f.vuln_type, f.port, f.parameter)
            if key not in seen or SEVERITY_ORDER[f.severity.value] < SEVERITY_ORDER[seen[key].severity.value]:
                seen[key] = f
        return list(seen.values())

    # =========================================================================
    # 信息 & 元数据
    # =========================================================================

    @property
    def vuln_rule_count(self) -> int:
        """已加载的漏洞规则数"""
        return len(self._vuln_rules)

    @property
    def harden_rule_count(self) -> int:
        """已加载的加固规则数"""
        return len(self._harden_rules)

    @property
    def imported_rule_count(self) -> int:
        """已导入的外部规则数"""
        return len(self._imported_vuln_ids) + len(self._imported_harden_ids)

    @property
    def rule_metadata(self) -> dict:
        """规则集元数据（版本 + 统计）

        Returns:
            {
                "vuln_count": N, "harden_count": N, "imported_count": N,
                "versions": {"vuln": "...", "harden": "..."},
                "last_loaded": ISO8601,
            }
        """
        from datetime import datetime

        return {
            "vuln_count": self.vuln_rule_count,
            "harden_count": self.harden_rule_count,
            "imported_count": self.imported_rule_count,
            "versions": dict(self._rule_versions),
            "last_loaded": (datetime.fromtimestamp(self._last_loaded_at).isoformat() if self._last_loaded_at else None),
        }


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
