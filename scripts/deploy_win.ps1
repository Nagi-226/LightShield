1|<#
2|.SYNOPSIS
3|    LightShield 轻盾 — Windows 一键部署脚本
4|.DESCRIPTION
5|    兼容 Windows Server 2016+ / Windows 10+
6|    自动检测 Python 环境，安装依赖，验证安装
7|.NOTES
8|    需要以管理员身份运行
9|    本工具仅用于自有资产安全自查，禁止用于非法用途
10|#>
11|
12|# =============================================================================
13|# LightShield 轻盾 — Windows 一键部署脚本
14|# 兼容：Windows Server 2016+ / Windows 10+
15|# 用法：以管理员身份运行此脚本
16|# =============================================================================
17|
18|# ── 合规声明 ──
19|Write-Host "============================================" -ForegroundColor Cyan
20|Write-Host "  LightShield 轻盾 — 一键部署" -ForegroundColor Cyan
21|Write-Host "============================================" -ForegroundColor Cyan
22|Write-Host ""
23|Write-Host "【合规声明】本工具仅用于自有资产安全自查，禁止用于非法用途。" -ForegroundColor Yellow
24|Write-Host ""
25|
26|# ── 检查管理员权限 ──
27|Write-Host "[1/6] 检查管理员权限..." -ForegroundColor Green
28|
29|$IsAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
30|
31|if (-not $IsAdmin) {
32|    Write-Host "[错误] 请以管理员身份运行此脚本！" -ForegroundColor Red
33|    Write-Host "  右键点击脚本文件，选择"以管理员身份运行"" -ForegroundColor Yellow
34|    exit 1
35|}
36|Write-Host "  管理员权限确认" -ForegroundColor Green
37|
38|# ── 检测 Python 环境 ──
39|Write-Host "[2/6] 检测 Python 环境..." -ForegroundColor Green
40|
41|$PythonPath = $null
42|$PythonVersion = $null
43|
44|# 尝试多个可能的 Python 路径
45|$pythonCandidates = @(
46|    "python3",
47|    "python",
48|    "$env:ProgramFiles\Python311\python.exe",
49|    "$env:ProgramFiles\Python312\python.exe",
50|    "$env:ProgramFiles\Python310\python.exe",
51|    "${env:ProgramFiles(x86)}\Python311\python.exe",
52|    "${env:ProgramFiles(x86)}\Python312\python.exe",
53|    "${env:ProgramFiles(x86)}\Python310\python.exe",
54|    "$env:LOCALAPPDATA\Programs\Python\Python311\python.exe",
55|    "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe",
56|    "$env:LOCALAPPDATA\Programs\Python\Python310\python.exe"
57|)
58|
59|foreach ($candidate in $pythonCandidates) {
60|    try {
61|        $version = & $candidate --version 2>&1
62|        if ($LASTEXITCODE -eq 0 -and $version -match "Python 3\.(\d+)") {
63|            $majorMinor = [int]$Matches[1]
64|            if ($majorMinor -ge 10) {
65|                $PythonPath = $candidate
66|                $PythonVersion = $version.Trim()
67|                break
68|            }
69|        }
70|    } catch {
71|        continue
72|    }
73|}
74|
75|if (-not $PythonPath) {
76|    Write-Host "  [提示] 未找到 Python 3.10+，尝试通过 winget 安装..." -ForegroundColor Yellow
77|
78|    try {
79|        # 检查 winget 是否可用（Windows 10 1809+ 内置）
80|        $wingetCheck = Get-Command winget -ErrorAction SilentlyContinue
81|        if ($wingetCheck) {
82|            Write-Host "  正在安装 Python 3.11..." -ForegroundColor Yellow
83|            winget install Python.Python.3.11 --accept-source-agreements --silent
84|            if ($LASTEXITCODE -eq 0) {
85|                # 安装后重新查找
86|                $PythonPath = "$env:ProgramFiles\Python311\python.exe"
87|                if (Test-Path $PythonPath) {
88|                    $PythonVersion = & $PythonPath --version
89|                    Write-Host "  Python 安装成功: $PythonVersion" -ForegroundColor Green
90|                } else {
91|                    Write-Host "[错误] Python 安装失败，请手动安装 Python 3.10+" -ForegroundColor Red
92|                    Write-Host "  下载地址: https://www.python.org/downloads/" -ForegroundColor Yellow
93|                    exit 1
94|                }
95|            } else {
96|                Write-Host "[错误] winget 安装失败，请手动安装 Python 3.10+" -ForegroundColor Red
97|                Write-Host "  下载地址: https://www.python.org/downloads/" -ForegroundColor Yellow
98|                exit 1
99|            }
100|        } else {
101|            Write-Host "[错误] 未找到 winget，请手动安装 Python 3.10+" -ForegroundColor Red
102|            Write-Host "  下载地址: https://www.python.org/downloads/" -ForegroundColor Yellow
103|            exit 1
104|        }
105|    } catch {
106|        Write-Host "[错误] 安装 Python 失败: $_" -ForegroundColor Red
107|        Write-Host "  请手动安装 Python 3.10+: https://www.python.org/downloads/" -ForegroundColor Yellow
108|        exit 1
109|    }
110|} else {
111|    Write-Host "  检测到: $PythonVersion" -ForegroundColor Green
112|    Write-Host "  路径: $PythonPath" -ForegroundColor Green
113|}
114|
115|# ── 获取脚本所在目录 ──
116|Write-Host "[3/6] 准备项目源码..." -ForegroundColor Green
117|
118|$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
119|$ProjectDir = Split-Path -Parent $ScriptDir
120|
121|# 验证项目结构
122|if (-not (Test-Path "$ProjectDir\pyproject.toml") -or -not (Test-Path "$ProjectDir\lightshield\__init__.py")) {
123|    Write-Host "[错误] 未找到项目源码！" -ForegroundColor Red
124|    Write-Host "  请确保 deploy_win.ps1 位于项目根目录的 scripts/ 文件夹中" -ForegroundColor Yellow
125|    Write-Host "  期望结构:" -ForegroundColor Yellow
126|    Write-Host "    project_root/" -ForegroundColor Yellow
127|    Write-Host "    ├── pyproject.toml" -ForegroundColor Yellow
128|    Write-Host "    ├── lightshield/" -ForegroundColor Yellow
129|    Write-Host "    └── scripts/deploy_win.ps1" -ForegroundColor Yellow
130|    exit 1
131|}
132|Write-Host "  项目源码已找到: $ProjectDir" -ForegroundColor Green
133|
134|# ── 安装 Python 依赖 ──
135|Write-Host "[4/6] 安装 Python 依赖..." -ForegroundColor Green
136|
137|Set-Location $ProjectDir
138|
139|try {
140|    # 升级 pip
141|    Write-Host "  正在升级 pip..." -ForegroundColor Gray
142|    & $PythonPath -m pip install --upgrade pip -q
143|    if ($LASTEXITCODE -ne 0) {
144|        Write-Host "  [警告] pip 升级失败，继续执行..." -ForegroundColor Yellow
145|    }
146|
147|    # 安装项目依赖
148|    Write-Host "  正在安装运行时依赖 (requirements.txt)..." -ForegroundColor Gray
149|    & $PythonPath -m pip install -r requirements.txt -q
150|    if ($LASTEXITCODE -ne 0) {
151|        Write-Host "[错误] 依赖安装失败" -ForegroundColor Red
152|        exit 1
153|    }
154|
155|    # 安装项目本身（可编辑模式）
156|    Write-Host "  正在安装 LightShield 包 (pip install -e .)..." -ForegroundColor Gray
157|    & $PythonPath -m pip install -e . -q
158|    if ($LASTEXITCODE -ne 0) {
159|        Write-Host "[错误] LightShield 安装失败" -ForegroundColor Red
160|        exit 1
161|    }
162|
163|    Write-Host "  Python 依赖安装完成" -ForegroundColor Green
164|} catch {
165|    Write-Host "[错误] 安装过程异常: $_" -ForegroundColor Red
166|    exit 1
167|}
168|
169|# ── 验证安装 ──
170|Write-Host "[5/6] 验证安装..." -ForegroundColor Green
171|
172|try {
173|    $versionOutput = & $PythonPath -m lightshield.cli version 2>&1
174|    if ($LASTEXITCODE -eq 0) {
175|        Write-Host "  $($versionOutput.Trim())" -ForegroundColor Green
176|    } else {
177|        # 尝试通过直接入口验证
178|        Write-Host "  尝试验证包导入..." -ForegroundColor Gray
179|        $importTest = & $PythonPath -c "import lightshield; print(f'LightShield v{lightshield.__version__}')" 2>&1
180|        if ($LASTEXITCODE -eq 0) {
181|            Write-Host "  $($importTest.Trim())" -ForegroundColor Green
182|        } else {
183|            Write-Host "  [警告] 验证输出: $($importTest.Trim())" -ForegroundColor Yellow
184|        }
185|    }
186|} catch {
187|    Write-Host "  [警告] 验证异常: $_" -ForegroundColor Yellow
188|}
189|
190|# ── 添加入 PATH（可选） ──
191|Write-Host "[6/6] 配置环境变量（可选）..." -ForegroundColor Green
192|
193|$PythonScriptsDir = Split-Path -Parent (& $PythonPath -c "import sys; print(sys.executable)")
194|$ScriptsPath = Join-Path $PythonScriptsDir "Scripts"
195|if (Test-Path $ScriptsPath) {
196|    $CurrentPath = [Environment]::GetEnvironmentVariable("Path", "User")
197|    if ($CurrentPath -notlike "*$ScriptsPath*") {
198|        try {
199|            [Environment]::SetEnvironmentVariable("Path", "$CurrentPath;$ScriptsPath", "User")
200|            Write-Host "  已将 $ScriptsPath 添加到用户 PATH" -ForegroundColor Green
201|        } catch {
202|            Write-Host "  无法自动添加 PATH（非阻塞，可手动添加）" -ForegroundColor Yellow
203|        }
204|    } else {
205|        Write-Host "  PATH 已包含 $ScriptsPath" -ForegroundColor Green
206|    }
207|} else {
208|    Write-Host "  Scripts 目录不存在，跳过 PATH 配置" -ForegroundColor Yellow
209|}
210|
211|# ── 完成提示 ──
212|Write-Host ""
213|Write-Host "============================================" -ForegroundColor Cyan
214|Write-Host "  LightShield 轻盾 — 部署成功！" -ForegroundColor Cyan
215|Write-Host "============================================" -ForegroundColor Cyan
216|Write-Host ""
217|Write-Host "  项目路径: $ProjectDir" -ForegroundColor White
218|Write-Host "  Python  : $PythonPath" -ForegroundColor White
219|Write-Host ""
220|
221|# 确定 lightshield 命令的完整路径
222|$LightShieldCli = Join-Path $ScriptsPath "lightshield.exe"
223|if (-not (Test-Path $LightShieldCli)) {
224|    $LightShieldCli = "$PythonPath -m lightshield.cli"
225|}
226|
227|Write-Host "  【快速开始】" -ForegroundColor Cyan
228|Write-Host "    全量扫描: $LightShieldCli scan 127.0.0.1 --confirm-ownership" -ForegroundColor White
229|Write-Host "    快速扫描: $LightShieldCli quick-scan 127.0.0.1 --confirm-ownership" -ForegroundColor White
230|Write-Host "    查看版本: $LightShieldCli version" -ForegroundColor White
231|Write-Host ""
232|Write-Host "  【重要】" -ForegroundColor Yellow
233|Write-Host "  1. 本工具仅用于自有资产安全自查" -ForegroundColor Yellow
234|Write-Host "  2. 首次使用请确认目标所有权 (--confirm-ownership)" -ForegroundColor Yellow
235|Write-Host "  3. 如需添加 PATH，手动执行:" -ForegroundColor Yellow
236|Write-Host "     将以下路径添加到系统环境变量 PATH:" -ForegroundColor Gray
237|Write-Host "     $ScriptsPath" -ForegroundColor Gray
238|Write-Host ""
239|Write-Host "============================================" -ForegroundColor Cyan
240|
