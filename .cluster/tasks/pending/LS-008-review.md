# LS-008: Phase 1 代码审查 — 合规 + 质量

## 任务信息
- **Task ID**: LS-008
- **Phase**: Phase 1 — 项目骨架
- **分配给**: CodeWhale
- **优先级**: P1（在 LS-001 ~ LS-007 完成后执行）
- **依赖**: LS-001 ~ LS-007
- **输出**: 审查报告 `docs/review-phase1.md`

## 项目上下文

LightShield（轻盾）是一个面向初创企业 & 个人站长的开源轻量化安全自检 + 防御加固工具。
这是 Phase 1 完成后的首次全量代码审查。

## 审查目标

对 Phase 1 产出的所有代码文件进行审查：

| 文件 | 重点 |
|------|------|
| `lightshield/base.py` | Adapter 接口设计是否合理 |
| `lightshield/core.py` | 调度逻辑是否解耦 |
| `lightshield/config.py` | 配置加载是否安全 |
| `lightshield/utils/validator.py` | 校验逻辑是否完备 |
| `lightshield/utils/logger.py` | 日志是否线程安全 |
| `lightshield/utils/constants.py` | MSF 白名单/黑名单是否完整 |

## ⚠️ 合规审查清单（逐条检查）

### R1 — 禁止对外主动攻击
- [ ] 所有代码中无 exploit/payload/attack 调用
- [ ] 无对外渗透测试逻辑

### R2 — 禁止批量扫描公网 IP 段
- [ ] validator.py 正确拒绝 CIDR/网段/通配符
- [ ] 所有扫描入口都调用了 validate()

### R3 — 禁止远控/后门/木马
- [ ] 全局搜索无 `bind_shell`、`reverse_shell`、`backdoor`、`trojan` 关键字
- [ ] 无远程控制、反弹 Shell 逻辑

### R4 — 仅允许自查自有资产
- [ ] 有所有权确认机制
- [ ] 日志记录扫描目标

### R5 — MSF 调用限制
- [ ] constants.py 的 MSF 白名单只包含 auxiliary/scanner 子路径
- [ ] 黑名单完整覆盖 exploit/payload/post/evasion/nops

### R6 — 扫描频率限制
- [ ] config.py 中有并发数和间隔控制
- [ ] 代码中有实际的频率限制逻辑

## 代码质量审查

- [ ] 所有 Python 文件有中文注释
- [ ] 所有公开方法有 docstring
- [ ] 异常捕获完善
- [ ] 无死代码或无用导入
- [ ] 类型标注完整

## 输出格式

生成 `docs/review-phase1.md`，包含：
1. 审查总结（通过/不通过）
2. 每项合规检查结果
3. 发现的问题清单（按严重程度排序）
4. 改进建议
