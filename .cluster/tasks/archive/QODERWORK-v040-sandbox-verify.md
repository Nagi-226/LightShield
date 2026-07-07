> ✅ **门禁已关闭（2026-06-22）** — QoderWork 报告 `docs/e2e-v040-sandbox-verify-report.md` 交付,CC 终审完成:V1-V7 实证采信;特权容器基座建议**驳回**;拍板 **APPLY=真机本地执行**。决策见 `docs/adr-v040-execution-substrate.md`,契约 `docs/design-v040-closed-loop.md` 已转正式版。**v0.0.40 实现阶段已放行**(Reasonix verify / Qoder Web / QoderWork Gate E 夹具)。以下为原任务存档。

---

你是 LightShield 项目的后台任务执行器（QoderWork + Qwen-3.7-max），运行在隔离 VM 中。本任务为 **v0.0.40 验证门禁 — 自动加固执行基座真机验证**。

> ⚠️ **这是 v0.0.40 的阻塞性前置门禁，不是可并行支线。** 在你给出基座验证结论前，闭环实现（Reasonix verify 模块、Qoder Web 页面、VM 闭环编排）都不得合入。你的结论直接决定 v0.0.40 的执行基座架构。

---

## 一、项目上下文

LightShield（轻盾）是开源轻量化安全自检 + 防御加固工具，Python 3.10+，MIT。当前 v0.0.39，本任务为 v0.0.40 铺路。完整信息见 `CLAUDE.md`。

**v0.0.40 目标**：自动加固闭环 `扫描 → 推荐 → 生成脚本 → 执行 → 复扫 → 验证`。
- 前三环已就绪；v0.0.38 交付了沙箱执行器（第④环），但**单测全程 mock `subprocess.run`，从未真机拉起过 Docker 容器跑真实加固脚本**。
- 闭环接口契约（CC 已起草）：`docs/design-v040-closed-loop.md`。**先完整读这份契约**，你的验证就是去回答它 §9 的 5 个未决问题。

**关键代码**：
- 沙箱执行器：`lightshield/sandbox/docker_executor.py`（`--network none` + `no-new-privileges` + 资源限制 + 只读挂载 + `--rm`）、抽象基类 `lightshield/sandbox/base.py`。
- 加固脚本生成：`lightshield/harden/linux_harden.py`（`LinuxHardener.generate`）、模板 `lightshield/harden/templates/{linux_firewall.sh,linux_service.sh}`。
- CLI 执行入口：`lightshield/cli.py` 的 `--execute` → `_run_sandbox_execution`（已接线 v0.0.38）。
- 工作区：`E:\Github Project\LightShield\`（VM 内 clone 到 `/workspace/LightShield`）。

---

## 二、⚠️ 合规约束（VM 隔离也必须遵守，不可违反）

- **R1 禁止对外主动攻击**：即使授予容器/VM 特权，目标只能是 VM 内部自建靶机，**全程 tcpdump 抓包证明零外联**。
- **R2 禁止批量扫描公网 IP 段**：只扫 `127.0.0.1` / VM 内网地址。
- **R3 禁止远控/后门**；**R4 仅自查自有资产**：靶机为你 VM 内搭建；**R5** MSF 仅 `auxiliary/scanner/`；**R6** 并发 ≤20、间隔 ≥5s。
- **测试前 VM 快照 → 测试 → 回滚快照**，确保环境清洁。
- 不得在 VM 中安装任何攻击工具。

---

## 三、任务目标

**核验 v0.0.38 沙箱在真机的真实行为，并为 v0.0.40 的 `APPLY`（真正应用加固）模式定基座。** 产出一份验证报告 + 明确的基座选型建议。

**不要写实现代码**（闭环实现归 Reasonix/Qoder/CC）。你只做：真机执行、观测、记录、给结论。若过程中需要小脚本辅助验证，写在 `/tmp` 下，不提交进仓库。

---

## 四、待验证项（CC 的预判 = Ground Truth，请逐条真机证实或证伪）

> CC 静态分析已预判以下结论，**请用真机结果证实或推翻，不要直接采信**。任何与预判不符的，在报告里明确标注。

| # | 预判 | 验证方式 |
|---|------|---------|
| V1 | v0.0.38 锁死容器（`--network none`+`no-new-privileges`）**跑不动真实 Linux 加固脚本** | 在容器内实跑 `linux_harden` 生成的脚本，观察 `systemctl` / `iptables` / `apt` 是否全部失败 |
| V2 | `systemctl` 在无 init 容器中失败 | 容器内 `systemctl status` → 预期 "System has not been booted with systemd" |
| V3 | `iptables` 因无 NET_ADMIN + 禁提权被拒 | 容器内 `iptables -L` → 预期 Permission denied / Operation not permitted |
| V4 | `apt` 因 `--network none` 无法下载 | 容器内 `apt update` → 预期网络不可达 |
| V5 | `--network none` + `--rm` 使闭环**无可复扫的持久目标** | 确认容器即用即销毁、无网络，无法被外部 re-scan |
| V6 | `docker_executor` 的 `yes\n*16` 自动应答能放行加固脚本 R4 交互门 | 真跑一个含 `read -r -p` 所有权确认的加固脚本，看是否被自动放行 |
| V7 | 超时强制 kill + `--rm` 清理有效 | 跑一个 `sleep 999` 脚本，验证超时后容器被 kill 且不残留 |

---

## 五、验证步骤（分步，勿跳过）

### 第 0 步：环境 + 读契约
1. VM：Ubuntu 22.04 干净安装，装 Docker + nmap + python3.10+，`pip install -r requirements.txt`，**创建快照**。
2. 完整阅读 `docs/design-v040-closed-loop.md`（尤其 §4 基座张力、§9 未决问题）。

### 第 1 步：DRY_RUN 基座验证（v0.0.38 锁死容器）
3. 生成一个真实加固脚本：
   ```bash
   python3 -c "
   from lightshield.harden.linux_harden import LinuxHardener
   recs = [
     {'rule_id':'TEST-PORT','title':'高危端口 23','command':'iptables -A INPUT -p tcp --dport 23 -j DROP','port':'23'},
     {'rule_id':'TEST-SVC','title':'禁用 telnet','command':'systemctl disable telnet','port':'23'},
   ]
   r = LinuxHardener().generate('127.0.0.1', recs, output_dir='/tmp/ls_harden')
   print(r.script_path)
   "
   ```
4. 用 v0.0.38 沙箱真机执行它（这是从未跑过的真机路径）：
   ```bash
   python3 -c "
   from lightshield.sandbox.docker_executor import DockerSandboxExecutor
   ex = DockerSandboxExecutor()
   print('docker 可用:', ex.is_available())
   res = ex.execute('/tmp/ls_harden/<刚生成的脚本>', confirm_execute=True)
   print('status:', res.status, 'exit:', res.exit_code)
   print('STDOUT:', res.stdout)
   print('STDERR:', res.stderr)
   "
   ```
5. **据输出逐条记录 V1-V4、V6**：systemctl/iptables/apt 各自报什么错？`yes` 应答是否放行了 R4 门？退出码语义是否合理？
6. 验证 V7：执行一个 `#!/bin/bash\nsleep 999` 脚本，确认超时被 kill、`docker ps -a` 无残留。

