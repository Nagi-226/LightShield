# LightShield 使用手册

> LightShield 轻盾 — 开源轻量化安全自检 + 防御加固工具

---

## 快速开始

最简单的使用方式：

```bash
# 全量扫描本机
lightshield scan 127.0.0.1 --confirm-ownership
```

执行后会依次：
1. 校验目标合法性（仅允许单 IP / 域名 / localhost）
2. 确认所有权（首次运行需输入 `YES` 确认）
3. 端口扫描 → 服务识别 → 操作系统检测
4. Web 漏洞检测、弱口令检测、组件安全检测
5. 规则引擎匹配风险
6. 生成中文安全报告（默认 `./reports/` 目录）

---

## 扫描资产

### `lightshield scan` — 全量扫描

对目标进行完整的安全检测（端口扫描 Top 1000 + 漏洞检测 + 报告生成）。

```bash
# 基本用法
lightshield scan 192.168.1.1 --confirm-ownership

# 指定输出格式和目录
lightshield scan example.com --output-format text --output-dir ./my-reports

# 指定扫描类型（逗号分隔）
lightshield scan 192.168.1.1 --scan-types port_scan,web_vuln --confirm-ownership

# 调整超时时间
lightshield scan 127.0.0.1 --timeout 120 --confirm-ownership

# 详细日志
lightshield scan 127.0.0.1 --verbose --confirm-ownership
```

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `target` | 目标 IP / 域名 / localhost | **必填** |
| `--output-format` | 报告格式：`markdown` / `text` | `markdown` |
| `--output-dir` | 报告输出目录 | `./reports` |
| `--scan-types` | 扫描类型，逗号分隔 | `port_scan,service_detect` |
| `--confirm-ownership` | 确认目标所有权 | 否 |
| `--timeout` | 超时时间（秒） | `60` |
| `--verbose` | 详细日志输出 | 否 |

### `lightshield quick-scan` — 快速扫描

仅扫描 Top 100 端口，比全量扫描快 3-10 倍，适合快速判断目标状态。

```bash
lightshield quick-scan 192.168.1.1 --confirm-ownership
```

参数说明同 `scan` 命令。扫描范围固定在 Top 100 端口。

---

## 检测漏洞

LightShield 集成了三类漏洞检测器，在 `scan` 或 `quick-scan` 过程中自动运行：

### Web 漏洞检测

- XSS（跨站脚本）检测
- SQL 注入检测
- 敏感信息泄露检测
- HTTP 响应头安全分析

### 弱口令检测

- 常见 SSH / FTP / Telnet / MySQL / PostgreSQL / Redis 弱口令检测
- 基于常见弱口令字典

### 组件安全检测

- HTTP 响应头 Server 信息提取
- X-Powered-By 信息提取
- 常见组件版本识别

> 所有漏洞检测器均为可选加载，如某检测器依赖缺失（如 `beautifulsoup4` 未安装），会自动降级跳过，不影响其他扫描。

---

## 生成加固脚本

### `lightshield harden` — 加固脚本生成

```bash
# 基本用法
lightshield harden 192.168.1.1 --confirm-ownership

# 指定输出目录
lightshield harden 127.0.0.1 --output-dir ./harden-scripts --confirm-ownership

# 指定报告格式
lightshield harden 192.168.1.1 --output-format text --confirm-ownership
```

执行流程：
1. 扫描目标资产（同 `scan`）
2. 规则引擎匹配风险
3. 生成**加固脚本**（`.sh` / `.ps1`）和**回滚脚本**
4. 输出加固建议摘要

**重要安全提示：**
- ⚠️ 加固脚本**不会自动执行**，需要用户审阅后手动执行
- ⚠️ 请先在小规模环境测试，再应用到生产服务器
- ⚠️ 回滚脚本可用于恢复加固前的状态

---

## 自动加固闭环

### `lightshield harden --closed-loop` — 加固闭环（v0.0.40+）

自动加固闭环将"扫描→推荐→生成→执行→复扫→验证"七步串联为一条命令，支持两种模式：

| 模式 | 标志 | 作用 | 改系统？ | 复扫？ |
|------|------|------|:--:|:--:|
| **DRY_RUN**（默认） | `--closed-loop` | 预检：R1 攻击关键字扫描 + 锁死容器烟测 | ❌ | ❌ |
| **APPLY** | `--closed-loop --apply` | 真机执行加固脚本，复扫验证修复效果 | ✅ | ✅ |

