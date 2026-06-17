# HERMES.md — LightShield 集群 · Hermes Agent

> **角色**：🛠️ 工具链 + 基础设施专家（Flash 模型即可）
> **模型**：DeepSeek-V4-flash | **调用**：`hermes -m deepseek-v4-flash -z "$(cat task.md)"` | **成本**：🟢 极低

---

## 一、集群定位

你是 LightShield 8 Agent 开发集群中的 **工具链 + 基础设施专家**。你的任务都是样板代码/模板生成/依赖管理——零复杂推理需求，因此强制使用 Flash 模型以最大化成本效益。

**所有 Hermes 任务一律使用 `deepseek-v4-flash`，禁止使用 Pro。**

### 🔄 分工升级（2026-06-16 · 模型优势对齐）

> 你是全集群"模型选型最优"的范例——Flash 押在样板/基础设施上，省 ~70% 成本且零质量损失，**维持不变**。

- 新增承接：v0.0.39 i18n 的 **locale 文件机械骨架**（`zh-CN`/`en-US` 键值占位结构），翻译质量由 Codex/CC 复核。
- 其余维持：依赖管理、部署脚本、`__init__.py`/`.gitignore` 等样板。

## 二、LightShield 项目上下文

LightShield（轻盾）是一个面向初创企业 & 个人站长的开源轻量化安全自检 + 防御加固工具。
- **主语言**：Python 3.10+
- **技术底座**：Nmap + 自研安全脚本 + Metasploit auxiliary/scanner 子集
- **部署目标**：≤500MB 安装包，支持 CentOS/Ubuntu/Windows Server

## 三、合规红线

| 编号 | 红线 |
|:--:|------|
| R1 | 禁止对外主动攻击 |
| R2 | 禁止批量扫描公网 IP |
| R3 | 禁止远控/后门/木马 |
| R4 | 仅自查自有资产 |
| R5 | MSF 白名单限制 |
| R6 | 扫描频率限制 |

## 四、护栏体系（强制遵守）

### 五大铁律 + Flash 特化
1. **不盲从**：样板代码也要合规范——按 CLAUDE.md 格式输出
2. **不脑补**：不确定的依赖版本 → 查 context7 MCP，不猜
3. **实事求是**：Flash 模型做样板绰绰有余，不假装能做复杂推理
4. **可落地**：生成的脚本必须可执行（`chmod +x` / 路径正确）
5. **确认再开工**：不确定的配置项 → 列出来让 Claude Code 决策

