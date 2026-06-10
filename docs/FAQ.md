# 常见问题

> LightShield 轻盾 — 开源轻量化安全自检 + 防御加固工具

---

### Q1: LightShield 和 Nmap 的关系？

LightShield 底层使用 Nmap 进行端口扫描和服务识别，但 LightShield **不是 Nmap 的替代品**。

- **Nmap** 是一个功能强大的网络探测工具，适合专业安全人员使用
- **LightShield** 在 Nmap 的基础上封装了**一站式安全自检工作流**：端口扫描完成后自动触发漏洞检测、规则匹配、加固建议生成和中文报告输出

简单来说，LightShield 让"跑一遍安全检查"这件事从**手动组合多个工具**变成了**一条命令**。

**场景对比：**

| 步骤 | 手动方式 | LightShield |
|------|---------|-------------|
| 端口扫描 | `nmap -sV -O 目标IP` | `lightshield scan 目标IP --confirm-ownership` |
| 漏洞检测 | 手动跑 SQLMap / XSS 测试 / 弱口令字典 | 自动运行（3 类检测器） |
| 风险分析 | 人工对照 CVE 数据库 | 规则引擎 14 条规则自动匹配 |
| 加固建议 | 手动编写 iptables / sshd 配置 | 自动生成 .sh / .ps1 加固脚本 + 回滚脚本 |
| 报告 | 手动整理 | 一条命令生成 Markdown 中文报告 |

---

### Q2: 扫描需要什么权限？

- **Linux**：部分扫描需要 root 权限（如 OS 探测、SYN 扫描），建议使用 `sudo` 运行
- **Windows**：需要以管理员身份运行（一键部署脚本会自动检测）

扫描**本机**（`127.0.0.1`）通常不需要额外权限，但 OS 指纹识别等功能仍可能需要管理员权限。

---

### Q3: 加固脚本可以自动执行吗？

**不可以。** 这是主要的安全设计原则。

加固脚本（`lightshield harden` 生成的 `.sh` / `.ps1` 文件）**不会自动执行**。LightShield 的设计哲学是"建议不代劳"——由安全工具生成建议，由运维人员审阅执行。

每次执行 `harden` 命令时会输出明确警告：
```
⚠️ 请审阅加固脚本后再手动执行。脚本运行时会再次确认所有权。
```

**执行加固脚本示例：**

```bash
# 1. 生成加固脚本
lightshield harden 192.168.1.1 --confirm-ownership

# 2. 审阅脚本内容
cat ./reports/harden_192_168_1_1_*.sh

# 3. 确认无误后手动执行（脚本内含 R4 所有权二次确认）
bash ./reports/harden_192_168_1_1_*.sh

# 4. 如需回滚
bash ./reports/rollback_192_168_1_1_*.sh
```

---

### Q4: 支持哪些操作系统？

| 系统 | 扫描 | 加固脚本生成 | 一键部署 |
|------|------|-------------|----------|
| Linux (CentOS 7+ / Ubuntu 18.04+ / Debian 10+) | ✅ | ✅ `.sh` | ✅ `deploy_linux.sh` |
| Windows (10+ / Server 2016+) | ✅ | ✅ `.ps1` | ✅ `deploy_win.ps1` |
| macOS | 手动安装 Python+Nmap 后可用 | ❌ 暂未适配 | ❌ |

> macOS 用户可以通过 `pip install -e .` 手动安装并使用扫描功能。加固脚本生成目前仅支持 Linux (.sh) 和 Windows (.ps1)，macOS 适配计划在 v0.3.0 中评估。

---

### Q5: 发现了漏洞但不知道怎么修复？

LightShield 在扫描报告中已经包含了针对每项风险的加固建议。如果报告中的建议不能满足你的需求，可以：

1. **运行 `lightshield harden`** 生成可执行的加固脚本，脚本中包含了详细的修复步骤
2. **查看报告中的"加固建议"章节**，每项风险都有对应的缓解措施说明
3. **参考社区文档** — 报告中的建议基于 NIST / OWASP 等标准安全实践

如果仍然不确定，建议咨询专业安全团队，或在测试环境中先验证加固脚本的效果。

**获取帮助的渠道：**
- 📖 阅读 [使用手册](USAGE.md) 了解命令详情
- 🐛 在 [GitHub Issues](https://github.com/LightShield/lightshield/issues) 报告问题或提问
- 📄 查看 [CHANGELOG.md](../CHANGELOG.md) 了解最新变更
- 🔧 报告中的加固建议基于 OWASP / NIST 标准安全实践，每项风险均有中文说明

---

> 📖 详细使用说明请参见 [使用手册](USAGE.md)。
> 📖 安装指南请参见 [INSTALL.md](INSTALL.md)。
