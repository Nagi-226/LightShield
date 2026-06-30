"""Repository 持久化层单元测试 — v0.0.45 覆盖率提升 T1。

覆盖 lightshield/repository/base.py：
  - JsonFileRepository: save / get / list_by_target / delete / list_recent
  - get_repository 工厂函数：按 backend+key 缓存（H-008 修复验证）
"""

from __future__ import annotations

import os

from lightshield.repository.base import JsonFileRepository, get_repository

# =============================================================================
# 辅助
# =============================================================================


def _sample_result(**overrides) -> dict:
    """构造测试用扫描结果 dict。"""
    data = {
        "target": "127.0.0.1",
        "status": "completed",
        "ports": [{"port": 22, "state": "open"}],
        "services": [{"name": "ssh", "port": 22}],
        "findings": [
            {"vuln_type": "high_risk_port", "severity": "high", "cve_id": None},
            {"vuln_type": "weak_password", "severity": "critical", "cve_id": "CVE-2024-0001"},
        ],
        "os_info": "Ubuntu 22.04",
        "error": None,
        "duration_seconds": 12.5,
    }
    data.update(overrides)
    return data


# =============================================================================
# get_repository 工厂 — H-008 修复验证
# =============================================================================


class TestGetRepository:
    """验证 H-008：按 backend+key 缓存，同 key 复用，不同 key 独立。"""

    def test_same_backend_and_key_returns_same_instance(self):
        r1 = get_repository("json", data_dir="./data")
        r2 = get_repository("json", data_dir="./data")
        assert r1 is r2

    def test_different_backend_returns_different_instance(self):
        r1 = get_repository("json", data_dir="./data")
        r2 = get_repository("sqlite", db_url="data/test.db")
        assert r1 is not r2

    def test_same_backend_different_key_returns_different_instance(self):
        r1 = get_repository("json", data_dir="./data-a")
        r2 = get_repository("json", data_dir="./data-b")
        assert r1 is not r2

    def test_default_backend_is_json(self):
        repo = get_repository()
        assert isinstance(repo, JsonFileRepository)

    def test_unsupported_backend_raises(self):
        with __import__("pytest").raises(ValueError, match="不支持的存储后端"):
            get_repository("mongodb")


# =============================================================================
# JsonFileRepository.save
# =============================================================================


class TestSave:
    """save()：创建 JSON 文件，返回 scan_id。"""

    def test_save_creates_file_and_returns_scan_id(self, tmp_path):
        repo = JsonFileRepository(data_dir=str(tmp_path))
        scan_id = repo.save(_sample_result())
        assert scan_id.startswith("LS-")
        # 验证文件存在
        assert repo.get(scan_id) is not None

    def test_saved_data_round_trips(self, tmp_path):
        repo = JsonFileRepository(data_dir=str(tmp_path))
        original = _sample_result(target="10.0.0.1")
        scan_id = repo.save(original)
        loaded = repo.get(scan_id)
        assert loaded is not None
        assert loaded["target"] == "10.0.0.1"
        assert loaded["status"] == "completed"
        assert loaded["scan_id"] == scan_id
        assert "saved_at" in loaded


# =============================================================================
# JsonFileRepository.get
# =============================================================================


class TestGet:
    """get()：按 scan_id 查找并加载。"""

    def test_get_existing_returns_dict(self, tmp_path):
        repo = JsonFileRepository(data_dir=str(tmp_path))
        scan_id = repo.save(_sample_result())
        loaded = repo.get(scan_id)
        assert isinstance(loaded, dict)
        assert loaded["target"] == "127.0.0.1"

    def test_get_nonexistent_returns_none(self, tmp_path):
        repo = JsonFileRepository(data_dir=str(tmp_path))
        assert repo.get("LS-nonexistent") is None

    def test_get_when_scans_dir_missing_returns_none(self, tmp_path):
        repo = JsonFileRepository(data_dir=str(tmp_path))
        # 不调用 save，scans 目录未创建
        assert repo.get("LS-00000000-000000-00000000") is None


# =============================================================================
# JsonFileRepository.list_by_target
# =============================================================================


class TestListByTarget:
    """list_by_target()：按目标筛选，时间倒序，limit 限制。"""

    def test_empty_when_no_scans(self, tmp_path):
        repo = JsonFileRepository(data_dir=str(tmp_path))
        results = repo.list_by_target("127.0.0.1")
        assert results == []

    def test_matching_target_returned(self, tmp_path):
        repo = JsonFileRepository(data_dir=str(tmp_path))
        repo.save(_sample_result(target="192.168.1.1"))
        repo.save(_sample_result(target="10.0.0.1"))
        results = repo.list_by_target("192.168.1.1")
        assert len(results) == 1
        assert results[0]["target"] == "192.168.1.1"

    def test_non_matching_target_returns_empty(self, tmp_path):
        repo = JsonFileRepository(data_dir=str(tmp_path))
        repo.save(_sample_result(target="192.168.1.1"))
        results = repo.list_by_target("10.0.0.99")
        assert results == []

    def test_respects_limit(self, tmp_path):
        repo = JsonFileRepository(data_dir=str(tmp_path))
        for _ in range(5):
            repo.save(_sample_result(target="10.0.0.1"))
        results = repo.list_by_target("10.0.0.1", limit=2)
        assert len(results) == 2