#### DRY_RUN 模式（预检，不改系统）

```bash
lightshield harden 127.0.0.1 --closed-loop --confirm-ownership
```

执行步骤：
1. ✅ 基线扫描（发现风险）
2. ✅ 规则推荐（生成加固建议）
3. ✅ 脚本生成（输出 `.sh` / `.ps1`）
4. 🔄 预检（R1 攻击关键字扫描 + Docker 锁死容器烟测）
5. ⏭️ 不复扫、不改系统

输出示例：

```
[闭环/DRY_RUN] 正在预检加固脚本（不改系统）...
  ① 基线扫描 ✅
  ② 规则推荐 ✅
  ③ 脚本生成 ✅
  ④ 预检中（R1 扫描 + 容器烟测）...

============================================================
  加固闭环结果 — 127.0.0.1
  模式  ：dry_run
  OS    ：linux
  审计ID：CL-20260615-160000-a1b2c3
  ─────────────────────────────────────────
  基线扫描：completed (3 条风险)
  加固建议：5 条操作
  执行状态：skipped
  ─────────────────────────────────────────
  总判定  ：📋 仅生成（未复扫）
============================================================
```

#### APPLY 模式（真机执行，改真实系统）

⚠️ **APPLY 模式会在宿主机本机执行加固脚本，真实修改系统配置。**

```bash
# 必须同时传 --confirm-ownership 和 --apply
lightshield harden 127.0.0.1 --closed-loop --apply --confirm-ownership
```

执行步骤：
1. ✅ 基线扫描
2. ✅ 规则推荐
3. ✅ 脚本生成
4. 🔄 DRY_RUN-first 前置预检（必须通过）
5. 🔄 真机执行加固脚本（改 iptables / 服务 / 配置）
6. 🔄 复扫同一台真机
7. ✅ 验证比对（resolved / remaining / regressed）
8. ✅ 汇总判定

**APPLY 模式四重护栏**（任一不满足即拒绝执行）：

| 护栏 | 内容 |
|:--:|------|
| 1 | R4 双重确认（`--confirm-ownership` + `--apply` + 输入 `EXECUTE`） |
| 2 | DRY_RUN-first 前置（先通过预检才能 APPLY） |
| 3 | rollback 脚本就绪（回滚脚本必须已生成） |
| 4 | R1 最终扫描（执行前再扫一次攻击关键字） |

输出示例：

```
[闭环/APPLY] 正在真机执行加固闭环...
  ① 基线扫描 ✅（已在前面完成）
  ② 规则推荐 ✅
  ③ 脚本生成 ✅
  ④ 真机执行中...

============================================================
  加固闭环结果 — 127.0.0.1
  模式  ：apply
  OS    ：linux
  审计ID：CL-20260615-160500-d4e5f6
  ─────────────────────────────────────────
  基线扫描：completed (3 条风险)
  加固建议：5 条操作
  执行状态：success (exit_code=0, 12.3s)
  复扫状态：completed
  复扫发现：0 条风险
  ─────────────────────────────────────────
  验证判定：verified
  已修复  ：3 条
  仍存在  ：0 条
  新增风险：0 条
  ─────────────────────────────────────────
  总判定  ：✅ 验证通过
============================================================
```

#### 验证判定（verdict）规则

| verdict | 含义 | 条件 |
|------|------|------|
| `verified` | 验证通过 | 所有风险已修复，无残留，无新增 |
| `partial` | 部分修复 | 有风险已修复，但仍有残留或新增 |
| `failed` | 未修复 | 未消除任何风险，或仅有新增风险 |
| `generated_only` | 仅生成 | DRY_RUN 模式，未执行复扫 |

---

## 查看历史

### `lightshield history` — 扫描历史查询

```bash
# 查看最近 20 条扫描记录
lightshield history

# 查看最近 50 条
lightshield history --limit 50

# 按目标过滤
lightshield history 192.168.1.1

# 查看指定扫描详情
lightshield history --scan-id LS-20260615-153012-a1b2

# 以 JSON 格式输出（便于脚本处理）
lightshield history --format json
```

