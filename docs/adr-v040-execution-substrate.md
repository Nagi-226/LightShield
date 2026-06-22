# ADR-v040：APPLY 执行基座 — 真机本地执行,非 VM/特权容器

> **状态**：✅ Accepted
> **日期**：2026-06-22
> **决策者**：Claude Code（架构 + 安全终审）｜**项目所有者拍板**：方向 A（真机）
> **关联**：`docs/design-v040-closed-loop.md`（接口契约）、`docs/e2e-v040-sandbox-verify-report.md`（QoderWork 真机验证）、`.cluster/tasks/pending/QODERWORK-v040-sandbox-verify.md`（验证门禁）
> **类型**：执行层架构模式改变 → 按范围漂移阀值「架构模式改变=任何→🟠 暂停+ADR」强制立项

---

## 1. 背景（Context）

v0.0.40 要做自动加固闭环 `扫描 → 推荐 → 生成脚本 → 执行 → 复扫 → 验证`。前三环已就绪（`run_vuln_scan` / `RuleEngine.recommend_hardening` / `Hardener.generate`），缺的是 **④执行 + ⑤复扫 + ⑥验证**。其中「④在什么基座上执行加固脚本」是决定整条闭环安全边界与验证有效性的关键决策。

v0.0.38 交付的 `DockerSandboxExecutor`（`--network none` + `no-new-privileges` + 丢弃 caps + `--rm`）单测全程 mock,从未真机运行。CC 静态预判它跑不动真实加固,遂下发 QoderWork 真机验证门禁（V1-V7）。

### 1.1 QoderWork 真机验证结论（已采信的实证）

V1-V7 **7/7 预判全部真机证实**（证据见验证报告）：

- 锁死容器中 `systemctl`（无 init→`System has not been booted with systemd`）、`iptables`（未安装且 `--network none` 装不上）、`apt`（无网,DNS 全败）**三杀**;
- `--network none` + `--rm` → 闭环**无可复扫的持久目标**;
- `subprocess.run(input="yes\n"*16)` 能放行加固脚本的 R4 交互确认门;
- 超时强制 `docker kill` + `--rm` 清理有效,无残留。

**结论:v0.0.38 锁死容器不能承载 APPLY,但作为 DRY_RUN 预检层胜任。** 此部分本 ADR 完全采信。

### 1.2 QoderWork 的基座建议 + CC 审查发现的两处问题

QoderWork 进一步建议:**特权容器（`--cap-add NET_ADMIN` + bridge 网络）作 APPLY 基座**,辅以脚本适配层把 `systemctl stop/disable` 改写为 `pkill / update-rc.d`。CC 安全终审**否决此建议**,理由:

1. **保真度陷阱(致命)**:`systemctl disable`（持久禁止开机自启）与 `pkill`（仅杀当前进程,重启复活）**语义不等价**,`update-rc.d` 对 systemd 单元无效。在「PID1=bash、命令被改写、镜像≠用户环境」的容器里复扫,会对一个真机上根本不会持久生效的加固判定 `verified`——**对一个"验证加固是否生效"的工具,这是最致命的假阳性**。
2. **R1 安全姿态退化**:APPLY 从 `--network none` 改到 bridge,R1「禁外联」就从"网络物理隔离保证"退化成"承诺只连内网+脚本已审"。且验证报告 §合规审计自称"零外联",却在 §2.1 用 `apt-get install -y iptables`（bridge 必然出网拉 archive.ubuntu.com）——**自相矛盾,且任务硬验收项「tcpdump 证明零外联」无任何真实抓包输出**。

**根因**:容器作为基座,根本不是用户的真实加固目标;在不保真的基座里验证,结论不可迁移到用户真机。

---

## 2. 决策（Decision）

**APPLY 模式在用户真实主机本机执行加固脚本,不引入 VM/容器作为产品级执行基座。**

LightShield 本质是装在被防护机器上的本地自检+加固工具（与现有 `scan 127.0.0.1` 形态一致）。因此闭环的「目标」自始至终是 **LightShield 所在的这台自有主机（R4 自有资产）**:

| 模式 | 基座 | 在哪执行 | 改变系统? | 复扫目标 |
|------|------|---------|:---:|---------|
| `DRY_RUN`（默认） | v0.0.38 锁死容器（`backend="docker"`）+ `bash -n` | 容器内（一次性、零网络） | ❌ 否 | 不复扫 |
| `APPLY` | **宿主机本机**（新增 `backend="host"`） | 真机 localhost | ✅ 是 | **同一台真机**（`run_vuln_scan` 复扫 localhost） |

具体:

1. **新增 `HostExecutor(SandboxExecutor)` 后端**,经既有 `get_executor("host")` 工厂接入（不破坏 v0.0.38 Docker 后端）。它在宿主机以当前权限直接 `subprocess` 执行加固脚本,**不套容器、不开特权、不动网络模型**。
2. **DRY_RUN 维持 v0.0.38 锁死容器不变**,职责明确为「预检层」:`bash -n` 语法检查 + R1 攻击关键字内容扫描 + 锁死容器烟测（脚本是否卡死/能否被自动应答放行/超时是否被干净 kill）。**DRY_RUN 不试图真机预演加固是否成功**（锁死容器里必然全失败,这是其设计,非缺陷）。
3. **QoderWork 的特权容器（NET_ADMIN+bridge）正名为「集群 E2E 测试夹具」**——它本来做的就是集群自身回归测试（Gate E）的事,放在测试基础设施,**不进产品代码、不进 `lightshield/sandbox/`、不随包分发**。
4. **加固脚本以原样在真机执行,不做 `systemctl→pkill` 改写**——真机有 systemd,无需降级改写,从根上消除保真度陷阱。

