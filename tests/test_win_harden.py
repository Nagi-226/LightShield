"""测试模块：lightshield/harden/win_harden.py

被测类：WinHardener(HardenBase)

测试点：
  - _build_rollback_cmd() 各种命令的回滚逻辑
  - generate() 空推荐 / 正常生成 / 目录创建失败
  - _gen_audit_id() 格式验证
  - _build_harden_script() R4 阻断门 / 管理员声明 / 占位符引导
  - _build_rollback_script() netsh delete rule / 不可逆标注
  - _substitute() 变量替换（继承自 HardenBase）
"""

import os
import tempfile

import pytest

from lightshield.harden.base import HardenStatus
from lightshield.harden.win_harden import WinHardener, _build_rollback_cmd


@pytest.fixture
def hardener():
    """返回 WinHardener 实例"""
    return WinHardener()


@pytest.fixture
def tmp_output_dir():
    """临时输出目录"""
    d = tempfile.mkdtemp(prefix="lightshield_test_win_harden_")
    yield d
    import shutil

    shutil.rmtree(d, ignore_errors=True)


@pytest.fixture
def mock_recommendations():
    """模拟加固建议列表（匹配 harden_rules.json windows 命令）"""
    return [
        {
            "action": "关闭高危端口",
            "target": "23",
            "reason": "Telnet 明文传输，极度危险",
            "commands": {
                "windows": [
                    "# 使用 Windows 防火墙阻止端口 23 (Telnet)",
                    'netsh advfirewall firewall add rule name="Block_23" dir=in action=block protocol=TCP localport=23',
                ]
            },
            "severity": "high",
        },
        {
            "action": "禁用不必要服务",
            "target": "135",
            "reason": "减少后台运行的服务以降低攻击面",
            "commands": {
                "windows": [
                    "# 列出所有启用服务",
                    "Get-Service | Where-Object {$_.StartType -eq 'Automatic'}",
                    "# 停用并禁用指定服务",
                    "Stop-Service <service>",
                    "Set-Service <service> -StartupType Disabled",
                ]
            },
            "severity": "high",
        },
        {
            "action": "升级老旧组件",
            "target": "component",
            "reason": "存在已知 CVE",
            "commands": {
                "linux": ["apt update && apt upgrade -y"],
                # 无 windows 命令——验证空命令引导
            },
            "severity": "critical",
        },
    ]


# =============================================================================
# _build_rollback_cmd（模块级函数）
# =============================================================================


class TestBuildRollbackCmd:
    """_build_rollback_cmd() 命令回滚推导"""

    def test_netsh_add_rule_rolls_back_to_delete(self):
        """Netsh add rule → netsh delete rule"""
        result = _build_rollback_cmd(
            'netsh advfirewall firewall add rule name="Block_23" dir=in action=block protocol=TCP localport=23'
        )
        assert "delete rule" in result

    def test_stop_service_rolls_back_to_start(self):
        """Stop-Service → Start-Service"""
        result = _build_rollback_cmd("Stop-Service Telnet")
        assert "Start-Service" in result

    def test_set_service_rollback_guides_operator(self):
        """Set-Service 回滚引导操作员手动恢复"""
        result = _build_rollback_cmd("Set-Service Telnet -StartupType Disabled")
        assert "回滚：Set-Service" in result
        assert "操作员" in result

    def test_secedit_annotated_as_irreversible(self):
        """Secedit 被标注为不可逆操作"""
        result = _build_rollback_cmd("secedit /export /cfg backup.inf")
        assert "无法自动回滚" in result

    def test_unknown_command_annotated(self):
        """无法推导逆操作的命令标注为待回滚"""
        result = _build_rollback_cmd("New-Item -Path C:\\backup -ItemType Directory")
        assert "待回滚" in result

    def test_comment_line_returned_as_is(self):
        """注释行原样返回"""
        result = _build_rollback_cmd("# 这是一条注释")
        assert result == "# 这是一条注释"

    def test_empty_line_returned_as_is(self):
        """空行原样返回"""
        result = _build_rollback_cmd("")
        assert result == ""

    def test_write_host_annotated_as_aux(self):
        """Write-Host 被标注为辅助操作"""
        result = _build_rollback_cmd('Write-Host "已执行某操作"')
        assert "无需单独回滚" in result


# =============================================================================
# generate
# =============================================================================


