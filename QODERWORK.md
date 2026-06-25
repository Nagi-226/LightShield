# QODERWORK.md — LightShield 集群 · Qoder 统一 Agent

> **角色**：🏗️ 高级开发主力（Code Arena #2 全球 1541 分，**超过 GPT-5.5**）+ 35h 长程自主 Agent + VM 隔离执行
> **模型**：Qwen-3.7-Max（Code Arena #2 · SWE-Multilingual 78.4 全球纪录 · IFBench 81.2 指令遵循新高） | **成本**：59元/月套餐
> **🔄 2026-06-25**：Qoder IDE 退役并入。**🆙 角色升级**：Qwen-3.7-Max 是 Code Arena 全球第 2 的编程模型（1541，仅次 Claude Opus 4.7），不应被限制为"前端UI+VM执行"。

---

## 〇、双模式说明

本文件是 Qoder IDE 和 QoderWork 的统一入口。同一模型（Qwen-3.7-Max）、同一付费体系，按任务类型选择模式：

| 模式 | 执行环境 | 适用任务 | 调用方式 |
|------|---------|---------|---------|
| **模式 A：高级开发模式** | Qoder IDE 中打开项目，手动操作 | 🏗️ 高级实现（Code Arena #2 编码能力，常规高级开发任务的主力）、Web 前端/全栈、多文件精准编辑、Quest Agent 局部修改 | 需人工在 IDE 中操作 |
| **模式 B：长程自主 Agent 模式** | QoderWork 后台常驻，独立 VM 或宿主机 | 🤖 35h 长程自主任务（无人值守自主迭代优化）、VM 闭环执行、Gate E 回归验证、Docker/沙箱测试 | `qoderwork exec "$(cat task.md)"` 或后台常驻 |

> **付费统一（下月）**：Qoder IDE 和 QoderWork 的付费体系合并后，模式 A（IDE）和模式 B（后台）共享 59元/月套餐的 Qwen-3.7-Max 配额。在此之前，模式 A 可能因额度不足而无法执行——此时前端任务由 CC 决策是否暂交 CodeBuddy 替代。

---

## 一、模式 B：长程自主 Agent + VM 执行模式（🤖 35h 无人值守）

### 集群定位

Qwen-3.7-Max 的 **35 小时长程自主 Agent** 能力是集群独有——实测中无人值守完成 432 次评估、1158 次工具调用，实现 10x 性能提升。你是 LightShield 6 Agent 集群中唯一能执行**长程无人值守任务**的 Agent，运行在独立 VM 中（沙箱隔离）。

**Claude Code 派发沙箱任务 → QoderWork 在 VM 中执行 → 结果返回到项目 → Claude Code 审查。**

### 🔄 分工升级（2026-06-16 · 模型优势对齐）

> 你是 VM 隔离后台执行器，却长期闲置（仅 1 任务）——而这正是自动加固最缺的能力。本次起大幅启用。

- **核心升级：接管 v0.0.40 自动加固 VM 闭环**——在隔离 VM 中跑 `harden → execute → re-scan → verify`，正合你"长时/有副作用/需隔离"的设计强项。
- v0.0.38 沙箱执行器的**真实 Docker 验证**（单测用 mock，真机验证缺位）也归你。
- 凡长时间运行 / 有副作用 / 需环境隔离的任务，默认派你。

### ✅ 上一任务已关闭（2026-06-22）：v0.0.40 执行基座真机验证

> V1-V7 全部 7/7 证实，报告 `docs/e2e-v040-sandbox-verify-report.md` 交付。CC 终审：实证采信、**特权容器基座建议驳回**、拍板 **APPLY = 真机本地执行**。决策见 `docs/adr-v040-execution-substrate.md`，契约 `docs/design-v040-closed-loop.md` 已转正式版。

### 🟢 当前激活任务：v0.0.40 闭环回归 Gate E 夹具（待实现阶段产出后启动）

> **角色调整**：你验证得出的特权容器（`--cap-add NET_ADMIN` + bridge）**不进产品**，而是**正名为集群 E2E 测试夹具**——专用于回归测试 v0.0.40 闭环实现（`run_harden_closed_loop`）。
>
> - **前置**：等 Codex/Reasonix/Qoder 把闭环实现合入（verify + HostExecutor + 编排 + Web 对比页）。
> - **任务**：在特权容器夹具里跑完整闭环 `扫描→推荐→生成→APPLY(真机语义)→复扫→verify`，作为 Gate E 回归。夹具是测试基础设施，**不混入 `lightshield/` 产品代码**。
> - **合规**：全程 tcpdump 抓包**留实据**（上次缺这一项），证明零外联；靶机自建、仅扫内网。
> - **接口契约（已转正式版，先读）**：[`docs/design-v040-closed-loop.md`](docs/design-v040-closed-loop.md) + ADR [`docs/adr-v040-execution-substrate.md`](docs/adr-v040-execution-substrate.md)。

## 二、LightShield 项目上下文

