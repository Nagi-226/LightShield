# LightShield 轻盾

> 开源轻量化安全自检 + 防御加固工具

<p align="left">
  <a href="./LICENSE"><img src="https://img.shields.io/badge/License-MIT-blue.svg" alt="License: MIT"></a>
  <a href="https://www.python.org/downloads/"><img src="https://img.shields.io/badge/Python-3.10+-brightgreen.svg" alt="Python 3.10+"></a>
  <a href="https://github.com/LightShield/lightshield"><img src="https://img.shields.io/badge/Version-0.2.0-orange.svg" alt="Version 0.2.0"></a>
  <a href="https://nmap.org/"><img src="https://img.shields.io/badge/Nmap-7.x+-blueviolet.svg" alt="Nmap 7.x+"></a>
</p>

LightShield（轻盾）是一款面向开发者和运维人员的**轻量级安全自检工具**。它不依赖商业安全平台或云端服务，只需一条命令即可对自有资产完成端口扫描、服务识别、漏洞检测和加固建议生成 —— 全程离线运行。

**核心设计理念：轻量、可控、可审计。** 无论是个人开发者检查自己的服务器，还是团队在 CI/CD 流程中嵌入安全自检关卡，LightShield 都能以极低的门槛提供有价值的安全基线反馈。

---

## 核心特性

- **🔍 资产扫描** — 自动探测开放端口、运行服务、操作系统指纹（基于 Nmap）
- **⚠️ 漏洞检测** — Web 漏洞扫描、弱口令检测、组件/依赖安全检查
- **📄 中文报告** — 自动生成 Markdown / Text 格式的详细安全报告
- **🛡️ 加固脚本生成** — 根据扫描结果自动生成加固脚本和回滚脚本
- **💻 跨平台** — 支持 Linux（CentOS/Ubuntu/Debian）和 Windows（10+/Server 2016+）
- **✅ 合规自查** — 内置所有权确认机制（R4），仅允许扫描自有资产

---

## 快速开始

### 1. 安装

```bash
# Linux
git clone https://github.com/LightShield/lightshield.git
cd lightshield
pip install -r requirements.txt
pip install -e .
```

```powershell
# Windows（管理员）
git clone https://github.com/LightShield/lightshield.git
cd lightshield
pip install -r requirements.txt
pip install -e .
```

> 详细安装说明请参见 [安装指南](docs/INSTALL.md)。

### 2. 扫描

```bash
lightshield scan 127.0.0.1 --confirm-ownership
```

首次使用需要确认目标所有权（输入 `YES`），也可以通过 `--confirm-ownership` 参数跳过交互确认。

### 3. 查看报告

扫描完成后，报告默认保存在 `./reports/` 目录下，格式为 Markdown。

---

## 命令参考

| 命令 | 功能 | 示例 |
|------|------|------|
| `scan` | 全量扫描（资产 + 漏洞 + 报告） | `lightshield scan 192.168.1.1 --confirm-ownership` |
| `quick-scan` | 快速扫描（Top 100 端口） | `lightshield quick-scan 127.0.0.1 --confirm-ownership` |
| `harden` | 扫描 + 加固脚本生成 | `lightshield harden 192.168.1.1 --confirm-ownership` |
| `version` | 查看版本号 | `lightshield version` |

### 通用参数

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `--output-format` | 报告格式：`markdown` / `text` | `markdown` |
| `--output-dir` | 输出目录 | `./reports` |
| `--confirm-ownership` | 确认目标所有权 | 否（需交互确认） |
| `--timeout` | 超时时间（秒） | `60` |
| `--verbose` | 输出详细日志 | 否 |

---

## 安装方法

- 📖 [安装指南](docs/INSTALL.md) — 环境要求、Linux / Windows 部署步骤、常见安装问题
- 🚀 一键部署脚本：`scripts/deploy_linux.sh`（Linux）、`scripts/deploy_win.ps1`（Windows）

---

## 使用文档

- 📖 [使用手册](docs/USAGE.md) — 命令详解、扫描参数、报告解读、加固脚本使用

---

## 常见问题

- ❓ [常见问题](docs/FAQ.md) — 权限要求、与 Nmap 的关系、操作系统兼容性等

---

## 项目架构

```
LightShield/
├── lightshield/          # 核心 Python 包
│   ├── cli.py            # 命令行入口（4 子命令）
│   ├── core.py           # 核心调度器（扫描编排+加固编排）
│   ├── config.py         # 配置管理（YAML/JSON + 环境变量覆盖）
│   ├── adapters/         # 扫描适配器（Nmap/MSF/自研引擎）
│   ├── scanners/         # 漏洞扫描器（Web漏洞/弱口令/组件）
│   ├── rules/            # 规则引擎（14条漏洞规则 + 6条加固规则）
│   ├── harden/           # 加固脚本生成器（Linux .sh / Windows .ps1）
│   ├── report/           # 中文报告生成（Markdown / Text）
│   └── utils/            # 工具函数（校验/日志/常量）
├── scripts/              # 一键部署脚本
├── tests/                # 单元测试（441 项，零失败）
├── docs/                 # 用户文档
├── LICENSE               # MIT 许可证
└── README.md             # 本文件

> 完整架构分层图及设计决策参见 [CLAUDE.md](./CLAUDE.md)。

---

## 许可证

[MIT License](./LICENSE) — Copyright (c) 2026 LightShield Team

本工具仅用于自有资产安全自查，**禁止**用于未授权的非法扫描。使用者须自行承担一切法律责任。