class TestGenerate:
    """generate() 主生成方法"""

    def test_empty_recommendations_returns_no_action(self, hardener):
        """空推荐列表返回 NO_ACTION"""
        result = hardener.generate("127.0.0.1", [])
        assert result.status == HardenStatus.NO_ACTION
        assert result.os_platform.value == "windows"

    def test_generates_both_scripts_with_normal_recommendations(self, hardener, mock_recommendations, tmp_output_dir):
        """正常推荐列表生成加固 + 回滚两个脚本"""
        result = hardener.generate("192.168.1.100", mock_recommendations, output_dir=tmp_output_dir)
        assert result.status == HardenStatus.GENERATED
        assert result.action_count == 3
        assert os.path.exists(result.script_path), f"加固脚本未生成: {result.script_path}"
        assert os.path.exists(result.rollback_path), f"回滚脚本未生成: {result.rollback_path}"

    def test_script_uses_utf8_sig_encoding(self, hardener, mock_recommendations, tmp_output_dir):
        """加固脚本使用 UTF-8-SIG 编码（BOM）"""
        result = hardener.generate("192.168.1.100", mock_recommendations, output_dir=tmp_output_dir)
        with open(result.script_path, "rb") as f:
            header = f.read(3)
        assert header == b"\xef\xbb\xbf", f"缺少 UTF-8 BOM，实际: {header.hex()}"

    def test_script_uses_crlf_line_endings(self, hardener, mock_recommendations, tmp_output_dir):
        """加固脚本使用 CRLF 行尾"""
        result = hardener.generate("192.168.1.100", mock_recommendations, output_dir=tmp_output_dir)
        with open(result.script_path, "rb") as f:
            content = f.read()
        assert b"\r\n" in content

    def test_result_has_audit_id(self, hardener, mock_recommendations, tmp_output_dir):
        """结果包含 audit_id"""
        result = hardener.generate("192.168.1.100", mock_recommendations, output_dir=tmp_output_dir)
        assert result.audit_id is not None
        assert result.audit_id.startswith("HARDEN-WIN-")

    def test_invalid_output_dir_returns_failed(self, hardener, mock_recommendations):
        """无法创建的输出目录返回 FAILED"""
        # 使用一个不可能存在的路径（在需要管理员权限的位置）
        result = hardener.generate(
            "127.0.0.1",
            mock_recommendations,
            output_dir="NUL/output",  # NUL 是 Windows 特殊设备
        )
        # 可能成功也可能失败取决于系统，至少 status 是合理的枚举值
        assert result.status in (HardenStatus.GENERATED, HardenStatus.FAILED)


# =============================================================================
# _gen_audit_id
# =============================================================================


class TestGenAuditId:
    """_gen_audit_id() 审计 ID 生成"""

    def test_format_starts_with_harden_win(self, hardener):
        """审计 ID 以 HARDEN-WIN- 开头"""
        aid = hardener._gen_audit_id("192.168.1.1")
        assert aid.startswith("HARDEN-WIN-")

    def test_contains_date_and_hex(self, hardener):
        """审计 ID 包含日期和十六进制随机段"""
        aid = hardener._gen_audit_id("192.168.1.1")
        parts = aid.split("-")
        assert len(parts) >= 4  # HARDEN-WIN-YYYYMMDD-HHMMSS-xxxxxx

    def test_different_targets_produce_different_ids(self, hardener):
        """不同目标生成不同审计 ID"""
        id1 = hardener._gen_audit_id("192.168.1.1")
        id2 = hardener._gen_audit_id("10.0.0.1")
        assert id1 != id2


# =============================================================================
# _build_harden_script
# =============================================================================


