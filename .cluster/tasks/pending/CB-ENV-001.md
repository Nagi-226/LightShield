# CB-ENV-001：LightShield 开发环境安全搬迁（C盘→D/E盘）

> **【CodeBuddy 模式：B · WorkBuddy Desktop 桌面端】**
> **【切换：代码开发 体系 + Craft 模式】**
> **【模型切换：DeepSeek-V4-Pro】**

---

## 一、任务概述

### 问题

C 盘 200G 全满（仅剩 13MB 可用）。当前 LightShield 项目的 Python 本体（Windows Store 版）和所有 pip 包、临时文件全落在 C 盘，导致 pytest、git、Claude Code 子进程频繁因磁盘空间不足（ENOSPC）而失败。

### 目标

在 D 盘安装一套独立的 Python 3.12，在 E 盘项目目录创建 venv，设置环境变量让所有工具未来把临时文件/缓存写到 E 盘。

### 核心原则（绝对不能违反）

| 红线 | 说明 |
|:--:|------|
| 🔴 | **绝对不卸载、不删除、不移动 C 盘任何文件或目录** |
| 🔴 | **绝对不修改系统 PATH 环境变量** |
| 🔴 | **绝对不碰 `C:\Users\FJL03\AppData` 下任何内容** |
| 🟢 | 所有操作仅限于 D 盘和 E 盘——新增文件 + 新增 User 级环境变量 |

C 盘作为"博物馆"原样保留——现有的 Windows Store Python、hermes venv 等一切照旧，不做任何改动。

---

## 二、执行步骤

请按顺序执行以下每一步。每一步执行完后确认结果符合预期，再进入下一步。如果任何一步失败，停下来报告，不要继续。

---

### Step 1：现状确认（只读，不做任何修改）

打开 PowerShell（以当前用户身份，不需要管理员），依次执行以下只读命令，确认当前状态：

```powershell
# 1.1 确认 C 盘 Python 位置（只读）
where.exe python
# 预期输出：C:\Users\FJL03\AppData\Local\Microsoft\WindowsApps\python.exe

# 1.2 确认当前 pip 包安装位置（只读）
python -c "import sys; print(sys.prefix)"

# 1.3 确认 C 盘剩余空间（只读）
Get-PSDrive C | Select-Object Used,Free

# 1.4 确认 D 盘和 E 盘空间（只读）
Get-PSDrive D,E | Format-Table Name,Used,Free

# 1.5 确认项目目录存在（只读）
Test-Path "E:\Github Project\LightShield\requirements.txt"
# 预期输出：True
```

**验收**：确认以上信息后，报告当前 C 盘剩余空间、Python 位置，然后进入 Step 2。

---

### Step 2：在 D 盘安装 Python 3.12

> LightShield 项目配置 `pyproject.toml` 和 `.pre-commit-config.yaml` 要求 Python 3.12。

尝试以下方法（按优先级，一个成功即可）：

**方法 A：使用 winget（推荐，如果可用）**

```powershell
winget install Python.Python.3.12 --location "D:\Python312" --override "/quiet InstallAllUsers=0 PrependPath=0"
```

**方法 B：使用 Chocolatey（如果可用）**

```powershell
choco install python312 --install-arguments='"/quiet InstallAllUsers=0 PrependPath=0"' --override -y
```

**方法 C：手动下载安装**

1. 打开浏览器，访问：`https://www.python.org/ftp/python/3.12.10/python-3.12.10-amd64.exe`
2. 下载到 D 盘任意位置
3. 运行安装程序，关键操作：
   - 勾选 "Add python.exe to PATH" → **取消勾选**
   - 选择 "Customize installation"
   - 安装路径改为：`D:\Python312`
   - 其余选项保持默认

安装完成后，**不要关闭安装窗口**，先验证：

```powershell
# 验证 D 盘 Python 可执行
D:\Python312\python.exe --version
# 预期输出：Python 3.12.10（或类似的 3.12.x）
```

**验收**：`D:\Python312\python.exe --version` 输出 Python 3.12.x → 进入 Step 3。

---

### Step 3：在 E 盘项目目录创建 venv

```powershell
# 3.1 用 D 盘 Python 创建虚拟环境到 E 盘项目内
D:\Python312\python.exe -m venv "E:\Github Project\LightShield\.venv"

# 3.2 确认 venv 创建成功
Test-Path "E:\Github Project\LightShield\.venv\Scripts\python.exe"
# 预期输出：True

# 3.3 确认 venv 内的 Python 路径不涉及 C 盘
& "E:\Github Project\LightShield\.venv\Scripts\python.exe" -c "import sys; print(sys.prefix)"
# 预期输出：E:\Github Project\LightShield\.venv
```

**验收**：venv 的 `sys.prefix` 在 E 盘 → 进入 Step 4。

---

### Step 4：在 venv 内安装全部依赖

```powershell
# 4.1 激活 venv
& "E:\Github Project\LightShield\.venv\Scripts\Activate.ps1"

# 4.2 确认当前 Python 来自 venv
(Get-Command python).Source
# 预期输出：E:\Github Project\LightShield\.venv\Scripts\python.exe

# 4.3 升级 pip
python -m pip install --upgrade pip

# 4.4 安装项目全部依赖（运行时 + 开发 + 可选）
# 这一步可能需要几分钟，取决于网络速度
pip install -e ".[dev,nmap,web]"

# 4.5 验证关键包已安装
pip list | Select-String -Pattern "pytest|ruff|mypy|bandit|pre-commit|Flask|requests|PyYAML|beautifulsoup4|fpdf2"
```

**验收**：`pip list` 输出中包含 pytest、ruff、mypy、bandit、pre-commit、Flask → 进入 Step 5。

