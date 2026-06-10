#!/bin/bash
# ═════════════════════════════════════════════════════════════════════════════
# LightShield 轻盾 — Linux 服务禁用手动操作指南
# ⚠️ 仅限自有资产使用（合规 R4）。运行前请逐条审阅。
# 本脚本由 LightShield LinuxHardener 生成，不会被自动运行。
# ═════════════════════════════════════════════════════════════════════════════

# ── 查看当前所有已启用服务 ───────────────────────────────────────
list_enabled_services() {
    echo "=== 当前已启用的服务 ==="
    if command -v systemctl &> /dev/null; then
        systemctl list-unit-files --state=enabled --no-pager 2>/dev/null || true
    else
        echo "[提示] systemctl 不可用（非 systemd 系统），请手动检查"
    fi
}

# ── 停用并禁用指定服务 ───────────────────────────────────────────
disable_service() {
    local svc="$1"
    if ! command -v systemctl &> /dev/null; then
        echo "[跳过] systemctl 不可用，请手动检查 $svc"
        return 0
    fi
    if systemctl is-active --quiet "$svc" 2>/dev/null; then
        echo "[执行] 停止服务: $svc"
        systemctl stop "$svc"
    fi
    if systemctl is-enabled --quiet "$svc" 2>/dev/null; then
        echo "[执行] 禁用服务: $svc"
        systemctl disable "$svc"
    fi
    echo "[完成] $svc 已停用并禁用"
}