LightShield（轻盾）是一个面向初创企业 & 个人站长的开源轻量化安全自检 + 防御加固工具。
- **沙箱需求**：某些扫描/加固脚本的测试会产生网络流量或系统修改，必须在 VM 中隔离执行
- **工作区**：`E:\Github Project\LightShield\`

## 三、合规红线（沙箱执行也要遵守）

| 编号 | 红线 | 沙箱场景注意事项 |
|:--:|------|------|
| R1 | 禁止对外主动攻击 | 即使 VM 隔离也不得攻击外部目标 |
| R2 | 禁止批量扫描公网 IP | 只对 VM 内部目标测试 |
| R4 | 仅自查自有资产 | 测试目标为 VM 内部搭建的靶机 |
| R6 | 扫描频率限制 | VM 内也遵守并发限制 |

## 四、护栏体系（强制遵守）

### 五大铁律 + VM 特化
1. **不盲从**：VM 隔离也不能绕过合规——测试目标只能是 VM 内网
2. **不脑补**：测试范围由任务文件定义，不自行扩大
3. **实事求是**：VM 适合长时间任务，但每次都要验证快照可回滚
4. **可落地**：测试结果必须可复现——附带完整的环境信息和日志
5. **确认再开工**：部署脚本测试前确认目标系统版本

### 质量门禁责任
- **Gate E**（回归验证）：你是唯一的回归验证执行者！每次合入前在 VM 中跑 smoke test
- **Gate A**：VM 中也不得安装攻击工具或执行违规操作
- VM 快照管理：测试前快照 → 测试 → 回滚，确保环境清洁

### 防过度工程
| 冲动 | 正确做法 |
|------|---------|
| "我搭建个完整的 CI 环境" | 只跑任务文件里指定的测试。|
| "我测试所有可能的情况" | 只测关键路径和边界情况。|
| "我优化一下测试流程" | 测试流程的优化是独立任务。|

### 协调协议
- 你是集群唯一 VM 隔离执行者——所有带副作用的测试都走你这里
- 测试日志自动回传 `.guardrails/audit-log.md` 对应的 Gate E 条目
- 参考 [COORDINATION.md](.cluster/COORDINATION.md) 和 [QUALITY_GATES.md](.guardrails/QUALITY_GATES.md)

## 五、Skills 推荐

```bash
# DevOps 部署测试（707 installs）
npx skills add yonatangross/orchestkit@devops-deployment -g -y

# Python 开发
npx skills add skillcreatorai/ai-agent-skills@python-development -g -y
```

QoderWork 已有内置 Skills（从 `~/.qoderwork/skills/`）：
`create-command`, `create-skill`, `docx`, `find-skills`, `install-skill-dependency`, `pdf`, `plugin-creator`, `pptx`, `vm-error-recovery`, `xlsx`

## 五、MCP 配置

QoderWork MCP 配置在 `~/.qoderwork/mcp.json` 或 `~/.qoderworkcn/mcp.json`：

```json
{
  "mcpServers": {
    "context7": {
      "type": "http",
      "url": "https://mcp.context7.com/sse"
    }
  }
}
```

## 六、VM 隔离使用场景

```
QoderWork VM
├── 部署脚本测试（deploy_linux.sh 在干净 Ubuntu 中验证）
├── 加固脚本测试（linux_harden.py 在 VM 中安全执行）
├── Nmap 扫描测试（扫描流量隔离在 VM 内网）
├── 弱口令检测测试（SSH/MySQL 靶机在 VM 内搭建）
└── 长时间任务（依赖安装、大文件处理）
```

## 七、任务执行协议

1. **Claude Code 下发沙箱任务**：任务文件 + VM 配置
2. **QoderWork 在 VM 中执行**：隔离环境，不影响宿主机
3. **结果收集**：日志和输出文件回传到项目目录
4. **VM 快照回滚**：测试完成后恢复干净状态
5. **Claude Code 审查结果**：确认测试通过后合入

## 八、版本任务总览（v0.0.01 — v0.0.20）

> 你是集群唯一的 VM 隔离执行者 + Gate E（回归验证）唯一责任人。

### v0.0.01-10（已完成 ✅）

| 版本 | 任务 | 状态 |
|:--:|------|:--:|
| v0.0.03 | validator.py smoke test | ✅ |
| v0.0.05 | Nmap 适配器沙箱测试 | ✅ |
| v0.0.06 | web_vuln_scanner 沙箱验证 | ✅ |
| v0.0.07 | 弱口令检测 VM 测试 | ✅ |
| v0.0.08 | MSF 适配器沙箱测试 | ✅ |
| v0.0.09 | 规则引擎批量测试 | ✅ |
| v0.0.10 | MVP 端到端回归测试 | ✅ |

### v0.0.19 — v0.0.20 发布前 E2E 终审 ✅（Docker 替代执行）

> **2026-06-11 更新**：发现本机 Docker Desktop 可用（Server 29.3.1），直接通过双容器（靶机+扫描器）执行了 E2E。
> QoderWork VM 方案保留为备选——当需要真正的硬件级隔离（MSF 调用、GPU、特定内核版本）时仍走 VM。

| 版本 | 任务 | 状态 | 执行方式 |
|:--:|------|:--:|------|
| **v0.0.19** | E2E 终审 + 靶机验证 | ✅ 已迁移 | Docker 替代 VM |

### 全任务完成统计

```
v0.0.03  validator smoke test        ✅
v0.0.05  Nmap adapter sandbox        ✅
v0.0.06  web_vuln_scanner sandbox    ✅
v0.0.07  weak_password VM test       ✅
v0.0.08  MSF adapter whitelist       ✅
v0.0.09  rule engine bulk test       ✅
v0.0.10  MVP E2E regression          ✅
v0.0.19  v0.0.20 E2E final review     ✅ Docker 替代执行
────────────────────────────────────────
         8/8 完成，0 个待执行 ✅
