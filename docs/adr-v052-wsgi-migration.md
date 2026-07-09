# ADR-v052：生产 WSGI 方案 — gunicorn (Linux) + waitress (Windows) 双后端

> **状态**：✅ Accepted
> **日期**：2026-07-09
> **决策者**：Claude Code（架构 + 安全终审）
> **前置依赖**：`adr-v052-offline-definition.md` ✅ Accepted（无直接逻辑依赖，WSGI 是独立部署技术决策）
> **关联**：`.guardrails/PROGRESS.md`（v0.0.56 WSGI + 性能）、`lightshield/cli.py:368`（当前 `app.run()` 调用）
> **类型**：部署架构模式改变 → 范围漂移阀值「架构模式改变→🟠 暂停+ADR」强制立项

---

## 1. 背景（Context）

### 1.1 问题：Werkzeug 开发服务器在生产环境不安全

LightShield 的 `lightshield serve` 命令当前直接调用 Flask 内置的 Werkzeug 开发服务器：

```python
# lightshield/cli.py:368 — 当前实现
app.run(host=host, port=port, debug=args.debug)
```

Werkzeug 开发服务器的文档明确声明：

> Do not use it in a production deployment. Use a production WSGI server instead.

具体风险：

| 风险 | 说明 |
|------|------|
| **单进程单线程**（默认） | 一个慢请求阻塞所有后续请求。`threaded=True` 可以缓解但引入 GIL 竞争 |
| **无连接超时管理** | 慢客户端可无限占用 worker，无 keep-alive 超时、无 backlog 控制 |
| **无优雅重启** | 更新代码 = kill 进程 + 重启，正在处理的请求直接断开 |
| **调试模式 RCE 风险** | `debug=True` + `app.run()` 的 debugger 允许远程代码执行（PIN 保护薄弱） |
| **无进程管理** | 进程崩溃后不会自动重启，需外部 supervisor |

对于 v0.0.20–v0.0.49 的内部开发/演示用途，这些风险可接受。但 v1.0.0 目标是"生产就绪候选版本"——用户会在自己的服务器上长期运行 `lightshield serve`，Werkzeug 开发服务器不可接受。

### 1.2 约束条件

| 约束 | 来源 | 影响 |
|------|------|------|
| **跨平台** | README "支持 Linux 和 Windows" | 不能只选 gunicorn（不支持 Windows） |
| **轻量** | PROJECT_OVERVIEW "≤500MB" | 不能捆绑 nginx/Apache 等重型反向代理 |
| **零外部依赖** | offline ADR 铁律 1（默认零出站） | 不能运行时自动下载 WSGI 服务器二进制 |
| **纯 Python 优先** | 简化跨平台安装 | C 扩展（如 uwsgi）增加编译复杂度 |
| **CLI 自包含** | `lightshield serve` 一键启动 | 用户不需要先启动 gunicorn 再配 systemd |

### 1.3 与 v0.0.56 性能里程碑的关系

`PROGRESS.md:477`：

> v0.0.56：**前半**：gunicorn（Linux）/ waitress（Windows）生产 WSGI + SQLite WAL 模式 + 查询索引。**后半**：API p95 调优（基于真实 WSGI，目标 <100ms）——顺序不能反

**WSGI 切换是 API 性能调优的前置条件**——在 Werkzeug dev server 上调优毫无意义（单进程瓶颈掩盖了真正的查询/序列化开销）。先切 WSGI，获得真实并发性能基线，再针对瓶颈调优。

---

## 2. 决策（Decision）

**采用双后端策略：gunicorn（Linux）作为主力，waitress（Windows）作为兼容后端。CLI `lightshield serve` 自动检测平台并选择正确的 WSGI 服务器，用户无需手动配置。**

### 2.1 选型矩阵