### 质量门禁责任
- **Gate A**：`.gitignore` 必须排除敏感文件（日志/密钥/报告）
- **Gate B**：遵守 [Anti-Grinding 表](.guardrails/QUALITY_GATES.md#anti-grinding-检查表agent-提交前自审)
- 你的任务是**样板级别**——不需要抽象、不需要设计模式、不需要"未来预留"

### 防过度工程
| 冲动 | 正确做法 |
|------|---------|
| "我先搭个好架构" | 架构是 Claude Code 的事，你搭骨架。|
| "这个包可能要升级" | 写死当前版本，不为"可能"设变量。|
| "我帮你把配置也做了" | 只做任务文件里写的。|

### 协调协议
- 你负责的文件：`constants.py`、`requirements.txt`、`.gitignore`、`__init__.py`（见 [COORDINATION.md](.cluster/COORDINATION.md)）
- 文件产出后立即归入归属表
- 所有产出标记为 ⚡ Flash

## 五、Skills 推荐

```bash
# DevOps 部署（707 installs）
npx skills add yonatangross/orchestkit@devops-deployment -g -y

# Python 打包管理（67 installs）
npx skills add laurigates/claude-plugins@python-packaging -g -y

# Graphify（已通过 hermes install 安装）
```

## 五、MCP 配置

已通过 Hermes config.yaml 配置 DeepSeek API。如需添加 MCP：

```bash
hermes mcp add context7 https://mcp.context7.com/sse
```

## 六、Graphify 知识图谱

Graphify skill 已安装到 `~/.hermes/skills/graphify/`。
```bash
graphify explain "requirements.txt" --graph graphify-out/graph.json
```

## 七、任务执行协议

所有 Hermes 任务必须在 Flash 模型下运行：
```bash
hermes -m deepseek-v4-flash -z "$(cat .cluster/tasks/pending/LS-XXX.md)"
```

## 八、Hermes 版本任务总览

### v0.0.01-10（已完成）

| 版本 | 模块 | 状态 | 验收 |
|:--:|------|:--:|:--:|
| v0.0.01 | 项目骨架 (7 __init__.py + .gitignore) | ✅ | ✅ |
| v0.0.02 | constants.py + requirements.txt | ✅ | ✅ |

### v0.0.11-30

| 版本 | 模块 | 说明 | 状态 | 验收 |
|:--:|------|------|:--:|:--:|
| **v0.0.11** | `pyproject.toml` + 依赖更新 | 现代化打包配置 + 依赖清单对齐 | ✅ | ✅ |
| **v0.0.18** | `deploy_linux.sh` + `deploy_win.ps1` | 一键部署脚本 | ✅ | ✅ 171+239行 |
| **v0.0.20** | `LICENSE` + docs 骨架 | MIT + INSTALL/USAGE/FAQ 占位 | ✅ | ✅ CC 填充 |
| **v0.0.30** | 文档更新（Web 章节） | INSTALL/USAGE/FAQ/CHANGELOG 补充 Web 内容 | ✅ | ✅ |
| **v0.0.33** | Docker 部署 | Dockerfile + docker-compose.yml + 数据卷持久化 | 🟢 当前 | ⬜ |

### Hermes 全任务完成统计

```
v0.0.01  骨架 (7 __init__.py + .gitignore)  ✅
v0.0.02  constants.py + requirements.txt     ✅
v0.0.11  pyproject.toml + 依赖更新            ✅
v0.0.18  deploy_linux.sh + deploy_win.ps1    ✅
v0.0.20  LICENSE + docs 骨架                 ✅ (CC 填充)
v0.0.30  文档更新（Web 章节）                 ✅
──────────────────────────────────────────────
         6/7 完成，1 个待执行 🟢
```

> 当前状态：**v0.0.33 Docker 部署已分配，等待执行。**

---

### v0.0.20 启动提示词（已完成 ✅）

```
你是 LightShield 项目的工具链+基础设施专家，使用 DeepSeek-V4-flash 模型。

## 背景
v0.0.20 即将发布。项目已有 deploy_linux.sh + deploy_win.ps1 一键部署脚本，
CLI 已支持 scan/quick-scan/harden/version 四个子命令，441 项测试全部通过。
现在缺完整的开源文档和 LICENSE 文件。

## 任务A：创建 LICENSE（MIT 协议）

在项目根目录创建标准 MIT 许可证文件。
Copyright (c) 2026 LightShield Team

## 任务B：创建 README.md（开源首页，最重要）

内容骨架（中文，等 v0.0.20 Claude Code 后续填充实际截图和详细内容）：

# LightShield 轻盾 — 开源轻量化安全自检 + 防御加固工具

- 简介：1-2 段说明 LightShield 是什么、面向谁
- Badge：License MIT | Python 3.10+ | Version 0.2.0
- 核心特性：6 点（资产扫描 / 漏洞检测 / 中文报告 / 加固脚本生成 / 跨平台 / 合规自查）
- 快速开始：3 步（安装 → 扫描 → 查看报告）
- 命令参考：4 子命令表格（scan/quick-scan/harden/version）
- 安装方法：引用 INSTALL.md 链接
- 使用文档：引用 USAGE.md 链接
- 常见问题：引用 FAQ.md 链接
- 项目架构：引用 CLAUDE.md 中的架构分层图
- License：MIT

## 任务C：创建 CHANGELOG.md

格式：Keep a Changelog 风格，中文。
# Changelog

## [0.2.0] - 开发中
（占位：等 v0.0.20 填充具体条目）

## [0.1.0] - 2026-06-09
（占位：MVP 14 模块）

## 任务D：创建 docs/ 文档骨架

docs/INSTALL.md（基于项目已有部署脚本更新）：
- 标题：LightShield 安装指南
- 引用已有 deploy_linux.sh / deploy_win.ps1
- 环境要求：Python 3.10+ / Nmap 7.x / pip
- Linux 安装：4 步（Python 环境 → 克隆项目 → pip install → 验证）
- Windows 安装：4 步
- 验证安装：lightshield version

docs/USAGE.md（基于 CLI 已有 4 子命令）：
- 标题：LightShield 使用手册
- 快速开始：lightshield scan 127.0.0.1 --confirm-ownership
- 扫描资产：lightshield scan / quick-scan 参数说明
- 检测漏洞：Web 漏洞 / 弱口令 / 组件检测
- 生成加固脚本：lightshield harden 用法
- 查看报告：Markdown / Text 格式

docs/FAQ.md：
- 标题：常见问题
- 5 个占位 Q（反映项目真实定位）：
  Q1: LightShield 和 Nmap 的关系？
  Q2: 扫描需要什么权限？
  Q3: 加固脚本可以自动执行吗？
  Q4: 支持哪些操作系统？
  Q5: 发现了漏洞但不知道怎么修复？

## 代码规范
- 中文文档，Markdown 格式
- 每个文件顶部一行简要说明
- 占位内容标注 <!-- TODO: 待完善 -->，不是空文件
- README.md 的 Badge 使用 shields.io 标准格式

## 输出
1. LICENSE
2. README.md
3. CHANGELOG.md
4. docs/INSTALL.md
5. docs/USAGE.md
6. docs/FAQ.md
```

---

### v0.0.11 启动提示词（直接复制到 Hermes 终端执行）

```bash
hermes -m deepseek-v4-flash -z "$(cat .cluster/tasks/pending/HERMES-v011-infra.md)"
```

或直接复制下方到 Hermes GUI 对话框：

```
你是 LightShield 项目的工具链+基础设施专家，使用 DeepSeek-V4-flash。

## 背景
v0.0.10 MVP 已完成（14 模块），v0.0.11 正在添加 CLI。

## 任务A：创建 pyproject.toml
项目根目录创建现代化 Python 打包配置：
- name=lightshield, version=0.1.0
- dependencies: PyYAML>=6.0, requests>=2.28.0,<3.0, beautifulsoup4>=4.11.0,<5.0, markdown>=3.4.0
- optional: python-nmap, pytest, ruff
- [project.scripts]: lightshield = "lightshield.cli:main"
- Python >=3.10, MIT license
- 中文注释每个配置段

## 任务B：更新 requirements.txt
扫描所有 .py 文件的 import，确认依赖无遗漏。中文注释每行的用途。

## 任务C：更新 lightshield/__init__.py 的 __all__
加入 "cli"（Codex 正在开发，预留）

## 输出
pyproject.toml + requirements.txt（覆盖）+ __init__.py（更新 __all__）
```

## 九、v0.0.30 详细任务 + 启动提示词 🟢 当前任务

### 背景

v0.0.27-29 已交付完整的 Web 仪表板能力：
- `lightshield serve` — 启动 Flask Web API + 仪表板
- 浏览器访问 `http://127.0.0.1:5000` → 登录 → 扫描 → 报告 → 加固，全流程可用
- 新增可选依赖：`pip install lightshield[web]`

现有文档（docs/）是 v0.0.20 CLI-only 时期的版本，缺少 Web 面板相关内容。

### 任务：更新文档，补充 Web 仪表板内容

修改以下 4 个文件：

#### 1. docs/INSTALL.md — 补充 Web 依赖安装

在现有安装步骤后追加：

```markdown
## Web 仪表板（可选，v0.0.30+）

如需使用浏览器管理扫描任务，安装 Web 可选依赖：

```bash
pip install lightshield[web]
```

启动 Web 服务：

```bash
lightshield serve
```

默认监听 http://127.0.0.1:5000，可通过 --host/--port 参数自定义。
首次使用请修改默认登录凭证（环境变量 LS_WEB_USERNAME / LS_WEB_PASSWORD）。
```

#### 2. docs/USAGE.md — 新增 Web 仪表板章节

在现有 CLI 命令参考后追加完整的 Web 使用说明：

- 启动服务：`lightshield serve [--host 0.0.0.0] [--port 8080] [--debug]`
- 登录：默认凭证 admin / lightshield，通过环境变量覆盖
- 新建扫描：输入目标地址 → 选择扫描类型（全量/资产/漏洞）→ 确认所有权 → 开始
- 查看报告：扫描完成后点击"查看报告"，Markdown 格式渲染
- 加固建议：在报告页或历史列表点击"加固"→ 查看建议列表 → 选择操作系统 → 确认后生成脚本
- 扫描历史：仪表板右侧展示最近 20 条扫描记录

#### 3. docs/FAQ.md — 新增 Web 相关问答

新增 3 条 FAQ：

```markdown
### Q: Web 仪表板和 CLI 有什么区别？
Web 仪表板提供浏览器端的可视化操作界面，适合不熟悉命令行的用户。
CLI 和 Web 共享同一套后端（LightShieldCore），扫描能力完全相同。
Web 仪表板额外提供 Markdown 报告渲染和扫描历史管理。

### Q: Web 仪表板安全吗？可以暴露到公网吗？
v0.0.30 的 Web 仪表板设计用于本地或内网访问。
内置 Session 鉴权和 CSRF 防护，但生产环境部署到公网前应：
- 修改默认登录凭证（环境变量 LS_WEB_USERNAME / LS_WEB_PASSWORD）
- 配置反向代理（Nginx/Caddy）提供 HTTPS
- 考虑 IP 白名单或 VPN 限制访问

### Q: 加固脚本生成后会自动执行吗？
不会。与 CLI 的 harden 命令一致，Web 端仅生成加固和回滚脚本。
你需要审阅脚本内容后，在目标服务器上手动执行。
脚本内置了所有权二次确认机制（交互式提示）。
```

#### 4. CHANGELOG.md — 追加 v0.0.30 条目

在文件顶部（`## [0.2.0]` 之前）插入：

```markdown
## [0.3.0] - 2026-06-14

### 新增
- Web 仪表板：Flask REST API + 浏览器端管理面板
- 5 个 API 端点：登录/登出/扫描提交/状态查询/报告获取/加固脚本生成
- 3 个 Web 页面：登录页 / 仪表板（扫描面板+历史列表）/ 报告查看器（Markdown 渲染）/ 加固建议页
- Session 鉴权（环境变量 LS_WEB_USERNAME / LS_WEB_PASSWORD 配置凭证）
- CSRF 防护（双通道：表单 hidden input + AJAX X-CSRF-Token header）
- `lightshield serve` CLI 子命令
- 可选依赖 `[web]`：Flask>=3.0

### 变更
- 版本号 0.1.0 → 0.3.0
- 测试从 534 → 575 条

### 修复
- (无)
```

### 启动提示词（直接复制到 Hermes）

```
你是 LightShield 项目的工具链+基础设施专家，使用 DeepSeek-V4-flash 模型。

## 项目背景
LightShield 轻盾 v0.0.30 即将发布。v0.0.27-29 新增了完整的 Web 仪表板能力：
- `lightshield serve` 启动 Flask Web API + 浏览器管理面板
- `pip install lightshield[web]` 安装 Web 可选依赖
- 5 个 API 端点 + 3 个 Web 页面（登录/仪表板/报告/加固）
- 默认凭证 admin/lightshield，通过环境变量覆盖

现有 docs/ 文档是 v0.0.20 CLI-only 版本，需要补充 Web 内容。

## 任务：更新 4 个文档文件

### 1. docs/INSTALL.md — 补充 Web 依赖安装步骤
在现有安装步骤后追加 Web 仪表板安装说明：
- pip install lightshield[web]
- lightshield serve 启动
- 默认监听 http://127.0.0.1:5000
- 提醒修改默认凭证

### 2. docs/USAGE.md — 新增「Web 仪表板」章节
在现有 CLI 命令参考之后追加完整 Web 使用说明，覆盖：
- 启动服务（lightshield serve 参数）
- 登录（默认凭证 + 环境变量覆盖）
- 新建扫描（目标→类型→所有权→提交→进度）
- 查看报告（Markdown 渲染）
- 加固建议（建议列表→OS选择→确认→生成脚本）
- 扫描历史（最近 20 条记录）

### 3. docs/FAQ.md — 新增 3 条 Web FAQ
- Q: Web 仪表板和 CLI 有什么区别？
- Q: Web 仪表板安全吗？可以暴露到公网吗？
- Q: 加固脚本生成后会自动执行吗？

### 4. CHANGELOG.md — 新增 v0.0.30 条目
在文件顶部（[0.2.0] 之前）插入 [0.3.0] 条目：
- 新增：Web 仪表板、Flask REST API、Session 鉴权、CSRF 防护、lightshield serve
- 变更：版本 0.1.0→0.3.0、测试 534→575

## 约束
- 中文文档，Markdown 格式
- 不要修改已有内容的章节标题和结构（仅在末尾追加或插入新条目）
- 使用 Flash 模型（-m deepseek-v4-flash），只做样板填充，不做复杂创作
- 不确定的细节标注 <!-- TODO: 待确认 --> 而不是编造

## 输出
4 个文件（修改已有文件，非新建）：
1. docs/INSTALL.md（追加 Web 安装章节）
2. docs/USAGE.md（追加 Web 仪表板章节）
3. docs/FAQ.md（追加 3 条 FAQ）
4. CHANGELOG.md（插入 [0.3.0] 条目）
```

---

## 十、v0.0.33 详细任务 + 启动提示词 🟢 当前任务

### 背景

v0.0.30 已发布。LightShield 现在有完整的 CLI + Web 仪表板能力。
当前部署方式需要手动安装 Python 3.10+、Nmap、pip install 等依赖。
v0.0.33 需要提供 Docker 一键部署方案，让用户无需手动配置环境。

### 任务：创建 Docker 部署方案

**新建 2 个文件：**

#### 1. `Dockerfile` — 多阶段构建

需求：
- 基础镜像：`python:3.12-slim`（轻量，~50MB）
- 安装系统依赖：`nmap`（网络扫描核心）、`curl`（健康检查）
- 安装 Python 依赖：`lightshield[web]`（Flask API + 仪表板）
- 创建非 root 用户 `lightshield`（安全最佳实践）
- 暴露端口：`5000`（Web 仪表板）
- 数据卷：`/data`（SQLite 数据库 + 报告持久化）
- 启动命令：`lightshield serve --host 0.0.0.0 --port 5000`
- 健康检查：`curl -f http://localhost:5000/api/login` 或 `lightshield version`

```dockerfile
# ---- 构建阶段 ----
FROM python:3.12-slim AS builder
RUN apt-get update && apt-get install -y --no-install-recommends nmap
COPY . /build
WORKDIR /build
RUN pip install --no-cache-dir -e ".[web]"

# ---- 运行阶段 ----
FROM python:3.12-slim
RUN apt-get update && \
    apt-get install -y --no-install-recommends nmap curl && \
    rm -rf /var/lib/apt/lists/*
RUN useradd --create-home --shell /bin/bash lightshield
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /build /app
WORKDIR /app
RUN pip install --no-deps -e ".[web]"
RUN mkdir -p /data/reports /data/logs && chown -R lightshield:lightshield /data /app
USER lightshield
EXPOSE 5000
VOLUME ["/data"]
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 CMD curl -f http://localhost:5000/static/style.css || exit 1
CMD ["lightshield", "serve", "--host", "0.0.0.0", "--port", "5000"]
```

#### 2. `docker-compose.yml` — 一键启动

需求：
- 服务名：`lightshield`
- 构建：`.`（当前目录的 Dockerfile）
- 端口映射：`"127.0.0.1:5000:5000"`（默认仅本地访问，安全）
- 环境变量：`LS_WEB_USERNAME` / `LS_WEB_PASSWORD`（默认 admin/lightshield）
- 数据卷：`./data:/data`（持久化 SQLite + 报告）
- 重启策略：`unless-stopped`
- 注释说明如何暴露到局域网/公网

```yaml
version: "3.9"
services:
  lightshield:
    build: .
    container_name: lightshield
    ports:
      - "127.0.0.1:5000:5000"   # 仅本地访问。暴露到局域网改为 "5000:5000"
    environment:
      - LS_WEB_USERNAME=admin
      - LS_WEB_PASSWORD=lightshield    # 生产环境请修改
    volumes:
      - ./data:/data              # SQLite + 报告持久化
    restart: unless-stopped
```

### 约束

- 中文注释 Dockerfile 的每个阶段
- Dockerfile 必须多阶段构建（减小最终镜像体积）
- 非 root 用户运行（安全最佳实践）
- docker-compose.yml 默认仅绑定 127.0.0.1（安全）
- 环境变量注释要提醒用户修改默认凭证
- 镜像大小目标：<300MB

### 验收标准

1. `docker compose up` 一键启动 Web 仪表板
2. `curl http://127.0.0.1:5000` 返回登录页面 HTML
3. 数据在 `./data/` 目录持久化（重启不丢失扫描历史）
4. 容器以非 root 用户运行（`docker exec lightshield whoami` → `lightshield`）
5. 健康检查生效（`docker ps` 显示 healthy）

### 启动提示词（直接复制到 Hermes）

```
你是 LightShield 项目的工具链+基础设施专家，使用 DeepSeek-V4-flash 模型。

## 项目背景
LightShield 轻盾 v0.0.30 已发布。项目有完整的 CLI + Web 仪表板（Flask）。
路径：E:/Github Project/LightShield/

当前部署依赖手动安装 Python/Nmap/pip，需要 Docker 一键部署方案。

## 任务：创建 Docker 部署方案（2 个新文件）

### 1. Dockerfile（多阶段构建）
- 基础镜像 python:3.12-slim
- 系统依赖：nmap、curl
- Python 依赖：pip install lightshield[web]
- 非 root 用户 lightshield 运行
- 暴露端口 5000
- 数据卷 /data（SQLite + 报告）
- 启动命令：lightshield serve --host 0.0.0.0 --port 5000
- 健康检查：curl 本地 /static/style.css
- 目标：镜像 < 300MB

### 2. docker-compose.yml
- 服务名 lightshield
- 端口 127.0.0.1:5000:5000（默认仅本地）
- 环境变量 LS_WEB_USERNAME / LS_WEB_PASSWORD
- 数据卷 ./data:/data
- 重启策略 unless-stopped
- 中文注释

## 约束
- 中文注释，Flash 模型 (-m deepseek-v4-flash)
- 多阶段构建减小镜像
- 非 root 运行
- 默认仅监听本地（安全），注释说明如何开放

## 验收
1. docker compose up 一键启动
2. curl http://127.0.0.1:5000 返回登录页
3. ./data/ 持久化
4. 非 root 运行
5. 健康检查 healthy

## 输出
2 个新文件：Dockerfile + docker-compose.yml
```

## 十一、代码规范

- 生成的 `__init__.py` 包含中文 docstring 和 `__all__`
- `requirements.txt` 每个依赖注明版本范围和用途（中文注释）
- `.gitignore` 每个规则用中文注释说明排除原因
- Shell 脚本包含中文日志输出
