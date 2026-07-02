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

> macOS 用户可以通过 `pip install -e .` 手动安装并使用扫描功能。加固脚本生成目前仅支持 Linux (.sh) 和 Windows (.ps1)，macOS 适配计划在 v0.0.30 中评估。

---

### Q5: 发现了漏洞但不知道怎么修复？

LightShield 在扫描报告中已经包含了针对每项风险的加固建议。如果报告中的建议不能满足你的需求，可以：

1. **运行 `lightshield harden`** 生成可执行的加固脚本，脚本中包含了详细的修复步骤
2. **查看报告中的"加固建议"章节**，每项风险都有对应的缓解措施说明
3. **参考社区文档** — 报告中的建议基于 NIST / OWASP 等标准安全实践

如果仍然不确定，建议咨询专业安全团队，或在测试环境中先验证加固脚本的效果。

**获取帮助的渠道：**
- 📖 阅读 [使用手册](USAGE.md) 了解命令详情
- 🐛 在 [GitHub Issues](https://github.com/Nagi-226/LightShield/issues) 报告问题或提问
- 📄 查看 [CHANGELOG.md](../CHANGELOG.md) 了解最新变更
- 🔧 报告中的加固建议基于 OWASP / NIST 标准安全实践，每项风险均有中文说明

---

### Q6: Web 仪表板和 CLI 有什么区别？

v0.0.30 新增 Web 仪表板，提供图形化操作界面，与 CLI 互补而非替代。

| 维度 | CLI | Web 仪表板 |
|------|-----|-----------|
| 使用方式 | 终端命令行 | 浏览器 `http://127.0.0.1:5000` |
| 依赖 | 无额外依赖 | 需安装 `lightshield[web]`（Flask + 前端） |
| 适用场景 | 批量扫描 / 脚本集成 / SSH 远程 | 交互式浏览 / 可视化报告 / 快速操作 |
| 扫描能力 | 完全一致（底层调用同一引擎） | 完全一致（调用同一引擎） |
| 报告阅读 | Markdown 文件手动翻阅 | 浏览器直接查看，含历史切换 |
| 加固脚本 | 命令行生成 + 手动执行 | 网页生成 + 下载后手动执行 |

**建议：** 日常排查用 Web 仪表板，自动化 / CI 集成用 CLI。

---

### Q7: Web 仪表板可以部署到公网吗？

**不推荐直接暴露公网。** 当前 Web 仪表板设计为本地运维工具，面向内网/本机使用。

注意事项：

1. **默认绑定 127.0.0.1** — `lightshield serve` 仅监听本地回环地址，外部无法访问
2. **基础鉴权** — 使用 Session + 登录密码保护，但未实现 HTTPS / 令牌 / OAuth
3. **CSRF 防护** — 自研 CSRF 模块（`secrets.compare_digest` 时序安全 + X-CSRF-Token header 双通道），防止跨站请求伪造
4. **无速率限制** — 登录接口未做暴力破解防护 <!-- TODO：v0.3.x 计划添加 -->

**安全部署建议（如需远程访问）：**
- 使用反向代理（Nginx / Caddy）添加 HTTPS + 访问控制
- 通过 SSH 隧道转发（`ssh -L 5000:127.0.0.1:5000 user@server`）
- 不要在公网直接暴露 Flask 开发服务器

---

### Q8: 在 Web 仪表板中点击加固会直接执行脚本吗？

**不会。** 与 CLI 的 `lightshield harden` 行为一致，Web 仪表板中的加固功能也遵循"建议不代劳"原则。

在 Web 仪表板中：
- 扫描报告底部展示加固建议列表
- 每条建议包含风险等级和修复说明
- 加固脚本以**文件下载**形式提供给用户
- 用户需要自行审阅脚本内容，确认后在目标机器上手动执行

这一设计确保运维人员始终掌握对系统变更的最终控制权。回滚脚本同样通过下载提供。

---

### Q9: Linux 和 Windows 上的加固脚本有什么差异？

LightShield 会根据 `--os-platform` 参数（或自动检测）生成对应平台的脚本：

| 维度 | Linux (`.sh`) | Windows (`.ps1`) |
|------|------|------|
| 防火墙 | `iptables -A INPUT -p tcp --dport <port> -j DROP` | `netsh advfirewall firewall add rule name="..." dir=in action=block protocol=TCP localport=<port>` |
| 服务管理 | `systemctl stop <service> && systemctl disable <service>` | `Set-Service -Name <service> -StartupType Disabled; Stop-Service -Name <service>` |
| SSH 加固 | `sed -i` 修改 `sshd_config` | 不适用（Windows 使用 OpenSSH，配置路径不同） |
| 回滚方式 | `iptables -D` + `systemctl start` + `sed` 还原 | `netsh delete rule` + `Set-Service -StartupType Automatic; Start-Service` |
| 执行权限 | `chmod +x` + `./script.sh` 或 `bash script.sh` | PowerShell 以管理员身份运行：`.\script.ps1` |

**注意**：脚本生成时需要指定正确的平台，否则生成的命令在错误平台上无法执行：

```bash
# Linux 目标
lightshield harden 192.168.1.1 --os-platform linux --confirm-ownership

# Windows 目标
lightshield harden 192.168.1.1 --os-platform windows --confirm-ownership
```

---

### Q10: 扫描报错 "Nmap 未安装或路径错误"怎么办？

**原因**：LightShield 通过 `subprocess` 调用 `nmap` 命令，Nmap 不在 PATH 中。

**排查步骤**：

```bash
# 1. 检查 nmap 是否安装
nmap --version

# 2. 若未安装：
# Linux
sudo apt install nmap        # Ubuntu/Debian
sudo yum install nmap        # CentOS/RHEL
# Windows: 从 https://nmap.org/download.html 下载安装

# 3. 若已安装但不在 PATH：
# 临时指定路径
lightshield scan 127.0.0.1 --confirm-ownership  # 默认从 PATH 找 nmap
# 或通过环境变量
export NMAP_PATH=/usr/local/bin/nmap    # Linux
$env:NMAP_PATH="C:\Program Files (x86)\Nmap\nmap.exe"   # Windows

# 4. Docker 环境：使用官方镜像（已含 Nmap）
docker compose up -d
```

---

### Q11: 报错 "R2 违规: 拒绝 CIDR 网段"但我的目标是合法的？

**原因**：LightShield 的合规红线 R2 **只接受单一 IP 或域名**，拒绝以下格式：

| 被拒绝的格式 | 示例 | 原因 |
|------|------|------|
| CIDR 网段 | `192.168.1.0/24` | 批量扫描公网段 |
| IP 范围 | `192.168.1.1-192.168.1.10` | 批量扫描 |
| IP 缩写范围 | `192.168.1.1-10` | 批量扫描 |
| 通配符域名 | `*.example.com` | 批量扫描 |
| URL 格式 | `http://example.com` | 应输入域名 `example.com` |
| 带端口 | `example.com:443` | 应输入域名 `example.com` |
| 带路径 | `example.com/admin` | 应输入域名 `example.com` |

**正确用法**：

```bash
# 单 IP
lightshield scan 192.168.1.1 --confirm-ownership

# 单域名
lightshield scan example.com --confirm-ownership

# localhost
lightshield scan localhost --confirm-ownership

# IPv6
lightshield scan ::1 --confirm-ownership
lightshield scan fe80::1 --confirm-ownership
```

如需扫描多个目标，请**逐个执行**命令——这是合规设计，不是 bug。

---

### Q12: Docker 中扫描为什么无法做 OS 探测？

**原因**：Nmap 的 OS 指纹探测（`-O`）需要原始套接字权限，Docker 容器默认不开启。

**表现**：

- 扫描报告中 `操作系统` 字段显示 `未知`
- 详细日志（`--verbose`）中看到 `WARNING: OS didn't match` 或 `WARNING: too few fingerprints`

**解决方案**：

| 方案 | 命令 | 适合场景 |
|------|------|------|
| 宿主机直接扫描（推荐） | 在宿主机安装 LightShield 后扫描 | 生产环境 |
| Docker 特权容器 | `docker run --privileged ...` | 仅测试环境，**不推荐**（安全风险） |
| 跳过 OS 探测 | `--scan-types port_scan,service_detect` | 不需要 OS 信息时 |

---

### Q13: 加固脚本执行后提示 "所有权未确认"怎么办？

**原因**：加固脚本内置 R4 所有权确认门（`read -r -p "..."`），需要输入 `yes` 才会继续。

**场景一：手动执行脚本**

```bash
bash ./reports/harden_192_168_1_1_*.sh
# 脚本会提示：
# 请确认你拥有目标 192.168.1.1 的所有权（输入 yes 继续）：
# 输入 yes 后回车
```

**场景二：在 CI/CD 中自动执行**

```bash
# 通过管道自动应答（仅限已通过 CLI --confirm-ownership 的场景）
echo "yes" | bash ./reports/harden_192_168_1_1_*.sh
```

⚠️ **安全提示**：自动应答会绕过交互式所有权确认。请确保 CI/CD 环境中的目标是自有资产，且脚本已审阅。

**场景三：自动加固闭环（v0.0.40+）**

```bash
# DRY_RUN 模式（预检，不改系统）
lightshield harden 127.0.0.1 --closed-loop --confirm-ownership

# APPLY 模式（真机执行，会改真实系统）
lightshield harden 127.0.0.1 --closed-loop --apply --confirm-ownership
```

APPLY 模式下，CLI 会要求输入 `EXECUTE` 二次确认，然后自动应答脚本内的 R4 门。

---

### Q14: Web 仪表板登录后立即被登出？

**可能原因与解决方案**：

| 原因 | 表现 | 解决方案 |
|------|------|------|
| Session 过期（8 小时） | 登录后过一段时间操作被踢出 | 重新登录 |
| Cookie 被浏览器拦截 | 登录成功但页面不跳转 | 检查浏览器是否禁用了 Cookie；允许 127.0.0.1 的 Cookie |
| 反向代理未传递 Cookie | Nginx 后登录失败 | 配置 `proxy_pass_header Set-Cookie;` |
| 多个标签页登录冲突 | A 标签登录后 B 标签失效 | 同一浏览器同一时间只用一个标签 |
| CSRF Token 过期 | 提交扫描时 403 | 刷新页面重新获取 CSRF Token |

---

> 📖 详细使用说明请参见 [使用手册](USAGE.md)。
> 📖 安装指南请参见 [INSTALL.md](INSTALL.md)。