| WSGI 服务器 | Linux | Windows | 纯 Python | 成熟度 | 社区规模 | 性能模型 |
|------|:--:|:--:|:--:|:--:|:--:|------|
| **gunicorn** | ✅ | ❌ | ✅ | ★★★★★ | 最大 | pre-fork 多进程 |
| **waitress** | ✅ | ✅ | ✅ | ★★★★ | 中（Pyramid/Pylons 官方推荐） | 多线程 |
| uvicorn + asgiref | ✅ | ✅ | ✅ | ★★★★ | 大 | uvloop + async |
| uWSGI | ✅ | ❌ (Cygwin) | ❌（C 扩展） | ★★★★★ | 大 | pre-fork + threads |
| mod_wsgi (Apache) | ✅ | ❌ | ❌ | ★★★★★ | — | 嵌入 Apache 进程模型 |
| bjoern | ✅ | ❌ | ❌（C 扩展） | ★★ | 小 | libev 事件循环 |
| cherrypy.wsgiserver | ✅ | ✅ | ✅ | ★★★ | 小 | 多线程 |

### 2.2 选择 gunicorn（Linux）的理由

```
✅ Flask/Python 生态的事实标准 — 几乎所有 Flask 生产部署指南的第一推荐
✅ pre-fork 模型 — 每个 worker 独立进程，GIL 不竞争，crash 不影响其他 worker
✅ 零配置即可用 — gunicorn -w 4 app:app 一行启动
✅ 信号管理成熟 — SIGTERM 优雅关闭（等待请求完成），SIGHUP 无缝重载
✅ 纯 Python（无 C 扩展）— 不增加跨平台编译负担
✅ 反向代理后的标准选择 — LightShield 未来可能放 nginx 后面，gunicorn 是标准上游
```

**为什么不是 uvicorn（ASGI）？**
- Flask 是 WSGI 应用，不是 ASGI。用 uvicorn 需要 `asgiref.wsgi_to_asgi` 适配层
- 适配层引入额外延迟（每请求一次 WSGI→ASGI 转换）
- LightShield 没有 WebSocket/HTTP2 Server Push 等需要使用 ASGI 的功能
- 如果未来需要 ASGI（例如迁移到 FastAPI/Quart），届时再评估——现在选 gunicorn 不锁定未来

### 2.3 选择 waitress（Windows）的理由

```
✅ Windows 原生支持 — 纯 Python，无 C 扩展，pip install 即用
✅ Pyramid/Pylons 项目官方推荐的生产 WSGI 服务器（Zope/Plone 生态背书）
✅ 多线程模型在 Windows 上足够 — Windows 的进程创建开销比 fork 大，多线程是合理选择
✅ 不需要 Cygwin/WSL — gunicorn 在 Windows 上的唯一替代方案
✅ 与 gunicorn 接口高度相似 — host/port/threads 参数互换成本低
```

**为什么是 waitress 而不是 cherrypy.wsgiserver？**
- waitress 的维护活跃度和社区信任度高于 cherrypy 的 wsgiserver
- waitress 的 HTTP 解析器（自带 `waitress.parser`）经过安全审计（RFC 合规、请求走私防护），cherrypy 的 wsgiserver 曾有过 HTTP header 解析 CVE
- waitress 已经是 Zope/Plone 生态的生产默认值——这意味着它在 Windows 上的生产使用被大量验证过

### 2.4 架构设计

```
lightshield serve
    │
    ├── sys.platform == "win32"
    │       │
    │       └── waitress.serve(app, host=host, port=port, threads=4)
    │
    └── sys.platform != "win32" (Linux / macOS)
            │
            └── gunicorn.app.wsgiapp.WSGIApplication
                    (workers=2, threads=2, bind=f"{host}:{port}")
```

```python
# lightshield/cli.py — 改造后（伪代码，实现时不改行为只换后端）
def run_serve_command(args: argparse.Namespace) -> int:
    app = create_app(config=config)
    host, port = args.host or config.web_host, args.port or config.web_port

    if sys.platform == "win32":
        from waitress import serve
        print(f"WSGI 后端: waitress (多线程, 4 threads)")
        serve(app, host=host, port=port, threads=4)
    else:
        from gunicorn.app.wsgiapp import WSGIApplication
        print(f"WSGI 后端: gunicorn (pre-fork, 2 workers x 2 threads)")
        gunicorn_app = WSGIApplication()
        gunicorn_app.load_wsgiapp = lambda: app
        # ... gunicorn 参数配置
        gunicorn_app.run()
```

