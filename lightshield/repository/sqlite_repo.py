"""SqliteRepository — SQLite 扫描结果持久化

v0.0.25 实现。零新依赖（仅 Python 标准库 sqlite3）。
实现 ScanRepository 抽象，支持扫描历史的 CRUD 和列表查询。

表结构（scans）：
  scan_id TEXT PRIMARY KEY    — 唯一扫描标识
  target TEXT NOT NULL        — 扫描目标
  status TEXT NOT NULL        — 扫描状态
  ports_count INTEGER         — 发现端口数
  services_count INTEGER      — 发现服务数
  findings_count INTEGER      — 漏洞发现数
  cve_count INTEGER           — CVE 命中数
  os_info TEXT                — 操作系统信息
  error TEXT                  — 错误信息
  duration_seconds REAL       — 扫描耗时
  raw_result TEXT NOT NULL    — 完整 ScanResult JSON
  created_at TEXT NOT NULL    — 创建时间 ISO8601
"""

from __future__ import annotations

import contextlib
import json
import os
import sqlite3
import uuid
from datetime import datetime

from lightshield.repository.base import ScanRepository
from lightshield.utils.logger import get_logger


class SqliteRepository(ScanRepository):
    """SQLite 扫描结果持久化 — v0.0.25 实现。

    用法：
        repo = SqliteRepository("data/lightshield.db")
        scan_id = repo.save(result_dict)
        history = repo.list_recent(limit=20)
        detail = repo.get(scan_id)
    """

    _SCHEMA = """
    CREATE TABLE IF NOT EXISTS scans (
        scan_id         TEXT PRIMARY KEY,
        target          TEXT NOT NULL,
        status          TEXT NOT NULL,
        ports_count     INTEGER DEFAULT 0,
        services_count  INTEGER DEFAULT 0,
        findings_count  INTEGER DEFAULT 0,
        cve_count       INTEGER DEFAULT 0,
        os_info         TEXT,
        error           TEXT,
        duration_seconds REAL DEFAULT 0,
        raw_result      TEXT NOT NULL,
        created_at      TEXT NOT NULL
    );
    """

    _INDEXES = [
        "CREATE INDEX IF NOT EXISTS idx_scans_target ON scans(target);",
        "CREATE INDEX IF NOT EXISTS idx_scans_created ON scans(created_at DESC);",
        "CREATE INDEX IF NOT EXISTS idx_scans_status ON scans(status);",
    ]

    def __init__(self, db_url: str = "data/lightshield.db"):
        """初始化 SQLite 存储。

        Args:
            db_url: SQLite 数据库文件路径。
                    自动创建目录和表结构。
        """
        super().__init__()
        self._db_path = db_url
        self._logger = get_logger()

        # 确保目录存在
        db_dir = os.path.dirname(db_url)
        if db_dir:
            os.makedirs(db_dir, exist_ok=True)

        # 初始化表结构
        self._ensure_schema()

    def _ensure_schema(self) -> None:
        """创建表结构和索引（幂等操作）。"""
        try:
            with self._connect() as conn:
                conn.executescript(self._SCHEMA)
                for idx_sql in self._INDEXES:
                    conn.execute(idx_sql)
        except sqlite3.Error as e:
            self._logger.error("sqlite_repo", f"初始化表结构失败: {e}")

    def _connect(self) -> sqlite3.Connection:
        """创建数据库连接（每次调用返回新连接，线程安全）。"""
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row  # 使查询结果可通过列名访问
        conn.execute("PRAGMA journal_mode=WAL")  # WAL 模式提升并发读性能
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    # =========================================================================
    # ScanRepository 接口实现
    # =========================================================================

    def save(self, result: dict) -> str:
        """保存扫描结果，返回 scan_id。

        Args:
            result: 扫描结果字典（ScanResult.to_dict() 或兼容结构）

        Returns:
            scan_id: 格式 "LS-YYYYMMDD-HHMMSS-xxxxxxxx"
        """
        scan_id = f"LS-{datetime.now().strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:8]}"

        findings = result.get("findings", [])
        cve_count = sum(1 for f in findings if f.get("cve_id"))

        row = {
            "scan_id": scan_id,
            "target": result.get("target", "unknown"),
            "status": result.get("status", "unknown"),
            "ports_count": len(result.get("ports", [])),
            "services_count": len(result.get("services", [])),
            "findings_count": len(findings),
            "cve_count": cve_count,
            "os_info": result.get("os_info"),
            "error": result.get("error"),
            "duration_seconds": result.get("duration_seconds", 0),
            "raw_result": json.dumps(result, ensure_ascii=False),
            "created_at": datetime.now().isoformat(),
        }

        try:
            with self._connect() as conn:
                conn.execute(
                    """INSERT INTO scans (
                        scan_id, target, status, ports_count, services_count,
                        findings_count, cve_count, os_info, error,
                        duration_seconds, raw_result, created_at
                    ) VALUES (
                        :scan_id, :target, :status, :ports_count, :services_count,
                        :findings_count, :cve_count, :os_info, :error,
                        :duration_seconds, :raw_result, :created_at
                    )""",
                    row,
                )
            self._logger.info("sqlite_repo", f"扫描已保存: {scan_id} target={row['target']}")
            return scan_id
        except sqlite3.Error as e:
            self._logger.error("sqlite_repo", f"保存扫描失败: {e}")
            raise OSError(f"数据库写入失败: {e}") from e

    def get(self, scan_id: str) -> dict | None:
        """按 scan_id 获取扫描结果（含完整 JSON）。"""
        try:
            with self._connect() as conn:
                row = conn.execute("SELECT * FROM scans WHERE scan_id = ?", (scan_id,)).fetchone()
                if row is None:
                    return None
                return self._row_to_dict(row)
        except sqlite3.Error as e:
            self._logger.error("sqlite_repo", f"读取扫描失败: {e}")
            return None

    def list_by_target(self, target: str, limit: int = 50) -> list[dict]:
        """列出指定目标的历史扫描（按时间倒序）。"""
        try:
            with self._connect() as conn:
                rows = conn.execute(
                    """SELECT * FROM scans
                       WHERE target = ?
                       ORDER BY created_at DESC
                       LIMIT ?""",
                    (target, limit),
                ).fetchall()
                return [self._row_to_dict(r) for r in rows]
        except sqlite3.Error as e:
            self._logger.error("sqlite_repo", f"查询扫描历史失败: {e}")
            return []

    def delete(self, scan_id: str) -> bool:
        """删除指定扫描记录。"""
        try:
            with self._connect() as conn:
                cursor = conn.execute("DELETE FROM scans WHERE scan_id = ?", (scan_id,))
                deleted = cursor.rowcount > 0
                if deleted:
                    self._logger.info("sqlite_repo", f"扫描已删除: {scan_id}")
                return deleted
        except sqlite3.Error as e:
            self._logger.error("sqlite_repo", f"删除扫描失败: {e}")
            return False

    # =========================================================================
    # 扩展查询方法（超越 ScanRepository 抽象）
    # =========================================================================

    def list_recent(self, limit: int = 20, offset: int = 0) -> list[dict]:
        """列出最近扫描记录（全部目标，按时间倒序）。

        Args:
            limit: 最大返回条数
            offset: 分页偏移

        Returns:
            扫描摘要列表（不含 raw_result 完整 JSON，节省内存）
        """
        try:
            with self._connect() as conn:
                rows = conn.execute(
                    """SELECT scan_id, target, status, ports_count,
                              services_count, findings_count, cve_count,
                              os_info, error, duration_seconds, created_at
                       FROM scans
                       ORDER BY created_at DESC
                       LIMIT ? OFFSET ?""",
                    (limit, offset),
                ).fetchall()
                return [dict(r) for r in rows]
        except sqlite3.Error as e:
            self._logger.error("sqlite_repo", f"查询最近扫描失败: {e}")
            return []

    def count_all(self) -> int:
        """返回扫描历史总数。"""
        try:
            with self._connect() as conn:
                row = conn.execute("SELECT COUNT(*) as cnt FROM scans").fetchone()
                return row["cnt"] if row else 0
        except sqlite3.Error:
            return 0

    def count_by_target(self, target: str) -> int:
        """返回指定目标的扫描次数。"""
        try:
            with self._connect() as conn:
                row = conn.execute("SELECT COUNT(*) as cnt FROM scans WHERE target = ?", (target,)).fetchone()
                return row["cnt"] if row else 0
        except sqlite3.Error:
            return 0

    def list_targets(self) -> list[str]:
        """返回所有被扫描过的目标列表（去重）。"""
        try:
            with self._connect() as conn:
                rows = conn.execute("SELECT DISTINCT target FROM scans ORDER BY target").fetchall()
                return [r["target"] for r in rows]
        except sqlite3.Error:
            return []

    # =========================================================================
    # 内部工具
    # =========================================================================

    @staticmethod
    def _row_to_dict(row: sqlite3.Row) -> dict:
        """将 sqlite3.Row 转为 dict，raw_result 从 JSON 反序列化。"""
        d = dict(row)
        raw = d.get("raw_result")
        if isinstance(raw, str):
            with contextlib.suppress(json.JSONDecodeError):
                d["raw_result"] = json.loads(raw)
        return d