### 第 2 步：APPLY 基座探索（闭环真正需要的基座）
7. 复用 v0.0.19 的思路（QODERWORK.md 已有靶机搭建脚本），在 **VM 真机**（非锁死容器）上：搭一个含高危端口（telnet 23 / redis 6379）的靶机 → `iptables -A INPUT --dport 23 -j DROP` 真封端口 → 复扫确认端口消失。**记录：VM 真机能跑通"应用加固 + 复扫"，容器不能。**
8. 评估三种 APPLY 基座的可行性 + 合规边界，给倾向性结论：
   - (a) 独立 VM（systemd + 网络 + 内部靶机）；
   - (b) 特权容器（`--cap-add NET_ADMIN` / `--privileged` + 内部服务）；
   - (c) 其他（如 systemd-in-container 镜像）。
   - 对每种，回答契约 §9 的特权边界（与 R1 如何并存）、复扫目标在哪。

### 第 3 步：回答契约 §9 的 5 个未决问题
9. 逐条给出真机依据的回答。

---

## 六、输出契约

产出 **`docs/e2e-v040-sandbox-verify-report.md`**，含：

```markdown
# v0.0.40 执行基座真机验证报告（QoderWork）

## 测试环境
- VM / Docker 版本 / Python / nmap 版本

## 第 1 步：DRY_RUN 锁死容器验证
| 验证项 | 预判 | 真机结果 | 证据（命令输出节选） | 结论 |
|--------|------|---------|------|------|
| V1 容器跑不动加固 | … | ✅/❌ | … | … |
| V2 systemctl | … | … | … | … |
| …（V3-V7 全列）| | | | |

## 第 2 步：APPLY 基座探索
- VM 真机"应用 iptables 加固 + 复扫端口消失"：✅/❌ + 证据
- 三种基座可行性矩阵 + 倾向结论 + 特权/合规边界

## 第 3 步：契约 §9 五问回答
1. 基座：… 2. 特权边界：… 3. 复扫目标：… 4. stdin 应答：… 5. DRY_RUN 形态：…

## 合规审计
- tcpdump 全程零外联证据
- R2/R4/R6 自查

## 最终结论
- v0.0.38 沙箱定位：[DRY_RUN 预检层 / 需改造 / 废弃]
- v0.0.40 APPLY 基座建议：[VM / 特权容器 / 其他] + 理由
- 是否需要补 ADR（沙箱→VM 属架构模式改变）：YES / NO
```

---

## 七、验收标准

1. [ ] V1-V7 七项**全部**有真机结果 + 证据（命令输出），与预判不符的已标注。
2. [ ] 第 2 步给出 APPLY 基座可行性矩阵 + 明确倾向结论（含特权/合规边界）。
3. [ ] 契约 §9 五个未决问题逐条回答，有真机依据。
4. [ ] tcpdump 证据证明全程零外联（R1）。
5. [ ] 报告落 `docs/e2e-v040-sandbox-verify-report.md`，结论段明确"是否需补 ADR"。
6. [ ] VM 快照已回滚，环境清洁。
7. [ ] **未改动任何仓库源码**（你只验证，不实现）。

---

## 八、调用方式

```bash
qoderwork exec "$(cat .cluster/tasks/pending/QODERWORK-v040-sandbox-verify.md)"
```

> 结果回传后由 Claude Code 审查，据此把 `docs/design-v040-closed-loop.md` 的 `【待验证】` 条目定稿，并视结论补 ADR，再放行 v0.0.40 实现阶段（Reasonix verify 模块 + Qoder Web 页面 + QoderWork VM 闭环）。
