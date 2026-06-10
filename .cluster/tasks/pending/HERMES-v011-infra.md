你是 LightShield 项目的工具链+基础设施专家，使用 DeepSeek-V4-flash 模型。

## 项目背景
LightShield v0.1.0 MVP 已完成（14 个 Python 模块），v0.0.11 正在添加 CLI 入口。
需要你为项目创建现代化的 Python 打包配置和更新依赖清单。

## 任务A：创建 pyproject.toml

在项目根目录创建 `pyproject.toml`，包含：

```toml
[build-system]
requires = ["setuptools>=68.0", "wheel"]
build-backend = "setuptools.backends._legacy:_Backend"

[project]
name = "lightshield"
version = "0.1.0"
description = "轻盾 — 面向初创企业和个人站长的开源轻量化安全自检+防御加固工具"
readme = "README.md"
license = {text = "MIT"}
authors = [
    {name = "LightShield Team"}
]
keywords = ["security", "vulnerability-scanner", "hardening", "cybersecurity", "self-check"]
classifiers = [
    "Development Status :: 4 - Beta",
    "Environment :: Console",
    "Intended Audience :: System Administrators",
    "License :: OSI Approved :: MIT License",
    "Operating System :: POSIX :: Linux",
    "Operating System :: Microsoft :: Windows",
    "Programming Language :: Python :: 3.10",
    "Programming Language :: Python :: 3.11",
    "Programming Language :: Python :: 3.12",
    "Topic :: Security",
    "Topic :: System :: Networking :: Monitoring",
]
requires-python = ">=3.10"
dependencies = [
    "PyYAML>=6.0",
    "requests>=2.28.0,<3.0",
    "beautifulsoup4>=4.11.0,<5.0",
    "markdown>=3.4.0",
]

[project.optional-dependencies]
nmap = ["python-nmap>=0.7.0,<1.0"]
dev = [
    "pytest>=7.0",
    "pytest-cov>=4.0",
    "ruff>=0.1.0",
]

[project.scripts]
lightshield = "lightshield.cli:main"

[project.urls]
Homepage = "https://github.com/lightshield/lightshield"
Documentation = "https://github.com/lightshield/lightshield/blob/main/README.md"
Repository = "https://github.com/lightshield/lightshield.git"
Issues = "https://github.com/lightshield/lightshield/issues"

[tool.setuptools.packages.find]
include = ["lightshield*"]

[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = ["test_*.py"]
addopts = "-v --tb=short"

[tool.ruff]
line-length = 120
target-version = "py310"

[tool.ruff.lint]
select = ["E", "F", "W", "I", "N"]
ignore = ["E501"]
```

## 任务B：更新 requirements.txt

当前 requirements.txt 缺少实际使用的依赖。扫描 lightshield/ 下所有 .py 文件的 import 语句，补充缺失的依赖：

已有：
- python-nmap, PyYAML, requests, beautifulsoup4, markdown

需要确认是否缺少：
- 所有 import 都是标准库或已在 requirements.txt 中

requirements.txt 格式（中文注释每个依赖的用途）：
```
# === LightShield 轻盾 — Python 依赖 ===
# 目标部署包 <= 500MB

# 核心依赖
PyYAML>=6.0                    # YAML 配置文件解析

# HTTP 客户端（Web 漏洞检测、组件版本检查）
requests>=2.28.0,<3.0          # HTTP 请求库
beautifulsoup4>=4.11.0,<5.0   # HTML 解析（可选，降级到正则）

# 报告生成
markdown>=3.4.0                # Markdown 报告渲染

# Nmap 集成（可选）
# python-nmap>=0.7.0,<1.0     # 取消注释以启用 Python Nmap 封装
```

## 任务C：更新 lightshield/__init__.py 的 __all__

```python
__all__ = ["core", "config", "adapters", "scanners", "rules", "report", "utils", "cli"]
```
加入 cli（Codex 正在开发，预留）。

## 代码规范
- 所有注释用中文
- TOML 格式注意缩进和引号
- requirements.txt 每个依赖一行，不要多余空行

## 输出
1. pyproject.toml
2. requirements.txt（覆盖更新）
3. lightshield/__init__.py（更新 __all__）