### 2.1 真机 APPLY 的强制护栏（R 红线落地）

真机执行加固是高风险动作,以下护栏不可省:

- **R4 双重确认**:`confirm_ownership=True` **且** `confirm_execute=True` 才进 APPLY;CLI 须 `--confirm-ownership --apply` 双显式标志。**自动 `yes` 应答仅限集群测试夹具,严禁作产品默认。**
- **DRY_RUN-first 前置**:APPLY 前必须先过一次 DRY_RUN（`bash -n` + R1 内容扫描）通过,否则拒绝执行。
- **rollback 强制先行**:`Hardener.generate` 已产 `rollback_path`,APPLY 必须在回滚脚本就绪后才执行加固。
- **防御性命令边界(R1)**:加固脚本只含防御命令（封端口/停服务/改配置）,生成阶段已做 R1 关键字扫描;真机执行**不调用任何 exploit/payload**。
- **单目标(R2/R6)**:只对本机/单一自有目标,无批量、并发≤20、间隔≥5s。
- **全程审计**:每条执行命令、所有权确认、退出码落 `audit_id` 本地日志。

---

## 3. 被否决的备选（Alternatives Considered）

| 方案 | 内容 | 否决理由 |
|------|------|---------|
| **B：保真一次性靶机** | APPLY 打一台抛弃式内部靶机(自测/演示),用 systemd-capable VM 或 systemd-in-container 保真 | 价值偏低（用户要的是加固自己的机器,不是抛弃靶机）;且仍需维护一套 ≠ 用户环境的基座,保真度永远打折。若将来要"演示模式"可另立 ADR。 |
| **C：QoderWork 原案** | NET_ADMIN 特权容器 + bridge + `systemctl→pkill` 适配层 | ①保真度陷阱→假验证(§1.2.1);②R1 网络姿态退化(§1.2.2);③膨胀(systemd 镜像/特权管理)违背"轻盾 ≤500MB"。仅"秒级启停"一项优势,不抵风险。 |
| **隐含旧设（v0.0.38 即 APPLY 基座）** | 直接用锁死容器执行加固 | V1-V7 已真机证伪:三杀 + 无复扫目标。 |

---

## 4. 后果（Consequences）

**正面:**
- ✅ **验证保真度满分**:复扫的就是被加固的真机,`verified` 判定可信,杜绝假阳性。
- ✅ **R1 不退化**:真机 APPLY 无需 bridge;DRY_RUN 保持 `--network none` 物理隔离。
- ✅ **无语义漂移**:脚本原样执行,不改写命令。
- ✅ **轻量**:无 VM/特权容器/systemd 镜像依赖,守住 ≤500MB。

**负面 / 需承担:**
- ⚠️ **APPLY 动真实 OS,风险高**——由 §2.1 护栏（双确认+rollback+DRY_RUN-first+审计+防御性边界）兜底。
- ⚠️ **DRY_RUN 无法完整预演加固成败**(锁死容器固有限制)——已明确文档化,DRY_RUN 定位为"语法+安全+不卡死"预检,非"加固有效性"预演。
- ⚠️ **不支持远程目标加固**(LightShield 须运行在被加固机上)——符合当前本地工具定位;未来"重盾"的 Agent/SSH 远程加固另行立项,本 ADR 不覆盖。

---

## 5. 合规映射（R1–R6）

| 红线 | 本决策落地方式 |
|:--:|------|
| R1 禁攻击 | 加固脚本仅防御命令 + 生成阶段 R1 关键字扫描;真机执行不引入网络下载/exploit;DRY_RUN 维持 `--network none` |
| R2 禁批量扫公网 | APPLY 单目标(本机),复扫复用 `run_vuln_scan` 单目标路径 |
| R3 禁远控后门 | 执行的是 `Hardener.generate` 产物,经 R1/R3 关键字审查;无 bind/reverse shell |
| R4 仅自查自有 | `confirm_ownership` + `confirm_execute` 双确认;目标=LightShield 所在自有主机 |
| R5 MSF 白名单 | 不受影响(闭环不调 MSF exploit) |
| R6 频率限制 | 复扫并发≤20、间隔≥5s |

---

## 6. 落地影响（给实现方）

- **Reasonix**：`verify_hardening` 纯函数不受影响(契约 §7 不变);可放行实现。
- **Qoder Web**：消费 `ClosedLoopResult.to_dict()`,`mode` 取值 `dry_run|apply`,`execution` 来自 host 后端(契约 §8 不变);可放行实现。
- **QoderWork**：特权容器脚本归为集群 Gate E 夹具(测试基础设施),用于闭环回归,不进产品包。
- **CC**：据本 ADR 回填 `docs/design-v040-closed-loop.md` §4/§6/§9【待验证】→ 契约转正式版。

---

> 本 ADR 由 Claude Code 起草并经项目所有者拍板方向 A。后续 v0.0.40 实现以本 ADR + 转正后的接口契约为准。
