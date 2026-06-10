"""
LightShield Windows 加固脚本生成器

与 linux_harden.py 对称——消费规则引擎的加固建议，生成可审阅的
PowerShell 加固脚本 + 回滚脚本。绝不自动执行任何系统命令。

设计约束（合规）：
  - 仅生成防御性加固命令
  - 脚本头含 R4 所有权确认阻断门（Read-Host）
  - 每条操作审计留痕（logger.audit_harden_action）
  - 不调用 subprocess / os.system 执行系统命令
  - 不调用 Invoke-Expression
  - {port} 等占位符自动替换；netsh/Set-Service 等标准命令直接生成
  - Windows-only 命令缺失时写引导注释，不臆测

用法：
    from lightshield.harden.win_harden import WinHardener
    hardener = WinHardener()
    result = hardener.generate("192.168.1.1", recommendations)
    print(result.script_path)
"""

import os
import sys as _sys
from datetime import datetime
from typing import Optional

# Allow direct script execution (python lightshield/harden/win_harden.py)
if __name__ == "__main__" and _sys.path[0] != os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))):
    _sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from lightshield.config import get_config
from lightshield.harden.base import HardenBase, HardenResult, HardenStatus
from lightshield.utils.constants import OSPlatform
from lightshield.utils.logger import get_logger


# =============================================================================
# 命令回滚映射（PowerShell 版）
# =============================================================================

# 可逆操作的逆命令生成规则
_ROLLBACK_RULES = [
    # netsh advfirewall add rule → delete rule
    ("netsh advfirewall firewall add rule", "netsh advfirewall firewall delete rule"),
    # Set-Service -StartupType Disabled → Automatic
    ("Set-Service ", "# 回滚：Set-Service "),
    # Stop-Service → Start-Service
    ("Stop-Service ", "Start-Service "),
]

# 不可逆操作关键词匹配
_IRREVERSIBLE_PATTERNS = [
    ("secedit /export", "安全策略已导出备份文件，无法自动回滚。操作员请手动恢复安全策略。"),
    ("secedit /configure", "安全策略已应用，无法自动回滚。操作员请从备份恢复。"),
]


def _build_rollback_cmd(line: str) -> str:
    """根据单行 PowerShell 命令生成对应的回滚命令

    规则：
      netsh add rule → delete rule
      Set-Service -StartupType Disabled → 注释引导操作员恢复
      Stop-Service → Start-Service
      secedit → 注释提示手动恢复
      不可逆 → 注释提示
    """
    stripped = line.strip()
    if not stripped or stripped.startswith("#"):
        return line

    # 不可逆检查
    for pattern, note in _IRREVERSIBLE_PATTERNS:
        if pattern in stripped:
            return f"# 无法自动回滚：{note} —— {stripped[:60]}..."

    # 可逆规则匹配
    for needle, replacement in _ROLLBACK_RULES:
        if needle in stripped:
            if replacement.startswith("# 回滚："):
                # Set-Service 需要结合原参数生成真正的回滚命令
                return f"{replacement}（操作员请根据原配置设置正确的 StartupType）"
            return stripped.replace(needle, replacement, 1)

    # 无法自动推导
    if stripped.startswith("Write-Host") or stripped.startswith("#"):
        return f"# 已执行辅助操作，无需单独回滚：{stripped[:60]}"
    return f"# 待回滚（无法自动推导逆操作）：{stripped[:60]}..."


def _script_filename(target: str, kind: str, ts: str) -> str:
    """生成脚本文件名：harden_<target>_<ts>.ps1 / rollback_<target>_<ts>.ps1"""
    safe_target = target.replace(".", "_").replace(":", "_").replace("/", "_")
    return f"{kind}_{safe_target}_{ts}.ps1"


# =============================================================================
# WinHardener
# =============================================================================

