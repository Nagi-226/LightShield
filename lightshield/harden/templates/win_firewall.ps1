<#
═════════════════════════════════════════════════════════════════════════════
LightShield 轻盾 — Windows 防火墙加固模板
⚠️  仅限自有资产使用（合规 R4）。运行前请逐条审阅本脚本内容。
本脚本由 LightShield WinHardener 生成，不会被自动运行。
要求以管理员身份运行 PowerShell。
═════════════════════════════════════════════════════════════════════════════
#>

#Requires -RunAsAdministrator

# ── R4 所有权确认（阻断门）─────────────────────────────────────────
function Confirm-Ownership {
    param([string]$Target = "(未指定)")

    Write-Host "╔══════════════════════════════════════════════╗"
    Write-Host "║  ⚠️  本脚本将修改系统防火墙/服务配置。         ║"
    Write-Host "║  仅限自有资产使用（合规 R4）。                 ║"
    Write-Host "╚══════════════════════════════════════════════╝"
    Write-Host ""
    Write-Host "  目标主机：$Target"
    Write-Host ""

    $answer = Read-Host "确认你拥有该主机的所有权或已获明确授权？(yes/no)"
    if ($answer -ne "yes") {
        Write-Host "已取消：未确认所有权。"
        exit 1
    }
}

# ── 备份当前防火墙规则（回滚用）────────────────────────────────────
function Backup-FirewallRules {
    $backupFile = Join-Path $env:TEMP "firewall-backup-$(Get-Date -Format yyyyMMdd-HHmmss).wfw"
    netsh advfirewall export "$backupFile" 2>$null
    if ($LASTEXITCODE -eq 0) {
        Write-Host "[备份] 防火墙规则已保存到: $backupFile"
        return $backupFile
    } else {
        Write-Host "[提示] 防火墙规则导出失败"
        return $null
    }
}

# ── 备份当前服务状态（回滚用）────────────────────────────────────
function Backup-ServiceState {
    $backupFile = Join-Path $env:TEMP "services-backup-$(Get-Date -Format yyyyMMdd-HHmmss).csv"
    Get-Service | Select-Object Name, DisplayName, Status, StartType |
        Export-Csv -Path $backupFile -NoTypeInformation
    Write-Host "[备份] 服务状态已保存到: $backupFile"
    return $backupFile
}

# ── 回滚防火墙规则（从备份恢复）──────────────────────────────────
function Restore-FirewallRules {
    param([string]$BackupFile)
    if (-not $BackupFile -or -not (Test-Path $BackupFile)) {
        Write-Host "[警告] 防火墙备份文件不存在，无法恢复"
        return $false
    }
    netsh advfirewall import "$BackupFile"
    if ($LASTEXITCODE -eq 0) {
        Write-Host "[回滚] 防火墙规则已从 $BackupFile 恢复"
        return $true
    } else {
        Write-Host "[错误] 防火墙规则恢复失败"
        return $false
    }
}

# ── 回滚服务状态（从 CSV 备份恢复 StartType）────────────────────
function Restore-ServiceState {
    param([string]$BackupFile)
    if (-not $BackupFile -or -not (Test-Path $BackupFile)) {
        Write-Host "[警告] 服务备份文件不存在，无法恢复"
        return
    }
    $services = Import-Csv -Path $BackupFile
    foreach ($svc in $services) {
        $name = $svc.Name
        $current = Get-Service -Name $name -ErrorAction SilentlyContinue
        if ($current) {
            try {
                Set-Service -Name $name -StartupType $svc.StartType -ErrorAction Stop
                Write-Host "[回滚] $name → $($svc.StartType)"
            } catch {
                Write-Host "[警告] $name 恢复失败: $_"
            }
        }
    }
    Write-Host "[回滚] 服务状态已从 $BackupFile 恢复"
}
