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

v0.3.0 新增 Web 仪表板，通过浏览器图形化界面使用 LightShield。

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