class WinHardener(HardenBase):
    """Windows 加固脚本生成器

    与 LinuxHardener 对称实现。不执行系统命令，仅生成 .ps1 加固与回滚脚本。
    """

    def __init__(self):
        super().__init__(name="WinHardener")
        self._logger = get_logger()

    # =========================================================================
    # 生成
    # =========================================================================

    def generate(
        self,
        target: str,
        recommendations: list[dict],
        output_dir: Optional[str] = None,
    ) -> HardenResult:
        """根据加固建议生成 PowerShell 加固脚本与回滚脚本

        Args:
            target: 加固目标（IP/域名）
            recommendations: 来自 engine.recommend_hardening() 的列表
            output_dir: 输出目录，默认使用配置的 report_output_dir

        Returns:
            HardenResult
        """
        if not recommendations:
            self._logger.info("hardener", f"目标 {target} 无加固项，跳过生成")
            return HardenResult(
                status=HardenStatus.NO_ACTION,
                target=target,
                os_platform=OSPlatform.WINDOWS,
                audit_id=self._gen_audit_id(target),
            )

        cfg = get_config()
        out_dir = output_dir or cfg.report_output_dir

        try:
            os.makedirs(out_dir, exist_ok=True)
        except OSError as e:
            self._logger.error("hardener", f"输出目录创建失败：{out_dir}", exception=e)
            return HardenResult(
                status=HardenStatus.FAILED,
                target=target,
                os_platform=OSPlatform.WINDOWS,
                error=f"输出目录创建失败：{out_dir}（{e}）",
            )

        ts = datetime.now().strftime("%Y%m%d-%H%M%S")
        audit_id = self._gen_audit_id(target)

        # 构建脚本
        harden_body = self._build_harden_script(target, recommendations, ts)
        rollback_body = self._build_rollback_script(target, recommendations, ts)

        harden_path = os.path.join(out_dir, _script_filename(target, "harden", ts))
        rollback_path = os.path.join(out_dir, _script_filename(target, "rollback", ts))

        try:
            with open(harden_path, "w", encoding="utf-8-sig", newline="\r\n") as f:
                f.write(harden_body)
            with open(rollback_path, "w", encoding="utf-8-sig", newline="\r\n") as f:
                f.write(rollback_body)
        except OSError as e:
            self._logger.error("hardener", f"加固脚本写入失败：{harden_path}", exception=e)
            return HardenResult(
                status=HardenStatus.FAILED,
                target=target,
                os_platform=OSPlatform.WINDOWS,
                error=f"脚本写入失败：{e}",
            )

        # 审计
        for rec in recommendations:
            self._audit_action(target, rec.get("action", "?"), "script_generated")

        self._logger.info(
            "hardener",
            f"加固脚本已生成（Windows）：target={target} "
            f"actions={len(recommendations)} "
            f"harden={harden_path} rollback={rollback_path}",
        )

        return HardenResult(
            status=HardenStatus.GENERATED,
            target=target,
            os_platform=OSPlatform.WINDOWS,
            recommendations=recommendations,
            script_path=harden_path,
            rollback_path=rollback_path,
            action_count=len(recommendations),
            audit_id=audit_id,
        )

    # =========================================================================
    # 脚本组装
    # =========================================================================

    def _build_harden_script(
        self, target: str, recommendations: list[dict], ts: str
    ) -> str:
        """组装 PowerShell 加固脚本全文"""
        lines = [
            "<#",
            "═══════════════════════════════════════════════════════════════════",
            "LightShield 轻盾 — Windows 加固脚本",
            "生成时间：" + datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "目标主机：" + target,
            "⚠️  仅限自有资产使用（合规 R4）。执行前请逐条审阅。",
            "本脚本由 LightShield 生成，不会被自动运行。",
            "要求以管理员身份运行 PowerShell。",
            "═══════════════════════════════════════════════════════════════════",
            "#>",
            "",
            "#Requires -RunAsAdministrator",
            "",
            '$ErrorActionPreference = "Stop"',
            "",
            "# ══════ R4 所有权确认（阻断门）══════",
            'Write-Host "╔══════════════════════════════════════════════╗"',
            'Write-Host "║  LightShield 轻盾 — Windows 加固脚本           ║"',
            'Write-Host "║  ⚠️  本脚本将修改系统防火墙/服务配置。        ║"',
            'Write-Host "║  仅限自有资产使用（合规 R4）。                 ║"',
            'Write-Host "╚══════════════════════════════════════════════╝"',
            'Write-Host ""',
            f'Write-Host "  目标主机：{target}"',
            'Write-Host ""',
            '$answer = Read-Host "确认你拥有该主机的所有权或已获明确授权？(yes/no)"',
            'if ($answer -ne "yes") {',
            '    Write-Host "已取消：未确认所有权。"',
            "    exit 1",
            "}",
            "",
            "# ══════ 自动备份（回滚用）══════",
            'Write-Host ""',
            'Write-Host "[备份] 导出当前防火墙规则..."',
            "$firewallBackup = Join-Path $env:TEMP \"firewall-backup-$(Get-Date -Format yyyyMMdd-HHmmss).wfw\"",
            "netsh advfirewall export `\"$firewallBackup`\" 2>$null",
            'if ($LASTEXITCODE -eq 0) {',
            '    Write-Host "[备份] $firewallBackup"',
            "} else {",
            '    Write-Host "[提示] 防火墙规则导出失败，继续执行"',
            "}",
            "",
            'Write-Host "[备份] 导出当前服务状态..."',
            '$serviceBackup = Join-Path $env:TEMP "services-backup-$(Get-Date -Format yyyyMMdd-HHmmss).csv"',
            "Get-Service | Select-Object Name, Status, StartType | Export-Csv -Path `$serviceBackup -NoTypeInformation",
            'Write-Host "[备份] $serviceBackup"',
            "",
            "# ══════ 加固操作 ══════",
            'Write-Host ""',
            'Write-Host "=== 开始执行加固操作 ==="',
            "",
        ]

        for i, rec in enumerate(recommendations, 1):
            action = rec.get("action", "未知操作")
            reason = rec.get("reason", "")
            commands = rec.get("commands", {}).get("windows", [])
            port = str(rec.get("target", ""))

            lines += [
                f'Write-Host ""',
                f"Write-Host '### [{i}/{len(recommendations)}] {action}'",
            ]
            if reason:
                lines.append(f"Write-Host '  原因：{reason}'")

            if not commands:
                # 无 Windows 命令——引导操作员
                lines.append(f"# [提示] 此操作暂无 Windows 自动化命令，请操作员手动处理。")
                lines.append(f"#        建议操作：{action}（{reason}）")
                continue

            for cmd in commands:
                substituted = self._substitute(cmd, port, target)
                if substituted.startswith("#"):
                    # 纯注释引导
                    lines.append(substituted)
                elif "<service>" in substituted or "<Service>" in substituted:
                    # 占位符——引导操作员替换
                    lines.append(f"# [引导] 以下命令需要操作员指定具体服务名：")
                    lines.append(f"# {substituted}")
                elif any(kw in substituted for kw in ("systemctl", "apt ", "yum ", "iptables", "sed ", "cp /etc")):
                    # Linux-only 命令——Windows 下引导
                    lines.append(f"# [跳过] 此命令仅适用于 Linux，Windows 下请手动处理：")
                    lines.append(f"#        {substituted[:80]}")
                else:
                    lines.append(f'Write-Host "  + {substituted[:80]}"')
                    lines.append(substituted)

        lines += [
            "",
            'Write-Host ""',
            'Write-Host "=== 加固完成 ==="',
            'Write-Host "回滚脚本已同时生成，必要时请以管理员身份运行对应的 rollback_*.ps1 文件。"',
        ]
        return "\r\n".join(lines) + "\r\n"

    def _build_rollback_script(
        self, target: str, recommendations: list[dict], ts: str
    ) -> str:
        """组装回滚脚本全文"""
        lines = [
            "<#",
            "═══════════════════════════════════════════════════════════════════",
            "LightShield 轻盾 — Windows 回滚脚本",
            "生成时间：" + datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "目标主机：" + target,
            "使用方法：以管理员身份运行 PowerShell，执行 ./" + _script_filename(target, "rollback", ts),
            "═══════════════════════════════════════════════════════════════════",
            "#>",
            "",
            '#Requires -RunAsAdministrator',
            "",
            '$ErrorActionPreference = "SilentlyContinue"',
            "",
            'Write-Host "=== LightShield 轻盾 — 回滚操作 ==="',
            f'Write-Host "  目标：{target}"',
            'Write-Host ""',
            "",
            "# ══════ 回滚操作 ══════",
            "",
        ]

        for i, rec in enumerate(recommendations, 1):
            action = rec.get("action", "未知操作")
            commands = rec.get("commands", {}).get("windows", [])
            port = str(rec.get("target", ""))

            lines.append(f"Write-Host '### 回滚 [{i}] {action}'")

            if not commands:
                lines.append(f"# [提示] 此操作无 Windows 自动化命令，无需回滚。")
                lines.append("")
                continue

            has_rollback = False
            for cmd in commands:
                substituted = self._substitute(cmd, port, target)
                rollback = _build_rollback_cmd(substituted)

                if substituted.startswith("#") and not rollback.startswith("#"):
                    lines.append(f"# 原操作为注释引导，无需回滚")
                elif "netsh advfirewall firewall add rule" in substituted:
                    # 提取规则名用于回滚
                    import re
                    rule_match = re.search(r'name="([^"]+)"', substituted)
                    if rule_match:
                        rule_name = rule_match.group(1)
                        lines += [
                            f"# 删除防火墙规则：{rule_name}",
                            f'netsh advfirewall firewall delete rule name="{rule_name}"',
                        ]
                    else:
                        lines.append(rollback)
                    has_rollback = True
                elif "netsh advfirewall export" in substituted:
                    lines.append(rollback)
                elif rollback.startswith("# 回滚："):
                    lines.append(rollback)
                elif rollback.startswith("# ") and "无法自动回滚" in rollback:
                    lines.append(rollback)
                elif rollback.startswith("# "):
                    lines.append(rollback)
                else:
                    lines.append(rollback)
                    has_rollback = True

            if not has_rollback:
                lines.append(f"# [提示] 操作「{action}」无法自动回滚，请参考备份文件手动恢复")

            lines.append("")

        # 防火墙全量回滚提示
        has_firewall = any(
            "netsh advfirewall" in str(rec.get("commands", {}).get("windows", []))
            for rec in recommendations
        )
        if has_firewall:
            lines += [
                'Write-Host ""',
                'Write-Host "[提示] 如需完全恢复防火墙规则到加固前状态，请执行："',
                'Write-Host "  netsh advfirewall import `"$firewallBackup`""',
            ]

        lines += [
            'Write-Host ""',
            'Write-Host "=== 回滚操作完成 ==="',
        ]
        return "\r\n".join(lines) + "\r\n"

    # =========================================================================
    # 工具
    # =========================================================================

    @staticmethod
    def _gen_audit_id(target: str) -> str:
        """生成审计 ID"""
        import uuid
        return f"HARDEN-WIN-{datetime.now().strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:6]}"


