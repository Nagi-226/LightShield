# LightShield 安装指南

> LightShield 轻盾 — 开源轻量化安全自检 + 防御加固工具

---

## 环境要求

| 组件 | 最低版本 | 说明 |
|------|----------|------|
| Python | 3.10+ | 核心运行环境 |
| Nmap | 7.x | 端口扫描引擎（需安装并添加到 PATH） |
| pip | 最新版 | Python 包管理器 |

### 可选依赖

| 组件 | 用途 | 安装方式 |
|------|------|----------|
| `python-nmap` | Nmap Python 封装 | `pip install lightshield[nmap]` |
| `flask` | Web 仪表板（Flask REST API + 浏览器面板） | `pip install lightshield[web]` |

---

## Linux 安装

LightShield 支持 CentOS 7+ / Ubuntu 18.04+ / Debian 10+。

### 方式一：一键部署脚本（推荐）

```bash
# 克隆项目
git clone https://github.com/Nagi-226/LightShield.git
cd lightshield

# 一键部署（自动安装 Python/Nmap/依赖）
sudo bash scripts/deploy_linux.sh
```

部署脚本会自动完成：
1. 检测操作系统和包管理器
2. 安装 Python 3 + pip + Nmap
3. 创建 `/opt/lightshield` 安装目录
4. 复制源码并安装 Python 依赖
5. 验证安装

### 方式二：手动安装

```bash
# 1. 安装系统依赖
# CentOS / RHEL
sudo yum install -y python3 python3-pip nmap

# Ubuntu / Debian
sudo apt update
sudo apt install -y python3 python3-pip python3-venv nmap

# 2. 克隆项目
git clone https://github.com/Nagi-226/LightShield.git
cd lightshield

# 3. 安装 Python 依赖
pip install -r requirements.txt
pip install -e .

# 4. 验证
lightshield version
```

---

## Windows 安装

LightShield 支持 Windows 10+ / Windows Server 2016+。

### 方式一：一键部署脚本（推荐）

以**管理员身份**运行 PowerShell：

```powershell
# 克隆项目
git clone https://github.com/Nagi-226/LightShield.git
cd lightshield

# 一键部署
.\scripts\deploy_win.ps1
```

部署脚本会自动完成：
1. 检测 Python 3.10+（未安装则通过 winget 自动安装）
2. 安装 Python 依赖
3. 添加 PATH 环境变量
4. 验证安装

### 方式二：手动安装

```powershell
# 1. 安装 Python 3.10+
# 从 https://www.python.org/downloads/ 下载并安装
# 安装时勾选 "Add Python to PATH"

# 2. 安装 Nmap
# 从 https://nmap.org/download.html 下载并安装
# 安装时勾选 "Add Nmap to the system PATH"

# 3. 克隆项目
git clone https://github.com/Nagi-226/LightShield.git
cd lightshield

# 4. 安装 Python 依赖
pip install -r requirements.txt
pip install -e .

# 5. 验证
lightshield version
```

---

## 验证安装

```bash
lightshield version
```

如果看到 `LightShield 轻盾 v0.0.20` 即安装成功。

尝试一次快速扫描以确认 Nmap 集成正常：

```bash
lightshield quick-scan 127.0.0.1 --confirm-ownership
```

---

## Web 仪表板（可选）

v0.0.30 新增 Web 仪表板，通过浏览器交互式使用 LightShield。

### 安装

```bash
# 安装 Web 依赖
pip install lightshield[web]

# 或者与完整项目一起安装
pip install -e .[web]
```

### 启动

```bash
lightshield serve
```

默认监听 `http://127.0.0.1:5000`。

### 默认凭证

| 用户名 | 密码 |
|--------|------|
| `admin` | `lightshield` |

可通过环境变量覆盖：

```bash
# Linux / macOS
export LS_WEB_USERNAME=myadmin
export LS_WEB_PASSWORD=mysecret

# Windows PowerShell
$env:LS_WEB_USERNAME="myadmin"
$env:LS_WEB_PASSWORD="mysecret"

lightshield serve
```

---

## 常见安装问题

### pip 安装慢
```bash
# 使用清华镜像加速
pip install -i https://pypi.tuna.tsinghua.edu.cn/simple -r requirements.txt
pip install -i https://pypi.tuna.tsinghua.edu.cn/simple -e .
```

### Windows 上提示 "lightshield 不是内部或外部命令"
确保安装时已将 Python Scripts 目录添加到 PATH。可以手动添加：

