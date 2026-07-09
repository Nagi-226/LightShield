# ADR-v052：R2 合规红线重定义 — 从单目标到多目标资产清单

> **状态**：✅ Accepted
> **日期**：2026-07-09
> **决策者**：Claude Code（架构 + 安全终审）
> **前置依赖**：`adr-v052-offline-definition.md` ✅ Accepted — 本 ADR 的资产来源假设基于其约束框架
> **关联**：`.guardrails/PROGRESS.md`（v0.0.57 资产清单、v0.0.61+ 批量扫描）、`lightshield/utils/validator.py`（当前 R2 实现）
> **类型**：合规红线重定义 → 范围漂移阀值「架构模式改变→🟠 暂停+ADR」强制立项

---

## 1. 背景（Context）

### 1.1 当前 R2 定义及其局限

CLAUDE.md §五 定义的 R2：

> | R2 | 禁止批量扫描公网 IP 段 | 输入校验层：只接受单一 IP 或域名，拒绝 CIDR/网段/通配符 |

当前实现（`lightshield/utils/validator.py`）严格执行此定义：

```python
# validator.py:102 — 仅接受单 IP、单域名、localhost
def validate(target: str) -> tuple[bool, str]:
    # 拒绝: CIDR, IP range(1.1.1.1-1.1.1.10), wildcard(*.example.com), URL
```

此定义在 v0.0.10 MVP 阶段是合理的——一个最小安全自检工具只需要扫一台机器。但随着功能增长，其局限已经显现：

| 局限 | 影响 | 用户真实需求 |
|------|------|------|
| 扫 5 台内网机器需手动跑 5 次命令 | UX 差，容易漏 | 一次命令扫全部自有资产 |
| 无法对比同一资产历次扫描变化 | 安全趋势不可见 | 知道"上次扫是 3 个高危，这次是 0" |
| 资产没有持久化标识 | 每次 CLI 传 IP 字符串，无法关联历史 | 给资产起名、分组、追踪 |

### 1.2 为什么现在必须定

1. **v0.0.57 资产清单（AssetRegistry）** 需要定义资产的数据模型——如果 R2 不先明确"什么是合法的多目标"，AssetRegistry 的设计就没有合规约束
2. **v0.0.61+ 批量扫描** 是用户最期待的功能之一，但它是 R2 重定义后的**实现**而非 ADR 本身
3. **offline-definition ADR** 已经给出了约束框架：资产清单默认本地文件，远程 CMDB 需 opt-in。R2 需要在此框架下细化执行规则

### 1.3 当前扫描流程中的 R2 位置

```
CLI target ──→ TargetValidator.validate(target) ──→ [拒绝] 返回 R2 违规
                         │
                     [通过：单 IP/域名]
                         │
                         ▼
              core.run_scan(target) ──→ 逐个适配器扫描 ──→ ScanResult
                         │
                     [单目标，同步]
```

**问题**：整个 core 是为单目标设计的。`run_scan(target: str)` 的参数签名就是单字符串。要支持多目标，不仅 validator 要改——core、CLI、Web API、报告、闭环都要知道"这是一批资产的一部分"。

---

## 2. 决策（Decision）

**R2 从"禁止批量扫描公网 IP 段"重定义为三层边界模型：单个目标格式（不变）、资产清单来源（新增）、批量执行约束（新增）。**

### 2.1 新 R2 三层边界

```
Layer 1: 目标格式（不变，收紧）
  → 单个目标仍然是 IP/域名/localhost，拒绝 CIDR/网段/通配符/URL
  → 这是永久底线——无论输入方式如何，每个被扫描的原子目标必须合法

Layer 2: 资产来源（新增）
  → 资产清单从哪来？本地文件（默认） / 远程 CMDB（opt-in）
  → 远程 CMDB 需独立 flag（--asset-source-url）+ R4 所有权确认
  → 资产清单本身不执行扫描——只是"允许扫描的目标列表"

Layer 3: 批量执行（新增，v0.0.61+ 实现）
  → 对资产清单中的目标逐个串行扫描
  → 每个目标独立过 R2 Layer 1 格式校验 + R4 所有权确认
  → R6 频率限制从"单目标扫描并发 ≤20"扩展为"目标间间隔 ≥5s × N_adapter"
```