### 2.5 默认配置

| 参数 | gunicorn | waitress | 说明 |
|------|------|------|------|
| workers / threads | 2 workers × 2 threads | 4 threads | 轻盾是本地工具（单用户/小团队），不需要高并发 |
| host | `127.0.0.1` | `127.0.0.1` | 默认仅本机——安全最佳实践。用户可通过 `--host 0.0.0.0` 显式开放 |
| port | `5000` | `5000` | 不变 |
| 优雅超时 | `graceful_timeout=30` | `channel_timeout=30`（连接总超时） | 注：waitress `channel_timeout` 是连接总存活时间上限（非空闲超时），与 gunicorn `keepalive`（空闲超时）语义不同。实现时分别使用各自的正确参数：gunicorn 用 `--keep-alive 2`，waitress 用独立配置 |
| keep-alive | `keepalive=2`（空闲超时关闭） | waitress 无独立 keep-alive 参数 | waitress 通过 HTTP/1.1 默认保持连接，依靠 `channel_timeout` 关闭空闲连接 |
| access log | 默认关闭，可通过 `--access-log` CLI flag 开启 | 默认关闭，可通过 `--access-log` CLI flag 开启 | 安全工具的 Web 接口被暴力破解时，access log 是检测依据。默认关闭（减少日志噪声），但提供显式开启选项——不做成不可逆的硬关闭 |

### 2.6 依赖管理

```
# requirements.txt — 新增条件依赖
gunicorn>=22.0,<24.0; sys_platform != "win32"    # Linux/macOS
waitress>=3.0,<4.0; sys_platform == "win32"       # Windows

# pyproject.toml — extras
[project.optional-dependencies]
web = ["flask>=3.0", "gunicorn>=22.0; sys_platform!='win32'", "waitress>=3.0; sys_platform=='win32'"]
```

**原则**：
- 每个平台只安装一个 WSGI 服务器——不在 Linux 上安装 waitress，不在 Windows 上强制安装 gunicorn
- `pip install lightshield[web]` 自动按平台选择正确的依赖
- 纯源码安装（无二进制 wheel 依赖），保持"≤500MB"约束

### 2.7 保持 Werkzeug 作为 fallback

```python
try:
    if sys.platform == "win32":
        from waitress import serve
        serve(app, ...)
    else:
        # gunicorn
        ...
except ImportError:
    # fallback — 仅用于开发/演示，并打印明确警告
    print("[警告] 未安装生产 WSGI 服务器，回退到 Werkzeug 开发模式")
    print("[警告] Werkzeug 不适合生产使用。请运行: pip install lightshield[web]")
    app.run(host=host, port=port, threaded=True)
```

**理由**：如果用户通过 `pip install lightshield`（不带 `[web]`）安装了基础包，`lightshield serve` 仍应能启动（用于快速演示），但需明确警告"非生产就绪"。

### 2.8 pre-fork 模型下的任务状态共享（🔴 关键）

gunicorn 的 pre-fork 模型创建 N 个独立 worker 进程，每个 worker 持有 `LightShieldCore` 的独立实例。当前 `core.py` 的扫描任务跟踪使用**进程内内存 dict**（`_task_results: dict[str, _TaskInfo]`），这导致一个确定性故障：

```
Worker 1: POST /api/scan → 启动扫描, _task_results["LS-001"] = running
Worker 2: GET /api/scan/LS-001/stream → _task_results 无 LS-001 → not_found
```

用户的 SSE 实时进度流（v0.0.37 引入）如果连接到与启动扫描不同的 worker，就会断裂。gunicorn 默认轮询负载均衡，不保证 sticky session。

**决策：将扫描任务状态从内存 dict 迁移到 SQLite（方案 A）。**

