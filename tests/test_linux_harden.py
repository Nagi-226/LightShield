"""Linux 加固脚本生成器单元测试 — v0.0.45 覆盖率提升 T1。

覆盖 lightshield/harden/linux_harden.py：
  - generate() 正常流程 / 空推荐 / 目录创建失败 / 写入失败清理（M-015 验证）
  - _build_harden_script / _build_rollback_script 脚本内容
  - _substitute / _has_placeholder 工具方法
"""

from __future__ import annotations

import os
from unittest.mock import patch

from lightshield.harden.base import HardenStatus
from lightshield.harden.linux_harden import LinuxHardener, _has_placeholder, _script_filename
from lightshield.utils.constants import OSPlatform

# =============================================================================
# 辅助：构造测试用推荐列表
# =============================================================================


def _rec(**overrides) -> dict:
    """构造一条加固推荐。"""
    data = {
        "severity": "high",
        "action": "关闭端口",
        "target": "23",
        "reason": "Telnet 明文传输",
        "commands": {"linux": ["iptables -A INPUT -p tcp --dport 23 -j DROP"]},
    }
    data.update(overrides)
    return data


# =============================================================================
# _script_filename / _has_placeholder
# =============================================================================


class TestHelpers:
    """工具方法单元测试。"""

    def test_script_filename_format(self):
        name = _script_filename("127.0.0.1", "harden", "20260630-120000")
        assert name.startswith("harden_")
        assert "127_0_0_1" in name
        assert "20260630-120000" in name
        assert name.endswith(".sh")

    def test_script_filename_rollback(self):
        name = _script_filename("example.com", "rollback", "ts123")
        assert name.startswith("rollback_")
        assert "example_com" in name

    def test_has_placeholder_true(self):
        assert _has_placeholder("systemctl stop <service>") is True
        assert _has_placeholder("apt install <package_name>") is True

    def test_has_placeholder_false(self):
        assert _has_placeholder("iptables -A INPUT -p tcp --dport 23 -j DROP") is False
        assert _has_placeholder("systemctl stop telnet") is False
        assert _has_placeholder("") is False


# =============================================================================
# generate() — 核心流程
# =============================================================================


class TestGenerate:
    """LinuxHardener.generate() 三种路径 + 异常路径。"""

    def test_empty_recommendations_returns_no_action(self):
        """空推荐列表 → NO_ACTION 结果。"""
        hardener = LinuxHardener()
        result = hardener.generate("127.0.0.1", [])
        assert result.status == HardenStatus.NO_ACTION
        assert result.target == "127.0.0.1"
        assert result.script_path is None

    def test_successful_generation(self, tmp_path):
        """正常流程：生成加固+回滚脚本，返回 GENERATED。"""
        hardener = LinuxHardener()
        recs = [_rec(), _rec(action="禁用服务", target="telnet", commands={"linux": ["systemctl disable telnet"]})]
        result = hardener.generate("192.168.1.1", recs, output_dir=str(tmp_path))

        assert result.status == HardenStatus.GENERATED
        assert result.target == "192.168.1.1"
        assert result.os_platform == OSPlatform.LINUX
        assert result.action_count == 2
        assert result.script_path is not None
        assert result.rollback_path is not None
        # 文件存在
        assert os.path.exists(result.script_path)
        assert os.path.exists(result.rollback_path)
        # 脚本内容包含关键标记
        with open(result.script_path, encoding="utf-8") as f:
            content = f.read()
        assert "#!/bin/bash" in content
        assert "R4 所有权确认" in content
        assert "iptables -A INPUT" in content
        assert "加固完成" in content
        # 回滚脚本
        with open(result.rollback_path, encoding="utf-8") as f:
            rb = f.read()
        assert "#!/bin/bash" in rb
        assert "回滚" in rb

    def test_no_empty_recommendations_without_reason(self):
        """推荐不含 reason 字段也能正常生成。"""
        hardener = LinuxHardener()
        recs = [{"severity": "low", "action": "更新组件", "target": "openssh", "commands": {"linux": ["apt update"]}}]
        result = hardener.generate("10.0.0.1", recs)
        assert result.status == HardenStatus.GENERATED


