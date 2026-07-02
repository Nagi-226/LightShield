# 贡献指南 / Contributing

> 感谢你对 LightShield 轻盾的兴趣！本文档说明如何参与项目开发。

LightShield 是一个开源安全自检 + 防御加固工具，欢迎社区贡献。作为安全工具项目，我们对代码质量和合规性有较高要求——请仔细阅读本指南。

---

## 开发环境搭建

### 系统要求

| 组件 | 版本 | 说明 |
|------|------|------|
| Python | 3.10+ | 核心运行环境 |
| Git | 最新版 | 版本控制 |
| Nmap | 7.x+ | 端口扫描引擎（运行时依赖，非开发必需） |
| Docker | 可选 | 沙箱执行器测试需要（`lightshield/sandbox/`） |

### 一次性搭建

```bash
# 1. Fork 仓库后在本地克隆
git clone https://github.com/<你的用户名>/lightshield.git
cd lightshield

# 2. 添加上游仓库
git remote add upstream https://github.com/Nagi-226/LightShield.git

# 3. 创建虚拟环境（推荐）
python -m venv .venv
# Linux / macOS
source .venv/bin/activate
# Windows
.venv\Scripts\activate

# 4. 安装开发依赖（含测试 / lint / 类型检查 / 安全扫描工具）
pip install -e ".[dev]"

# 5. 安装 pre-commit 钩子
pre-commit install

# 6. 验证安装
lightshield version
pytest --version
ruff --version
mypy --version
bandit --version
```

### 验证基线

```bash
# 运行全量测试（应在 30-90 秒内完成，0 失败）
pytest

# 检查覆盖率
pytest --cov=lightshield --cov-report=term

# 代码风格检查（应零违规）
ruff check lightshield/ tests/

# 类型检查（应零错误）
mypy lightshield/

# 安全扫描（应零违规）
bandit -r lightshield/
```

---

## 代码规范

### 风格

LightShield 使用以下工具链保证代码一致性，配置见 `pyproject.toml`：

| 工具 | 用途 | 触发方式 |
|------|------|---------|
| `ruff` | 格式 + lint + import 排序 + 命名规范 | `pre-commit run --all-files` |
| `mypy` | 静态类型检查 | `mypy lightshield/` |
| `bandit` | 安全漏洞扫描 | `bandit -r lightshield/` |
| `pytest` | 单元测试 | `pytest` |

### 注释与文档

- **中文注释为主**，关键术语保留英文（如 CVE / OWASP / exploit）
- 所有公开类和函数使用 **Google 风格 docstring**
- 每个模块包含模块级 docstring，说明职责和用法
- 安全关键代码在注释中标注对应的合规红线（如 `# R5 白名单防线`）

### 类型标注

- 所有函数签名使用 type hints（`def foo(x: int) -> str:`）
- 使用现代语法：`list[str]` 而非 `List[str]`，`str | None` 而非 `Optional[str]`
- `pyproject.toml` 中 `target-version = "py310"`

### 示例

```python
def validate_target(target: str) -> tuple[bool, str]:
    """校验扫描目标合法性（合规 R2 防线）。

    Args:
        target: 待校验的目标 IP / 域名

    Returns:
        (是否合法, 原因说明) 元组

    Raises:
        TypeError: target 非 str 类型时
    """
    if not isinstance(target, str):
        raise TypeError(f"target 必须为 str，实得 {type(target).__name__}")
    # ... 校验逻辑
```

---

## PR 流程

### 提交前：先开 Issue 讨论