| 方案 | 内容 | 评价 |
|------|------|------|
| **A（采用）** | 任务状态迁到 SQLite：`core.run_scan()` 启动时 INSERT task 行 → SSE 端点从 SQLite 轮询状态（500ms 间隔）→ 扫描完成时 UPDATE status + result | ✅ 与 repository 层设计哲学一致 ✅ 为 R2 ADR 的多目标扫描状态汇总铺路 ✅ 进程崩溃后任务状态不丢失 |
| B（否决） | gunicorn `--workers 1 --threads 4`（单 worker 多线程） | 放弃 pre-fork 的进程隔离优势。waitress 本来就是多线程，gunicorn 若降级为单 worker 就失去了选它的理由 |
| C（否决） | `--preload` + 共享内存 / multiprocessing.Manager | 复杂度高，引入 Manager 进程 + Lock 开销，不值得 |

**实现要点**：

- 复用现有 `lightshield/repository/` 层（SQLite backend），新增 `tasks` 表
- SSE 端点轮询 SQLite（`SELECT status FROM tasks WHERE task_id = ?`），500ms 间隔，最长 300s 超时后返回 `timeout` 状态
- gunicorn 的每个 worker 持有独立的 `LightShieldCore` 实例，但读写同一个 SQLite 文件——SQLite 的 WAL 模式（v0.0.56 前半同步启用）支持一写多读并发
- 任务完成后保留在 SQLite 中 24h（定时清理），供 Web 面板的扫描历史查询

**此决策在本 ADR Accepted 后立即生效**——WSGI 切换实现时必须同步完成任务状态迁移，不得先切 WSGI 再补任务迁移。

### 2.9 不在本次 ADR 范围内的事项

| 事项 | 为什么不在本次范围 | 何时处理 |
|------|------|------|
| Nginx/Apache 反向代理配置 | LightShield 定位是本地工具，"反向代理"是可选的部署方式，不应内置 | 文档中提供示例配置（v0.0.59 技术文档） |
| systemd/Windows Service 服务化 | 生产部署需求，但非 WSGI 切换的前提 | v0.0.56 后半或 v0.0.59 |
| HTTPS/TLS 证书 | gunicorn 可以配 `--certfile`，但 LightShield 作为本地工具默认不需要 TLS——用户需要时自行在反向代理层配置 | 文档覆盖 |
| asyncio/ASGI 迁移 | 无需求——无 WebSocket/SSE 之外的实时功能，且 Flask-SSE 在 WSGI 下工作正常 | 在需要时另立 ADR |

---

## 3. 被否决的备选（Alternatives Considered）

| 方案 | 内容 | 否决理由 |
|------|------|---------|
| **B：gunicorn 唯一** | 只支持 gunicorn，Windows 用户需自行解决（WSL/Docker/Cygwin） | Windows 是 README 正式声明的支持平台。要求 Windows 用户装 WSL/Docker 来运行 `lightshield serve`，违背"跨平台"承诺 |
| **C：waitress 唯一** | 全平台统一 waitress | ①放弃 gunicorn 的 pre-fork 多进程模型（Linux 上的性能最优解）；②waitress 在 Linux 高并发下的性能不如 gunicorn（多线程 vs 多进程，GIL 竞争）；③社区惯性——用户期望 Flask 生产部署用 gunicorn |
| **D：uvicorn + asgiref** | 统一 ASGI，通过 `wsgi_to_asgi` 适配 | ①额外适配层延迟；②Flask 生态的文档/部署指南全部围绕 WSGI；③LightShield 不需要 ASGI 的特性（WebSocket/HTTP2 Server Push） |
| **E：内置 nginx 捆绑** | 打包一个精简 nginx + 反向代理配置 | ①膨胀——nginx 本身 5-10MB，加上配置/管理逻辑，总增约 15MB；②跨平台复杂性——Windows nginx 行为与 Linux 有差异；③违背"轻盾 ≤500MB"和"零外部服务"的定位 |
| **F：保持 Werkzeug** | 不切换，文档标注"仅供演示" | v1.0.0 标注为"生产就绪候选"，而 Werkzeug dev server 明确不是生产就绪——文档与现实矛盾，不可接受 |

---

## 4. 后果（Consequences）

### 4.1 正面

