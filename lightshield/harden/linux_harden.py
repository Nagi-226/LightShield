"""LightShield Linux 加固脚本生成器

消费规则引擎的加固建议，生成可审阅的加固脚本 + 回滚脚本。
绝不自动执行任何系统命令——脚本生成后由操作员自行审阅与执行。

设计约束（合规）：
  - 仅生成防御性加固命令
  - 脚本头含 R4 所有权确认阻断门
  - 每条操作审计留痕（logger.audit_harden_action）
  - 不调用 subprocess / os.system 执行系统命令
  - {port} 等占位符自动替换；<service> 等保留引导操作员填写

用法：
    from lightshield.harden.linux_harden import LinuxHardener
    hardener = LinuxHardener()
    result = hardener.generate("192.168.1.1", recommendations)
    print(result.script_path)
"""

import os
import sys as _sys
from datetime import datetime

# Allow direct script execution (python lightshield/harden/linux_harden.py)
if __name__ == "__main__" and _sys.path[0] != os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
):
    _sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from lightshield.config import get_config
from lightshield.harden.base import HardenBase, HardenResult, HardenStatus
from lightshield.utils.constants import OSPlatform
from lightshield.utils.logger import get_logger

# =============================================================================
# 命令回滚映射
# =============================================================================

# 可逆操作的逆命令生成规则（按行匹配）
_ROLLBACK_RULES = [
    # iptables -A ... -j DROP → -D ... -j DROP
    ("iptables -A INPUT -p tcp --dport", "iptables -D INPUT -p tcp --dport"),
    # systemctl stop → start
    ("systemctl stop ", "systemctl start "),
    # systemctl disable → enable
    ("systemctl disable ", "systemctl enable "),
    # sed 修改 sshd_config → 回退到备份
    ("sed ", "# 回滚：cp 备份文件到原路径（见 _build_rollback_script 中的 SSH 备份恢复逻辑）"),
    # iptables-save 持久化 → 无需回滚
    ("iptables-save", "# 无需回滚：iptables-save 记录已在回滚脚本中显式 -D"),
]

# 不可逆操作关键词匹配
_IRREVERSIBLE_PATTERNS = [
    ("apt update", "系统更新操作不可自动回滚"),
    ("apt upgrade", "系统升级操作不可自动回滚"),
    ("yum update", "系统更新操作不可自动回滚"),
    ("yum upgrade", "系统升级操作不可自动回滚"),
    ("apt install", "软件包安装不可自动回滚，请手动卸载"),
]


def _build_rollback_cmd(line: str) -> str:
    """根据单行命令生成对应的回滚命令

    规则：
      iptables -A → -D
      systemctl stop → start
      systemctl disable → enable
      sed → 引用备份文件
      不可逆 → 注释提示
    """
    stripped = line.strip()
    if not stripped or stripped.startswith("#"):
        # 注释原样保留
        return line

    # 不可逆检查
    for pattern, note in _IRREVERSIBLE_PATTERNS:
        if pattern in stripped:
            return f"# 无法自动回滚：{note} —— {stripped[:60]}..."

    # 可逆规则匹配
    for needle, replacement in _ROLLBACK_RULES:
        if needle in stripped:
            if needle == "sed ":
                return "# 回滚操作：请从备份目录恢复原配置。操作员请手动执行："
            return stripped.replace(needle, replacement, 1)

    # 默认：无法自动生成回滚命令
    if stripped.startswith("cp ") or stripped.startswith("echo "):
        return f"# 已执行辅助操作，无需单独回滚：{stripped[:60]}"
    return f"# 待回滚（无法自动推导逆操作）：{stripped[:60]}..."


def _script_filename(target: str, kind: str, ts: str) -> str:
    """生成脚本文件名：harden_<target>_<ts>.sh / rollback_<target>_<ts>.sh"""
    safe_target = target.replace(".", "_").replace(":", "_").replace("/", "_")
    return f"{kind}_{safe_target}_{ts}.sh"


def _has_placeholder(command: str) -> bool:
    """检测命令中是否包含未替换的 <...> 占位符

    {port} / {target} 由 HardenBase._substitute() 处理；
    如果替换后仍残留 <service> / <Service> 等尖括号占位符，
    说明此命令需要操作员手动填写，不得作为可执行命令写入脚本。

    Returns:
        True 表示包含未处理的占位符，命令应改写为注释。
    """
    import re

    return bool(re.search(r"<[\w-]+>", command))


# =============================================================================
# LinuxHardener
# =============================================================================


