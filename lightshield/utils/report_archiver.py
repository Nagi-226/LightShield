"""LightShield Loop Hook — 报告自动归档（v0.0.40）

卡兹克 Hook #4「文件自动整理」落地：安全报告按日期+目标自动归档，
保持 reports/ 目录整洁，方便回溯历史扫描结果。

目录结构：
    reports/
    ├── 2026-06/
    │   ├── 26/
    │   │   ├── 127.0.0.1/
    │   │   │   ├── scan_20260626-143022.md
    │   │   │   ├── harden_20260626-143045.sh
    │   │   │   └── rollback_20260626-143045.sh
    │   │   └── example.com/
    │   │       └── scan_20260626-150000.md
    │   └── 27/
    └── latest/  ← 软链接指向最近一次的报告目录

设计原则：
  - 纯文件操作，不引入新依赖
  - 失败不影响安全扫描流程
  - 按日期+目标二级归档，自然去重
  - 可配置保留天数，自动清理过期报告

用法：
    from lightshield.utils.report_archiver import archive_report
    archive_report("reports/scan_x.md", target="127.0.0.1")
"""

from __future__ import annotations

import datetime
import os
import shutil

# =============================================================================
# 核心函数
# =============================================================================


def archive_report(
    report_path: str,
    target: str = "unknown",
    *,
    base_dir: str = "./reports",
    max_age_days: int = 90,
) -> str | None:
    """将报告文件归档到按日期+目标组织的目录中。

    文件被**移动**到 `base_dir/YYYY-MM/DD/{target}/` 下，
    同时更新 `base_dir/latest/` 软链接指向最新归档日期。

    Args:
        report_path: 报告文件的当前路径
        target: 扫描目标（IP/域名），用于子目录命名
        base_dir: 报告根目录，默认 ./reports
        max_age_days: 归档后自动清理超过此天数的旧报告（0=不清理）

    Returns:
        归档后的文件路径，或 None（归档失败时）

    Raises:
        不抛异常——失败静默，不影响扫描流程
    """
    if not report_path or not os.path.isfile(report_path):
        return None

    try:
        now = datetime.datetime.now()
        # 目录结构: reports/YYYY-MM/DD/target/
        date_dir = os.path.join(
            base_dir,
            now.strftime("%Y-%m"),
            now.strftime("%d"),
            _safe_dirname(target),
        )
        os.makedirs(date_dir, exist_ok=True)

        # 移动文件
        filename = os.path.basename(report_path)
        dest = os.path.join(date_dir, filename)
        shutil.move(report_path, dest)

        # 更新 latest 软链接
        _update_latest_link(base_dir, date_dir)

        # 按需清理
        if max_age_days > 0:
            _cleanup_old(base_dir, max_age_days)

        return os.path.abspath(dest)

    except OSError:
        # 静默失败——不阻断安全扫描的核心流程
        return None


def archive_harden_scripts(
    script_path: str | None,
    rollback_path: str | None,
    target: str = "unknown",
    *,
    base_dir: str = "./reports",
) -> tuple[str | None, str | None]:
    """归档加固脚本和回滚脚本。

    Args:
        script_path: 加固脚本路径
        rollback_path: 回滚脚本路径
        target: 加固目标
        base_dir: 报告根目录

    Returns:
        (归档后的 script 路径, 归档后的 rollback 路径)
    """
    archived_script = archive_report(script_path, target, base_dir=base_dir) if script_path else None
    archived_rollback = archive_report(rollback_path, target, base_dir=base_dir) if rollback_path else None
    return archived_script, archived_rollback


# =============================================================================
# 内部辅助
# =============================================================================


def _safe_dirname(target: str) -> str:
    """将目标转为安全的目录名。

    替换非法字符为下划线，确保目录名不含路径分隔符。
    """
    safe = target.strip().replace("/", "_").replace("\\", "_").replace(":", "_")
    safe = safe.replace("*", "_").replace("?", "_").replace('"', "_")
    safe = safe.replace("<", "_").replace(">", "_").replace("|", "_")
    # 截断过长目标名
    return safe[:80] if len(safe) > 80 else safe


def _update_latest_link(base_dir: str, latest_target_dir: str) -> None:
    """更新 latest 软链接（跨平台兼容）。"""
    latest_link = os.path.join(base_dir, "latest")
    try:
        # Windows: 删除旧链接/目录
        if os.path.islink(latest_link) or os.path.exists(latest_link):
            if os.path.islink(latest_link):
                os.unlink(latest_link)
            elif os.path.isdir(latest_link):
                # 如果 latest 已经是真实目录（非符号链接），不覆盖
                return

        # 计算相对路径
        rel = os.path.relpath(latest_target_dir, base_dir)
        os.symlink(rel, latest_link)

    except OSError:
        # 软链接创建失败（Windows 可能需管理员权限）→ 静默跳过
        pass


def _cleanup_old(base_dir: str, max_age_days: int) -> None:
    """清理超过保留期限的报告目录。"""
    cutoff = datetime.datetime.now() - datetime.timedelta(days=max_age_days)

    try:
        for month_dir_name in os.listdir(base_dir):
            month_dir = os.path.join(base_dir, month_dir_name)
            if not os.path.isdir(month_dir) or month_dir_name == "latest":
                continue

            for day_dir_name in os.listdir(month_dir):
                day_dir = os.path.join(month_dir, day_dir_name)
                if not os.path.isdir(day_dir):
                    continue

                # 按目录修改时间判断是否过期
                try:
                    mtime = datetime.datetime.fromtimestamp(os.path.getmtime(day_dir))
                    if mtime < cutoff:
                        shutil.rmtree(day_dir)
                except OSError:
                    continue
    except OSError:
        pass


# =============================================================================
# 自检
# =============================================================================

if __name__ == "__main__":
    import tempfile

    print("=== report_archiver 自检 ===")

    # 1. 文件不存在 → None
    assert archive_report("/nonexistent/path.md", "test") is None
    print("[OK] 文件不存在 → None")

    # 2. 正常归档流程
    with tempfile.TemporaryDirectory() as tmpdir:
        # 创建一个测试报告文件
        test_file = os.path.join(tmpdir, "scan_test.md")
        with open(test_file, "w", encoding="utf-8") as f:
            f.write("# Test Report\n")

        dest = archive_report(test_file, "127.0.0.1", base_dir=tmpdir)
        assert dest is not None, "归档应成功"
        assert os.path.isfile(dest), f"归档文件应存在: {dest}"
        assert "127.0.0.1" in dest, f"路径应含目标: {dest}"
        print(f"[OK] 报告归档成功: {os.path.relpath(dest, tmpdir)}")

        # 3. latest 软链接
        latest = os.path.join(tmpdir, "latest")
        if os.path.islink(latest):
            print("[OK] latest 软链接已更新")
        else:
            print("[OK] latest 软链接跳过（Windows 需管理员权限，非阻塞）")

        # 4. _safe_dirname
        assert _safe_dirname("example.com") == "example.com"
        assert _safe_dirname("127.0.0.1") == "127.0.0.1"
        assert _safe_dirname("evil.com/path") == "evil.com_path"
        assert "/" not in _safe_dirname("a/b")
        print("[OK] _safe_dirname 路径安全")

        # 5. 非法目标字符替换
        assert _safe_dirname("site:80") == "site_80"
        assert _safe_dirname("a?query") == "a_query"
        assert _safe_dirname("a<b>c|d") == "a_b_c_d"
        print("[OK] _safe_dirname 非法字符替换")

    print("=== report_archiver: ALL PASSED ===")
