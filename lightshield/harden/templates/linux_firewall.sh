#!/bin/bash
# ═════════════════════════════════════════════════════════════════════════════
# LightShield 轻盾 — Linux 防火墙加固模板
# ⚠️ 仅限自有资产使用（合规 R4）。运行前请逐条审阅本脚本内容。
# 本脚本由 LightShield LinuxHardener 生成，不会被自动运行。
# ═════════════════════════════════════════════════════════════════════════════

set -euo pipefail

# ── R4 所有权确认（阻断门）─────────────────────────────────────────
confirm_ownership() {
    echo "⚠️  本脚本将修改系统防火墙规则。"
    echo "    目标主机：${1:-(未指定)}"
    echo ""
    read -r -p "确认你拥有该主机的所有权或已获明确授权？(yes/no) " answer
    if [ "$answer" != "yes" ]; then
        echo "已取消：未确认所有权。"
        exit 1
    fi
}

# ── 备份文件（加固前快照，用于回滚）────────────────────────────────
backup_file() {
    local file="$1"
    local backup="${file}.bak.$(date +%Y%m%d-%H%M%S)"
    if [ -f "$file" ]; then
        cp "$file" "$backup"
        echo "[备份] $file → $backup"
        echo "$backup"
    else
        echo "[提示] $file 不存在，无需备份"
        echo ""
    fi
}

# ── 保存当前 iptables 规则（回滚用）────────────────────────────────
backup_iptables() {
    local backup_file="/tmp/iptables-backup-$(date +%Y%m%d-%H%M%S).rules"
    if command -v iptables-save &> /dev/null; then
        iptables-save > "$backup_file"
        echo "[备份] iptables 规则已保存到: $backup_file"
        echo "$backup_file"
    else
        echo "[提示] iptables-save 不可用，跳过备份"
        echo ""
    fi
    return 0
}
