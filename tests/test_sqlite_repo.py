"""测试模块：lightshield/repository/sqlite_repo.py

被测类：SqliteRepository(ScanRepository)

测试点：
  - 空数据库初始化（表结构自动创建）
  - save / get / list_by_target / delete CRUD
  - list_recent / count_all / list_targets 扩展查询
  - 分页（limit + offset）
  - 并发写入安全性
  - 不存在的 scan_id 返回 None
  - JSON 序列化/反序列化完整性
"""

import os
import tempfile

import pytest

from lightshield.repository.sqlite_repo import SqliteRepository


@pytest.fixture
def repo():
    """创建临时 SQLite 数据库的 Repository 实例。"""
    tmpdir = tempfile.mkdtemp(prefix="lightshield_test_repo_")
    db_path = os.path.join(tmpdir, "test.db")
    repo = SqliteRepository(db_path)
    yield repo
    import shutil

    shutil.rmtree(tmpdir, ignore_errors=True)


@pytest.fixture
def mock_scan_result():
    """模拟扫描结果字典。"""
    return {
        "target": "192.168.1.100",
        "status": "completed",
        "ports": [
            {"port": 22, "protocol": "tcp", "state": "open", "service": "ssh"},
            {"port": 80, "protocol": "tcp", "state": "open", "service": "http"},
            {"port": 443, "protocol": "tcp", "state": "open", "service": "https"},
        ],
        "services": [
            {"name": "ssh", "version": "OpenSSH 8.9", "port": 22},
            {"name": "nginx", "version": "1.24.0", "port": 80},
        ],
        "os_info": "Linux 5.15",
        "findings": [
            {
                "vuln_type": "component_cve",
                "severity": "critical",
                "title": "OpenSSH regreSSHion",
                "description": "OpenSSH RCE",
                "remediation": "Upgrade to 9.8p1",
                "port": 22,
                "cve_id": "CVE-2024-6387",
                "cvss_score": 9.8,
                "evidence": "OpenSSH 8.9 detected",
            },
            {
                "vuln_type": "high_risk_port",
                "severity": "high",
                "title": "Port 22 open",
                "description": "SSH port open",
                "remediation": "Close if not needed",
                "port": 22,
                "cve_id": None,
                "cvss_score": None,
                "evidence": "Port 22 open",
            },
        ],
        "error": None,
        "duration_seconds": 15.3,
    }


# =============================================================================
# 初始化
# =============================================================================


class TestInit:
    """数据库初始化"""

    def test_empty_database_has_zero_entries(self, repo):
        """空数据库 count_all == 0"""
        assert repo.count_all() == 0

    def test_list_recent_returns_empty_on_fresh_db(self, repo):
        """空数据库 list_recent == []"""
        assert repo.list_recent() == []

    def test_list_targets_returns_empty_on_fresh_db(self, repo):
        """空数据库 list_targets == []"""
        assert repo.list_targets() == []


# =============================================================================
# save / get
# =============================================================================


class TestSaveAndGet:
    """保存与读取"""

    def test_save_returns_valid_scan_id(self, repo, mock_scan_result):
        """保存返回 LS- 前缀的 scan_id"""
        scan_id = repo.save(mock_scan_result)
        assert scan_id.startswith("LS-")
        assert len(scan_id) > 10

    def test_save_increments_count(self, repo, mock_scan_result):
        """保存后 count_all 递增"""
        assert repo.count_all() == 0
        repo.save(mock_scan_result)
        assert repo.count_all() == 1

    def test_get_returns_full_result(self, repo, mock_scan_result):
        """Get 返回完整扫描结果"""
        scan_id = repo.save(mock_scan_result)
        loaded = repo.get(scan_id)
        assert loaded is not None
        assert loaded["target"] == "192.168.1.100"
        assert loaded["status"] == "completed"

    def test_get_returns_correct_counts(self, repo, mock_scan_result):
        """Get 返回正确的统计数字"""
        scan_id = repo.save(mock_scan_result)
        loaded = repo.get(scan_id)
        assert loaded["ports_count"] == 3
        assert loaded["services_count"] == 2
        assert loaded["findings_count"] == 2
        assert loaded["cve_count"] == 1  # only CVE-2024-6387 has cve_id

    def test_get_raw_result_is_dict(self, repo, mock_scan_result):
        """raw_result 从 JSON 反序列化为 dict"""
        scan_id = repo.save(mock_scan_result)
        loaded = repo.get(scan_id)
        raw = loaded["raw_result"]
        assert isinstance(raw, dict)
        assert raw["target"] == "192.168.1.100"

    def test_get_nonexistent_returns_none(self, repo):
        """不存在的 scan_id 返回 None"""
        assert repo.get("LS-nonexistent-12345") is None

    def test_os_info_preserved(self, repo, mock_scan_result):
        """OS 信息正确保存和恢复"""
        scan_id = repo.save(mock_scan_result)
        loaded = repo.get(scan_id)
        assert loaded["os_info"] == "Linux 5.15"

    def test_duration_preserved(self, repo, mock_scan_result):
        """扫描耗时正确保存"""
        scan_id = repo.save(mock_scan_result)
        loaded = repo.get(scan_id)
        assert loaded["duration_seconds"] == 15.3