# =============================================================================
# JsonFileRepository.delete
# =============================================================================


class TestDelete:
    """delete()：删除扫描记录文件。"""

    def test_delete_existing_returns_true(self, tmp_path):
        repo = JsonFileRepository(data_dir=str(tmp_path))
        scan_id = repo.save(_sample_result())
        assert repo.delete(scan_id) is True
        assert repo.get(scan_id) is None

    def test_delete_nonexistent_returns_false(self, tmp_path):
        repo = JsonFileRepository(data_dir=str(tmp_path))
        assert repo.delete("LS-nonexistent") is False

    def test_delete_when_scans_dir_missing_returns_false(self, tmp_path):
        repo = JsonFileRepository(data_dir=str(tmp_path))
        assert repo.delete("LS-any") is False


# =============================================================================
# JsonFileRepository.list_recent
# =============================================================================


class TestListRecent:
    """list_recent()：全部目标，按时间倒序，带分页。"""

    def test_empty_when_no_scans(self, tmp_path):
        repo = JsonFileRepository(data_dir=str(tmp_path))
        assert repo.list_recent() == []

    def test_returns_recent_entries(self, tmp_path):
        repo = JsonFileRepository(data_dir=str(tmp_path))
        repo.save(_sample_result(target="a.example.com"))
        import time as _time

        _time.sleep(0.05)  # 确保时间戳不同
        repo.save(_sample_result(target="b.example.com"))
        results = repo.list_recent()
        assert len(results) == 2
        # 两个条目都出现，不关心顺序（同一秒内文件名排序可能不可靠）
        targets = {r["target"] for r in results}
        assert targets == {"a.example.com", "b.example.com"}

    def test_respects_limit(self, tmp_path):
        repo = JsonFileRepository(data_dir=str(tmp_path))
        for i in range(10):
            repo.save(_sample_result(target=f"host-{i}"))
        results = repo.list_recent(limit=3)
        assert len(results) == 3

    def test_offset_pagination(self, tmp_path):
        repo = JsonFileRepository(data_dir=str(tmp_path))
        for i in range(5):
            repo.save(_sample_result(target=f"host-{i}"))
        page1 = repo.list_recent(limit=2, offset=0)
        page2 = repo.list_recent(limit=2, offset=2)
        assert len(page1) == 2
        assert len(page2) == 2
        # 页间无重叠
        targets_p1 = {r["target"] for r in page1}
        targets_p2 = {r["target"] for r in page2}
        assert targets_p1.isdisjoint(targets_p2)

    def test_summary_fields_present(self, tmp_path):
        repo = JsonFileRepository(data_dir=str(tmp_path))
        repo.save(_sample_result())
        results = repo.list_recent()
        r = results[0]
        assert "scan_id" in r
        assert "target" in r
        assert "status" in r
        assert "ports_count" in r
        assert "services_count" in r
        assert "findings_count" in r
        assert "cve_count" in r
        assert "created_at" in r

    def test_cve_count_accurate(self, tmp_path):
        """cve_count 统计 findings 中含有 cve_id 的记录数。"""
        repo = JsonFileRepository(data_dir=str(tmp_path))
        repo.save(_sample_result())
        results = repo.list_recent()
        assert results[0]["cve_count"] == 1  # 只有第 2 个 finding 有 cve_id

    def test_corrupted_json_skipped(self, tmp_path):
        """目录中非 JSON 文件 / 损坏 JSON 不导致崩溃。"""
        repo = JsonFileRepository(data_dir=str(tmp_path))
        scan_id = repo.save(_sample_result())
        # 在同一月份目录下放置损坏的 JSON 文件
        scans_root = os.path.join(str(tmp_path), "scans")
        for d in os.listdir(scans_root):
            month_dir = os.path.join(scans_root, d)
            if os.path.isdir(month_dir):
                broken = os.path.join(month_dir, "LS-corrupt.json")
                with open(broken, "w") as f:
                    f.write("{not valid json")
                break
        results = repo.list_recent()
        assert len(results) == 1
        assert results[0]["scan_id"] == scan_id


# =============================================================================
# JsonFileRepository 边界
# =============================================================================


class TestEdgeCases:
    """JsonFileRepository 边界与异常路径。"""

    def test_data_dir_does_not_exist_is_created_on_save(self, tmp_path):
        nonexistent = os.path.join(str(tmp_path), "nested", "data")
        repo = JsonFileRepository(data_dir=nonexistent)
        scan_id = repo.save(_sample_result())
        assert os.path.exists(nonexistent)
        assert repo.get(scan_id) is not None

    def test_list_by_target_skips_non_month_dirs(self, tmp_path):
        """月份目录中包含非目录文件时不影响 list_by_target。"""
        repo = JsonFileRepository(data_dir=str(tmp_path))
        repo.save(_sample_result(target="10.0.0.1"))
        # 在 scans 根目录放一个非目录文件
        scans_root = os.path.join(str(tmp_path), "scans")
        with open(os.path.join(scans_root, "README.txt"), "w") as f:
            f.write("not a month dir")
        results = repo.list_by_target("10.0.0.1")
        assert len(results) == 1
