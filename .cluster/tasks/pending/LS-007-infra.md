# LS-007: 项目基础设施 — 依赖管理 + 项目骨架

## 任务信息
- **Task ID**: LS-007
- **Phase**: Phase 1 — 项目骨架
- **分配给**: Hermes（`-m deepseek-v4-flash`，此任务为纯样板代码，Flash 完全足够）
- **模型层级**: ⚡ Flash（无需 Pro，预计节省 ~70% token 费用）
- **优先级**: P0
- **依赖**: 无
- **输出文件**: `requirements.txt`, `.gitignore`, `lightshield/__init__.py`, 各子包的 `__init__.py`

## 项目上下文

LightShield（轻盾）是一个面向初创企业 & 个人站长的开源轻量化安全自检 + 防御加固工具。
技术栈：Python 3.10+，Nmap + 自研脚本 + Metasploit auxiliary/scanner 子集。
目标部署包 ≤ 500MB。

## ⚠️ 合规约束（不可违反）

1. `.gitignore` 必须排除所有含敏感信息的文件（日志、报告、密钥、MSF 模块缓存等）
2. 不得引入任何攻击向依赖包
3. 依赖包保持最小集合（轻盾定位）

## 任务内容

### 1. requirements.txt

列出项目必需的 Python 依赖，每个依赖注明版本范围和用途：

```
# === 核心依赖 ===
python-nmap>=0.7.0,<1.0        # Nmap Python 封装
PyYAML>=6.0                     # YAML 配置文件解析

# === Web 扫描（自研，依赖少）===
requests>=2.28.0,<3.0           # HTTP 请求库
beautifulsoup4>=4.11.0,<5.0    # HTML 解析

# === 报告生成 ===
markdown>=3.4.0                 # Markdown 报告渲染

# === Web 界面（v0.2.0+）===
# flask>=3.0.0                   # Flask Web 框架（注释掉，v0.1.0 不需要）

# === 桌面界面（v0.3.0+）===
# 使用内置 Tkinter，无需额外依赖
```

### 2. .gitignore

排除以下内容：
- `__pycache__/`, `*.pyc`, `*.pyo`
- `.venv/`, `venv/`, `env/`
- `logs/`, `reports/` （运行时生成）
- `*.log`
- IDE 配置: `.vscode/`, `.idea/`
- OS 文件: `.DS_Store`, `Thumbs.db`
- MSF 相关: `msf_cache/`, `.msf4/`
- 敏感信息: `*.key`, `*.pem`, `*.p12`, `*.pfx`
- 本地配置: `lightshield.local.yaml`
- 测试缓存: `.pytest_cache/`, `.coverage`

### 3. __init__.py 文件

创建以下包初始化文件：

```
lightshield/__init__.py          # 顶层包：版本号 + 包说明
lightshield/adapters/__init__.py  # 适配器子包
lightshield/scanners/__init__.py  # 扫描器子包
lightshield/rules/__init__.py     # 规则引擎子包
lightshield/harden/__init__.py    # 加固子包
lightshield/report/__init__.py    # 报告子包
lightshield/utils/__init__.py     # 工具子包
```

每个 `__init__.py` 需要：
- 模块级 docstring（中文说明该包的用途）
- `__all__` 导出列表（预留给后续模块）

`lightshield/__init__.py` 额外需要：
```python
"""
LightShield 轻盾 — 轻量化安全自检 + 防御加固工具
"""

__version__ = "0.1.0"
__author__ = "LightShield Team"
__license__ = "MIT"
```

### 4. 目录结构确认

确保以下目录存在（创建 `.gitkeep` 占位）：
- `lightshield/harden/templates/`
- `tests/`
- `docs/`
- `scripts/`

### 代码要求

- 所有 `__init__.py` 包含中文 docstring
- `.gitignore` 使用中文注释说明每个排除项的用途
- `requirements.txt` 使用中文注释