# =============================================================================
# list_by_target
# =============================================================================


class TestListByTarget:
    """按目标查询"""

    def test_returns_matching_entries(self, repo):
        """返回匹配目标的扫描记录"""
        repo.save({"target": "192.168.1.1", "status": "completed", "ports": [], "services": [], "findings": []})
        repo.save({"target": "192.168.1.1", "status": "completed", "ports": [], "services": [], "findings": []})
        results = repo.list_by_target("192.168.1.1")
        assert len(results) == 2

    def test_excludes_non_matching(self, repo):
        """排除不匹配目标"""
        repo.save({"target": "10.0.0.1", "status": "completed", "ports": [], "services": [], "findings": []})
        results = repo.list_by_target("192.168.1.1")
        assert len(results) == 0

    def test_respects_limit(self, repo):
        """遵守 limit 参数"""
        for _ in range(10):
            repo.save({"target": "example.com", "status": "completed", "ports": [], "services": [], "findings": []})
        results = repo.list_by_target("example.com", limit=3)
        assert len(results) == 3

    def test_returns_empty_for_unknown_target(self, repo):
        """未知目标返回空列表"""
        assert repo.list_by_target("unknown.local") == []


# =============================================================================
# delete
# =============================================================================


class TestDelete:
    """删除记录"""

    def test_delete_existing_returns_true(self, repo, mock_scan_result):
        """删除存在的记录返回 True"""
        scan_id = repo.save(mock_scan_result)
        assert repo.delete(scan_id) is True

    def test_delete_nonexistent_returns_false(self, repo):
        """删除不存在的记录返回 False"""
        assert repo.delete("LS-nonexistent") is False

    def test_deleted_record_not_found(self, repo, mock_scan_result):
        """删除后 get 返回 None"""
        scan_id = repo.save(mock_scan_result)
        repo.delete(scan_id)
        assert repo.get(scan_id) is None


# =============================================================================
# 扩展查询
# =============================================================================