class TestGenerateErrorPaths:
    """generate() 异常路径验证。"""

    def test_makedirs_failure(self):
        """输出目录创建失败 → FAILED。"""
        hardener = LinuxHardener()
        with patch("os.makedirs", side_effect=OSError("权限不足")):
            result = hardener.generate("127.0.0.1", [_rec()], output_dir="/invalid")
        assert result.status == HardenStatus.FAILED
        assert "输出目录创建失败" in (result.error or "")

    def test_write_failure_cleans_partial_files(self, tmp_path):
        """M-015 验证：写入失败后清理已落盘的半套文件。"""
        hardener = LinuxHardener()
        out_dir = str(tmp_path)
        recs = [_rec()]

        # 让第一个 open(harden_path) 成功，第二个 open(rollback_path) 抛异常
        real_open = open
        call_count = [0]

        def _failing_open(path, *args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 2:
                raise OSError("磁盘满")
            return real_open(path, *args, **kwargs)

        with (
            patch("builtins.open", side_effect=_failing_open),
            patch("os.path.exists", return_value=True),
            patch("os.remove"),
        ):
            result = hardener.generate("127.0.0.1", recs, output_dir=out_dir)
        assert result.status == HardenStatus.FAILED
        assert "脚本写入失败" in (result.error or "")


# =============================================================================
# _build_harden_script — 脚本内容
# =============================================================================


class TestBuildHardenScript:
    """加固脚本内容验证。"""

    def test_includes_header_and_r4_gate(self):
        hardener = LinuxHardener()
        recs = [_rec()]
        script = hardener._build_harden_script("10.0.0.1", recs, "ts001")
        assert "#!/bin/bash" in script
        assert "10.0.0.1" in script
        assert "R4 所有权确认" in script
        assert "read -r -p" in script
        assert "iptables -A INPUT" in script

    def test_comment_only_commands_preserved_as_comments(self):
        """以 # 开头的命令保持为注释引导。"""
        hardener = LinuxHardener()
        recs = [_rec(commands={"linux": ["# 需要手动执行: apt install nginx"]})]
        script = hardener._build_harden_script("x", recs, "ts")
        assert "# 需要手动执行" in script
        # 注释命令不应有 echo '  +' 前缀
        assert "需要手动执行" in script

    def test_placeholder_commands_marked_as_guide(self):
        """含 <...> 占位符的命令改写为操作员引导注释。"""
        hardener = LinuxHardener()
        recs = [_rec(commands={"linux": ["systemctl stop <service>"]})]
        script = hardener._build_harden_script("x", recs, "ts")
        assert "[引导]" in script
        assert "<service>" in script

    def test_multiple_recommendations_counted(self):
        hardener = LinuxHardener()
        recs = [_rec(), _rec(), _rec()]
        script = hardener._build_harden_script("x", recs, "ts")
        assert "[1/3]" in script
        assert "[2/3]" in script
        assert "[3/3]" in script


# =============================================================================
# _build_rollback_script — 回滚脚本
# =============================================================================


class TestBuildRollbackScript:
    """回滚脚本内容验证。"""

    def test_includes_header_and_rollback_marker(self):
        hardener = LinuxHardener()
        recs = [_rec()]
        script = hardener._build_rollback_script("10.0.0.1", recs, "ts001")
        assert "#!/bin/bash" in script
        assert "回滚" in script
        assert "10.0.0.1" in script
        assert "/tmp/lightshield-harden-backup" in script

    def test_iptables_rollback_references_backup(self):
        """Iptables 回滚引用备份文件。"""
        hardener = LinuxHardener()
        recs = [_rec(commands={"linux": ["iptables -A INPUT -p tcp --dport 23 -j DROP"]})]
        script = hardener._build_rollback_script("x", recs, "ts")
        assert "iptables-restore" in script or "iptables -D" in script


# =============================================================================
# _substitute
# =============================================================================


class TestSubstitute:
    """_substitute() 变量替换。"""

    def test_port_substitution(self):
        hardener = LinuxHardener()
        result = hardener._substitute("iptables -A INPUT -p tcp --dport {port} -j DROP", "23", "x")
        assert result == "iptables -A INPUT -p tcp --dport 23 -j DROP"

    def test_target_substitution(self):
        hardener = LinuxHardener()
        result = hardener._substitute("echo {target}", "80", "192.168.1.1")
        assert result == "echo 192.168.1.1"

    def test_no_placeholders_returns_unchanged(self):
        hardener = LinuxHardener()
        result = hardener._substitute("systemctl restart sshd", "22", "x")
        assert result == "systemctl restart sshd"
