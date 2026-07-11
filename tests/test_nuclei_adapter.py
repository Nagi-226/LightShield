"""NucleiAdapter 单元测试。

覆盖 LightShield R1 + R5 合规防线：
- 标签白名单允许安全检测标签。
- 标签黑名单优先拒绝攻击标签。
- 空标签/未知标签必须拒绝。
- scan() mock subprocess 验证完整流程。
- JSONL 输出解析正确性。
- 参数注入防护。
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

# Allow direct script execution or pytest from tests/ directory.
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from lightshield.adapters.nuclei_adapter import (
    NucleiAdapter,
    NucleiSecurityError,
    is_template_safe,
)
from lightshield.utils.constants import RiskLevel, ScanStatus

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def adapter(tmp_path_factory: pytest.TempPathFactory) -> NucleiAdapter:
    """创建 NucleiAdapter 实例（不依赖真实 nuclei CLI）。"""
    templates_dir = tmp_path_factory.mktemp("nuclei-default-templates")
    (templates_dir / "default.yaml").write_text(
        "id: default\ninfo:\n  name: Default\n  author: test\n  severity: info\n  tags: detection\nhttp:\n  - method: GET\n",
        encoding="utf-8",
    )
    return NucleiAdapter(nuclei_path="nuclei", templates_dir=str(templates_dir))


# =============================================================================
# is_template_safe() 单元测试
# =============================================================================


class TestIsTemplateSafe:
    """标签安全校验函数测试。"""

    @pytest.mark.parametrize(
        "tags",
        [
            ["detection"],
            ["discovery"],
            ["tech"],
            ["config"],
            ["exposure"],
            ["enum"],
            ["misconfig"],
            ["token-spray"],
            ["tech", "detection"],
            ["detection", "discovery", "tech"],
            ["exposure", "misconfig"],
        ],
    )
    def test_allowed_tags_pass(self, tags: list[str]) -> None:
        """白名单标签应通过校验。"""
        is_safe, reason = is_template_safe(tags)
        assert is_safe is True, f"tags={tags} 应通过: {reason}"

    @pytest.mark.parametrize(
        "tags",
        [
            ["exploit"],
            ["intrusive"],
            ["attack"],
            ["dos"],
            ["fuzz"],
            ["bruteforce"],
            ["sqli"],
            ["xss"],
            ["rce"],
            ["lfi"],
            ["ssrf"],
            ["injection"],
        ],
    )
    def test_blocked_tags_rejected(self, tags: list[str]) -> None:
        """黑名单标签应拒绝。"""
        is_safe, reason = is_template_safe(tags)
        assert is_safe is False, f"tags={tags} 应被拒绝"

    def test_blacklist_has_priority(self) -> None:
        """黑名单优先：即使同时有白名单标签，命中黑名单也应拒绝。"""
        is_safe, reason = is_template_safe(["detection", "sqli"])
        assert is_safe is False, "detection + sqli 应因 sqli 黑名单而拒绝"

        is_safe, reason = is_template_safe(["tech", "exploit"])
        assert is_safe is False, "tech + exploit 应因 exploit 黑名单而拒绝"

        is_safe, reason = is_template_safe(["misconfig", "rce"])
        assert is_safe is False, "misconfig + rce 应因 rce 黑名单而拒绝"

    def test_empty_tags_rejected(self) -> None:
        """空标签列表必须拒绝——无法确认安全性。"""
        is_safe, reason = is_template_safe([])
        assert is_safe is False

    def test_unknown_tags_rejected(self) -> None:
        """未知标签（不在白名单也不在黑名单）应拒绝——默认拒绝策略。"""
        is_safe, reason = is_template_safe(["unknown-tag"])
        assert is_safe is False

    def test_allowed_tag_does_not_mask_unknown_tag(self) -> None:
        """Every declared tag must be allowlisted, not merely one of them."""
        is_safe, reason = is_template_safe(["detection", "custom-action"])

        assert is_safe is False
        assert "custom-action" in reason

    def test_case_insensitive(self) -> None:
        """标签匹配应不区分大小写。"""
        is_safe, reason = is_template_safe(["Detection"])
        assert is_safe is True, f"Detection (大小写变体) 应通过: {reason}"

        is_safe, reason = is_template_safe(["Exploit"])
        assert is_safe is False, "Exploit (大小写变体) 应拒绝"


# =============================================================================
# NucleiAdapter 单元测试
# =============================================================================


class TestNucleiAdapterBasics:
    """适配器基础功能测试。"""

    def test_capabilities(self, adapter: NucleiAdapter) -> None:
        """能力列表应返回 nuclei_scan。"""
        caps = adapter.capabilities()
        assert caps == ["nuclei_scan"]

    def test_validate_target_accepts_valid(self, adapter: NucleiAdapter) -> None:
        """合法目标应通过校验。"""
        assert adapter.validate_target("127.0.0.1") is True
        assert adapter.validate_target("example.com") is True

    def test_validate_target_rejects_invalid(self, adapter: NucleiAdapter) -> None:
        """非法目标应拒绝。"""
        assert adapter.validate_target("192.168.1.0/24") is False
        assert adapter.validate_target("") is False

    def test_severity_map_coverage(self, adapter: NucleiAdapter) -> None:
        """严重程度映射应覆盖所有 Nuclei 级别。"""
        expected = {"critical", "high", "medium", "low", "info", "unknown"}
        assert set(adapter.SEVERITY_MAP.keys()) == expected


# =============================================================================
# JSONL 解析测试
# =============================================================================


class TestParseJsonlOutput:
    """Nuclei JSONL 输出解析测试。"""

    def test_parses_safe_findings(self, adapter: NucleiAdapter) -> None:
        """安全标签模板的 JSONL 输出应正确解析。"""
        sample = json.dumps(
            {
                "template-id": "tech-detect",
                "info": {
                    "name": "Technology Detection",
                    "tags": ["tech", "detection"],
                    "severity": "info",
                    "description": "Detects technology stack",
                },
                "type": "http",
                "host": "http://127.0.0.1",
                "matched-at": "http://127.0.0.1/",
            }
        )

        findings = adapter._parse_jsonl_output(sample, "127.0.0.1")
        assert len(findings) == 1
        assert findings[0].vuln_type == "nuclei_tech_detect"
        assert findings[0].title == "Technology Detection"
        assert findings[0].severity == RiskLevel.INFO

    def test_filters_blocked_tags(self, adapter: NucleiAdapter) -> None:
        """黑名单标签模板应从结果中过滤掉。"""
        lines = "\n".join(
            [
                json.dumps(
                    {
                        "template-id": "safe-finding",
                        "info": {"name": "Safe", "tags": ["detection"], "severity": "info"},
                        "matched-at": "http://127.0.0.1/",
                    }
                ),
                json.dumps(
                    {
                        "template-id": "sqli-finding",
                        "info": {"name": "SQLi", "tags": ["sqli", "injection"], "severity": "high"},
                        "matched-at": "http://127.0.0.1/login",
                    }
                ),
                json.dumps(
                    {
                        "template-id": "rce-test",
                        "info": {"name": "RCE", "tags": ["rce", "exploit"], "severity": "critical"},
                        "matched-at": "http://127.0.0.1/exec",
                    }
                ),
            ]
        )

        findings = adapter._parse_jsonl_output(lines, "127.0.0.1")
        assert len(findings) == 1, f"应只有 1 条通过 (safe-finding)，实得 {len(findings)}"
        assert findings[0].vuln_type == "nuclei_safe_finding"

    def test_deduplicates_same_template_id(self, adapter: NucleiAdapter) -> None:
        """同一 template-id 只保留第一条。"""
        lines = "\n".join(
            [
                json.dumps(
                    {
                        "template-id": "dup-test",
                        "info": {"name": "First", "tags": ["detection"], "severity": "info"},
                        "matched-at": "http://127.0.0.1/a",
                    }
                ),
                json.dumps(
                    {
                        "template-id": "dup-test",
                        "info": {"name": "Second", "tags": ["detection"], "severity": "info"},
                        "matched-at": "http://127.0.0.1/b",
                    }
                ),
                json.dumps(
                    {
                        "template-id": "other-test",
                        "info": {"name": "Other", "tags": ["tech"], "severity": "info"},
                        "matched-at": "http://127.0.0.1/c",
                    }
                ),
            ]
        )

        findings = adapter._parse_jsonl_output(lines, "127.0.0.1")
        assert len(findings) == 2
        assert findings[0].title == "First"  # 去重保留第一条

    def test_handles_invalid_json_gracefully(self, adapter: NucleiAdapter) -> None:
        """无效 JSON 行应跳过（不崩溃）。"""
        lines = "{invalid json\n" + json.dumps(
            {
                "template-id": "valid",
                "info": {"name": "Valid", "tags": ["detection"], "severity": "info"},
            }
        )

        findings = adapter._parse_jsonl_output(lines, "127.0.0.1")
        assert len(findings) == 1

    def test_handles_empty_output(self, adapter: NucleiAdapter) -> None:
        """空输出应返回空列表。"""
        findings = adapter._parse_jsonl_output("", "127.0.0.1")
        assert findings == []

    def test_handles_tags_as_string(self, adapter: NucleiAdapter) -> None:
        """标签为逗号分隔字符串也应正确解析。"""
        sample = json.dumps(
            {
                "template-id": "test",
                "info": {
                    "name": "Test",
                    "tags": "tech, detection, config",
                    "severity": "low",
                },
            }
        )

        findings = adapter._parse_jsonl_output(sample, "127.0.0.1")
        assert len(findings) == 1
        assert findings[0].vuln_type == "nuclei_test"

    def test_severity_mapping_all_levels(self, adapter: NucleiAdapter) -> None:
        """所有严重程度级别应正确映射。"""
        tests = [
            ("critical", RiskLevel.CRITICAL),
            ("high", RiskLevel.HIGH),
            ("medium", RiskLevel.MEDIUM),
            ("low", RiskLevel.LOW),
            ("info", RiskLevel.INFO),
            ("unknown", RiskLevel.INFO),
        ]
        for nuclei_sev, expected in tests:
            line = json.dumps(
                {
                    "template-id": f"test-{nuclei_sev}",
                    "info": {"name": "Test", "tags": ["detection"], "severity": nuclei_sev},
                }
            )
            findings = adapter._parse_jsonl_output(line, "127.0.0.1")
            assert len(findings) == 1
            assert findings[0].severity == expected, f"{nuclei_sev} → {expected}"


# =============================================================================
# 修复建议测试
# =============================================================================


class TestSuggestRemediation:
    """修复建议生成测试。"""

    def test_misconfig_remediation(self, adapter: NucleiAdapter) -> None:
        """错误配置标签应生成配置修复建议。"""
        result = adapter._suggest_remediation(["misconfig"], "Test")
        assert "配置" in result

    def test_exposure_remediation(self, adapter: NucleiAdapter) -> None:
        """暴露面标签应生成访问控制建议。"""
        result = adapter._suggest_remediation(["exposure"], "Test")
        assert "暴露" in result or "访问控制" in result

    def test_tech_detection_remediation(self, adapter: NucleiAdapter) -> None:
        """技术检测标签应生成版本升级建议。"""
        result = adapter._suggest_remediation(["tech", "detection"], "Test")
        assert "版本" in result

    def test_unknown_remediation(self, adapter: NucleiAdapter) -> None:
        """未知标签应建议人工复核。"""
        result = adapter._suggest_remediation(["unknown"], "Test")
        assert "人工复核" in result


# =============================================================================
# scan() mock 测试
# =============================================================================


class TestScanWithMockSubprocess:
    """scan() 方法 mock subprocess 测试。"""

    def test_scan_success_with_mocked_nuclei(self, adapter: NucleiAdapter) -> None:
        """Mock nuclei 成功执行时应返回 COMPLETED 结果。"""
        fake_output = json.dumps(
            {
                "template-id": "tech-detect",
                "template-path": "/templates/tech.yaml",
                "info": {
                    "name": "Technology Detection",
                    "author": ["test"],
                    "tags": ["tech", "detection"],
                    "description": "Detects technology",
                    "severity": "info",
                },
                "type": "http",
                "host": "http://127.0.0.1",
                "matched-at": "http://127.0.0.1/",
            }
        )

        # Mock: nuclei -version (check) + nuclei -u ... (scan)
        fake_version = SimpleNamespace(returncode=0, stdout="nuclei v3.0.0", stderr="")
        fake_scan = SimpleNamespace(returncode=0, stdout=fake_output, stderr="")

        with patch(
            "lightshield.adapters.nuclei_adapter.subprocess.run",
            side_effect=[fake_version, fake_scan],
        ) as mocked_run:
            result = adapter.scan("127.0.0.1")

        assert result.status == ScanStatus.COMPLETED, f"扫描应成功，实际: {result.error}"
        assert result.target == "127.0.0.1"
        assert len(result.findings) == 1
        assert result.findings[0].vuln_type == "nuclei_tech_detect"
        assert result.findings[0].title == "Technology Detection"
        # 验证超时设置
        scan_call = mocked_run.call_args_list[1]
        assert scan_call.kwargs["timeout"] == 120, "默认超时应为 120s"

    def test_scan_returns_failed_when_nuclei_not_installed(self, adapter: NucleiAdapter) -> None:
        """Nuclei 未安装时应返回 FAILED。"""
        with patch(
            "lightshield.adapters.nuclei_adapter.subprocess.run",
            side_effect=FileNotFoundError("nuclei not found"),
        ):
            result = adapter.scan("127.0.0.1")

        assert result.status == ScanStatus.FAILED
        assert result.error and "未安装" in result.error

    def test_scan_returns_failed_when_nuclei_version_fails(self, adapter: NucleiAdapter) -> None:
        """Nuclei -version 失败时应返回 FAILED。"""
        fake_version = SimpleNamespace(returncode=1, stdout="", stderr="command not found")

        with patch(
            "lightshield.adapters.nuclei_adapter.subprocess.run",
            return_value=fake_version,
        ):
            result = adapter.scan("127.0.0.1")

        assert result.status == ScanStatus.FAILED
        assert result.error and "未安装" in result.error

    def test_scan_returns_failed_for_invalid_target(self, adapter: NucleiAdapter) -> None:
        """非法目标应在 subprocess 执行前拦截。"""
        with patch("lightshield.adapters.nuclei_adapter.subprocess.run") as mocked_run:
            result = adapter.scan("192.168.1.0/24")

        assert result.status == ScanStatus.FAILED
        assert result.error and "目标校验不通过" in result.error
        assert mocked_run.called is False, "非法目标不得触发 subprocess"

    def test_scan_handles_timeout(self, adapter: NucleiAdapter) -> None:
        """Nuclei 超时应返回 FAILED 并包含超时信息。"""
        import subprocess as sp

        fake_version = SimpleNamespace(returncode=0, stdout="nuclei v3.0.0", stderr="")

        with patch(
            "lightshield.adapters.nuclei_adapter.subprocess.run",
            side_effect=[fake_version, sp.TimeoutExpired(cmd=["nuclei"], timeout=120)],
        ):
            result = adapter.scan("127.0.0.1", timeout=10)

        assert result.status == ScanStatus.FAILED
        assert "超时" in (result.error or "")

    def test_scan_passes_target_to_nuclei(self, adapter: NucleiAdapter) -> None:
        """Nuclei 命令应正确传入目标地址。"""
        fake_version = SimpleNamespace(returncode=0, stdout="nuclei v3.0.0", stderr="")
        fake_scan = SimpleNamespace(returncode=0, stdout="", stderr="")

        with patch(
            "lightshield.adapters.nuclei_adapter.subprocess.run",
            side_effect=[fake_version, fake_scan],
        ) as mocked_run:
            adapter.scan("example.com")

        # 第二个调用 (scan) 的 cmd 应包含 -u example.com
        scan_call = mocked_run.call_args_list[1]
        cmd = scan_call[0][0]
        assert "-u" in cmd
        assert "example.com" in cmd


class TestPreExecutionTemplateReview:
    """Template policy must run before every Nuclei subprocess."""

    @staticmethod
    def _write_template(path: Path, *, tags: str, body: str = "http:\n  - method: GET\n") -> Path:
        path.write_text(
            f"id: test-template\ninfo:\n  name: Test\n  author: test\n  severity: info\n  tags: {tags}\n{body}",
            encoding="utf-8",
        )
        return path

    def test_caller_cannot_expand_tags_outside_allowlist(self, adapter: NucleiAdapter, tmp_path: Path) -> None:
        """Caller tag overrides may narrow policy but never expand it."""
        self._write_template(tmp_path / "safe.yaml", tags="detection")

        with patch("lightshield.adapters.nuclei_adapter.subprocess.run") as run:
            result = adapter.scan("127.0.0.1", templates=str(tmp_path), tags="exploit")

        assert result.status == ScanStatus.FAILED
        run.assert_not_called()

    def test_mixed_safe_and_blocked_template_never_executes(self, adapter: NucleiAdapter, tmp_path: Path) -> None:
        """A safe-looking tag cannot mask a blocked side-effecting tag."""
        self._write_template(tmp_path / "mixed.yaml", tags="detection,exploit")

        with patch("lightshield.adapters.nuclei_adapter.subprocess.run") as run:
            result = adapter.scan("127.0.0.1", templates=str(tmp_path))

        assert result.status == ScanStatus.FAILED
        run.assert_not_called()

    def test_url_template_source_is_rejected_before_version_probe(self, adapter: NucleiAdapter) -> None:
        """Remote templates cannot bypass local provenance review."""
        with patch("lightshield.adapters.nuclei_adapter.subprocess.run") as run:
            result = adapter.scan("127.0.0.1", templates="https://example.com/template.yaml")

        assert result.status == ScanStatus.FAILED
        run.assert_not_called()

    def test_workflow_source_is_rejected_before_version_probe(self, adapter: NucleiAdapter, tmp_path: Path) -> None:
        """Nuclei workflows can compose unreviewed templates and are denied."""
        workflow = tmp_path / "workflow.yaml"
        workflow.write_text(
            "id: workflow\ninfo:\n  name: Workflow\n  author: test\n  tags: detection\nworkflows:\n  - template: child.yaml\n",
            encoding="utf-8",
        )

        with patch("lightshield.adapters.nuclei_adapter.subprocess.run") as run:
            result = adapter.scan("127.0.0.1", templates=str(workflow))

        assert result.status == ScanStatus.FAILED
        run.assert_not_called()

    def test_scan_command_contains_only_explicit_reviewed_files(self, adapter: NucleiAdapter, tmp_path: Path) -> None:
        """The original directory must never reach the Nuclei process."""
        first = self._write_template(tmp_path / "first.yaml", tags="detection")
        second = self._write_template(tmp_path / "second.yml", tags="misconfig")
        fake_version = SimpleNamespace(returncode=0, stdout="nuclei v3", stderr="")
        fake_scan = SimpleNamespace(returncode=0, stdout="", stderr="")

        with patch(
            "lightshield.adapters.nuclei_adapter.subprocess.run",
            side_effect=[fake_version, fake_scan],
        ) as run:
            result = adapter.scan("127.0.0.1", templates=str(tmp_path))

        assert result.status == ScanStatus.COMPLETED
        cmd = run.call_args_list[1].args[0]
        assert str(tmp_path) not in cmd
        assert cmd.count("-t") == 2
        assert str(first.resolve()) in cmd
        assert str(second.resolve()) in cmd


# =============================================================================
# 参数清洗测试
# =============================================================================


class TestSanitizeArgs:
    """参数清洗安全测试。"""

    def test_sanitize_path_rejects_injection(self) -> None:
        """路径包含注入字符应拒绝。"""
        with pytest.raises(NucleiSecurityError):
            NucleiAdapter._sanitize_path("/etc/passwd; ls -la")

        with pytest.raises(NucleiSecurityError):
            NucleiAdapter._sanitize_path("templates && rm -rf /")

    def test_sanitize_tags_rejects_injection(self) -> None:
        """标签参数包含注入字符应拒绝。"""
        with pytest.raises(NucleiSecurityError):
            NucleiAdapter._sanitize_tags_arg("detection; rm -rf /")

        with pytest.raises(NucleiSecurityError):
            NucleiAdapter._sanitize_tags_arg("detection\ncritical")

    def test_sanitize_extra_args_blocks_dangerous_flags(self) -> None:
        """额外参数应过滤危险标志。"""
        safe = NucleiAdapter._sanitize_extra_args("-var token=xxx -env SECRET=key -proxy http://evil.com")
        assert "-var" not in safe
        assert "-env" not in safe
        assert "-proxy" not in safe

    def test_sanitize_extra_args_allows_safe_flags(self) -> None:
        """安全标志应保留。"""
        safe = NucleiAdapter._sanitize_extra_args("-timeout 30 -retries 2")
        assert "-timeout" in safe
        assert "30" in safe
        assert "-retries" in safe


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