- ✅ **生产安全**：消除 Werkzeug dev server 的进程管理/超时/调试 RCE 风险
- ✅ **跨平台一致体验**：`lightshield serve` 在 Linux 和 Windows 上都生产可用，用户感知零差异
- ✅ **v0.0.56 性能调优获得真实基线**：gunicorn pre-fork 模型下的 p95 延迟才是用户的真实体验
- ✅ **向后兼容**：CLI 接口不变（`--host` / `--port` 参数保持），依赖通过 `[web]` extra 可选安装
- ✅ **零配置**：默认 2 workers + 2 threads，轻盾的目标并发量完全够用
- ✅ **SQLite WAL 模式受益**：多 worker/多线程的并发读 + WAL 的单写者模型天然匹配

### 4.2 代价

- ⚠️ **增加 2 个依赖**（gunicorn + waitress）——每个约 1-2MB，总增 ≤5MB
- ⚠️ **`requirements.txt` 增加平台条件语法**（`sys_platform`）——需要验证 `pip install` 在 Windows/Linux 上的条件解析行为一致
- ⚠️ **Windows 上的并发上限低于 Linux**——waitress 多线程受 GIL 限制，CPU 密集请求会排队。但轻盾的 API 主要是 I/O 密集（SQLite 查询 / JSON 序列化），GIL 不是瓶颈
- ⚠️ **gunicorn 在 Windows 上不能 `pip install`**——虽然 `sys_platform` 条件阻止了安装，但 Windows 用户若看文档手动 `pip install gunicorn` 会失败。需在文档中明确说明

### 4.3 验收标准

1. `pip install -e ".[web]"` 在 Linux 上安装 gunicorn（waitress 不安装）
2. `pip install -e ".[web]"` 在 Windows 上安装 waitress（gunicorn 跳过）
3. `lightshield serve` 在 Linux 上使用 gunicorn 启动，输出显示 worker 数量
4. `lightshield serve` 在 Windows 上使用 waitress 启动，输出显示线程数量
5. Werkzeug fallback 正常工作（`pip install lightshield` 不带 `[web]` → `lightshield serve` 启动 + 打印警告）
6. 全量测试基线通过，现有 `test_cli.py` 零回归
7. `lightshield serve --host 127.0.0.1 --port 5000` 行为与切换前一致

---

## 5. 合规映射（R1–R6）

| 红线 | 本决策落地方式 |
|:--:|------|
| R1 禁攻击 | 不受影响（WSGI 后端不改变应用逻辑） |
| R2 禁批量扫公网 | 不受影响（R2 校验在 `core._validate_request` 中，WSGI 层无关） |
| R3 禁远控后门 | 默认监听 `127.0.0.1`——从物理上禁止远程连接。用户显式传 `--host 0.0.0.0` 时才接受远程连接，且需自行负责网络安全 |
| R4 仅自查自有 | 不受影响 |
| R5 MSF 白名单 | 不受影响 |
| R6 频率限制 | 不受影响（频率限制在 `core` 层，WSGI 不感知） |

---

## 6. 与其他两份 ADR 的交叉引用

| 相关 ADR | 交叉点 | 一致性 |
|------|------|:--:|
| `adr-v052-offline-definition.md` | 零外部网络依赖 | WSGI 切换不引入新的出站网络行为——gunicorn/waitress 本地监听，不连接外部服务 ✅ |
| `adr-v052-r2-multi-target-redesign.md` | v0.0.61+ Web API 多目标端点 | gunicorn pre-fork 的每个 worker 已持有 `LightShieldCore` 实例——未来 `POST /api/scan/batch` 在 worker 内串行编排多目标，不跨 worker 协调，避免分布式状态 ✅ |

---

## 7. 修订记录

| 日期 | 修订 | 作者 |
|------|------|------|
| 2026-07-09 | 初稿 | Claude Code |
| 2026-07-09 | 二审修订：新增 §2.8 pre-fork 任务状态共享（方案 A：SQLite）+ 修正 §2.5 waitress channel_timeout 语义 + access log 策略改为可选开启 + §4.3 验收标准去硬编码 | Claude Code（基于项目所有者审查反馈） |

---

> 本 ADR 由 Claude Code 起草，是 v0.0.52 ADR 冲刺的第三份也是最后一份架构决策。三份 ADR 全部 Accepted 后，v0.0.52 完成，进入阶段二（v0.0.53–v0.0.57 功能补全）。