class LinuxHardener(HardenBase):
    """Linux 加固脚本生成器

    不执行系统命令，仅生成 .sh 加固与回滚脚本。
    """

    def __init__(self):
        super().__init__(name="LinuxHardener")
        self._logger = get_logger()

    # =========================================================================
    # 生成
    # =========================================================================

    def generate(
        self,
        target: str,
        recommendations: list[dict],
        output_dir: str | None = None,
    ) -> HardenResult:
        """根据加固建议生成加固脚本与回滚脚本

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
                os_platform=OSPlatform.LINUX,
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
                os_platform=OSPlatform.LINUX,
                error=f"输出目录创建失败：{out_dir}（{e}）",
            )

        ts = datetime.now().strftime("%Y%m%d-%H%M%S")
        audit_id = self._gen_audit_id(target)

        # 构建加固脚本体
        harden_body = self._build_harden_script(target, recommendations, ts)
        rollback_body = self._build_rollback_script(target, recommendations, ts)

        harden_path = os.path.join(out_dir, _script_filename(target, "harden", ts))
        rollback_path = os.path.join(out_dir, _script_filename(target, "rollback", ts))

        try:
            with open(harden_path, "w", encoding="utf-8", newline="\n") as f:
                f.write(harden_body)
            with open(rollback_path, "w", encoding="utf-8", newline="\n") as f:
                f.write(rollback_body)
        except OSError as e:
            self._logger.error("hardener", f"加固脚本写入失败：{harden_path}", exception=e)
            # 清理已写入的半套文件（防止用户误执行无回滚的加固脚本）
            for p in (harden_path, rollback_path):
                if os.path.exists(p):
                    try:
                        os.remove(p)
                        self._logger.info("hardener", f"已清理残留文件：{p}")
                    except OSError:
                        pass
            return HardenResult(
                status=HardenStatus.FAILED,
                target=target,
                os_platform=OSPlatform.LINUX,
                error=f"脚本写入失败：{e}",
            )

        # 审计
        for rec in recommendations:
            self._audit_action(target, rec.get("action", "?"), "script_generated")

        self._logger.info(
            "hardener",
            f"加固脚本已生成：target={target} "
            f"actions={len(recommendations)} "
            f"harden={harden_path} rollback={rollback_path}",
        )

        return HardenResult(
            status=HardenStatus.GENERATED,
            target=target,
            os_platform=OSPlatform.LINUX,
            recommendations=recommendations,
            script_path=harden_path,
            rollback_path=rollback_path,
            action_count=len(recommendations),
            audit_id=audit_id,
        )

    # =========================================================================
    # 脚本组装
    # =========================================================================

    def _build_harden_script(self, target: str, recommendations: list[dict], ts: str) -> str:
        """组装加固脚本全文"""
        lines = [
            "#!/bin/bash",
            "# ═══════════════════════════════════════════════════════════════════",
            "# LightShield 轻盾 — Linux 加固脚本",
            "# 生成时间：" + datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            f"# 目标主机：{target}",
            "# ⚠️  仅限自有资产使用（合规 R4）。执行前请逐条审阅。",
            "# 本脚本由 LightShield 生成，不会被自动运行。",
            "# ═══════════════════════════════════════════════════════════════════",
            "",
            "set -euo pipefail",
            "",
            "# ══════ R4 所有权确认（阻断门）══════",
            'echo "⚠️  本脚本将修改系统防火墙/服务配置。"',
            f'echo "    目标主机：{target}"',
            'echo ""',
            'read -r -p "确认你拥有该主机的所有权或已获明确授权？(yes/no) " _answer',
            'if [ "$_answer" != "yes" ]; then',
            '    echo "已取消：未确认所有权。"',
            "    exit 1",
            "fi",
            "",
            "# ══════ 自动备份（回滚用）══════",
            "# 备份文件写入固定路径 /tmp/lightshield-harden-backup/",
            "# 回滚脚本读取同一路径，确保跨脚本可用（Codex B2 修复）",
            "_LS_BACKUP_DIR=/tmp/lightshield-harden-backup",
            'mkdir -p "$_LS_BACKUP_DIR"',
            "",
            'echo "[备份] 保存当前 iptables 规则..."',
            '_IPT_BACKUP="$_LS_BACKUP_DIR/iptables.rules"',
            'iptables-save > "$_IPT_BACKUP" 2>/dev/null && echo "[备份] $_IPT_BACKUP" || echo "[提示] iptables-save 不可用"',
            "",
            'echo "[备份] 保存 sshd_config..."',
            "if [ -f /etc/ssh/sshd_config ]; then",
            '    _SSHD_BACKUP="$_LS_BACKUP_DIR/sshd_config.bak"',
            '    cp /etc/ssh/sshd_config "$_SSHD_BACKUP"',
            '    echo "[备份] $_SSHD_BACKUP"',
            "fi",
            "",
            "# ══════ 加固操作 ══════",
            'echo ""',
            'echo "=== 开始执行加固操作 ==="',
            "",
        ]

        for i, rec in enumerate(recommendations, 1):
            action = rec.get("action", "未知操作")
            reason = rec.get("reason", "")
            commands = rec.get("commands", {}).get("linux", [])
            port = str(rec.get("target", ""))

            lines += [
                "echo ''",
                f"echo '### [{i}/{len(recommendations)}] {action}'",
            ]
            if reason:
                lines.append(f"echo '  原因：{reason}'")

            for cmd in commands:
                substituted = self._substitute(cmd, port, target)
                if substituted.startswith("#"):
                    # 纯注释引导——输出给操作员看，不执行
                    lines.append(substituted)
                elif _has_placeholder(substituted):
                    # 含 <service> 等未填占位符——禁止作为命令执行，
                    # 改写为注释引导操作员填写（Codex B1 修复）
                    lines.append("# [引导] 以下命令需要操作员指定具体值后手动执行：")
                    lines.append(f"# {substituted}")
                else:
                    lines.append(f"echo '  + {substituted[:80]}'")
                    lines.append(substituted)

        lines += [
            "",
            'echo ""',
            'echo "=== 加固完成 ==="',
            'echo "回滚脚本已同时生成，必要时请运行对应的 rollback_*.sh 文件。"',
        ]
        return "\n".join(lines) + "\n"

    def _build_rollback_script(self, target: str, recommendations: list[dict], ts: str) -> str:
        """组装回滚脚本全文"""
        lines = [
            "#!/bin/bash",
            "# ═══════════════════════════════════════════════════════════════════",
            "# LightShield 轻盾 — Linux 回滚脚本",
            "# 生成时间：" + datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            f"# 目标主机：{target}",
            "# 使用方法：bash ./" + _script_filename(target, "rollback", ts),
            "# ═══════════════════════════════════════════════════════════════════",
            "",
            "set -euo pipefail",
            "",
            "# 备份文件路径——与加固脚本使用相同固定路径（Codex B2 修复）",
            "_LS_BACKUP_DIR=/tmp/lightshield-harden-backup",
            '_IPT_BACKUP="$_LS_BACKUP_DIR/iptables.rules"',
            '_SSHD_BACKUP="$_LS_BACKUP_DIR/sshd_config.bak"',
            "",
            'echo "=== LightShield 轻盾 — 回滚操作 ==="',
            f'echo "  目标：{target}"',
            'echo ""',
            "",
            "# ══════ 回滚操作 ══════",
            "",
        ]

        for i, rec in enumerate(recommendations, 1):
            action = rec.get("action", "未知操作")
            commands = rec.get("commands", {}).get("linux", [])
            port = str(rec.get("target", ""))

            lines.append(f"echo '### 回滚 [{i}] {action}'")

            has_rollback = False
            for cmd in commands:
                substituted = self._substitute(cmd, port, target)
                rollback = _build_rollback_cmd(substituted)

                if substituted.startswith("sed ") and "sshd_config" in substituted:
                    # SSH 配置回滚：从 .bak 恢复
                    lines += [
                        "# 恢复 sshd_config 备份（固定路径，跨脚本可靠——Codex B2 修复）",
                        'if [ -f "$_SSHD_BACKUP" ]; then',
                        "    echo '  恢复 sshd_config 从备份'",
                        '    cp "$_SSHD_BACKUP" /etc/ssh/sshd_config',
                        "    systemctl restart sshd || service ssh restart",
                        "else",
                        "    echo '  [警告] 未找到 sshd_config 备份：$_SSHD_BACKUP'",
                        "fi",
                    ]
                    has_rollback = True
                elif substituted.startswith("iptables-save"):
                    lines.append(rollback)
                elif "iptables -A INPUT" in substituted:
                    lines += [
                        rollback,
                        "# 持久化回滚后的规则",
                        "iptables-save > /etc/iptables/rules.v4 2>/dev/null || true",
                    ]
                    has_rollback = True
                elif rollback.startswith("# ") and "待回滚" in rollback or rollback.startswith("# "):
                    lines.append(rollback)
                else:
                    lines.append(rollback)
                    has_rollback = True

            if not has_rollback:
                lines.append(f"# [提示] 操作「{action}」已自动备份或无需单独回滚")

            lines.append("")

        # iptables 全量回滚（仅 iptables 相关操作存在时）
        has_iptables = any("iptables" in str(rec.get("commands", {}).get("linux", [])) for rec in recommendations)
        if has_iptables:
            lines += [
                'echo ""',
                'echo "[提示] 如需完全回滚 iptables 到加固前状态，请执行："',
                'echo "  iptables-restore < \\"$_IPT_BACKUP\\""',
            ]

        lines += [
            'echo ""',
            'echo "=== 回滚操作完成 ==="',
        ]
        return "\n".join(lines) + "\n"

    # =========================================================================
    # 工具
    # =========================================================================

    @staticmethod
    def _gen_audit_id(target: str) -> str:
        """生成审计 ID"""
        import uuid

        return f"HARDEN-{datetime.now().strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:6]}"


# =============================================================================
# 自检
# =============================================================================

if __name__ == "__main__":
    import tempfile

    print("=== LinuxHardener 自检 ===")

    hardener = LinuxHardener()
    assert hardener.name == "LinuxHardener", f"名称错误: {hardener.name}"
    print(f"[OK] 名称: {hardener.name}")

    # 构造模拟加固建议（匹配 harden_rules.json 格式）
    mock_recommendations = [
        {
            "action": "关闭高危端口",
            "target": "23",
            "reason": "Telnet 明文传输，极度危险",
            "commands": {
                "linux": [
                    "# 使用 iptables 关闭端口 23 (Telnet)",
                    "iptables -A INPUT -p tcp --dport 23 -j DROP",
                    "# 持久化规则",
                    "iptables-save > /etc/iptables/rules.v4",
                ]
            },
            "severity": "high",
        },
        {
            "action": "配置 SSH 安全",
            "target": "22",
            "reason": "加固 SSH 服务防止暴力破解",
            "commands": {
                "linux": [
                    "# 备份原配置",
                    "cp /etc/ssh/sshd_config /etc/ssh/sshd_config.bak",
                    "# 禁用 root 登录",
                    "sed -i 's/^#PermitRootLogin.*/PermitRootLogin no/' /etc/ssh/sshd_config",
                    "# 重启 SSH",
                    "systemctl restart sshd",
                ]
            },
            "severity": "high",
        },
        {
            "action": "升级老旧组件",
            "target": "component",
            "reason": "存在已知 CVE",
            "commands": {
                "linux": [
                    "# 更新包列表并升级所有包",
                    "apt update && apt upgrade -y",
                ]
            },
            "severity": "critical",
        },
    ]

    out_dir = tempfile.mkdtemp(prefix="lightshield_harden_test_")
    print(f"  输出目录: {out_dir}")

    try:
        result = hardener.generate("192.168.1.100", mock_recommendations, output_dir=out_dir)

        # 断言
        assert result.status == HardenStatus.GENERATED, f"状态错误: {result.status}"
        assert result.action_count == 3
        assert result.script_path is not None
        assert result.rollback_path is not None
        assert os.path.exists(result.script_path), f"加固脚本未生成: {result.script_path}"
        assert os.path.exists(result.rollback_path), f"回滚脚本未生成: {result.rollback_path}"
        print(f"[OK] 状态: {result.status.value}")

        # 检查加固脚本内容
        with open(result.script_path, encoding="utf-8") as f:
            harden_text = f.read()
        assert "#!/bin/bash" in harden_text, "缺少 shebang"
        assert "R4" in harden_text, "缺少 R4 所有权提示"
        assert "iptables -A INPUT -p tcp --dport 23 -j DROP" in harden_text, "缺少 iptables 命令"
        assert "PermitRootLogin no" in harden_text, "缺少 SSH 加固命令"
        assert "apt update" in harden_text, "缺少组件升级命令"
        assert "read -r -p" in harden_text, "缺少所有权确认输入"
        print(f"[OK] 加固脚本: {len(harden_text)} 字符，含 R4 阻断门 + iptables + SSH + apt")

        # 检查回滚脚本内容
        with open(result.rollback_path, encoding="utf-8") as f:
            rollback_text = f.read()
        assert "#!/bin/bash" in rollback_text, "回滚脚本缺少 shebang"
        assert "iptables -D INPUT -p tcp --dport 23 -j DROP" in rollback_text, "回滚脚本缺少 iptables -D"
        assert "无法自动回滚" in rollback_text or "apt" in rollback_text, "缺少不可逆操作标注"
        print(f"[OK] 回滚脚本: {len(rollback_text)} 字符，含 iptables -D 逆操作")

        # 空推荐 → NO_ACTION
        empty_result = hardener.generate("127.0.0.1", [], output_dir=out_dir)
        assert empty_result.status == HardenStatus.NO_ACTION
        print(f"[OK] 空推荐 → {empty_result.status.value}")

        # 变量替换
        substituted = hardener._substitute("iptables -A INPUT -p tcp --dport {port} -j DROP", "8080", "192.168.1.1")
        assert "--dport 8080" in substituted, f"端口替换失败: {substituted}"
        print(f"[OK] 变量替换: {substituted[:60]}")

        print("=== LinuxHardener: ALL PASSED ===")
    finally:
        import shutil

        shutil.rmtree(out_dir, ignore_errors=True)