### 2.2 永远禁止（不变）

| 禁止项 | 原因 | 检测方式 |
|------|------|------|
| CIDR 网段（`192.168.1.0/24`） | 无法逐一确认所有权，等同批量扫公网 | `ipaddress.ip_network()` 检测 |
| IP 范围（`1.1.1.1-1.1.1.10`） | 同上 | 正则检测 |
| 通配符域名（`*.example.com`） | 同上 | `*` 字符检测 |
| 公网随机地址 | 用户可能输入不属于自己的地址 | 无技术检测——由 R4 所有权确认兜底 |
| 从远程 CMDB 无确认批量导入 | 绕过所有权验证 | `--asset-source-url` 必须配 `--confirm-ownership` |

### 2.3 资产清单格式（v0.0.57 定义，v0.0.61+ 使用）

```json
{
  "version": 1,
  "generated_by": "LightShield AssetRegistry v0.0.57",
  "updated_at": "2026-07-09T12:00:00Z",
  "assets": [
    {
      "id": "asset-001",
      "name": "生产 Web 服务器",
      "target": "192.168.1.10",
      "type": "ip",
      "groups": ["production", "web"],
      "last_scanned": "2026-07-08T10:00:00Z",
      "ownership_confirmed": true
    },
    {
      "id": "asset-002",
      "name": "开发数据库",
      "target": "db-dev.internal",
      "type": "domain",
      "groups": ["development", "database"],
      "ownership_confirmed": true
    }
  ]
}
```

**关键设计决策**：
- `target` 字段必须通过 R2 Layer 1 格式校验（单 IP/域名/localhost）
- `ownership_confirmed` 是资产级标记——每个资产独立确认所有权
- `groups` 支持分组批量操作（`lightshield scan --group production`）
- `id` 是持久化标识——同一资产多次扫描结果通过 `id` 关联，实现对比报告

### 2.4 所有权确认（R4）在多目标场景下的扩展

| 场景 | 确认方式 | 审计日志 |
|------|------|------|
| CLI 单目标（现有） | `--confirm-ownership` flag 或交互输入 YES | `ownership_confirmed` + target |
| CLI 资产清单文件 | `--confirm-ownership` 确认"我拥有此清单中全部资产的所有权" | `ownership_confirmed_batch` + asset_ids[] |
| CLI 远程 CMDB | `--asset-source-url https://...` + `--confirm-ownership` 双 flag | `ownership_confirmed_remote` + source_url + asset_count |
| Web API | 通过 API 提交时传 `confirm_ownership: true`（同现有模式） | 按请求记录 |

**原则**：所有权确认的最小粒度是"资产清单"，不是"资产清单中的每个 IP"。如果用户在清单里混入了不属于自己的资产，责任在用户——LightShield 无法也不可能验证 IP 归属。这与现有单目标 R4 的逻辑一致：传了 `--confirm-ownership` = 用户声明拥有目标，工具不验证。

> ⚠️ **风险量级差异**：单目标确认时用户看清一个 IP 再确认；100 个资产的清单中混入 1 个非自有资产，用户很难逐条审核。建议 v0.0.57 实现时提供 `--assets-file --dry-run` 预览清单内容（目标列表 + 分组 + 所有权标记），用户人工确认后再正式执行。

### 2.5 CLI 接口设计（v0.0.61+ 实现）

```bash
# 单目标（不变）
lightshield scan 192.168.1.1 --confirm-ownership

# 资产清单文件（v0.0.61+）
lightshield scan --assets-file ./my-assets.json --confirm-ownership

# 按分组扫描（v0.0.61+）
lightshield scan --assets-file ./my-assets.json --group production --confirm-ownership

# 远程 CMDB（v0.0.61+，需同时传 --confirm-ownership）
lightshield scan --asset-source-url https://cmdb.internal/api/assets --confirm-ownership

# 逗号分隔的临时列表（v0.0.61+，仅限内网 IP）
lightshield scan --targets 192.168.1.1,192.168.1.2,192.168.1.3 --confirm-ownership
```

