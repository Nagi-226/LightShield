# 安全策略 / Security Policy

> LightShield 轻盾 — 开源轻量化安全自检 + 防御加固工具

LightShield 是一个**安全工具**——它自身也应当以最严苛的安全标准被审视和维护。本文档说明 LightShield 项目安全漏洞的报告流程与响应承诺。

---

## 报告范围

### 包含

LightShield **自身代码**的安全漏洞，包括但不限于：

- 命令注入 / 路径遍历 / SSRF 等代码执行类漏洞
- 认证/鉴权绕过（Web 仪表板的 Session / CSRF / 速率限制）
- 合规红线（R1-R6）被绕过的可能路径
- 依赖项中的已知 CVE（仅指影响 LightShield 运行时的依赖）
- 信息泄露（日志中输出敏感数据、报告包含未脱敏凭证等）

### 不包含

以下情况**不在 LightShield 安全响应范围内**，请勿通过本渠道报告：

- LightShield **检测的目标系统**的漏洞（LightShield 是自检工具，被扫描的目标漏洞请向目标系统管理员报告）
- 使用 LightShield 对**非自有资产**进行扫描的法律/道德问题（违反 R4 红线，非安全漏洞）
- 第三方工具（Nmap / Metasploit / Nuclei）自身的漏洞——请向对应项目报告
- 社区使用中的配置问题或误用——请在 [GitHub Issues](https://github.com/Nagi-226/LightShield/issues) 提交普通 issue

---

## 报告渠道

### 首选渠道：GitHub 私密报告

1. 前往 [LightShield Security Advisories](https://github.com/Nagi-226/LightShield/security/advisories/new)
2. 点击 **"Report a vulnerability"**
3. 填写漏洞描述、复现步骤、影响范围

### 备选渠道：邮箱

若 GitHub 私密报告不可用，发送加密邮件至：

```
security [at] lightshield [dot] dev
```

> **PGP 公钥**：[待发布]（v1.0.0 正式版发布前补全。当前阶段请使用 GitHub 私密报告渠道。）

---

## 报告内容要求

为帮助我们快速响应，请在报告中包含：

- [ ] **漏洞描述**：清晰说明漏洞类型和影响
- [ ] **复现步骤**：可独立复现的最小步骤（命令 / 代码 / 配置）
- [ ] **影响范围**：受影响的版本、模块、配置项
- [ ] **PoC（可选但强烈推荐）**：证明漏洞可利用的最小示例
- [ ] **建议修复方案**（可选）：你认为合理的修复方向

---

## 响应承诺

| 阶段 | 承诺 | 说明 |
|------|------|------|
| **确认收到** | **48 小时内** | 收到报告后 48 小时内回复确认（GitHub 私密报告自动通知 + 人工回复） |
| **初步评估** | 7 天内 | 给出漏洞等级初评（Critical/High/Medium/Low）和是否接受 |
| **修复开发** | 视等级而定 | Critical ≤ 7 天 / High ≤ 30 天 / Medium ≤ 90 天 / Low 下个版本 |
| **修复发布** | 修复完成后 3 天内 | 发布修复版本 + Security Advisory + CHANGELOG 同步 |
| **公开披露** | 修复发布后 **90 天内** | 默认 90 天后公开披露（或与报告者协商更早/更晚） |

> 若报告者要求更长的保密期，我们尊重并配合。若 90 天到期仍未修复，我们将在披露前 7 天通知报告者。

---

## 漏洞等级标准

| 等级 | 标准 | LightShield 特化示例 |
|------|------|------|
| **Critical** | 远程代码执行 / 合规红线完全绕过 | MSF 白名单（R5）被绕过可调用 exploit 模块；Web 鉴权完全绕过 |
| **High** | 权限提升 / 敏感数据泄露 / 合规红线部分绕过 | 命令注入可执行任意命令；扫描结果含未脱敏凭证 |
| **Medium** | 拒绝服务 / 信息泄露（非敏感） / 配置不当默认值 | 速率限制可被绕过导致 API 滥用；CSRF 防护失效 |
| **Low** | 最佳实践偏离 / 防御纵深不足 | 日志未完全脱敏；错误信息包含过多内部细节 |

---

## 合规与免责

- LightShield 遵循**负责任的披露**原则
- 我们不会对善意的安全研究采取法律行动（前提是：不破坏数据、不影响服务可用性、不在修复前公开披露）
- 报告者的身份默认保密，除非报告者本人要求公开致谢
- 安全修复版本发布后，我们会在 CHANGELOG 和 GitHub Security Advisories 中致谢报告者（如报告者同意）

---

## 依赖漏洞（供应链安全）

LightShield 的运行时依赖（`requests` / `PyYAML` / `beautifulsoup4`）及可选依赖（`Flask` / `fpdf2`）若出现已知 CVE：

1. 请通过上述渠道报告
2. 我们会在 7 天内评估 CVE 是否影响 LightShield 运行时
3. 若影响 → 按上述响应承诺升级依赖版本
4. 若不影响（如受影响 API 未被 LightShield 使用）→ 在 SECURITY.md 记录评估结论

---

## 版本

- **本策略版本**：v1.0
- **生效日期**：2026-07-02
- **最后更新**：2026-07-02

> 本安全策略基于 [GitHub SECURITY.md 标准](https://docs.github.com/en/code-security/security-advisories/guidance-on-reporting-and-writing-information-about-vulnerabilities/privately-reporting-a-security-vulnerability) 和 [RFC 9116](https://www.rfc-editor.org/rfc/rfc9116) 制定。