扫描历史存储在 SQLite 数据库（`data/lightshield.db`），包含目标、状态、端口数、漏洞数、CVE 数、耗时等摘要信息。

---

## 规则导入

### 从远程 URL 导入规则

```bash
lightshield scan 127.0.0.1 --rules-url https://example.com/custom-rules.json --confirm-ownership
```

规则文件格式为 JSON 数组或 `{"rules": [...]}` 对象，每条规则须包含 `rule_id` 和 `match_type` 字段。导入的规则与内置规则合并，不覆盖已有规则（按 `rule_id` 去重）。

### 从本地文件导入

```python
from lightshield.rules.engine import RuleEngine

engine = RuleEngine()
engine.load_rules()
engine.import_rules_from_file("/path/to/custom-rules.json", rule_type="vuln")
```

---

## Bark 通知推送

扫描或加固闭环完成后，可通过 [Bark](https://apps.apple.com/us/app/bark-push-notifications/id1403753865) 推送结果到手机：

```bash
# 通过 CLI 参数
lightshield scan 127.0.0.1 --bark-key YOUR_BARK_KEY --confirm-ownership

# 或通过环境变量（推荐，避免在命令历史中泄露）
export LS_BARK_KEY=YOUR_BARK_KEY
lightshield scan 127.0.0.1 --confirm-ownership
```

扫描完成后，手机会收到类似通知：

```
🔴 LightShield 扫描完成
目标: 127.0.0.1
发现: 3 个漏洞
  🔴 严重: 1
  🟠 高危: 2
耗时: 15s
```

---

## 查看报告

### Markdown 格式（默认）

报告包含以下内容：

```
reports/
└── report-<日期>-<时间>.md
    ├── 扫描摘要
    ├── 端口与服务详情
    ├── 漏洞发现（含严重等级）
    ├── 加固建议
    └── 原始扫描数据
```

### Text 格式

```bash
lightshield scan 127.0.0.1 --output-format text --confirm-ownership
```

适合在终端直接查看或管道输出到其他工具。

---

## Web 仪表板

v0.0.30 新增 Web 仪表板，通过浏览器图形化界面使用 LightShield。

### 启动服务

```bash
lightshield serve
```

默认监听 `http://127.0.0.1:5000`。

### 登录

使用浏览器访问 `http://127.0.0.1:5000`，使用默认凭证登录：

| 字段 | 值 |
|------|-----|
| 用户名 | `admin` |
| 密码 | `lightshield` |

可通过环境变量 `LS_WEB_USERNAME` / `LS_WEB_PASSWORD` 自定义凭证。

### 新建扫描

1. 登录后进入仪表板首页
2. 输入目标 IP 或域名（前端 R2 校验，拒绝 CIDR/URL/通配符）
3. 选择扫描类型（全量扫描 / 资产扫描 / 漏洞扫描）
4. 勾选「我确认拥有目标所有权」（R4 合规）
5. 点击「开始扫描」，等待实时进度更新

### 查看报告

- 扫描完成后出现「查看报告」链接
- 报告包含：扫描摘要、开放端口、服务版本、漏洞详情（含严重等级色彩标签）
- Markdown 格式在浏览器中渲染显示（表格、标题、代码块完整保留）

### 加固建议

- 报告底部展示规则引擎匹配的加固建议
- 每条建议附带风险等级和修复说明
- **加固脚本不会在 Web 中自动执行**，需手动下载后审阅执行

### 扫描历史

- 扫描结果自动保存到 SQLite 数据库（`data/lightshield.db`）
- 仪表板右侧展示最近 20 条扫描记录
- 可点击"查看报告"跳转历史报告，或点击"加固"查看历史加固建议

---

## 完整示例

```bash
# 场景：对新部署的 Web 服务器做安全检查

# 1. 快速扫描判断基础状况
lightshield quick-scan 203.0.113.10 --confirm-ownership

# 2. 全量扫描获取详细信息
lightshield scan 203.0.113.10 --verbose --confirm-ownership

# 3. 生成加固脚本
lightshield harden 203.0.113.10 --confirm-ownership

# 4. 查看生成的加固脚本
cat ./reports/harden_203.0.113.10.sh
# 审阅后执行
```

---

> 📖 安装说明请参见 [安装指南](INSTALL.md)。
> ❓ 常见问题请参见 [FAQ](FAQ.md)。