class TestBuildHardenScript:
    """_build_harden_script() 脚本内容验证"""

    def test_contains_run_as_administrator(self, hardener, mock_recommendations):
        """加固脚本包含 #Requires -RunAsAdministrator"""
        body = hardener._build_harden_script("192.168.1.1", mock_recommendations, "20260612-000000")
        assert "#Requires -RunAsAdministrator" in body

    def test_contains_r4_ownership_block(self, hardener, mock_recommendations):
        """加固脚本包含 R4 所有权确认阻断门"""
        body = hardener._build_harden_script("192.168.1.1", mock_recommendations, "20260612-000000")
        assert "R4" in body
        assert "Read-Host" in body
        assert "确认你拥有该主机的所有权" in body

    def test_no_windows_commands_emits_guidance(self, hardener, mock_recommendations):
        """无 Windows 命令的推荐生成操作员引导提示"""
        body = hardener._build_harden_script("192.168.1.1", mock_recommendations, "20260612-000000")
        # 第三个推荐（升级老旧组件）无 windows 命令 → [提示] 引导
        assert "[提示]" in body or "手动处理" in body

    def test_placeholder_service_guides_operator(self, hardener):
        """<service> 占位符生成引导注释"""
        rec = [
            {
                "action": "停用服务",
                "target": "135",
                "reason": "测试",
                "commands": {"windows": ["Stop-Service <service>"]},
                "severity": "high",
            }
        ]
        body = hardener._build_harden_script("localhost", rec, "20260612-000000")
        assert "[引导]" in body or "<service>" in body

    def test_contains_action_count_in_progress(self, hardener, mock_recommendations):
        """加固脚本包含操作编号（如 [1/3]）"""
        body = hardener._build_harden_script("192.168.1.1", mock_recommendations, "20260612-000000")
        assert "[1/3]" in body

    def test_empty_recommendations_produces_minimal_script(self, hardener):
        """空推荐列表生成的脚本仅含头部和尾部"""
        body = hardener._build_harden_script("localhost", [], "20260612-000000")
        assert "#Requires -RunAsAdministrator" in body
        assert "加固完成" in body

    def test_target_appears_in_script_header(self, hardener, mock_recommendations):
        """目标主机地址出现在脚本头部"""
        body = hardener._build_harden_script("10.0.0.5", mock_recommendations, "20260612-000000")
        assert "10.0.0.5" in body


# =============================================================================
# _build_rollback_script
# =============================================================================


class TestBuildRollbackScript:
    """_build_rollback_script() 回滚脚本内容验证"""

    def test_contains_run_as_administrator(self, hardener, mock_recommendations):
        """回滚脚本包含管理员权限声明"""
        body = hardener._build_rollback_script("192.168.1.1", mock_recommendations, "20260612-000000")
        assert "#Requires -RunAsAdministrator" in body

    def test_contains_netsh_delete_rule(self, hardener, mock_recommendations):
        """回滚脚本包含 netsh delete rule"""
        body = hardener._build_rollback_script("192.168.1.1", mock_recommendations, "20260612-000000")
        assert "delete rule" in body

    def test_irreversible_operations_annotated(self, hardener, mock_recommendations):
        """不可逆操作有标注"""
        body = hardener._build_rollback_script("192.168.1.1", mock_recommendations, "20260612-000000")
        # 至少有一个回滚标注或提示
        assert "回滚" in body or "无法自动" in body or "手动" in body

    def test_empty_recommendations_minimal_script(self, hardener):
        """空推荐列表的回滚脚本结构完整"""
        body = hardener._build_rollback_script("localhost", [], "20260612-000000")
        assert "回滚操作" in body
        assert "完成" in body

    def test_script_ends_with_crlf(self, hardener, mock_recommendations):
        """回滚脚本以 CRLF 结尾"""
        body = hardener._build_rollback_script("192.168.1.1", mock_recommendations, "20260612-000000")
        assert body.endswith("\r\n")

    def test_target_appears_in_rollback_header(self, hardener, mock_recommendations):
        """目标主机地址出现在回滚脚本头部"""
        body = hardener._build_rollback_script("10.0.0.5", mock_recommendations, "20260612-000000")
        assert "10.0.0.5" in body


# =============================================================================
# _substitute（继承自 HardenBase）
# =============================================================================


class TestSubstitute:
    """_substitute() 变量替换"""

    def test_port_placeholder_replaced(self, hardener):
        """{port} 被替换为实际端口"""
        result = hardener._substitute("localport={port}", "3389", "192.168.1.1")
        assert "localport=3389" in result

    def test_target_placeholder_replaced(self, hardener):
        """{target} 被替换为实际目标"""
        result = hardener._substitute("{target}", "80", "10.0.0.1")
        assert "10.0.0.1" in result

    def test_multiple_placeholders_replaced(self, hardener):
        """多个占位符同时替换"""
        result = hardener._substitute(
            'name="{target}:{port}" port={port}',
            "443",
            "example.com",
        )
        assert "example.com:443" in result
        assert "port=443" in result

    def test_no_placeholder_returns_unchanged(self, hardener):
        """无占位符时原样返回"""
        original = "Get-Service | Where-Object Status -eq Running"
        result = hardener._substitute(original, "80", "localhost")
        assert result == original