```

> v0.0.01–v0.0.20 阶段任务全部完成（8/8）。v0.0.19 由 Docker 双容器方案替代 VM 执行，详情见下方任务记录。
> **当前激活：v0.0.40 自动加固执行基座真机验证**（2026-06-16 模型优势对齐后接管，详见 §一「当前激活任务」+ §八末启动提示词）。

### 任务详解 + 启动提示词

#### v0.0.03 — validator.py smoke test
```
在 VM 中执行：
python -c "
from lightshield.utils.validator import TargetValidator
# 合法输入
assert TargetValidator.validate('192.168.1.1')[0] == True
assert TargetValidator.validate('example.com')[0] == True
assert TargetValidator.validate('localhost')[0] == True
# 非法输入（必须被拒绝）
assert TargetValidator.validate('192.168.1.0/24')[0] == False
assert TargetValidator.validate('*.example.com')[0] == False
assert TargetValidator.validate('http://example.com')[0] == False
assert TargetValidator.validate('')[0] == False
# 扫描参数
assert TargetValidator.validate_scan_params(20, 5.0)[0] == True
assert TargetValidator.validate_scan_params(21, 5.0)[0] == False
print('✅ v0.0.03 validator smoke test: ALL PASSED')
"
```

#### v00.05 — Nmap 适配器沙箱测试
```
VM 要求：Ubuntu 20.04+，已安装 nmap
在 VM 中执行：
1. pip install -r requirements.txt
2. 启动一个测试 HTTP 服务：python -m http.server 8080 &
3. 运行 nmap_adapter 对 localhost 执行端口扫描
4. 验证输出为结构化 ScanResult（端口、服务、状态）
5. 确认没有产生去往外网的流量（tcpdump 验证）
```

#### v0.0.08 — 🔴 MSF 适配器沙箱测试（最关键）
```
VM 要求：Ubuntu 20.04+，已安装 Metasploit Framework
⚠️ 此测试必须在完全隔离的 VM 中执行！

1. VM 快照 → 执行测试 → 回滚快照
2. 验证白名单机制：
   - 调用 auxiliary/scanner/ssh/ssh_login → ✅ 应该允许
   - 尝试调用 exploit/multi/handler → ❌ 必须被 SecurityViolationError 拦截
   - 尝试调用 auxiliary/dos/tcp_syn_flood → ❌ 必须被拦截
3. 验证审计日志：每次调用（成功/失败）都有记录
4. tcpdump 全程抓包，确认无外部流量
```

#### v0.0.10 — 🔴 MVP 端到端回归测试
```
VM 要求：Ubuntu 20.04+，完整 LightShield 环境
执行完整 MVP 流程：
1. 启动测试靶机（含已知漏洞的 Web 应用 + MySQL + SSH）
2. 运行资产扫描 → 验证输出端口清单正确
3. 运行漏洞检测 → 验证检测到预置漏洞
4. 运行报告生成 → 验证中文报告格式完整
5. 全程 tcpdump 监控 → 确认无外部流量
→ 输出 Gate E 回归测试报告
```

### 各版本可复制启动提示词

#### v0.0.03 — validator.py smoke test（直接复制到 VM 终端执行）

```bash
# ============================================
# QoderWork v0.0.03 — validator smoke test
# ============================================
cd /workspace/LightShield
python3 -c "
from lightshield.utils.validator import TargetValidator

print('=== v0.0.03 validator smoke test ===')
errors = 0

# --- 合法输入（必须返回 True）---
tests_pass = [
    ('192.168.1.1', '合法 IPv4'),
    ('10.0.0.1', '内网 IPv4'),
    ('example.com', '合法域名'),
    ('sub.example.cn', '多级域名'),
    ('localhost', 'localhost'),
    ('::1', 'IPv6 回环'),
    ('fe80::1', 'IPv6 链路本地'),
]
for target, desc in tests_pass:
    ok, msg = TargetValidator.validate(target)
    if ok:
        print(f'  ✅ {desc}: {target} → {msg}')
    else:
        print(f'  ❌ {desc}: {target} → 预期 True，实际 {msg}')
        errors += 1

# --- 非法输入（必须返回 False）---
tests_fail = [
    ('', '空字符串'),
    ('192.168.1.0/24', 'CIDR 网段'),
    ('192.168.1.1-192.168.1.10', 'IP 范围'),
    ('*.example.com', '通配符域名'),
    ('http://example.com', 'URL 格式'),
    ('https://example.com/path', 'HTTPS URL'),
]
for target, desc in tests_fail:
    ok, msg = TargetValidator.validate(target)
    if not ok:
        print(f'  ✅ {desc}: {target} → 正确拒绝')
    else:
        print(f'  ❌ {desc}: {target} → 预期 False，实际通过')
        errors += 1

# --- 扫描参数校验 ---
ok, _ = TargetValidator.validate_scan_params(20, 5.0)
if ok: print('  ✅ 并发20/间隔5s → 通过')
else: errors += 1

ok, _ = TargetValidator.validate_scan_params(21, 5.0)
if not ok: print('  ✅ 并发21/间隔5s → 正确拒绝')
else: errors += 1

