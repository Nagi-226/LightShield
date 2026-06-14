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
git clone https://github.com/LightShield/lightshield.git
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
git clone https://github.com/LightShield/lightshield.git
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
git clone https://github.com/LightShield/lightshield.git
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
git clone https://github.com/LightShield/lightshield.git
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

如果看到 `LightShield 轻盾 v0.2.0` 即安装成功。

尝试一次快速扫描以确认 Nmap 集成正常：

```bash
lightshield quick-scan 127.0.0.1 --confirm-ownership
```

---

## Web 仪表板（可选）

v0.3.0 新增 Web 仪表板，通过浏览器交互式使用 LightShield。

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

> 详细使用说明请参见 [使用手册](USAGE.md)。
> 常见问题请参见 [FAQ](FAQ.md)。
