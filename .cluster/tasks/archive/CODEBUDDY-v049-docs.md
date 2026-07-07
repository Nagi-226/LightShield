# CODEBUDDY-v049-docs：v0.0.49 合规审计文档全套

> **【CodeBuddy 模式：A · IDE 手动（文档需视觉审查）】**
> **【模型切换：GLM-5.2（744B MoE，1M 上下文——一次装载全项目 + 全部文档）】**
> **【下发 Agent：Claude Code】**
> **【关联里程碑：v0.0.49 合规审计】**

---

## ⚠️ 核心约束摘要（≤5 条，不可被上下文稀释覆盖）

| # | 约束 | 违反后果 |
|---|------|---------|
| 1 | 所有文档使用**中文**（项目面向中文开发者），关键术语保留英文原名 | 目标用户无法阅读 |
| 2 | 不修改任何 `.py` 源码（文档任务 ≠ 代码任务） | 引入未审查的代码变更 |
| 3 | pyproject.toml 仅补全元数据字段，不修改依赖版本号 | 破坏现有构建 |
| 4 | SECURITY.md 必须写清**漏洞报告流程 + 响应时间承诺 + PGP 公钥**（安全工具项目标配） | 安全研究者无法报告漏洞 |
| 5 | 文档变更后必须验证 `docs/` 目录下所有 `.md` 文件无死链 | 用户点击 404 |

---

## ⚠️ 提问姿态约束（来自注意力机制原理）

**本任务禁止的指令方式**：

| ❌ 禁止 | ✅ 必须 |
|--------|--------|
| "README 写得不错" | "对照开源社区最佳实践，README 缺少哪些关键章节？" |
| "这个安装说明够详细了" | "分别以新手和运维的视角走一遍安装流程，有哪些步骤会让用户卡住？" |
| "pyproject.toml 元数据都填了" | "以 PyPI 审核员的视角，逐一检查哪些字段缺失或不规范？" |

---

## 一、项目上下文（简短）

LightShield 轻盾 — 开源轻量化安全自检 + 防御加固工具，基于 Python 3.10+ / MIT 协议。当前 v0.0.48（996 tests / 覆盖率 ~82.7% / 0C/0H/0M），目标是持续迭代完善直至 v1.0.0 正式版发布。

v1.0.0 远期里程碑意味着项目向公众正式开放、接受外部贡献、可能发布到 PyPI。文档必须达到开源社区标配水平。

---

## 二、⚠️ 合规约束片段（必读）

| 红线 | 本任务相关？ | 具体要求 |
|:--:|:--:|------|
| R1 | 否 | — |
| R2 | 否 | — |
| R3 | 否 | — |
| R4 | 否 | — |
| R5 | 否 | — |
| R6 | 否 | — |

---

## 三、任务详情

### 3.1 文档交付清单

#### 🆕 新建文档（当前缺失）

| 文件 | 必要原因 | 内容要点 |
|------|------|------|
| **SECURITY.md** | GitHub 安全工具项目标配——安全研究者需要知道如何报告漏洞 | 漏洞报告渠道（邮箱/PGP）、响应时间承诺（如 48h 确认 / 90d 修复）、范围说明、赏金政策（如有） |
| **CODE_OF_CONDUCT.md** | 接受外部贡献的先决条件 | 采用 Contributor Covenant 2.1 标准模板 + LightShield 社群特定规则（不接受攻击代码相关 PR） |
| **CONTRIBUTING.md** | 降低外部贡献门槛 | 开发环境搭建、代码规范（ruff/mypy/bandit）、PR 流程、测试要求、Commit 规范 |

#### 📝 审查+增强已有文档