---

### Step 5：安装 pre-commit hooks

```powershell
# 确保 venv 仍处于激活状态（如果上一步的 PowerShell 窗口没关）
# 如果关了，重新激活：
& "E:\Github Project\LightShield\.venv\Scripts\Activate.ps1"

# 确认工作目录在项目根
Set-Location "E:\Github Project\LightShield"

# 5.1 安装 pre-commit hooks
pre-commit install

# 5.2 运行全量检查（首次会比较慢，需下载 hook 环境）
pre-commit run --all-files
```

**预期**：12 个 hook 全部通过（显示 PASSED 或绿色的成功标记）。如果有失败的，报告具体是哪个 hook 失败以及错误信息。

**验收**：`pre-commit run --all-files` 全部通过 → 进入 Step 6。

---

### Step 6：设置四个 User 级环境变量

> ⚠️ 以下操作仅新增 User 级别的环境变量。不修改系统变量（Machine 级别），不删除任何已有变量。这些变量随时可通过"Windows 设置 → 系统 → 关于 → 高级系统设置 → 环境变量"查看和删除。

```powershell
# 6.1 Claude Code 临时文件 → E 盘（阻止磁盘满导致的 ENOSPC 错误）
[Environment]::SetEnvironmentVariable("CLAUDE_CODE_TMPDIR", "E:\ClaudeTemp", "User")

# 6.2 pip 下载缓存 → E 盘
[Environment]::SetEnvironmentVariable("PIP_CACHE_DIR", "E:\pip-cache", "User")

# 6.3 Python __pycache__ 集中存放 → E 盘（Python 3.8+ 原生支持）
[Environment]::SetEnvironmentVariable("PYTHONPYCACHEPREFIX", "E:\pycache", "User")

# 6.4 pre-commit 缓存 → E 盘
[Environment]::SetEnvironmentVariable("PRE_COMMIT_HOME", "E:\pre-commit-cache", "User")
```

**立即验证（在同一个 PowerShell 窗口中读取刚设的值）**：

```powershell
[Environment]::GetEnvironmentVariable("CLAUDE_CODE_TMPDIR", "User")
[Environment]::GetEnvironmentVariable("PIP_CACHE_DIR", "User")
[Environment]::GetEnvironmentVariable("PYTHONPYCACHEPREFIX", "User")
[Environment]::GetEnvironmentVariable("PRE_COMMIT_HOME", "User")
```

**预期输出**：
```
E:\ClaudeTemp
E:\pip-cache
E:\pycache
E:\pre-commit-cache
```

**验收**：四个变量均指向 E 盘 → 进入 Step 7。

---

### Step 7：运行全量测试验证

```powershell
# 确保 venv 处于激活状态，工作目录在项目根
& "E:\Github Project\LightShield\.venv\Scripts\Activate.ps1"
Set-Location "E:\Github Project\LightShield"

# 运行全量测试
python -m pytest tests/ -v --tb=short
```

**验收标准**：
- `771 passed` / `0 failed` / `1 skip`（或 passed 数量不下降）
- 不再出现 `ENOSPC` 错误

---

## 三、最终验收清单

全部步骤完成后，请逐一确认：

- [ ] `D:\Python312\python.exe --version` → Python 3.12.x
- [ ] `E:\Github Project\LightShield\.venv\Scripts\python.exe` 存在
- [ ] venv 内的 `sys.prefix` 指向 `E:\Github Project\LightShield\.venv`
- [ ] `pip list` 包含 pytest / ruff / mypy / bandit / pre-commit / Flask / requests / PyYAML / beautifulsoup4 / fpdf2
- [ ] `pre-commit run --all-files` 全部通过（12 hooks）
- [ ] 四个环境变量（CLAUDE_CODE_TMPDIR / PIP_CACHE_DIR / PYTHONPYCACHEPREFIX / PRE_COMMIT_HOME）指向 E 盘
- [ ] `python -m pytest tests/ -v` → 771 passed / 0 failed / 1 skip
- [ ] C 盘 Python（`C:\Users\FJL03\AppData\Local\Microsoft\WindowsApps\python.exe`）仍然存在且可执行
- [ ] C 盘 AppData 目录下没有任何内容被改动

---

## 四、回滚方案

如果以上步骤导致任何问题，按以下顺序恢复：

```powershell
# 1. 删除四个环境变量（恢复 C 盘默认行为）
[Environment]::SetEnvironmentVariable("CLAUDE_CODE_TMPDIR", $null, "User")
[Environment]::SetEnvironmentVariable("PIP_CACHE_DIR", $null, "User")
[Environment]::SetEnvironmentVariable("PYTHONPYCACHEPREFIX", $null, "User")
[Environment]::SetEnvironmentVariable("PRE_COMMIT_HOME", $null, "User")

# 2. 删除 E 盘 venv（如果它有问题）
Remove-Item -Recurse -Force "E:\Github Project\LightShield\.venv"

# 3. 卸载 D 盘 Python（控制面板 → 程序和功能 → Python 3.12 → 卸载）
```

回滚后系统恢复到原始状态——C 盘从头到尾没有被修改过。

---

## 五、不确定性声明

| 判断 | 置信度 | 替代方案 |
|------|:--:|------|
| winget 命令可用 | 🟡 中 | 手动下载 Python 安装包（方法 C） |
| pip install 所有包一次性成功 | 🟢 高 | 如个别包失败，单独 pip install 该包 |
| pre-commit hook 首次下载较慢 | 🟢 高 | 正常现象，耐心等待即可 |
| 测试 771 passed | 🟢 高 | 环境和依赖完全一致，不应出现新失败 |
