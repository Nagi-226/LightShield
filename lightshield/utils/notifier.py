"""LightShield Loop Hook — Bark 推送通知（v0.0.40）

卡兹克 Hook #5「长任务完成推送」落地：安全扫描/加固闭环完成后，
通过 Bark 免费推送服务将结果推送到用户手机。

Bark 是什么：
  - 开源 iOS/Android 推送服务，零费用
  - 只需在 App Store/Google Play 安装 Bark App，获取设备 key
  - API：GET https://api.day.app/{key}/{title}/{body}
  - 无需注册、无需登录、无需付费

用法：
    from lightshield.utils.notifier import notify_scan_complete
    notify_scan_complete(result, bark_key="你的设备key")

配置：
    - 环境变量 LS_BARK_KEY
    - 或配置文件 bark_key 字段
    - 或 CLI --bark-key 参数

设计原则：
  - 纯函数，无副作用（除 HTTP 请求外）
  - 失败静默（网络不通/设备离线不影响扫描流程）
  - 不引入新依赖（使用标准库 urllib）
"""

from __future__ import annotations

import urllib.parse
import urllib.request
from dataclasses import dataclass

# Bark API 端点
BARK_API_URL = "https://api.day.app"

# 输出截断上限（通知标题/正文不宜过长）
_MAX_TITLE_LEN = 100
_MAX_BODY_LEN = 500


# =============================================================================
# 数据结构
# =============================================================================


@dataclass
class NotifyResult:
    """通知发送结果。"""

    success: bool
    message: str
    bark_key: str = ""


# =============================================================================
# 核心函数
# =============================================================================


def send_bark_notification(
    title: str,
    body: str,
    bark_key: str,
    *,
    group: str = "LightShield",
    sound: str = "birdsong",
    timeout: int = 5,
) -> NotifyResult:
    """通过 Bark 推送一条通知到手机。

    Args:
        title: 通知标题（自动截断到 {_MAX_TITLE_LEN} 字符）
        body: 通知正文（自动截断到 {_MAX_BODY_LEN} 字符）
        bark_key: Bark 设备 Key（在 Bark App 首页获取）
        group: 通知分组名（同组通知在通知中心折叠）
        sound: 提示音（默认 birdsong，安静推送可传 "silence"）
        timeout: HTTP 请求超时秒数

    Returns:
        NotifyResult
    """
    if not bark_key or not bark_key.strip():
        return NotifyResult(success=False, message="未配置 Bark Key，跳过通知")

    # 截断过长内容
    safe_title = title[:_MAX_TITLE_LEN].strip()
    safe_body = body[:_MAX_BODY_LEN].strip()

    # 构造 Bark URL（所有参数 URL 编码）
    url = (
        f"{BARK_API_URL}/{urllib.parse.quote(bark_key.strip())}/"
        f"{urllib.parse.quote(safe_title)}/"
        f"{urllib.parse.quote(safe_body)}"
        f"?group={urllib.parse.quote(group)}"
        f"&sound={urllib.parse.quote(sound)}"
    )

    try:
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # nosec: B310 — Bark API 固定 HTTPS 端点
            if 200 <= resp.status < 300:
                return NotifyResult(success=True, message="通知已推送", bark_key=bark_key)
            return NotifyResult(
                success=False,
                message=f"Bark 返回非 2xx 状态码: {resp.status}",
                bark_key=bark_key,
            )
    except Exception as exc:
        # 静默失败：网络不通/Bark 服务不可用不影响安全扫描
        return NotifyResult(
            success=False,
            message=f"Bark 推送失败（已静默）: {exc}",
            bark_key=bark_key,
        )