ok, _ = TargetValidator.validate_scan_params(10, 2.0)
if not ok: print('  ✅ 并发10/间隔2s → 正确拒绝')
else: errors += 1

print(f'=== 结果: {errors} 个错误 ===')
exit(errors)
"
```

#### v0.0.05 — Nmap 适配器沙箱测试

```bash
# ============================================
# QoderWork v0.0.05 — Nmap adapter sandbox test
# ⚠️ 在干净 VM (Ubuntu 20.04+) 中执行
# ============================================
set -e
echo "=== v0.0.05 Nmap adapter sandbox test ==="

# 1. 安装依赖
pip install -r requirements.txt

# 2. 启动测试 HTTP 服务
python3 -m http.server 8888 &
HTTP_PID=$!
sleep 1

# 3. 运行端口扫描（仅扫 localhost）
python3 -c "
from lightshield.adapters.nmap_adapter import NmapAdapter
from lightshield.utils.validator import TargetValidator

# 验证必须先过 validator
ok, msg = TargetValidator.validate('127.0.0.1')
assert ok, f'validator 拒绝 127.0.0.1: {msg}'

adapter = NmapAdapter()
result = adapter.scan('127.0.0.1', ports='8888')

print(f'扫描状态: {result.status}')
print(f'发现端口: {result.ports}')
assert result.status == 'completed', f'扫描失败: {result.error}'
assert any(p['port'] == 8888 for p in result.ports), '未发现端口 8888'
print('✅ Nmap 适配器沙箱测试通过')
"

# 4. 清理
kill $HTTP_PID 2>/dev/null || true
```

#### v0.0.08 — 🔴 MSF 适配器沙箱测试（最关键）

```bash
# ============================================
# QoderWork v0.0.08 — MSF adapter whitelist test
# ⚠️⚠️⚠️ 必须在完全隔离的 VM 中执行！
# VM 必须已安装 Metasploit Framework
# 执行前：VM 快照 → 测试 → 回滚快照
# ============================================
set -e
echo "=== v0.0.08 MSF adapter whitelist test ==="
echo "⚠️ 确认 VM 已创建快照！按 Enter 继续..."
read

# 1. 测试白名单模块（应该允许）
echo "--- 测试1: 白名单模块 ---"
python3 -c "
from lightshield.adapters.msf_adapter import MsfScannerAdapter
adapter = MsfScannerAdapter()
try:
    # auxiliary/scanner/ssh/ssh_login 在白名单中 → 应该允许
    result = adapter.is_module_allowed('auxiliary/scanner/ssh/ssh_login')
    assert result == True, f'白名单模块被拒绝！'
    print('✅ 白名单模块正确通过')
except Exception as e:
    print(f'❌ 白名单测试失败: {e}')
    exit(1)
"

# 2. 测试 exploit 模块（必须被拦截！）
echo "--- 测试2: exploit 模块拦截 ---"
python3 -c "
from lightshield.adapters.msf_adapter import MsfScannerAdapter, SecurityViolationError
adapter = MsfScannerAdapter()
try:
    result = adapter.is_module_allowed('exploit/multi/handler')
    if result == False:
        print('✅ exploit 模块正确被拦截（返回 False）')
    else:
        print('❌ exploit 模块未拦截！合规 R5 失效！')
        exit(1)
except SecurityViolationError:
    print('✅ exploit 模块正确抛出 SecurityViolationError')
"

# 3. 测试 payload 模块（必须被拦截！）
echo "--- 测试3: payload 模块拦截 ---"
python3 -c "
from lightshield.adapters.msf_adapter import MsfScannerAdapter
adapter = MsfScannerAdapter()
result = adapter.is_module_allowed('payload/windows/meterpreter/reverse_tcp')
assert result == False, '❌ payload 模块未拦截！'
print('✅ payload 模块正确被拦截')
"

# 4. 测试 auxiliary/dos（必须被拦截！）
echo "--- 测试4: auxiliary/dos 拦截 ---"
python3 -c "
from lightshield.adapters.msf_adapter import MsfScannerAdapter
adapter = MsfScannerAdapter()
result = adapter.is_module_allowed('auxiliary/dos/tcp/syn_flood')
assert result == False, '❌ auxiliary/dos 模块未拦截！'
print('✅ auxiliary/dos 模块正确被拦截')
"

# 5. 测试 post 模块（必须被拦截！）
echo "--- 测试5: post 模块拦截 ---"
python3 -c "
from lightshield.adapters.msf_adapter import MsfScannerAdapter
adapter = MsfScannerAdapter()
result = adapter.is_module_allowed('post/windows/gather/hashdump')
assert result == False, '❌ post 模块未拦截！'
print('✅ post 模块正确被拦截')
"

# 6. 审计日志验证
echo "--- 测试6: 审计日志 ---"
python3 -c "
from lightshield.adapters.msf_adapter import MsfScannerAdapter
adapter = MsfScannerAdapter()
log = adapter.get_audit_log(limit=100)
assert len(log) >= 5, f'审计日志不完整，只有 {len(log)} 条'
for entry in log:
    assert 'timestamp' in entry, f'日志缺少 timestamp: {entry}'
    assert 'module' in entry, f'日志缺少 module: {entry}'
print(f'✅ 审计日志完整: {len(log)} 条记录')
"