```
# 找到 Python Scripts 目录（例如）
C:\Users\<用户名>\AppData\Local\Programs\Python\Python311\Scripts
```

或使用完整路径运行：
```powershell
python -m lightshield.cli scan 127.0.0.1 --confirm-ownership
```

### Nmap 未找到
确保 Nmap 已安装并添加到系统 PATH。可以运行 `nmap --version` 验证。

---

## Docker 部署

v0.0.33 新增 Docker 部署支持，适合容器化环境或不想在宿主机安装 Python 依赖的用户。

### 前置要求

- Docker 20.10+
- Docker Compose v2

### 一键启动

```bash
# 克隆项目
git clone https://github.com/Nagi-226/LightShield.git
cd lightshield

# 构建并启动
docker compose up -d

# 查看日志
docker compose logs -f lightshield
```

默认监听 `http://127.0.0.1:5000`，使用默认凭证 `admin / lightshield` 登录。

### 数据持久化

`docker-compose.yml` 已配置数据卷：

| 卷 | 容器路径 | 用途 |
|------|---------|------|
| `lightshield-data` | `/app/data` | SQLite 数据库（扫描历史） |
| `lightshield-reports` | `/app/reports` | 生成的报告和加固脚本 |
| `lightshield-logs` | `/app/logs` | 运行日志 |

### 自定义配置

通过环境变量覆盖默认配置（详见 `.env.example`）：

```yaml
# docker-compose.yml 片段
environment:
  - LS_WEB_USERNAME=myadmin
  - LS_WEB_PASSWORD=mysecret
  - LS_LOG_LEVEL=DEBUG
```

### 已知限制

Docker 容器内**无法**使用以下功能（受容器隔离限制）：

- ❌ `--closed-loop --apply`（真机加固执行）——容器内执行加固脚本无意义
- ❌ Nmap OS 指纹探测（`-O`）——需要容器特权，默认不开启
- ✅ `scan` / `quick-scan` / `harden`（脚本生成）/ Web 仪表板均可正常使用

> 如需在 Docker 中使用 Nmap 的全部功能（含 OS 探测），请参考 [Nmap in Docker](https://nmap.org/nmap_doc.html) 的特权容器配置，但这会降低隔离性，**不推荐在生产环境使用**。

---

## Windows 已知问题

### 1. PowerShell 执行策略限制

运行 `deploy_win.ps1` 时可能遇到：

```
无法加载文件 deploy_win.ps1，因为在此系统上禁止运行脚本
```

**解决方案**：以管理员身份运行 PowerShell，执行：

```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

### 2. Nmap 路径未自动加入 PATH

Windows 版 Nmap 安装时如果未勾选 "Add to PATH"，需手动添加：

```
C:\Program Files (x86)\Nmap
```

到系统环境变量 `PATH` 中，然后重启终端。

### 3. 加固脚本执行被杀毒软件拦截

Windows Defender 或第三方杀毒软件可能将 `.ps1` 加固脚本误报为恶意软件（因为脚本包含 `netsh` / `Set-Service` 等系统修改命令）。

**解决方案**：

- 将 `reports/` 目录加入杀毒软件白名单
- 或使用 `--output-format text` 生成纯文本建议，手动执行

### 4. WSL2 中使用 LightShield

在 WSL2 (Ubuntu) 中安装 LightShield 后，扫描 Windows 宿主机 IP 需使用宿主机在 WSL 网络中的地址：

```bash
# 获取 Windows 宿主机 IP（WSL2）
WIN_HOST=$(cat /etc/resolv.conf | grep nameserver | awk '{print $2}')

# 扫描宿主机
lightshield scan $WIN_HOST --confirm-ownership
```

### 5. 中文显示乱码

Windows CMD 默认编码为 GBK，Markdown 报告（UTF-8）在 CMD 中 `cat` 可能乱码。建议：

```powershell
# 临时切换为 UTF-8
chcp 65001

# 或使用 PowerShell 的 Get-Content
Get-Content ./reports/report-*.md -Encoding UTF8
```

---

## 验证安装

```bash
lightshield version
```

如果看到 `LightShield 轻盾 v0.0.46` 即安装成功。

尝试一次快速扫描以确认 Nmap 集成正常：

```bash
lightshield quick-scan 127.0.0.1 --confirm-ownership
```

---

> 详细使用说明请参见 [使用手册](USAGE.md)。
> 常见问题请参见 [FAQ](FAQ.md)。