| 文件 | 当前状态 | 审查重点 |
|------|:--:|------|
| **README.md** | 134 行，基础骨架 | 补全：徽章（tests/coverage/python）、安装方式（pip vs 源码）、快速开始（3 步）、功能矩阵表、致谢 |
| **INSTALL.md** | 162 行 | 验证所有依赖版本号与实际一致、补充 Windows 已知问题、Docker 备选方案突出 |
| **USAGE.md** | 173 行 | 按场景组织（首次扫描 / 加固 / Web 面板 / 定时任务）、加实际输出示例 |
| **FAQ.md** | 71 行 | 补充：跨平台差异、常见报错及解决、安全疑虑解答 |
| **CHANGELOG.md** | 现有到 v0.0.44 | 回填 v0.0.45 + v0.0.46 |
| **docs/API.md** | 8 端点已有 | 补充请求/响应示例、错误码完整表 |

#### 🔧 pyproject.toml 最终化

```toml
# 当前缺/待确认的字段
[project]
name = "lightshield"  # ✅ 已有
version = "0.0.46"    # ✅ 已有（但需确认与 __init__.py 一致）
authors = []           # ❌ 缺——填 [{name = "Nagi_226", email = "..."}]
description = ""       # ❌ 缺——填一句定位
readme = ""            # ❌ 缺——填 "README.md"
license = ""           # ❌ 缺——填 {text = "MIT"}
requires-python = ""   # ❌ 缺——填 ">=3.10"
classifiers = []       # ❌ 缺——PyPI trove classifiers
urls = {}              # ❌ 缺——Homepage/Repository/Issues

[project.scripts]      # 确认 CLI 入口点
lightshield = "lightshield.cli:main"
```

**笔记**：pyproject.toml 的 `version` 字段需要从当前源码中的 `0.0.46` 读取并保持一致。如果源码中是另一个值，保持源码不变，只在此任务中记录给 CC 处理。

---

## 四、代码要求（文档类调整）

- [ ] 所有文档中文为主，关键术语（MIT/SQLite/Flask/Python）保留英文
- [ ] Markdown 格式规范（标题层级、代码块语言标注、表格对齐）
- [ ] 内链使用相对路径，外链使用完整 URL
- [ ] 图片/截图路径确保存在（如 `docs/images/`）
- [ ] SECURITY.md 中的联系方式必须真实可用

---

## 五、验收清单

> **Agent 注意**：此清单即子目标列表。每完成一项打勾，完成前不扩展新目标（防 Subgoal Displacement）。

- [ ] SECURITY.md 新建完成
- [ ] CODE_OF_CONDUCT.md 新建完成
- [ ] CONTRIBUTING.md 新建完成
- [ ] README.md 审查增强完成
- [ ] INSTALL.md 审查更新完成
- [ ] USAGE.md 审查更新完成
- [ ] FAQ.md 审查更新完成
- [ ] CHANGELOG.md v0.0.45 + v0.0.46 回填
- [ ] docs/API.md 补充请求/响应示例 + 错误码表
- [ ] pyproject.toml 元数据补全
- [ ] 🆕 全部文档死链检查通过（`grep -r "](.*\.md)" docs/` 验证所有内链目标存在）
- [ ] 🆕 Goal Drift 自检通过（对照 AGENT_CODE_OF_CONDUCT.md §8.4）

---

## 六、不确定性声明

| 判断 | 置信度 | 替代方案 | 待确认点 |
|------|:--:|------|------|
| GLM-5.2 的 1M 上下文可一次装载全项目文档做一致性检查 | 🟢 | — | — |
| pyproject.toml 的 authors.email 需要向 CC 确认实际邮箱 | 🟡 | 使用 GitHub 主页链接代替 | Nagi_226 的公开邮箱 |
| SECURITY.md 的响应时间承诺（48h/90d）是建议值 | 🟡 | 可根据维护者实际可用时间调整 | — |

---

## 七、关联资源

- 当前版本：v0.0.46（commit: `2d41a15`）
- 已有文档：README.md, INSTALL.md, USAGE.md, FAQ.md, CHANGELOG.md, docs/API.md
- 配置：pyproject.toml, CLAUDE.md
- 护栏：.guardrails/AGENT_CODE_OF_CONDUCT.md, .guardrails/QUALITY_GATES.md
