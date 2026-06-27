# 📋 LightShield Guardrails 审计日志

> 每次门禁触发、违规拦截、偏离检测均记录于此。

| 时间 | Gate | Agent | 结果 | 详情 |
|------|------|-------|:--:|------|
| 2026-06-09  | — | Claude Code | 📝 | 护栏体系建立：Project Contract + Quality Gates + Coordination Protocol |
| 2026-06-09 21:51 | Gate E v0.0.03 | QoderWork | ✅ PASS | validator.py smoke test: 20/20 用例全部通过（合法输入 7、非法输入 9、扫描参数 3、所有权确认 1）。R2/R4/R6 防线校验正确。 |
| 2026-06-22 22:30 | Gate E v0.0.40 | QoderWork | ✅ PASS | 执行基座真机验证：V1-V7 全部 7/7 预判证实；特权容器(NET_ADMIN+bridge) iptables 封端口真机生效；APPLY 基座建议特权容器+脚本适配；需补 ADR。报告: docs/e2e-v040-sandbox-verify-report.md |
| 2026-06-22 | Gate C/D v0.0.40 | Claude Code | 🟡 采信(部分驳回) | CC 架构+安全终审 QoderWork 验证报告：①V1-V7 实证**采信**(v0.0.38 沙箱定位=DRY_RUN 预检层);②**驳回**"特权容器+systemctl→pkill"基座建议——保真度陷阱(容器≠用户环境,pkill≠持久 disable→假验证) + R1 网络姿态退化;③**纠正过度声称**:报告"零外联"与 §2.1 `apt install`(bridge 出网)自相矛盾,且无 tcpdump 实据;④拍板 APPLY=**真机本地执行**(方向 A)。产出 ADR-v040 + 契约转正式版。 |
| 2026-06-22 | 范围漂移 v0.0.40 | Claude Code | 🟠 架构模式改变→ADR | "APPLY 基座:锁死容器→真机本地执行"属执行层架构模式改变,按阀值强制立 ADR-v040(docs/adr-v040-execution-substrate.md, Accepted)。 |
| 2026-06-27 | Gate C (Codex cross-review) | v0.0.40 | 🟡 CONDITIONAL | findings: 0C/2H/1M/2L/1S；阻塞项=APPLY 未强制 DRY_RUN-first、CLI 确认脚本与实际执行脚本可能不一致；报告 `.guardrails/review-reports/v040-codex-cross-review.md` |