# =============================================================================
# 自检
# =============================================================================

if __name__ == "__main__":
    import tempfile

    print("=== SqliteRepository 自检 ===")

    # 临时数据库
    tmpdir = tempfile.mkdtemp(prefix="lightshield_sqlite_test_")
    db_path = os.path.join(tmpdir, "test.db")

    try:
        repo = SqliteRepository(db_path)

        # 1. 空状态
        assert repo.count_all() == 0
        assert repo.list_recent() == []
        assert repo.list_targets() == []
        print("✅ 空数据库初始化通过")

        # 2. 保存扫描
        mock_result = {
            "target": "192.168.1.1",
            "status": "completed",
            "ports": [
                {"port": 22, "protocol": "tcp", "state": "open", "service": "ssh"},
                {"port": 80, "protocol": "tcp", "state": "open", "service": "http"},
            ],
            "services": [
                {"name": "ssh", "version": "OpenSSH 8.9", "port": 22},
                {"name": "nginx", "version": "1.24.0", "port": 80},
            ],
            "findings": [
                {"vuln_type": "component_cve", "cve_id": "CVE-2024-6387", "severity": "critical", "title": "test"},
                {"vuln_type": "high_risk_port", "cve_id": None, "severity": "high", "title": "port 22"},
            ],
            "os_info": "Linux 5.15",
            "duration_seconds": 12.5,
        }
        scan_id = repo.save(mock_result)
        assert scan_id.startswith("LS-")
        assert repo.count_all() == 1
        print(f"✅ 保存扫描: {scan_id}")

        # 3. 读取扫描
        loaded = repo.get(scan_id)
        assert loaded is not None
        assert loaded["target"] == "192.168.1.1"
        assert loaded["ports_count"] == 2
        assert loaded["services_count"] == 2
        assert loaded["findings_count"] == 2
        assert loaded["cve_count"] == 1
        assert loaded["os_info"] == "Linux 5.15"
        assert isinstance(loaded["raw_result"], dict)
        print(f"✅ 读取扫描: target={loaded['target']} ports={loaded['ports_count']} cve={loaded['cve_count']}")

        # 4. 列表查询
        recent = repo.list_recent()
        assert len(recent) == 1
        assert recent[0]["scan_id"] == scan_id
        print(f"✅ 最近扫描: {len(recent)} 条")

        # 5. 按目标查询
        by_target = repo.list_by_target("192.168.1.1")
        assert len(by_target) == 1
        by_target_none = repo.list_by_target("10.0.0.1")
        assert by_target_none == []
        print(f"✅ 按目标查询: 192.168.1.1 → {len(by_target)} 条, 10.0.0.1 → {len(by_target_none)} 条")

        # 6. 目标去重
        repo.save({"target": "10.0.0.1", "status": "completed", "findings": [], "ports": [], "services": []})
        targets = repo.list_targets()
        assert set(targets) == {"192.168.1.1", "10.0.0.1"}
        assert repo.count_all() == 2
        print(f"✅ 目标列表: {targets}")

        # 7. 读取不存在的扫描
        assert repo.get("LS-nonexistent") is None
        print("✅ 不存在扫描返回 None")

        # 8. 分页
        for i in range(5):
            repo.save({"target": f"test-{i}.local", "status": "completed", "findings": [], "ports": [], "services": []})
        page1 = repo.list_recent(limit=3, offset=0)
        assert len(page1) == 3
        page2 = repo.list_recent(limit=3, offset=3)
        assert len(page2) == 3
        print(f"✅ 分页查询: page1={len(page1)} page2={len(page2)}")

        # 9. 删除扫描
        assert repo.delete(scan_id) is True
        assert repo.get(scan_id) is None
        assert repo.delete("LS-nonexistent") is False
        print("✅ 删除扫描")

        print("\n=== SqliteRepository 自检全部通过 ===")
    finally:
        import shutil

        shutil.rmtree(tmpdir, ignore_errors=True)
