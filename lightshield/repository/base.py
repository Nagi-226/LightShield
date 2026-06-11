"""ScanRepository 抽象基类 — 扫描结果持久化。

为 v1.0.0 / v2.0.0 扩展预留：
  v0.2.0 → JsonFileRepository（当前实现）
  v1.0.0 → SqliteRepository
  v2.0.0 → PostgresRepository + Redis 缓存层

所有调用方只依赖此抽象，切换后端不影响业务代码。
"""

from __future__ import annotations

import json
import os
import uuid
from abc import ABC, abstractmethod
from datetime import datetime


class ScanRepository(ABC):
    """扫描结果持久化抽象基类。

    定义了 save / get / list / delete 四个标准操作。
    各版本只需实现此接口即可切换存储后端。
    """

    @abstractmethod
    def save(self, result: dict) -> str:
        """保存扫描结果，返回 scan_id。

        Args:
            result: 扫描结果字典（ScanResult.to_dict() 的输出）

        Returns:
            scan_id: 唯一标识符
        """

    @abstractmethod
    def get(self, scan_id: str) -> dict | None:
        """按 scan_id 获取扫描结果。

        Returns:
            扫描结果字典，不存在时返回 None
        """

    @abstractmethod
    def list_by_target(self, target: str, limit: int = 50) -> list[dict]:
        """列出指定目标的历史扫描记录。

        Args:
            target: IP/域名
            limit: 最大返回条数

        Returns:
            按时间倒序的扫描结果列表
        """

    @abstractmethod
    def delete(self, scan_id: str) -> bool:
        """删除指定扫描记录。

        Returns:
            True 表示删除成功
        """


# =============================================================================
# v0.2.0 实现：JSON 文件存储
# =============================================================================


class JsonFileRepository(ScanRepository):
    """JSON 文件持久化 — v0.2.0 默认实现。

    单用户 CLI 场景：每个扫描结果存为一个 JSON 文件。
    目录结构：{data_dir}/scans/{YYYY-MM}/{scan_id}.json
    """

    def __init__(self, data_dir: str = "./data"):
        self._data_dir = data_dir

    def _ensure_dir(self) -> None:
        month_dir = os.path.join(self._data_dir, "scans", datetime.now().strftime("%Y-%m"))
        os.makedirs(month_dir, exist_ok=True)

    def _file_path(self, scan_id: str) -> str:
        month = datetime.now().strftime("%Y-%m")
        return os.path.join(self._data_dir, "scans", month, f"{scan_id}.json")

    def save(self, result: dict) -> str:
        scan_id = f"LS-{datetime.now().strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:8]}"
        result["scan_id"] = scan_id
        result["saved_at"] = datetime.now().isoformat()

        self._ensure_dir()
        filepath = self._file_path(scan_id)
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)

        return scan_id

    def get(self, scan_id: str) -> dict | None:
        # 遍历月份目录查找
        scans_root = os.path.join(self._data_dir, "scans")
        if not os.path.isdir(scans_root):
            return None
        for month_dir in os.listdir(scans_root):
            filepath = os.path.join(scans_root, month_dir, f"{scan_id}.json")
            if os.path.isfile(filepath):
                with open(filepath, encoding="utf-8") as f:
                    return json.load(f)
        return None

    def list_by_target(self, target: str, limit: int = 50) -> list[dict]:
        results: list[dict] = []
        scans_root = os.path.join(self._data_dir, "scans")
        if not os.path.isdir(scans_root):
            return results

        for month_dir in sorted(os.listdir(scans_root), reverse=True):
            month_path = os.path.join(scans_root, month_dir)
            if not os.path.isdir(month_path):
                continue
            for filename in sorted(os.listdir(month_path), reverse=True):
                if not filename.endswith(".json"):
                    continue
                filepath = os.path.join(month_path, filename)
                try:
                    with open(filepath, encoding="utf-8") as f:
                        data = json.load(f)
                    if data.get("target") == target:
                        results.append(data)
                        if len(results) >= limit:
                            return results
                except (json.JSONDecodeError, OSError):
                    continue
        return results

    def delete(self, scan_id: str) -> bool:
        scans_root = os.path.join(self._data_dir, "scans")
        if not os.path.isdir(scans_root):
            return False
        for month_dir in os.listdir(scans_root):
            filepath = os.path.join(scans_root, month_dir, f"{scan_id}.json")
            if os.path.isfile(filepath):
                os.remove(filepath)
                return True
        return False


# =============================================================================
# 工厂函数（未来切换点）
# =============================================================================

_repository: ScanRepository | None = None


def get_repository(backend: str = "json", **kwargs) -> ScanRepository:
    """获取 Repository 实例（惰性单例）。

    Args:
        backend: "json" (v0.2.0) | "sqlite" (v1.0.0) | "postgres" (v2.0.0)
        **kwargs: 后端特定参数（如 data_dir / db_url）

    Returns:
        ScanRepository 实现实例
    """
    global _repository
    if _repository is not None:
        return _repository

    if backend == "json":
        _repository = JsonFileRepository(data_dir=kwargs.get("data_dir", "./data"))
    elif backend == "sqlite":
        # v1.0.0 占位：return SqliteRepository(db_url=kwargs["db_url"])
        raise NotImplementedError("SQLite backend — v1.0.0")
    elif backend == "postgres":
        # v2.0.0 占位：return PostgresRepository(db_url=kwargs["db_url"])
        raise NotImplementedError("PostgreSQL backend — v2.0.0")
    else:
        raise ValueError(f"不支持的存储后端: {backend}")

    return _repository