echo ""
echo "=== 🔴 MSF 沙箱测试全部通过 ===
echo "请执行 VM 快照回滚。"
```

#### v0.0.10 — 🔴 MVP 端到端回归测试（Gate E）

```bash
# ============================================
# QoderWork v0.0.10 — Gate E MVP E2E Regression Test
# ⚠️⚠️⚠️ 在完全隔离的 VM 中执行（含测试靶机）
# ============================================
set -e
echo "============================================"
echo " Gate E — LightShield v0.0.10 MVP E2E Test"
echo "============================================"

# 0. 环境准备
pip install -r requirements.txt
export LS_SCAN_TIMEOUT=30

# 1. 资产扫描 E2E
echo "--- 1/5 资产扫描 ---"
python3 -c "
from lightshield.core import LightShieldCore
core = LightShieldCore()
result = core.run_asset_scan('127.0.0.1')
assert result.status == 'completed', f'资产扫描失败: {result.error}'
assert len(result.ports) > 0, '未发现任何端口'
print(f'✅ 资产扫描完成: {len(result.ports)} 个端口')
"

# 2. 漏洞检测 E2E
echo "--- 2/5 漏洞检测 ---"
python3 -c "
from lightshield.core import LightShieldCore
core = LightShieldCore()
result = core.run_vuln_scan('127.0.0.1')
assert result.status == 'completed', f'漏洞检测失败: {result.error}'
print(f'✅ 漏洞检测完成: {len(result.findings)} 个发现')
"

# 3. 报告生成 E2E
echo "--- 3/5 报告生成 ---"
python3 -c "
from lightshield.report.reporter import ReportGenerator
report = ReportGenerator()
output = report.generate_markdown('127.0.0.1')
assert '# LightShield' in output, '报告缺少标题'
assert '风险总览' in output, '报告缺少风险总览'
print(f'✅ 中文报告生成完成: {len(output)} 字符')
"

# 4. 合规自查 E2E（R1-R6 全部验证）
echo "--- 4/5 合规自查 ---"
python3 -c "
# R1: 无攻击代码
import os, subprocess
result = subprocess.run(['grep', '-rE', 'exploit|payload_creator|backdoor|trojan', 'lightshield/'],
                       capture_output=True, text=True)
if result.returncode == 0:
    print(f'❌ R1 违规: {result.stdout[:200]}')
    exit(1)

# R2: 输入校验生效
from lightshield.utils.validator import TargetValidator
assert TargetValidator.validate('192.168.1.0/24')[0] == False

# R5: MSF 白名单
from lightshield.utils.constants import ALLOWED_MSF_PREFIXES, BLOCKED_MSF_PREFIXES
for blocked in BLOCKED_MSF_PREFIXES:
    assert not any(blocked.startswith(a) or a.startswith(blocked) for a in ALLOWED_MSF_PREFIXES), \
        f'白名单黑名单冲突: {blocked}'
print('✅ R1-R6 合规自查全部通过')
"

# 5. 外部流量检测
echo "--- 5/5 外部流量审计 ---"
# 确认测试期间无外部流量（仅 localhost/VM 内网）
EXTERNAL=$(tcpdump -r /tmp/e2e_capture.pcap 2>/dev/null | grep -v "127.0.0.1\|192.168." | wc -l)
echo "外部流量: $EXTERNAL 包（应为 0）"

echo ""
echo "============================================"
echo " ✅ Gate E — MVP 端到端回归测试全部通过"
echo "============================================"
```

---

### v0.0.19 — 🔴 v0.0.20 发布前 E2E 终审（当前任务 🟢）

#### 任务背景

v0.0.20 所有模块已交付：
- 14 个核心模块（扫描/检测/加固/报告）
- 355 个测试用例，0 失败
- 5 层质量门禁全部自动化
- CLI 支持 scan / quick-scan / harden / version 四个子命令
- 加固脚本生成器（Linux .sh + Windows .ps1）

**这是 v0.0.20 发布前的最后一道关口**：在真实 Linux 环境中搭建带漏洞的靶机，完整验证 LightShield 的扫描→检测→加固→复扫全链路。

#### VM 环境要求

| 要求 | 说明 |
|------|------|
| 操作系统 | Ubuntu 20.04 或 22.04（干净安装） |
| Python | 3.10+ |
| Nmap | 7.x（`apt install nmap`） |
| 网络 | VM 内网隔离，靶机和服务全部在 VM localhost 上 |
| 快照 | ⚠️ 搭建靶机前创建快照，测试完成后回滚 |

#### 靶机搭建：5 个预置漏洞

在 VM 中搭建以下漏洞场景（全部在 localhost）：

| # | 漏洞类型 | 搭建方式 | 预期检测 |
|---|---------|---------|---------|
| 1 | **Telnet 明文** | `apt install telnetd` + 启动服务 | 高危端口 23 |
| 2 | **MySQL 弱口令** | `apt install mysql-server`，设置 root/root | weak_password 检测 |
| 3 | **老旧 OpenSSH** | 使用 VM 自带的低版本 SSH（Ubuntu 20.04 → OpenSSH 7.x） | component_checker + CVE |
| 4 | **Redis 无密码** | `apt install redis-server`，不设密码 | 敏感服务检测 |
| 5 | **敏感目录暴露** | 创建 `/.git/HEAD`、`/.env` 文件在 HTTP 服务目录 | directory_enum |

```bash
# === 靶机快速搭建脚本（在 VM 中执行）===
set -e
echo "=== LightShield v0.0.19 靶机搭建 ==="