# =============================================================================
# 自检
# =============================================================================

if __name__ == "__main__":
    import tempfile

    print("=== WinHardener 自检 ===")

    hardener = WinHardener()
    assert hardener.name == "WinHardener", f"名称错误: {hardener.name}"
    print(f"[OK] 名称: {hardener.name}")

    # 构造模拟加固建议（匹配 harden_rules.json windows 命令）
    mock_recommendations = [
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

    out_dir = tempfile.mkdtemp(prefix="lightshield_win_harden_test_")
    print(f"  输出目录: {out_dir}")

    try:
        result = hardener.generate("192.168.1.100", mock_recommendations, output_dir=out_dir)

        # 断言
        assert result.status == HardenStatus.GENERATED, f"状态错误: {result.status}"
        assert result.action_count == 3
        assert result.os_platform == OSPlatform.WINDOWS
        assert result.script_path is not None
        assert result.rollback_path is not None
        assert os.path.exists(result.script_path), f"加固脚本未生成: {result.script_path}"
        assert os.path.exists(result.rollback_path), f"回滚脚本未生成: {result.rollback_path}"
        print(f"[OK] 状态: {result.status.value} os={result.os_platform.value}")

        # 检查加固脚本内容
        with open(result.script_path, "r", encoding="utf-8-sig") as f:
            harden_text = f.read()
        assert "#Requires -RunAsAdministrator" in harden_text, "缺少管理员权限声明"
        assert "R4" in harden_text, "缺少 R4 所有权提示"
        assert 'Read-Host "确认你拥有该主机的所有权' in harden_text, "缺少所有权确认 Read-Host"
        assert "netsh advfirewall firewall add rule" in harden_text, "缺少 netsh 防火墙命令"
        assert "Get-Service" in harden_text, "缺少服务管理命令"
        assert "[跳过]" in harden_text or "[引导]" in harden_text, "缺少 Linux-only 跳过或占位符引导"
        assert "<service>" in harden_text, "缺少占位符引导操作员填写"
        print(f"[OK] 加固脚本: {len(harden_text)} 字符，含 R4 Read-Host + netsh + Get-Service + 占位符引导")

        # 检查回滚脚本内容
        with open(result.rollback_path, "r", encoding="utf-8-sig") as f:
            rollback_text = f.read()
        assert "#Requires -RunAsAdministrator" in rollback_text, "回滚脚本缺管理员声明"
        assert "delete rule" in rollback_text, "回滚脚本缺少 netsh delete rule"
        assert "无法自动回滚" in rollback_text or "无法自动" in rollback_text, "缺少不可逆操作标注"
        print(f"[OK] 回滚脚本: {len(rollback_text)} 字符，含 netsh delete rule + 不可逆标注")

        # 空推荐 → NO_ACTION
        empty_result = hardener.generate("127.0.0.1", [], output_dir=out_dir)
        assert empty_result.status == HardenStatus.NO_ACTION
        assert empty_result.os_platform == OSPlatform.WINDOWS
        print(f"[OK] 空推荐 → {empty_result.status.value}")

        # 变量替换
        substituted = hardener._substitute(
            'netsh advfirewall firewall add rule name="Block_{port}" dir=in action=block protocol=TCP localport={port}',
            "3389", "192.168.1.1"
        )
        assert "localport=3389" in substituted, f"端口替换失败: {substituted}"
        assert 'name="Block_3389"' in substituted, f"名称替换失败: {substituted}"
        print(f"[OK] 变量替换: {substituted[:60]}")

        # 确认无执行性代码
        dangerous = ["subprocess", "os.system", "Invoke-Expression", "iex ", "Start-Process "]
        full_text = harden_text + rollback_text
        for kw in dangerous:
            assert kw not in full_text, f"检测到执行性代码: {kw}"
        print(f"[OK] 零执行性代码（无 subprocess/Invoke-Expression/Start-Process）")

        print("=== WinHardener: ALL PASSED ===")
    finally:
        import shutil
        shutil.rmtree(out_dir, ignore_errors=True)