**强制约束**：
- `--asset-source-url` 必须与 `--confirm-ownership` 同时传入，否则拒绝
- `--targets` 逗号列表仅接受内网 IPv4 地址（`is_private_ip()`），拒绝公网 IP 和内网域名。内网域名（如 `db-dev.internal`）不是 IP 格式，无法用 `is_private_ip()` 判定归属——需要域名支持时使用 `--assets-file`，由资产清单逐条管理所有权
- `--assets-file` 接受文件路径（本地），不做网络请求

### 2.6 R6 频率限制在多目标场景下的扩展

| 维度 | 单目标（现有） | 多目标（v0.0.61+） |
|------|:--:|:--:|
| 适配器并发 | ≤ 20 | ≤ 20（不变——每个目标内的适配器并发） |
| 目标间间隔 | 不适用 | ≥ 5s × active_adapter_count（给前一个目标的网络连接留足关闭时间） |
| 总目标数上限 | 1 | ≤ 100（一次性扫描上限，防止无界执行。依据：目标用户典型场景 5-20 台内网机器，100 是 5 倍安全冗余——足够覆盖固定资产清单 + 临时设备，同时防止误传千级目标导致扫描无限运行） |
| 公网目标限制 | 无（单目标已由 R4 覆盖） | `--targets` 仅接受内网 IP；公网目标只能通过资产清单文件逐条确认 |

### 2.7 实现阶段划分

```
v0.0.52 (本 ADR):        R2 边界定义 Accepted
v0.0.57 (AssetRegistry):  数据模型落地——asset 表/id/分组/ownership_confirmed
                           不执行批量扫描，仅单目标 + 资产入库
v0.0.61+ (批量执行):       --assets-file / --targets / --group 接线
                           core.run_scan_multi() 串行编排
                           远程 CMDB（--asset-source-url）实现
```

**为什么 v0.0.57 先做数据模型但不做批量扫描？**
- 即使只有单目标扫描，用户也希望"扫描结果持久化、历史可查、同一资产多次扫描可对比"——这是 v0.0.57 的价值
- 批量扫描的执行编排（串行/并发策略、失败重试、部分成功汇总）复杂度高，不应在 v0.0.52-57 这个版本窗口内追加

**批量扫描的失败策略（v0.0.61+ 实现时遵守）**：
- 单目标失败（任何原因：R2 校验不通过 / 网络不可达 / 扫描超时）**不中断后续目标**——记录失败原因到该 asset 的 `last_scan_error` 字段，继续下一个
- 最终汇总报告列出：成功 N / 失败 M / 跳过 K（所有权标记为 false 的跳过），每个失败目标附原因
- 提前终止的唯一条件：用户按 Ctrl+C 或进程收到 SIGTERM

---

## 3. 被否决的备选（Alternatives Considered）

| 方案 | 内容 | 否决理由 |
|------|------|---------|
| **B：保持单目标，永远不做多目标** | R2 不变，用户自己写 shell 脚本循环调用 CLI | ①需要对比报告的开发工作量转移到用户侧；②Web 仪表板的资产视图失去意义（永远只有 1 个 target）；③与"面向初创企业&个人站长"的定位不符——他们的典型场景是 5-20 台内网机器 |
| **C：放开 CIDR 为合法输入** | 允许 `lightshield scan 192.168.1.0/24` | ①无法逐 IP 确认所有权（R4 失效）；②即使用户确认"我拥有整个 C 段"，也无法保证 C 段内 254 个 IP 中每一个都属于用户（DHCP 分配的设备可能不属于用户管理范围）；③公网 CIDR 段几乎不可能被单一用户全量拥有 |
| **D：远程 CMDB 作默认资产源** | 资产清单默认从远程拉取 | 违反 offline-definition ADR 铁律 1（默认零出站）；资产清单是核心扫描流程的前置条件→必须本地优先 |

---

## 4. 后果（Consequences）

### 4.1 正面