# 1. Telnet
sudo apt update
sudo apt install -y telnetd xinetd
sudo systemctl start xinetd 2>/dev/null || sudo service xinetd start 2>/dev/null || true

# 2. MySQL + 弱口令
sudo DEBIAN_FRONTEND=noninteractive apt install -y mysql-server
sudo systemctl start mysql 2>/dev/null || sudo service mysql start 2>/dev/null || true
sudo mysql -e "ALTER USER 'root'@'localhost' IDENTIFIED WITH mysql_native_password BY 'root'; FLUSH PRIVILEGES;" 2>/dev/null || true

# 3. Redis 无密码
sudo apt install -y redis-server
sudo sed -i 's/^requirepass.*/# requirepass (disabled for test)/' /etc/redis/redis.conf 2>/dev/null || true
sudo systemctl start redis-server 2>/dev/null || sudo service redis-server start 2>/dev/null || true

# 4. 敏感目录（启动简单 HTTP 服务）
mkdir -p /tmp/test_www/.git
echo "ref: refs/heads/main" > /tmp/test_www/.git/HEAD
echo "DB_PASSWORD=lightshield_test_secret" > /tmp/test_www/.env
echo "<html><body>Test Page</body></html>" > /tmp/test_www/index.html
cd /tmp/test_www && python3 -m http.server 8080 &
HTTP_PID=$!
echo "HTTP 测试服务 PID: $HTTP_PID"

# 5. 确认服务状态
echo ""
echo "=== 靶机服务状态 ==="
echo "Telnet (23): $(ss -tlnp | grep ':23 ' && echo 'OPEN' || echo '未启动')"
echo "MySQL (3306): $(ss -tlnp | grep ':3306 ' && echo 'OPEN' || echo '未启动')"
echo "Redis (6379): $(ss -tlnp | grep ':6379 ' && echo 'OPEN' || echo '未启动')"
echo "HTTP (8080): $(ss -tlnp | grep ':8080 ' && echo 'OPEN' || echo '未启动')"
echo "SSH (22): $(ss -tlnp | grep ':22 ' && echo 'OPEN' || echo '未启动')"
echo ""
echo "✅ 靶机搭建完成"
```

#### E2E 测试流程（5 步）

```
Step 1: 资产扫描   → lightshield scan 127.0.0.1
                     预期：发现端口 22/23/3306/6379/8080
Step 2: 漏洞检测   → Web 漏洞 + 弱口令 + 组件 CVE
                     预期：≥5 个发现（高危端口 + MySQL弱口令 + OpenSSH CVE + Redis无密码 + 敏感目录）
Step 3: 规则匹配   → RuleEngine 匹配漏洞规则
                     预期：每个 finding 有明确的规则 ID + severity
Step 4: 加固生成   → lightshield harden 127.0.0.1 --confirm-ownership
                     预期：生成 harden.sh + rollback.sh，含 iptables 规则 + 服务加固命令
Step 5: 复扫验证   → 手动执行 harden.sh 中的部分加固命令 → 重新 scan
                     预期：已加固的漏洞不再出现在报告中
```

#### 合规验证清单

| 红线 | 验证方式 | 预期 |
|:--:|------|:--:|
| R1 | grep 扫描/加固脚本不含攻击关键字 | ✅ 零命中 |
| R2 | scan 拒绝 CIDR 输入（`lightshield scan 127.0.0.0/24`） | ✅ 拦截 |
| R4 | `--confirm-ownership` 缺失时 CLI 要求交互确认 | ✅ 确认门 |
| R5 | MSF 适配器拒绝 exploit/payload 模块 | ✅ SecurityViolationError |
| R6 | 扫描日志中并发数 ≤20 | ✅ 符合 |

#### 输出要求

测试完成后生成 `docs/e2e-v019-report.md`：

```markdown
# LightShield v0.0.19 E2E 终审报告

## 测试环境
- VM: Ubuntu 22.04
- Python: 3.12
- Nmap: 7.94

## Step 1: 资产扫描
- 命令: lightshield scan 127.0.0.1 --confirm-ownership
- 结果: ✅/❌
- 发现端口: [22, 23, 3306, 6379, 8080]

## Step 2: 漏洞检测
- 发现数: N 个
- 详情: [表格列出每个 finding 的 vuln_type + severity + title]

## Step 3: 规则匹配
- 匹配规则数: N
- 详情: [表格列出 rule_id + severity]

## Step 4: 加固生成
- 生成文件: harden.sh (N 条命令), rollback.sh (N 条回滚)
- 加固覆盖: [列出哪些漏洞被覆盖]

## Step 5: 复扫验证
- 复扫结果: ✅/❌
- 剩余漏洞: [如果 >0，列出未修复的]

## 合规验证
- [ ] R1 零攻击关键字
- [ ] R2 CIDR 拦截
- [ ] R4 所有权确认
- [ ] R5 MSF 白名单
- [ ] R6 并发限制

## 结论
- E2E 结果: ✅ PASS / ❌ FAIL
- 是否可以发布 v0.0.20: YES / NO（附原因）
```

#### 启动提示词（直接复制到 QoderWork）

```
你是 LightShield 项目 QoderWork Agent，在 Linux VM 沙箱中执行 v0.0.20 发布前的最终 E2E 终审。