对于**非琐碎改动**（新增功能 / 重构 / 接口变更），请先在 [GitHub Issues](https://github.com/Nagi-226/LightShield/issues) 开 issue 说明意图，避免重复工作或方向偏差。

**琐碎改动**（typo / 文档修正 / 明显 bug 修复）可直接提 PR。

### 分支策略

```bash
# 从最新的 main 创建 feature 分支
git checkout main
git pull upstream main
git checkout -b feature/your-feature-name

# 命名约定：
# feature/xxx  — 新功能
# fix/xxx      — bug 修复
# docs/xxx     — 文档
# refactor/xxx — 重构（无行为变更）
```

### 开发周期

1. **编写代码** + **同步编写测试**（TDD 鼓励但不强制）
2. **本地验证**：`pytest` + `ruff check` + `mypy` + `bandit` 全绿
3. **Commit**：遵循下方 commit 规范
4. **Rebase**：保持分支与 main 同步
5. **Push** 到你的 fork
6. **提交 PR** 到 `LightShield/lightshield:main`

### PR 检查清单

提交 PR 前自检：

- [ ] **测试通过**：`pytest` 全绿，且新增了对应测试
- [ ] **覆盖率不降**：`pytest --cov` 覆盖率不低于 main 分支基线
- [ ] **lint 零违规**：`ruff check` + `mypy` + `bandit` 全零
- [ ] **无攻击代码**：不包含 exploit / payload / 后门（合规 R1）
- [ ] **合规红线未绕过**：R1-R6 校验逻辑未被削弱
- [ ] **文档同步**：若改动接口，已同步更新 `docs/API.md` / `README.md`
- [ ] **CHANGELOG**：在 `CHANGELOG.md` 的 `[Unreleased]` 段补充条目
- [ ] **Commit 规范**：遵循下方格式

### 审查流程

1. **自动检查**：CI 跑测试 + lint + 类型检查 + 安全扫描
2. **人工审查**：维护者审查代码质量、架构一致性、合规性
3. **安全审查**（涉及合规红线的改动）：架构审查 + 合规审查双签
4. **合并**：Squash merge（保留 PR 标题作为 commit message）

---

## Commit 规范

### 格式

```
v0.0.XX: 中文简述

[可选] 详细说明，每行 ≤72 字符

[可选] 关联 issue: #123
```

### 示例

```
v0.0.46: HTTP 响应头安全检测规则实现

- engine.py 新增 _match_header 方法，支持检测缺失的安全头
  (X-Frame-Options / X-Content-Type-Options / Strict-Transport-Security)
- vuln_rules.json 新增 8 条 header 匹配规则
- 补充 12 条单元测试覆盖匹配逻辑

关联 issue: #45
```

### 约定

- **版本号**：commit message 开头标注影响的版本号（如 `v0.0.46:`）
- **简述**：中文，祈使句（"新增"/"修复"/"重构"），≤50 字符
- **详细说明**：与简述空一行，每行 ≤72 字符，说明"做了什么"和"为什么"
- **关联**：末尾标注关联的 issue / PR 编号

---

## 合规约束（强制）

### 禁止的提交

以下提交将被**直接拒绝**，严重者可能被封禁：

- 包含 exploit / payload / shellcode / 后门代码
- 绕过合规红线（R1-R6）的功能
- 将 LightShield 用于攻击非自有资产的"功能增强"
- 在公开 PR / Issue 中暴露安全漏洞细节（应走 [SECURITY.md](./SECURITY.md) 私密渠道）

### 合规红线 R1-R6

所有贡献者须理解并遵守项目的 6 条合规红线（详见 [CLAUDE.md](./CLAUDE.md) §五）：

| 红线 | 内容 |
|:--:|------|
| R1 | 禁止对外主动攻击 |
| R2 | 禁止批量扫描公网 IP（只接受单 IP/域名） |
| R3 | 禁止远控/后门/木马 |
| R4 | 仅自查自有资产 |
| R5 | MSF 调用仅限 `auxiliary/scanner/*` |
| R6 | 扫描并发 ≤20，间隔 ≥5s |

涉及合规红线的改动须在 PR 描述中说明**如何保持合规**。

---

## 测试要求

### 覆盖率基线

- 当前基线：**79%**（`pyproject.toml` 中 `fail_under = 60`，实际目标 ≥79%）
- 新增代码须有对应测试，不允许降低整体覆盖率
- 安全关键模块（`validator.py` / `msf_adapter.py` / `sandbox/`）目标覆盖率 ≥90%

### 测试风格

- 使用 `pytest` 风格（函数名 `test_` 开头）
- 中文注释说明测试意图
- 使用 `parametrize` 减少重复
- 外部依赖（Nmap / Docker / MSF）须 mock，不在 CI 中跑真实集成测试

### 示例

```python
import pytest
from lightshield.utils.validator import TargetValidator


class TestTargetValidator:
    """TargetValidator 合规 R2 校验测试。"""

    @pytest.mark.parametrize("target,expected", [
        ("192.168.1.1", True),    # 合法单 IPv4
        ("10.0.0.1", True),       # 内网 IP
        ("example.com", True),    # 合法域名
        ("localhost", True),      # localhost
        ("192.168.1.0/24", False),  # CIDR 必须拒绝
        ("*.example.com", False),   # 通配符必须拒绝
    ])
    def test_validate(self, target: str, expected: bool):
        """参数化校验各类输入。"""
        is_valid, _ = TargetValidator.validate(target)
        assert is_valid == expected
```

---

## 文档贡献

文档贡献同样欢迎！包括但不限于：

- **用户文档**：`README.md` / `docs/INSTALL.md` / `docs/USAGE.md` / `docs/FAQ.md`
- **API 文档**：`docs/API.md` / `lightshield/web/static/openapi.json`
- **架构文档**：`CLAUDE.md` / `PROJECT_OVERVIEW.md` / `docs/adr-*.md`
- **国际化**：`lightshield/web/locales/{zh-CN,en-US}.json`（中英键集须对称）

文档改动不需要跑测试，但须保证：

- 内链无死链（相对路径正确）
- 中文为主，术语保留英文
- Markdown 格式规范（标题层级 / 表格 / 代码块语言标注）

---

## 获取帮助

- 📖 [使用手册](docs/USAGE.md)
- ❓ [常见问题](docs/FAQ.md)
- 🐛 [GitHub Issues](https://github.com/Nagi-226/LightShield/issues) — 提问 / 报 bug
- 💬 [GitHub Discussions](https://github.com/Nagi-226/LightShield/discussions) — 讨论功能想法
- 🔒 [安全漏洞](SECURITY.md) — 私密报告（**勿在 Issues 中公开**）

---

## 致谢

感谢每一位为 LightShield 贡献代码、文档、issue 和反馈的贡献者。你的参与让这个工具更好。

贡献者名单维护在 [README.md](./README.md#致谢) 的致谢章节（v1.0.0 正式版发布时补全）。

---

## 版本

- **本指南版本**：v1.0
- **生效日期**：2026-07-02
- **最后更新**：2026-07-02
