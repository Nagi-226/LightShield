"""扫描结果持久化子包 — 为 v1.0 web 化预留的 Repository 抽象。

当前 (v0.2.0)：JSON 文件存储，单用户场景。
v1.0.0：SQLite 存储，Web Panel 多会话。
v2.0.0：PostgreSQL + Redis 缓存，SaaS 多租户。

切换方式：修改 config.py → repository_backend，调用方只依赖 ScanRepository 抽象。
"""

__all__ = ["ScanRepository", "JsonFileRepository", "SqliteRepository", "get_repository"]