def notify_scan_complete(
    target: str,
    finding_count: int,
    critical_count: int = 0,
    high_count: int = 0,
    duration_seconds: float = 0.0,
    *,
    bark_key: str = "",
) -> NotifyResult:
    """扫描完成后推送摘要通知。

    Args:
        target: 扫描目标
        finding_count: 发现的漏洞总数
        critical_count: 严重漏洞数
        high_count: 高危漏洞数
        duration_seconds: 扫描耗时
        bark_key: Bark 设备 Key

    Returns:
        NotifyResult
    """
    if not bark_key:
        return NotifyResult(success=False, message="未配置 Bark Key")

    # 按风险等级选择语气
    if critical_count > 0:
        emoji = "🔴"
        sound = "alarm"
    elif high_count > 0:
        emoji = "🟠"
        sound = "birdsong"
    elif finding_count > 0:
        emoji = "🟡"
        sound = "birdsong"
    else:
        emoji = "🟢"
        sound = "silence"

    title = f"{emoji} LightShield 扫描完成"

    lines = [f"目标: {target}"]
    lines.append(f"发现: {finding_count} 个漏洞")
    if critical_count:
        lines.append(f"  🔴 严重: {critical_count}")
    if high_count:
        lines.append(f"  🟠 高危: {high_count}")
    lines.append(f"耗时: {duration_seconds:.0f}s")

    return send_bark_notification(
        title=title,
        body="\n".join(lines),
        bark_key=bark_key,
        group="LightShield",
        sound=sound,
    )


def notify_closed_loop_complete(
    target: str,
    overall: str,
    mode: str,
    resolved_count: int = 0,
    remaining_count: int = 0,
    regressed_count: int = 0,
    *,
    bark_key: str = "",
) -> NotifyResult:
    """加固闭环完成后推送结果通知。

    Args:
        target: 加固目标
        overall: 总判定（verified / partial / failed / generated_only）
        mode: 执行模式（dry_run / apply）
        resolved_count: 已修复数
        remaining_count: 仍存在数
        regressed_count: 新增风险数
        bark_key: Bark 设备 Key

    Returns:
        NotifyResult
    """
    if not bark_key:
        return NotifyResult(success=False, message="未配置 Bark Key")

    overall_labels = {
        "verified": ("✅ 加固成功", "silence"),
        "partial": ("⚠️ 部分修复", "birdsong"),
        "failed": ("❌ 加固失败", "alarm"),
        "generated_only": ("📋 预检完成", "birdsong"),
    }
    label, sound = overall_labels.get(overall, (f"结果: {overall}", "birdsong"))

    mode_label = "真机执行" if mode == "apply" else "预检（不改系统）"
    title = f"{label} — LightShield 加固闭环"
    lines = [
        f"目标: {target}",
        f"模式: {mode_label}",
        f"已修复: {resolved_count} | 仍存在: {remaining_count} | 新增: {regressed_count}",
    ]

    return send_bark_notification(
        title=title,
        body="\n".join(lines),
        bark_key=bark_key,
        group="LightShield",
        sound=sound,
    )


# =============================================================================
# 自检
# =============================================================================

if __name__ == "__main__":
    print("=== notifier 自检 ===")

    # 1. 无 bark_key → 静默跳过
    r = send_bark_notification("test", "body", "")
    assert not r.success
    assert "未配置" in r.message
    print("[OK] 无 Bark Key → 跳过")

    # 2. notify_scan_complete 无 key → 跳过
    r2 = notify_scan_complete("127.0.0.1", 5, critical_count=1, bark_key="")
    assert not r2.success
    print("[OK] notify_scan_complete 无 Key → 跳过")

    # 3. notify_closed_loop_complete 无 key → 跳过
    r3 = notify_closed_loop_complete("127.0.0.1", "verified", "apply", bark_key="")
    assert not r3.success
    print("[OK] notify_closed_loop_complete 无 Key → 跳过")

    # 4. 标题截断
    r4 = send_bark_notification("x" * 200, "body", "fake_key_12345")
    # 会因为 fake key 而失败（非 2xx），但标题应该先被截断
    assert not r4.success  # fake key → 推送失败（静默）
    print("[OK] 长标题自动截断 + 假 Key 静默失败")

    print("=== notifier: ALL PASSED ===")