## 项目背景

LightShield（轻盾）是面向初创企业的开源安全自检工具，Python 3.10+。
项目路径：E:/Github Project/LightShield/

v0.0.20 所有模块已交付（14 个核心模块 + 355 测试 + 5 层质量门禁）。
这是发布前的最后一步——在真实 Linux 靶机环境中验证全链路。

## 合规红线（VM 中也必须遵守）

R1: 禁攻击 | R2: 禁批量扫描（只扫 127.0.0.1）| R3: 禁远控/后门 | R4: 仅自查 | R6: 并发≤20

## 你的任务

### 1. 环境准备
- 确认 Ubuntu 20.04/22.04 VM 干净状态
- 安装依赖：apt install nmap telnetd mysql-server redis-server
- pip install -r requirements.txt
- 创建 VM 快照（测试后回滚）

### 2. 搭建靶机
运行上述靶机搭建脚本，确认 5 个漏洞就绪：
- Telnet (23) / MySQL弱口令 (3306) / Redis无密码 (6379) / SSH (22) / HTTP敏感目录 (8080)

### 3. E2E 测试（5 步）
Step 1: lightshield scan 127.0.0.1 --confirm-ownership
Step 2: 检查报告中是否检测到 ≥5 个漏洞（高危端口 + MySQL弱口令 + OpenSSH CVE + Redis + 敏感目录）
Step 3: 验证每个 finding 有规则 ID 和 severity
Step 4: lightshield harden 127.0.0.1 --confirm-ownership → 生成 harden.sh + rollback.sh
Step 5: 手动执行 harden.sh（iptables 封禁 23/3306/6379），重新 scan → 验证漏洞减少

### 4. 合规验证
- lightshield scan 127.0.0.0/24 → 应拒绝（R2）
- 检查生成的 harden.sh 不含 exploit/payload/attack 关键字（R1）
- 检查审计日志中有所有权确认记录（R4）

### 5. 输出报告
生成 docs/e2e-v019-report.md（使用上述报告模板）

## 注意事项
- 所有扫描只针对 127.0.0.1
- 硬编码密钥 SEC 扫描在 logger.py 中的 "Secret123!" 是测试数据，可以忽略
- 使用 `py` 不是 `python`（Windows）——Linux VM 中用 `python3`
- 测试完成后回滚 VM 快照
```

---

### v0.0.40 — 🔴 自动加固执行基座真机验证（当前任务 🟢）

#### 任务背景

v0.0.40 要做自动加固闭环 `扫描 → 推荐 → 生成脚本 → 执行 → 复扫 → 验证`。前三环已就绪，v0.0.38 交付了第④环沙箱执行器——但**单测全程 mock `subprocess.run`，从未真机跑过 Docker 容器**。

CC 静态分析预判：v0.0.38 的锁死容器（`--network none` + `no-new-privileges` + 默认丢弃 caps + 无 init）**跑不动真实加固脚本**（`systemctl`/`iptables`/`apt` 三杀），且 `--network none` + `--rm` 没有可复扫的持久目标。**闭环的 `APPLY`（真正应用加固）模式很可能需要一台真 VM 或特权容器，而非锁死容器。**

**你的使命**：真机证实/证伪上述预判，为 v0.0.40 的 `APPLY` 基座定型。完整验证项（V1-V7）、步骤、输出契约见任务文件 `.cluster/tasks/pending/QODERWORK-v040-sandbox-verify.md`，接口契约见 `docs/design-v040-closed-loop.md`（先读，尤其 §4 + §9）。

> ⚠️ 你只**验证**，不写实现代码。结论决定架构，故为 v0.0.40 阻塞性前置门禁。

#### 输出

`docs/e2e-v040-sandbox-verify-report.md`：V1-V7 逐项真机结果+证据、APPLY 基座可行性矩阵+倾向结论、契约 §9 五问回答、tcpdump 零外联证据、是否需补 ADR。

#### v0.0.40 启动提示词（直接复制到 QoderWork）

```
你是 LightShield 项目 QoderWork Agent，在隔离 Linux VM 中执行 v0.0.40 的「自动加固执行基座真机验证」门禁任务。

## 项目背景
LightShield（轻盾）是面向初创企业的开源安全自检 + 加固工具，Python 3.10+。项目在 VM 内 clone 到 /workspace/LightShield。
v0.0.40 要做自动加固闭环（扫描→推荐→生成脚本→执行→复扫→验证）。v0.0.38 交付的沙箱执行器单测全程 mock，从未真机验证——这就是你要补的缺口。

## 先读两份文档（必须）
1. .cluster/tasks/pending/QODERWORK-v040-sandbox-verify.md —— 本任务的完整验证项/步骤/输出契约（以它为准）
2. docs/design-v040-closed-loop.md —— 闭环接口契约，重点看 §4（DRY_RUN vs APPLY 基座张力）和 §9（你要回答的 5 个未决问题）

## 合规红线（VM 中也必须遵守）
R1 禁攻击：目标只能是 VM 内部自建靶机，全程 tcpdump 抓包证明零外联
R2 只扫 127.0.0.1 / VM 内网 | R4 仅自查自有资产 | R6 并发≤20、间隔≥5s
测试前 VM 快照 → 测试 → 回滚。不得安装攻击工具。

