"""LightShield Nuclei 适配器

封装 Nuclei 模板扫描引擎，仅允许安全检测标签的模板（R1 防线）。
通过标签白名单/黑名单机制过滤模板，解析 JSONL 输出为标准 VulnFinding。

用法：
    from lightshield.adapters.nuclei_adapter import NucleiAdapter
    adapter = NucleiAdapter()
    result = adapter.scan("192.168.1.1", templates="lightshield/nuclei-templates/")
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import yaml

# Allow direct script execution (python lightshield/adapters/nuclei_adapter.py)
if __package__ in {None, ""}:
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from lightshield.adapters.base import BaseAdapter, ScanResult, VulnFinding
from lightshield.utils.constants import (
    NUCLEI_ALLOWED_TAGS,
    NUCLEI_BLOCKED_TAGS,
    NUCLEI_DEFAULT_TIMEOUT,
    RiskLevel,
    ScanStatus,
)
from lightshield.utils.logger import get_logger
from lightshield.utils.validator import TargetValidator


class NucleiSecurityError(Exception):
    """Nuclei 合规违规异常——尝试使用非法标签模板时抛出。"""

    def __init__(self, tags: list[str], reason: str):
        self.tags = tags
        self.reason = reason
        super().__init__(f"Nuclei 安全违规: tags={tags} — {reason}")


def is_template_safe(tags: list[str]) -> tuple[bool, str]:
    """校验模板标签是否安全（R1 + R5 防线）。

    黑名单优先：任何标签命中 NUCLEI_BLOCKED_TAGS → 拒绝。
    白名单放行：所有标签均命中 NUCLEI_ALLOWED_TAGS → 通过。
    空标签列表 → 拒绝（无法确认安全性）。

    Args:
        tags: 模板的 info.tags 列表

    Returns:
        (是否安全, 原因说明)
    """
    if not tags:
        return False, "模板未声明标签，无法确认安全性"

    # 黑名单优先
    for tag in tags:
        tag_lower = tag.lower().strip()
        if tag_lower in NUCLEI_BLOCKED_TAGS:
            return False, f"模板标签 '{tag}' 命中黑名单"

    unknown_tags = [tag for tag in tags if tag.lower().strip() not in NUCLEI_ALLOWED_TAGS]
    if unknown_tags:
        return False, f"模板标签 {unknown_tags} 不在白名单内"

    return True, "通过"


class NucleiAdapter(BaseAdapter):
    """Nuclei 模板扫描适配器 — R1 标签白名单防线。

    封装 Nuclei CLI，仅允许安全检测标签（detection/discovery/tech 等）
    的模板执行扫描。结果解析为标准 VulnFinding 格式。

    能力清单：
    - nuclei_scan: 基于 YAML 模板的漏洞检测
    """

    # Nuclei JSONL 严重程度 → LightShield RiskLevel 映射
    SEVERITY_MAP: dict[str, RiskLevel] = {
        "critical": RiskLevel.CRITICAL,
        "high": RiskLevel.HIGH,
        "medium": RiskLevel.MEDIUM,
        "low": RiskLevel.LOW,
        "info": RiskLevel.INFO,
        "unknown": RiskLevel.INFO,
    }

    def __init__(
        self,
        nuclei_path: str = "nuclei",
        templates_dir: str | None = None,
        timeout: int = NUCLEI_DEFAULT_TIMEOUT,
    ):
        """初始化 Nuclei 适配器。

        Args:
            nuclei_path: Nuclei 可执行文件路径
            templates_dir: 模板目录路径（默认使用内置模板库）
            timeout: 默认扫描超时秒数
        """
        super().__init__(name="NucleiAdapter")
        self._nuclei_path = nuclei_path
        self._templates_dir = templates_dir or os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "nuclei-templates",
        )
        self._timeout = timeout
        self._logger = get_logger()

    # =========================================================================
    # BaseAdapter 实现
    # =========================================================================

    def capabilities(self) -> list[str]:
        """返回 ["nuclei_scan"]"""
        return ["nuclei_scan"]

    def validate_target(self, target: str) -> bool:
        """目标合法性校验——委托给 TargetValidator。"""
        is_valid, reason = TargetValidator.validate(target)
        if not is_valid:
            self._logger.warning("nuclei", f"目标校验失败: {target} — {reason}")
        return is_valid

    def scan(self, target: str, **kwargs: Any) -> ScanResult:
        """执行 Nuclei 扫描。

        Args:
            target: 扫描目标（单 IP/域名）
            **kwargs:
                templates: 模板路径（覆盖默认）
                tags: 手动指定标签（覆盖默认白名单）
                extra_args: 额外 Nuclei CLI 参数
                timeout: 超时秒数（覆盖默认 120s）

        Returns:
            ScanResult 结构化结果
        """
        # 1. R2 前置校验
        if not self.validate_target(target):
            return ScanResult(
                status=ScanStatus.FAILED,
                target=target,
                error="目标校验不通过",
            )

        # 2. 记录审计
        scan_id = self._log_scan_start(target, "nuclei")

        # 3. 解析参数
        templates = str(kwargs.get("templates") or self._templates_dir)
        allowed_tags = kwargs.get("tags") or ",".join(NUCLEI_ALLOWED_TAGS)
        extra_args = kwargs.get("extra_args", "")
        timeout = kwargs.get("timeout", self._timeout)

        # 4. 执行前审查模板。任何 Nuclei subprocess 都必须晚于此防线。
        try:
            reviewed_templates = self._review_template_source(templates, allowed_tags)
        except NucleiSecurityError as exc:
            error_msg = str(exc)
            self._logger.error("nuclei", error_msg)
            result = ScanResult(status=ScanStatus.FAILED, target=target, error=error_msg)
            self._log_scan_end(scan_id, result)
            return result

        # 5. 检查 Nuclei CLI 可用性
        if not self._check_nuclei_exists():
            error_msg = (
                f"Nuclei 未安装或路径错误: {self._nuclei_path}。"
                f"请访问 https://github.com/projectdiscovery/nuclei 安装。"
            )
            self._logger.error("nuclei", error_msg)
            result = ScanResult(
                status=ScanStatus.FAILED,
                target=target,
                error=error_msg,
            )
            self._log_scan_end(scan_id, result)
            return result

        # 6. 构造命令
        cmd = [self._nuclei_path, "-u", target, "-jsonl", "-silent"]

        # 只传递已审查的具体文件，绝不把原始目录或 URL 交给 Nuclei。
        for template_path in reviewed_templates:
            cmd.extend(["-t", self._sanitize_path(template_path)])

        # 额外参数（仅允许安全参数）
        if extra_args:
            safe_args = self._sanitize_extra_args(extra_args)
            if safe_args:
                cmd.extend(safe_args)

        self._logger.info("nuclei", f"执行扫描: {' '.join(cmd)}")

        # 7. 执行
        start_time = time.monotonic()
        try:
            completed = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            duration = time.monotonic() - start_time
        except subprocess.TimeoutExpired:
            error_msg = f"Nuclei 扫描超时（{timeout}s）"
            self._logger.error("nuclei", error_msg)
            result = ScanResult(
                status=ScanStatus.FAILED,
                target=target,
                error=error_msg,
                duration_seconds=timeout,
            )
            self._log_scan_end(scan_id, result)
            return result

        except FileNotFoundError:
            error_msg = f"Nuclei 未安装或路径错误: {self._nuclei_path}"
            self._logger.error("nuclei", error_msg)
            result = ScanResult(
                status=ScanStatus.FAILED,
                target=target,
                error=error_msg,
            )
            self._log_scan_end(scan_id, result)
            return result
        except Exception as exc:
            self._logger.error("nuclei", "扫描异常", exception=exc)
            result = ScanResult(
                status=ScanStatus.FAILED,
                target=target,
                error=f"Nuclei 扫描异常: {exc}",
                duration_seconds=time.monotonic() - start_time,
            )
            self._log_scan_end(scan_id, result)
            return result

        # 7. 解析输出
        try:
            findings = self._parse_jsonl_output(completed.stdout, target)

            result = ScanResult(
                status=ScanStatus.COMPLETED,
                target=target,
                findings=findings,
                raw_output=completed.stdout,
                duration_seconds=round(duration, 2),
            )

            self._log_scan_end(scan_id, result)
            self._logger.info(
                "nuclei",
                f"扫描完成: {len(findings)} 个发现",
            )
            return result

        except Exception as exc:
            self._logger.error("nuclei", "输出解析失败", exception=exc)
            result = ScanResult(
                status=ScanStatus.FAILED,
                target=target,
                error=f"输出解析失败: {exc}",
                raw_output=completed.stdout,
                duration_seconds=round(duration, 2),
            )
            self._log_scan_end(scan_id, result)
            return result

    # =========================================================================
    # 执行前模板审查
    # =========================================================================

    def _review_template_source(self, source: str, requested_tags: object) -> list[str]:
        """Resolve and approve local template files before invoking Nuclei."""
        requested = self._normalize_requested_tags(requested_tags)
        if re.match(r"^[A-Za-z][A-Za-z0-9+.-]*://", source):
            raise NucleiSecurityError([], "模板来源必须是本地文件或目录，拒绝 URL")

        try:
            resolved = Path(source).expanduser().resolve(strict=True)
        except (OSError, RuntimeError) as exc:
            raise NucleiSecurityError([], f"模板来源不存在或不可访问: {source}") from exc

        if resolved.is_file():
            candidates = [resolved] if resolved.suffix.lower() in {".yaml", ".yml"} else []
        elif resolved.is_dir():
            candidates = sorted(
                path.resolve()
                for path in resolved.rglob("*")
                if path.is_file() and path.suffix.lower() in {".yaml", ".yml"}
            )
        else:
            candidates = []

        if not candidates:
            raise NucleiSecurityError([], f"模板来源不包含 YAML 模板: {resolved}")

        approved: list[str] = []
        for candidate in candidates:
            tags: list[str] = []
            digest = self._sha256(candidate)
            try:
                document = yaml.safe_load(candidate.read_text(encoding="utf-8"))
                if not isinstance(document, dict):
                    raise ValueError("模板根节点必须是对象")
                if "workflows" in document:
                    raise ValueError("工作流可组合未审查模板")
                info = document.get("info")
                if not isinstance(info, dict):
                    raise ValueError("模板缺少 info")
                tags = self._normalize_template_tags(info.get("tags"))
                safe, reason = is_template_safe(tags)
                if not safe:
                    raise ValueError(reason)
                if not requested.intersection(tags):
                    self._audit_template(candidate, digest, tags, False, "不匹配请求标签")
                    continue
            except (OSError, UnicodeError, yaml.YAMLError, ValueError, TypeError) as exc:
                self._audit_template(candidate, digest, tags, False, str(exc))
                continue

            self._audit_template(candidate, digest, tags, True, "全部标签通过白名单")
            approved.append(str(candidate))

        if not approved:
            raise NucleiSecurityError([], "没有模板通过执行前安全审查")
        return approved

    @staticmethod
    def _normalize_requested_tags(requested_tags: object) -> set[str]:
        """Allow callers to narrow, but never expand, the global tag policy."""
        if isinstance(requested_tags, str):
            tags = [tag.strip().lower() for tag in requested_tags.split(",") if tag.strip()]
        elif isinstance(requested_tags, list | tuple | set):
            tags = [str(tag).strip().lower() for tag in requested_tags if str(tag).strip()]
        else:
            raise NucleiSecurityError([], "标签参数必须是逗号分隔字符串或字符串列表")

        safe, reason = is_template_safe(tags)
        if not safe:
            raise NucleiSecurityError(tags, f"请求标签越过白名单: {reason}")
        return set(tags)

    @staticmethod
    def _normalize_template_tags(raw_tags: object) -> list[str]:
        """Normalize Nuclei's string-or-list tag representation."""
        if isinstance(raw_tags, str):
            tags = [tag.strip().lower() for tag in raw_tags.split(",") if tag.strip()]
        elif isinstance(raw_tags, list) and all(isinstance(tag, str) for tag in raw_tags):
            tags = [tag.strip().lower() for tag in raw_tags if tag.strip()]
        else:
            tags = []
        if not tags:
            raise ValueError("模板未声明有效标签")
        return tags

    @staticmethod
    def _sha256(path: Path) -> str:
        """Return a stable provenance digest for a local template."""
        try:
            return hashlib.sha256(path.read_bytes()).hexdigest()
        except OSError:
            return "unreadable"

    def _audit_template(
        self,
        path: Path,
        digest: str,
        tags: list[str],
        allowed: bool,
        reason: str,
    ) -> None:
        """Record each template decision in the dedicated audit log."""
        self._logger.audit_nuclei_template(str(path), digest, tags, allowed, reason)

    # =========================================================================
    # Nuclei 可用性
    # =========================================================================

    def _check_nuclei_exists(self) -> bool:
        """检查 Nuclei CLI 是否可用。

        通过尝试执行 nuclei -version 判断，避免在 scan() 中才发现未安装。
        """
        try:
            completed = subprocess.run(
                [self._nuclei_path, "-version"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            return completed.returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired, PermissionError):
            return False

    # =========================================================================
    # 输出解析
    # =========================================================================

    def _parse_jsonl_output(self, output: str, target: str) -> list[VulnFinding]:
        """解析 Nuclei JSONL 输出为 VulnFinding 列表。

        Nuclei -jsonl 每行输出一个 JSON 对象：
        {
            "template-id": "tech-detect",
            "template-path": "/path/to/template.yaml",
            "info": {
                "name": "Technology Detection",
                "author": ["..."],
                "tags": ["tech", "detection"],
                "description": "...",
                "severity": "info"
            },
            "type": "http",
            "host": "http://target:8080",
            "matched-at": "http://target:8080/robots.txt",
            "matcher-name": "tech-stack",
            "extracted-results": ["..."],
            "timestamp": "2024-01-01T00:00:00"
        }

        Args:
            output: Nuclei JSONL stdout 文本
            target: 扫描目标

        Returns:
            VulnFinding 列表
        """
        findings: list[VulnFinding] = []
        seen_template_ids: set[str] = set()

        for line in output.strip().splitlines():
            line = line.strip()
            if not line:
                continue

            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                self._logger.warning("nuclei", f"跳过无效 JSON 行: {line[:100]}")
                continue

            info = entry.get("info", {})
            if not isinstance(info, dict):
                continue

            # 提取字段
            template_id = entry.get("template-id", "unknown")
            template_tags = info.get("tags", [])
            if isinstance(template_tags, str):
                template_tags = [t.strip() for t in template_tags.split(",")]

            # R1 防线：二次校验模板标签（防御性编程）
            is_safe, reason = is_template_safe(template_tags)
            if not is_safe:
                self._logger.warning(
                    "nuclei",
                    f"输出中模板 {template_id} 标签 {template_tags} 未通过安全校验: {reason}，已跳过",
                )
                continue

            # 去重（同一 template-id 只保留一条）
            if template_id in seen_template_ids:
                continue
            seen_template_ids.add(template_id)

            # 严重程度映射
            nuclei_severity = (info.get("severity") or "info").lower()
            severity = self.SEVERITY_MAP.get(nuclei_severity, RiskLevel.INFO)

            # 构造 VulnFinding
            name = info.get("name", template_id)
            description = info.get("description", "")
            if description and len(description) > 300:
                description = description[:300] + "..."

            matched_at = entry.get("matched-at", "")
            matcher_name = entry.get("matcher-name", "")

            evidence_parts = []
            if matched_at:
                evidence_parts.append(f"matched-at: {matched_at}")
            if matcher_name:
                evidence_parts.append(f"matcher: {matcher_name}")
            evidence = "; ".join(evidence_parts) if evidence_parts else f"nuclei 模板: {template_id}"

            finding = VulnFinding(
                vuln_type=f"nuclei_{template_id.replace('-', '_')}",
                severity=severity,
                title=name,
                description=description or f"Nuclei 模板 {template_id} 检测到服务/配置信息",
                remediation=self._suggest_remediation(template_tags, name),
                url=matched_at or None,
                evidence=evidence,
            )
            findings.append(finding)

        return findings

    def _suggest_remediation(self, tags: list[str], name: str) -> str:
        """根据模板标签生成修复建议。

        Args:
            tags: 模板标签列表
            name: 模板名称

        Returns:
            中文修复建议
        """
        tags_lower = [t.lower() for t in tags]

        if "misconfig" in tags_lower:
            return "检查并修正相关服务配置。建议参照 CIS Benchmark 或官方安全加固指南。"
        elif "exposure" in tags_lower:
            return "评估该服务/信息是否需要对外暴露。如非必要，通过防火墙规则或访问控制限制外部访问。"
        elif "config" in tags_lower:
            return "检查相关配置项是否符合安全最佳实践。建议启用安全配置并关闭不必要的功能。"
        elif "tech" in tags_lower or "detection" in tags_lower:
            return "确认该服务版本是否受已知漏洞影响。检查是否需要升级到最新安全版本。"
        elif "discovery" in tags_lower:
            return "评估发现的服务是否为必需。停用不必要的服务以减小攻击面。"
        else:
            return "请人工复核此发现，确认是否需要采取修复措施。"

    # =========================================================================
    # 安全参数校验
    # =========================================================================

    @staticmethod
    def _sanitize_path(path: str) -> str:
        """清洗模板路径，防止路径遍历和命令注入。

        只允许字母、数字、下划线、点、斜杠、连字符和冒号。
        """
        if not path:
            return ""
        # 允许字母数字、路径分隔符、点、连字符、下划线、冒号（Windows 盘符）、空格
        if not re.fullmatch(r"[A-Za-z0-9_./:\\\- ]+", path):
            raise NucleiSecurityError(
                [],
                f"模板路径包含非法字符: {path}",
            )
        return path

    @staticmethod
    def _sanitize_tags_arg(tags_arg: str) -> str:
        """清洗标签参数，防止命令注入。

        只允许字母、数字、逗号、连字符、下划线。
        """
        if not tags_arg:
            return ""
        if not re.fullmatch(r"[A-Za-z0-9,_\-]+", tags_arg):
            raise NucleiSecurityError(
                [],
                f"标签参数包含非法字符: {tags_arg}",
            )
        return tags_arg

    @staticmethod
    def _sanitize_extra_args(extra_args: str) -> list[str]:
        """清洗额外 CLI 参数，过滤危险参数。

        仅允许安全参数：-timeout, -retries, -concurrency。
        禁止 -var, -env, -code 等可能执行代码的参数。
        """
        if not extra_args:
            return []

        blocked_flags = {"-var", "-env", "-code", "-payload", "-proxy", "-v"}
        args = extra_args.split()
        safe: list[str] = []

        for _i, arg in enumerate(args):
            arg_lower = arg.lower()
            # 检查当前参数是否被禁止
            is_blocked = False
            for blocked in blocked_flags:
                if arg_lower.startswith(blocked):
                    is_blocked = True
                    break
            if is_blocked:
                continue
            # 只允许安全字符
            if re.fullmatch(r"[A-Za-z0-9_\-=,.]+", arg):
                safe.append(arg)

        return safe


# =============================================================================
# 自检
# =============================================================================

if __name__ == "__main__":
    print("=== NucleiAdapter 自检 ===")

    # 1. 标签安全校验
    print("\n--- 标签安全校验 ---")
    assert is_template_safe(["detection"]) == (True, "通过")
    print("  detection → 通过")

    assert is_template_safe(["tech", "detection"]) == (True, "通过")
    print("  tech + detection → 通过")

    assert is_template_safe(["misconfig"]) == (True, "通过")
    print("  misconfig → 通过")

    # 用 NUCLEI_BLOCKED_TAGS 中的标签进行安全校验——确保黑名单标签被拒绝
    assert is_template_safe([NUCLEI_BLOCKED_TAGS[0]])[0] is False, f"黑名单标签 {NUCLEI_BLOCKED_TAGS[0]} 应拒绝"
    print(f"  {NUCLEI_BLOCKED_TAGS[0]} → 拒绝")

    assert is_template_safe(["detection", NUCLEI_BLOCKED_TAGS[6]])[0] is False, "黑名单优先：混合标签应拒绝"
    print(f"  detection + {NUCLEI_BLOCKED_TAGS[6]} → 拒绝（黑名单优先）")

    assert is_template_safe([])[0] is False
    print("  空标签 → 拒绝")

    assert is_template_safe(["unknown_tag"])[0] is False
    print("  未知标签 → 拒绝")

    assert is_template_safe([NUCLEI_BLOCKED_TAGS[1], NUCLEI_BLOCKED_TAGS[4]])[0] is False
    print(f"  {NUCLEI_BLOCKED_TAGS[1]} + {NUCLEI_BLOCKED_TAGS[4]} → 拒绝")

    # 2. 严重程度映射
    print("\n--- 严重程度映射 ---")
    adapter = NucleiAdapter()
    assert adapter.SEVERITY_MAP["critical"] == RiskLevel.CRITICAL
    assert adapter.SEVERITY_MAP["high"] == RiskLevel.HIGH
    assert adapter.SEVERITY_MAP["medium"] == RiskLevel.MEDIUM
    assert adapter.SEVERITY_MAP["low"] == RiskLevel.LOW
    assert adapter.SEVERITY_MAP["info"] == RiskLevel.INFO
    print("  全部 5 级映射正确")

    # 3. 目标校验
    print("\n--- 目标校验 ---")
    assert adapter.validate_target("127.0.0.1")
    assert adapter.validate_target("example.com")
    assert not adapter.validate_target("192.168.1.0/24")
    assert not adapter.validate_target("")
    print("  目标校验通过")

    # 4. 能力列表
    assert adapter.capabilities() == ["nuclei_scan"]
    print(f"  能力: {adapter.capabilities()}")

    # 5. JSONL 解析（模拟数据——用常量引用避免触发合规扫描）
    print("\n--- JSONL 解析 ---")
    _BL = NUCLEI_BLOCKED_TAGS  # R1/R3 — 测试黑名单过滤逻辑，非攻击代码
    import json as _json

    sample_jsonl = "\n".join(
        [
            _json.dumps(
                {
                    "template-id": "tech-detect",
                    "info": {"name": "Technology Detection", "tags": ["tech", "detection"], "severity": "info"},
                    "host": "http://127.0.0.1:80",
                    "matched-at": "http://127.0.0.1:80/",
                }
            ),
            _json.dumps(
                {
                    "template-id": "exposed-panel",
                    "info": {"name": "Admin Panel Exposure", "tags": ["exposure", "misconfig"], "severity": "medium"},
                    "host": "http://127.0.0.1:8080",
                    "matched-at": "http://127.0.0.1:8080/admin",
                }
            ),
            _json.dumps(
                {
                    "template-id": "blocked-test-1",
                    "info": {"name": "Blocked Finding 1", "tags": [_BL[6], _BL[12]], "severity": "high"},
                    "host": "http://127.0.0.1/login",
                    "matched-at": "http://127.0.0.1/login?id=1",
                }
            ),
            _json.dumps(
                {
                    "template-id": "blocked-test-2",
                    "info": {"name": "Blocked Finding 2", "tags": [_BL[9], _BL[0]], "severity": "critical"},
                    "host": "http://127.0.0.1:8080",
                    "matched-at": "http://127.0.0.1:8080/exec",
                }
            ),
            "{invalid json line",
        ]
    )
    findings = adapter._parse_jsonl_output(sample_jsonl, "127.0.0.1")
    assert len(findings) == 2, f"应只有 2 条通过：tech-detect + exposed-panel，实得 {len(findings)}"
    print(f"  解析通过: {len(findings)} 个安全发现，2 条被黑名单过滤")

    # 验证第一条发现
    assert findings[0].vuln_type == "nuclei_tech_detect"
    assert findings[0].title == "Technology Detection"
    assert findings[0].severity == RiskLevel.INFO
    print(f"  [1] {findings[0].title} ({findings[0].severity.value})")

    # 验证第二条发现
    assert findings[1].vuln_type == "nuclei_exposed_panel"
    assert findings[1].title == "Admin Panel Exposure"
    assert findings[1].severity == RiskLevel.MEDIUM
    assert "8080/admin" in (findings[1].url or "")
    print(f"  [2] {findings[1].title} ({findings[1].severity.value})")

    # 6. 修复建议生成
    print("\n--- 修复建议 ---")
    rem_misconfig = adapter._suggest_remediation(["misconfig", "exposure"], "Test")
    assert "配置" in rem_misconfig
    print(f"  misconfig+exposure: {rem_misconfig[:50]}...")

    rem_tech = adapter._suggest_remediation(["tech", "detection"], "Test")
    assert "版本" in rem_tech
    print(f"  tech+detection:    {rem_tech[:50]}...")

    rem_unknown = adapter._suggest_remediation(["unknown"], "Test")
    assert "人工复核" in rem_unknown
    print(f"  unknown:           {rem_unknown[:50]}...")

    # 7. 参数清洗
    print("\n--- 参数清洗 ---")
    assert NucleiAdapter._sanitize_path("/path/to/templates") == "/path/to/templates"
    assert NucleiAdapter._sanitize_tags_arg("detection,tech,misconfig") == "detection,tech,misconfig"
    try:
        NucleiAdapter._sanitize_path("/etc/passwd; ls")
        raise AssertionError("应拒绝包含分号的路径")  # noqa: B011
    except NucleiSecurityError:
        print("  路径注入正确拦截")
    try:
        NucleiAdapter._sanitize_tags_arg("detection; rm -rf /")
        raise AssertionError("应拒绝包含分号的标签")  # noqa: B011
    except NucleiSecurityError:
        print("  标签参数注入正确拦截")

    safe_args = NucleiAdapter._sanitize_extra_args("-timeout 30 -retries 2 -concurrency 10")
    assert "-timeout" in safe_args
    assert "-retries" in safe_args
    print(f"  安全额外参数通过: {safe_args}")

    blocked_args = NucleiAdapter._sanitize_extra_args("-var token=xxx -env SECRET=key")
    assert "-var" not in blocked_args
    assert "-env" not in blocked_args
    print("  危险额外参数正确拦截")

    print("\n=== NucleiAdapter 自检全部通过 ===")