- ✅ **R2 从"一个否定句"变成"三层可执行规则"**——当前 R2 只说了不准做什么，本 ADR 定义了可以做什么以及怎么做
- ✅ **v0.0.57 AssetRegistry 获得合规约束**——数据模型设计时就知道 `target` 字段必须过 Layer 1 校验
- ✅ **用户获得多资产管理能力**——分组、历史对比、批量扫描，不牺牲合规
- ✅ **与 offline-definition ADR 一致**——资产源默认本地，远程 opt-in
- ✅ **向后兼容**——单目标 CLI 调用不改一行

### 4.2 代价

- ⚠️ **validator.py 需重构**——从"拒绝一切非单目标"变为"Layer 1 格式校验 + Layer 2 来源校验 + Layer 3 执行参数校验"，预计 +40-60 行
- ⚠️ **core.py 需新增 `run_scan_multi()`**——串行编排 + 部分失败汇总 + 批量审计日志，预计 +80-120 行（v0.0.61+ 实现）
- ⚠️ **增加实现复杂度**——资产清单文件格式、分组语义、目标间间隔计算、100 上限，都是新概念
- ⚠️ **`--targets` 仅限内网** 是一个可能引起用户疑惑的限制——需在文档中解释原因

### 4.3 对下游版本和 ADR 的约束

| 下游 | 本决策给出的约束 |
|------|------|
| v0.0.57 AssetRegistry | asset 表结构：`id`/`name`/`target`(经 Layer 1 校验)/`type`/`groups`/`ownership_confirmed`/`last_scanned`。`target` 写入前必须过 `TargetValidator.validate()` |
| v0.0.61+ 批量扫描 | 基于 asset 表实现。`--targets` 仅限内网 IP。`--asset-source-url` 需双 flag |
| 未来的 `adr-v052-wsgi-migration.md` | Web API 的 `/api/scan` 端点需支持 `assets_file` 参数（与单 `target` 互斥）。多目标扫描通过 Web API 提交时返回 `task_ids[]` |

---

## 5. 合规映射（R1–R6）

| 红线 | 本决策落地方式 |
|:--:|------|
| R1 禁攻击 | 不受影响（攻击性 payload 不由目标数量决定） |
| **R2 禁批量扫公网** | **重定义**：三层边界（格式→来源→执行）。CIDR/网段/通配符永久禁止。`--targets` 仅限内网 IP。公网目标必须通过资产清单逐条确认 |
| R3 禁远控后门 | 不受影响 |
| R4 仅自查自有 | 资产级 `ownership_confirmed` 标记。清单级确认（"我拥有全部资产"） |
| R5 MSF 白名单 | 不受影响（MSF 适配器白名单不因目标数量改变） |
| R6 频率限制 | 扩展：适配器并发 ≤20（不变）+ 目标间间隔 ≥5s × N_adapter + 一次性总目标 ≤100 |

---

## 6. 验收标准

1. R2 新定义在 `CLAUDE.md` §五 中更新（从"禁止批量扫描公网 IP 段"→三层边界摘要）
2. `TargetValidator.validate()` 保留 Layer 1 格式校验逻辑不变
3. v0.0.57 AssetRegistry 的 asset 表 `target` 字段写入前调用 `TargetValidator.validate()`
4. `--targets` 逗号列表参数实现后，公网 IP 输入 → 拒绝并提示"仅限内网 IP"
5. `--asset-source-url` 不与 `--confirm-ownership` 同时传入 → 拒绝
6. 全量回归测试通过（Layer 1 行为不变 → 现有 test_validator.py 零回归）

---

## 7. 修订记录

| 日期 | 修订 | 作者 |
|------|------|------|
| 2026-07-09 | 初稿（基于 offline-definition ADR §4.3 约束框架） | Claude Code |
| 2026-07-09 | 二审修订：§2.4 补批量所有权确认风险提示 + dry-run 建议 / §2.5 明确 `--targets` 不含内网域名 / §2.6 补 100 上限依据 / §2.7 补批量扫描失败策略 | Claude Code（基于项目所有者审查反馈） |

---

> 本 ADR 由 Claude Code 起草，接受 `adr-v052-offline-definition.md`（✅ Accepted）§4.3 约束：资产清单默认本地文件，远程 CMDB 需 opt-in + `--confirm-ownership` 双 flag。下一份 ADR `adr-v052-wsgi-migration.md` 在 R2 约束下补充 Web API 的多目标端点设计。