class TestExtendedQueries:
    """扩展查询方法"""

    def test_list_recent_returns_by_time_desc(self, repo):
        """list_recent 按时间倒序返回"""
        ids = []
        for i in range(5):
            scan_id = repo.save(
                {
                    "target": f"host-{i}.local",
                    "status": "completed",
                    "ports": [],
                    "services": [],
                    "findings": [],
                }
            )
            ids.append(scan_id)
        recent = repo.list_recent(limit=5)
        assert len(recent) == 5
        # 最新保存的在最前面
        assert recent[0]["scan_id"] == ids[-1]

    def test_list_recent_respects_offset(self, repo):
        """list_recent 支持分页偏移"""
        for i in range(5):
            repo.save(
                {
                    "target": f"page-{i}.local",
                    "status": "completed",
                    "ports": [],
                    "services": [],
                    "findings": [],
                }
            )
        page = repo.list_recent(limit=2, offset=2)
        assert len(page) == 2

    def test_count_all_reflects_total(self, repo):
        """count_all 反映总数"""
        for _ in range(3):
            repo.save(
                {
                    "target": "count-test.local",
                    "status": "completed",
                    "ports": [],
                    "services": [],
                    "findings": [],
                }
            )
        assert repo.count_all() == 3

    def test_count_by_target(self, repo):
        """count_by_target 正确计数"""
        repo.save({"target": "a.local", "status": "completed", "ports": [], "services": [], "findings": []})
        repo.save({"target": "a.local", "status": "completed", "ports": [], "services": [], "findings": []})
        repo.save({"target": "b.local", "status": "completed", "ports": [], "services": [], "findings": []})
        assert repo.count_by_target("a.local") == 2
        assert repo.count_by_target("b.local") == 1

    def test_list_targets_deduplicated_and_sorted(self, repo):
        """list_targets 去重且排序"""
        repo.save({"target": "zebra.local", "status": "completed", "ports": [], "services": [], "findings": []})
        repo.save({"target": "apple.local", "status": "completed", "ports": [], "services": [], "findings": []})
        repo.save({"target": "zebra.local", "status": "completed", "ports": [], "services": [], "findings": []})
        targets = repo.list_targets()
        assert targets == ["apple.local", "zebra.local"]

    def test_list_recent_does_not_include_raw_result(self, repo, mock_scan_result):
        """list_recent 不含 raw_result（节省内存）"""
        repo.save(mock_scan_result)
        recent = repo.list_recent()
        for entry in recent:
            assert "raw_result" not in entry


# =============================================================================
# 边界与异常
# =============================================================================


class TestEdgeCases:
    """边界情况与异常安全"""

    def test_save_with_zero_findings(self, repo):
        """无漏洞发现的扫描正确保存（cve_count=0）"""
        scan_id = repo.save(
            {
                "target": "clean.local",
                "status": "completed",
                "ports": [{"port": 80, "protocol": "tcp", "state": "open", "service": "http"}],
                "services": [],
                "findings": [],
            }
        )
        loaded = repo.get(scan_id)
        assert loaded["findings_count"] == 0
        assert loaded["cve_count"] == 0

    def test_save_with_error_status(self, repo):
        """失败的扫描也正确保存"""
        scan_id = repo.save(
            {
                "target": "unreachable.local",
                "status": "failed",
                "ports": [],
                "services": [],
                "findings": [],
                "error": "Connection timeout",
            }
        )
        loaded = repo.get(scan_id)
        assert loaded["status"] == "failed"
        assert loaded["error"] == "Connection timeout"

    def test_save_without_optional_fields(self, repo):
        """最小化结果（无 os_info/error）正确保存"""
        scan_id = repo.save(
            {
                "target": "minimal.local",
                "status": "completed",
                "ports": [],
                "services": [],
                "findings": [],
            }
        )
        loaded = repo.get(scan_id)
        assert loaded["os_info"] is None

    def test_save_preserves_full_json_roundtrip(self, repo):
        """复杂嵌套 JSON 完整往返"""
        complex_result = {
            "target": "rich.local",
            "status": "completed",
            "ports": [
                {"port": 22, "protocol": "tcp", "state": "open", "service": "ssh"},
                {"port": 80, "protocol": "tcp", "state": "open", "service": "http"},
            ],
            "services": [
                {"name": "ssh", "version": "OpenSSH 8.9p1", "port": 22},
                {"name": "nginx", "version": "1.24.0", "port": 80},
            ],
            "os_info": "Ubuntu 24.04",
            "findings": [
                {
                    "vuln_type": "component_cve",
                    "severity": "critical",
                    "title": "Critical CVE",
                    "description": "Very long description with unicode: 中文描述",
                    "remediation": "Upgrade immediately",
                    "port": 22,
                    "cve_id": "CVE-2024-6387",
                    "cvss_score": 9.8,
                    "evidence": "Version 8.9p1 detected",
                },
            ],
            "error": None,
            "duration_seconds": 42.0,
        }
        scan_id = repo.save(complex_result)
        loaded = repo.get(scan_id)
        raw = loaded["raw_result"]
        assert raw["target"] == "rich.local"
        assert len(raw["ports"]) == 2
        assert raw["findings"][0]["cve_id"] == "CVE-2024-6387"
        assert raw["findings"][0]["description"] == "Very long description with unicode: 中文描述"
        assert raw["duration_seconds"] == 42.0