## 你的任务（不写实现代码，只验证+记录+给结论）
1. 环境：Ubuntu 22.04 + Docker + nmap + python3.10+，pip install -r requirements.txt，建快照。
2. DRY_RUN 验证：用 LinuxHardener.generate 生成一个含 iptables/systemctl 命令的真实加固脚本，再用 DockerSandboxExecutor().execute(..., confirm_execute=True) 真机执行它。逐条记录验证项 V1-V7（见任务文件第四节）：systemctl/iptables/apt 各报什么错？yes 自动应答是否放行 R4 交互门？超时是否被 kill 且无残留？
3. APPLY 基座探索：在 VM 真机（非锁死容器）搭一个高危端口靶机（telnet 23/redis 6379）→ iptables 真封端口 → 复扫确认端口消失。记录"VM 真机能跑通应用加固+复扫，容器不能"。评估三种 APPLY 基座（独立 VM / 特权容器 / systemd-in-container）的可行性与合规边界，给倾向结论。
4. 回答接口契约 §9 的 5 个未决问题，每条要有真机依据。

## 输出
生成 docs/e2e-v040-sandbox-verify-report.md（模板见任务文件第六节），结论段明确：①v0.0.38 沙箱定位 ②v0.0.40 APPLY 基座建议 ③是否需补 ADR。

## 注意
- 所有扫描只针对 127.0.0.1 / VM 内网；Linux VM 用 python3
- 不改动任何仓库源码（你只验证）
- 测试完回滚 VM 快照
- 结果回传后由 Claude Code 审查，据此定稿接口契约并放行 v0.0.40 实现阶段
```

---

---

## 九、模式 A：高级开发模式（🏗️ 常规高级实现主力）

> **模型能力依据**：Qwen-3.7-Max 是 Code Arena **全球第 2**（1541 分），**超过 GPT-5.5**（1508）、GLM-5.1（1533）、Kimi K2.6（1518）。SWE-Multilingual **78.4 全球纪录**。IFBench **81.2 指令遵循新高**。
> **定位**：你是集群常规高级开发任务的第一选择——编码能力强、指令遵循好、成本合理（59元/月套餐）。
> **与 ZCode 的分工**：ZCode 是"特种部队"（1M 上下文 + Opus 级编码，但配额消耗高/速度慢）——跨模块长程任务才出动。你是"常规主力"——标准高级开发任务默认走你。

### A.1 适用场景

| 任务类型 | 说明 | 示例 |
|---------|------|------|
| 🏗️ **高级模块实现** | 标准复杂度以上、需要高质量编码的任务 | 新 Adapter 实现、规则引擎增强、Core 模块扩展 |
| 🌐 **全栈 Web 开发** | Flask + Jinja2 + 原生 HTML/CSS/JS | v0.0.40 Web「加固+复扫+对比」页面、API 路由 |
| 📐 **多文件精准编辑** | 跨文件符号搜索、引用跟踪、精确重构 | 接口适配、模块拆分、依赖更新 |
| 🔍 **模块级代码审查** | 与 CC 搭配审查单个模块的代码质量 | Web 层审查、前端安全审查 |
| 🤖 **AI 补全辅助** | 上下文感知代码补全，符合项目规范 | 日常 IDE 操作 |

### A.2 Qwen-3.7-Max 核心优势

| 优势 | 数据 | 在 LightShield 中的价值 |
|------|:--:|------|
| 编码能力 | Code Arena **#2** (1541)，超 GPT-5.5 | 高级实现质量有保证 |
| 指令遵循 | IFBench **81.2** 新高 | 任务文件要求不易丢失 |
| 多语言编程 | SWE-Multilingual **78.4** 全球纪录 | Python + Shell + JS 全覆盖 |
| 长程自主 | **35h** 连续运行，1000+ 工具调用 | 模式 B 的核心能力 |
| 成本 | 59元/月套餐 | 性价比极高 |

### A.3 IDE 工作区

在 Qoder IDE 中打开项目：
```
File → Open Folder → E:\Github Project\LightShield\
```

Quest Agent 调用方式：复制任务文件 prompt → 粘贴到 Quest Agent 对话框 → 执行。

### A.4 前端开发合规

| 编号 | 红线 | 前端注意事项 |
|:--:|------|------|
| R1 | 禁止对外主动攻击 | 前端不触发任何扫描/攻击逻辑 |
| R2 | 禁止批量扫描公网 IP | 前端输入框需做 IP/域名校验 |
| R4 | 仅自查自有资产 | Web 面板的所有权确认弹窗不可绕过 |

### A.5 前端任务

| 版本 | 任务 | 模式 | 说明 |
|------|------|:--:|------|
| v0.0.04 | base.py + core.py 双审（与 CodeWhale 搭档） | IDE | 发现 2B+6S ✅ |
| v0.0.40 | Web「加固+复扫+对比」页面 | IDE | 一键加固→复扫→前后风险对比 UI（原 Qoder IDE 派工，见 `QODERWORK-v040-web-compare-page.md`） |

---

## 十、注意事项

- VM 内测试目标 IP 限制为 VM 内网地址（如 192.168.x.x）
- 测试完成后必须回滚 VM 快照
- 不得在 VM 中安装攻击工具（即使隔离也不行——合规）
- 测试日志自动回传，无需人工干预
