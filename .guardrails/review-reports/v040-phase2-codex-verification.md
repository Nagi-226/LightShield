# 三阶段审计 Phase 2  可行性边界验证报告
> **审查者**：Codex (GPT-5.5) | **日期**：2026-06-27

## 输入
- Phase 1-A：Kimi BUG报告（18项：4C/6H/8M）
- Phase 1-B：CB-GLM-5.2 结构报告（30项：4H/14M/12L）
- 验证方法：先精读两份 Phase 1 报告，再对必要触发路径读源码反证；本报告只裁决既有 48 项，不新增问题。

## 验证总览
| 来源 | 原始 | 确认原级 | 降级 | 升级 | 误报(INFO) | 去重合并 |
|------|:--:|:--:|:--:|:--:|:--:|:--:|
| Kimi | 18 | 4 | 12 | 0 | 2 | 1（与 CB-C1 同根） |
| CB-GLM-5.2 | 30 | 10 | 13 | 0 | 7 | 4（R2/L5/A5、R3/C5、R8/A1 等） |
| 独立去重合并后 | 43 | 11 | 23 | 0 | 9 | 5 |

## 最终分级清单（去重合并后）
| 等级 | 数量 | 阻塞tag? |
|------|:--:|:--:|
| 🔴 CRITICAL | 0 | 否 |
| 🟠 HIGH | 2 | 强烈建议先修，但不等同 CRITICAL 门禁 |
| 🟡 MEDIUM | 18 | v0.0.41 迭代；其中少数建议随 HIGH 顺手修 |
| 🔵 LOW | 14 | backlog |
| 💡 INFO | 9 | 不阻塞 |

## 总体裁决
- 两份 Phase 1 报告中没有发现“当前生产环境一定触发且后果严重”的 CRITICAL。
- Kimi 原 4 个 CRITICAL 均降级：触发条件存在，但当前产品是本地 CLI/单用户 Web 面板，且多数需要非正常输入或并发边界，不满足“必炸”。
- 需要优先修的 HIGH 仅保留 2 项：CLI closed-loop 前后扫描范围不一致、HostExecutor 超时未清理进程树。
- Web/Core 分层问题成立，但更像 v0.0.41 专项治理，不应按 v0.0.40 tag 阻塞项处理。

## 逐项验证

### [Kimi-C-001] `_task_results` 多线程无锁
| 验证维度 | 结论 |
|------|------|
| Q1 触发条件 | Web 异步扫描轮询与后台线程并发读写 `_task_results` / `_TaskInfo`；单用户面板下概率低，多用户/压力轮询下更高。 |
| Q2 现有防御 | 无显式锁；但当前没有遍历 dict 的路径，CPython GIL 使单次 dict get/set 不会轻易数据损坏，主要风险是状态可见性/丢失中间态。 |
| Q3 成本 vs 风险 | 加 `RLock` 成本低；不修最坏是状态短暂不一致或未来扩展时踩雷，不是当前必现崩溃。 |
| **最终等级** | 🟡 MEDIUM（由 CRITICAL 降级） |
| **理由** | 触发路径成立，但“dict 并发写必炸/数据损坏”论据过强；当前无迭代读写和单用户部署降低风险。 |

### [Kimi-C-002] CLI 交互确认未处理 `EOFError`
| 验证维度 | 结论 |
|------|------|
| Q1 触发条件 | 非交互 stdin/CI/管道执行 `scan` 或 `harden` 且未传 `--confirm-ownership`；自动化场景会触发，日常手动 CLI 不触发。 |
| Q2 现有防御 | `_ensure_ownership()` 在 `run_scan_command`/`run_harden_command` 外层 try 之前调用，`EOFError` 会直接冒泡；没有优雅错误。 |
| Q3 成本 vs 风险 | 修复只需捕获 `EOFError` 返回 False；不修最坏是非交互任务堆栈退出，不会绕过确认执行。 |
| **最终等级** | 🟡 MEDIUM（由 CRITICAL 降级） |
| **理由** | 是真实自动化 UX/稳定性 bug，但不是生产必炸，也不是安全绕过。 |

### [Kimi-C-003] Web 登录接口非字符串凭证触发 `TypeError`
| 验证维度 | 结论 |
|------|------|
| Q1 触发条件 | 未认证请求向 `/api/login` 提交 `null`/数字等 JSON；攻击者或异常客户端可触发。 |
| Q2 现有防御 | `request.get_json(silent=True)` 与空值检查能挡住 `null`，但数字/对象等 truthy 非字符串仍可进入 `secrets.compare_digest()`。 |
| Q3 成本 vs 风险 | 强转/类型校验成本极低；不修最坏是局部 500 与日志噪声，本地单用户面板降低暴露面。 |
| **最终等级** | 🟡 MEDIUM（由 CRITICAL 降级） |
| **理由** | 可达且应修，但属于输入健壮性/小型 DoS，不满足 CRITICAL。 |

### [Kimi-C-004] Web `scan_types` 类型未校验
| 验证维度 | 结论 |
|------|------|
| Q1 触发条件 | 已登录用户或脚本向 `/api/scan` 传字符串/整数等非 `list[str]`；前端正常路径固定传合法数组。 |
| Q2 现有防御 | Web 仅取 `data.get("scan_types")`，core 对字符串会按字符迭代、对整数会 `len()` 抛错；没有类型门。 |
| Q3 成本 vs 风险 | 增加 list+元素类型校验成本低；不修最坏是 500 或扫描能力被错误解释。 |
| **最终等级** | 🟡 MEDIUM（由 CRITICAL 降级） |
| **理由** | 真实 API 健壮性问题，但当前是登录后内部 API，正常前端不会触发。 |

### [Kimi-H-005] `generate_hardening` 对 `OSPlatform` 调 `.lower()`
| 验证维度 | 结论 |
|------|------|
| Q1 触发条件 | 直接调用 `generate_hardening(os_platform=OSPlatform.LINUX)`；CLI/Web/closed-loop 当前多数传字符串或 `.value`。 |
| Q2 现有防御 | `run_harden_closed_loop` 内部能接受枚举并传 `.value` 给 `generate_hardening`；但 `generate_hardening` 自身签名/实现不兼容枚举。 |
| Q3 成本 vs 风险 | 修复 1-3 行；不修会让外部 Python 调用者踩 `AttributeError`，当前主路径概率不高。 |
| **最终等级** | 🟡 MEDIUM（由 HIGH 降级；与 CB-C1 合并） |
| **理由** | 根因是 os_platform 类型契约不统一，真实但非当前 CLI/Web 主路径高频故障。 |

### [Kimi-H-006] APPLY 可显式指定 `backend="docker"`
| 验证维度 | 结论 |
|------|------|
| Q1 触发条件 | 直接调用 `run_harden_closed_loop(mode="apply", backend="docker")`；CLI/Web 不暴露 backend 参数。 |
| Q2 现有防御 | `backend is None` 时会按 mode 选择 host，但显式 docker 不会被覆盖，`_run_apply_and_verify` 会选择 DockerSandboxExecutor。 |
| Q3 成本 vs 风险 | 修复成本极低；不修会让 direct API 的 APPLY 语义失真，但普通用户入口不可达。 |
| **最终等级** | 🟡 MEDIUM（由 HIGH 降级） |
| **理由** | 契约漏洞成立，安全语义重要；但触发需要绕过 CLI/Web 直接传参，未达到 HIGH 的“不罕见”条件。 |

### [Kimi-H-007] CLI 闭环前后扫描范围不一致
| 验证维度 | 结论 |
|------|------|
| Q1 触发条件 | `lightshield harden <target> --closed-loop --apply`；当前 CLI 先做资产扫描+规则匹配，闭环 after scan 仍使用 `scan_types=None` 下的 `run_vuln_scan()`。 |
| Q2 现有防御 | `pre_generated` 已修复“before 重新扫描”问题，但 after scan 仍与基线能力集不一致，可能引入 false regressed。 |
| Q3 成本 vs 风险 | 需要保存并传入原 scan_types 或在 pre_generated 中带扫描范围；不修会误判加固效果，是 v0.0.40 核心闭环可信度问题。 |
| **最终等级** | 🟠 HIGH（确认原级） |
| **理由** | H-002/pre_generated 只解决一半；APPLY 核心路径仍可能得出错误验证结论。 |

### [Kimi-H-008] `get_repository` 单例忽略后续 backend 参数
| 验证维度 | 结论 |
|------|------|
| Q1 触发条件 | 同一 Python 进程内先 `get_repository("json")` 再 `get_repository("sqlite", db_url=...)`，常见于测试、嵌入式调用或初始化顺序变化。 |
| Q2 现有防御 | 全局 `_repository` 命中后直接返回，没有按 backend/db_url 缓存；无 reset 钩子被业务路径自动使用。 |
| Q3 成本 vs 风险 | 按 key 缓存或提供 reset 成本中低；不修最坏是读写错误后端、测试污染。 |
| **最终等级** | 🟡 MEDIUM（由 HIGH 降级） |
| **理由** | 真实状态生命周期缺陷，但默认 CLI/Web 均倾向 sqlite，触发依赖同进程混用。 |

### [Kimi-H-009] HostExecutor 超时只杀主进程不杀进程树
| 验证维度 | 结论 |
|------|------|
| Q1 触发条件 | APPLY 脚本启动子进程/后台服务/包管理器，主脚本超时；真实加固脚本扩展后并不罕见。 |
| Q2 现有防御 | 使用 `subprocess.run(timeout=...)`，未创建进程组/job object，也未递归清理；错误信息声称进程已终止但只保证主进程。 |
| Q3 成本 vs 风险 | 跨平台进程树清理成本中等；不修最坏是 orphan 子进程继续改系统或占资源。 |
| **最终等级** | 🟠 HIGH（确认原级） |
| **理由** | APPLY 是高风险真机路径，超时清理语义必须可信；这里条件满足后后果严重。 |

### [Kimi-H-010] 版本 fallback 使用字符串字典序比较
| 验证维度 | 结论 |
|------|------|
| Q1 触发条件 | 需要 `_parse_semver()` 抛 `ValueError/IndexError` 后进入 fallback；当前实现对任意字符串都吞掉单段解析错误并补 0，fallback 基本不可达。 |
| Q2 现有防御 | `_parse_semver()` 内部 `try/except ValueError` 使非数字段变 0，不会因 `10.0`/`2.0` 这类例子进入字典序比较。 |
| Q3 成本 vs 风险 | 删除 fallback 或改保守返回成本低；不修当前没有报告所述触发面。 |
| **最终等级** | 💡 INFO（由 HIGH 降级为误报/不可达路径） |
| **理由** | 报告举例针对 fallback，但当前 parser 设计让 fallback 对正常字符串不可达；这不是 D1/D2 死语句调用点。 |

### [Kimi-M-011] CLI 历史保存异常静默吞掉
| 验证维度 | 结论 |
|------|------|
| Q1 触发条件 | SQLite/JSON 历史不可写、磁盘满、序列化异常；扫描主体已完成后触发。 |
| Q2 现有防御 | `except Exception: pass`，没有 verbose/log 提示。 |
| Q3 成本 vs 风险 | 打 warning 成本极低；不修影响可观测性，不影响扫描结果本身。 |
| **最终等级** | 🔵 LOW（由 MEDIUM 降级） |
| **理由** | 是异常处理风格问题，不是功能主路径失败。 |

### [Kimi-M-012] CLI `--output-dir` 未限制目录穿越
| 验证维度 | 结论 |
|------|------|
| Q1 触发条件 | 本地 CLI 用户显式指定 `../`、绝对路径或任意输出目录。 |
| Q2 现有防御 | 无限制；但这是本地工具的显式输出参数，用户本来拥有本机写权限。 |
| Q3 成本 vs 风险 | 可加确认/文档；强行限制可能破坏合法用例。 |
| **最终等级** | 💡 INFO（由 MEDIUM 降级） |
| **理由** | 在当前本地 CLI 威胁模型下属于刻意可配置输出位置，不应当作目录穿越漏洞。 |

### [Kimi-M-013] 报告归档后 CLI 仍打印旧路径
| 验证维度 | 结论 |
|------|------|
| Q1 触发条件 | 开启 report auto archive 后 `_run_hooks()` 移动报告文件，用户按前面打印的路径查找。 |
| Q2 现有防御 | `archive_report()` 返回新路径，但 CLI 没有回写/重新打印主路径。 |
| Q3 成本 vs 风险 | 更新返回路径成本低；不修会造成用户找不到报告的确定性 UX bug。 |
| **最终等级** | 🟡 MEDIUM（确认原级） |
| **理由** | 正常成功路径可触发，虽非安全问题但影响交付物可发现性。 |

### [Kimi-M-014] Web 登录失败计数器无锁
| 验证维度 | 结论 |
|------|------|
| Q1 触发条件 | Flask 多线程下同 IP 并发失败登录；暴力请求才明显。 |
| Q2 现有防御 | `_login_failures` 无锁，`+= 1` 非原子；但单用户本地面板、单进程内存计数降低实际风险。 |
| Q3 成本 vs 风险 | 加锁成本低；不修最坏是少计几次失败，非持久认证绕过。 |
| **最终等级** | 🔵 LOW（由 MEDIUM 降级） |
| **理由** | 风险成立但依赖并发攻击，当前部署暴露面小。 |

### [Kimi-M-015] 加固脚本部分写入失败残留文件
| 验证维度 | 结论 |
|------|------|
| Q1 触发条件 | harden 脚本写入成功、rollback 写入失败，或反向；磁盘/权限/中断可触发。 |
| Q2 现有防御 | 异常时返回 FAILED，但没有清理已写成功的半套文件。 |
| Q3 成本 vs 风险 | 清理临时文件或原子写成本中等偏低；不修可能让用户误执行无回滚脚本。 |
| **最终等级** | 🟡 MEDIUM（确认原级） |
| **理由** | 失败路径虽不高频，但与加固/回滚安全语义直接相关。 |

### [Kimi-M-016] `_safe_dirname` 未过滤 `.` / `..` / NUL
| 验证维度 | 结论 |
|------|------|
| Q1 触发条件 | 传入异常 target 给独立 `archive_report()`；主扫描 target 通常已被 R2 校验。 |
| Q2 现有防御 | 替换了常见路径分隔/Windows 非法字符，但未处理点目录和 NUL；文件系统异常多会被上层静默返回 None。 |
| Q3 成本 vs 风险 | 增加几行过滤即可；不修主要是边界输入下归档失败/路径混乱。 |
| **最终等级** | 🔵 LOW（由 MEDIUM 降级） |
| **理由** | 工具函数边界健壮性问题，主调用链已有 target 约束。 |

### [Kimi-M-017] MSF `-x` 选项值含空格解析风险
| 验证维度 | 结论 |
|------|------|
| Q1 触发条件 | 白名单 MSF scanner 的自定义 option 值含空格；RHOSTS 被过滤，常规选项多为简单值。 |
| Q2 现有防御 | key 有白名单正则，value 禁 `;`/换行，但不处理空格引用；不会形成 shell 注入，因为 subprocess 使用 argv。 |
| Q3 成本 vs 风险 | 使用 resource 文件更稳；不修最坏是 msfconsole set 参数失败或值截断。 |
| **最终等级** | 🔵 LOW（由 MEDIUM 降级） |
| **理由** | 主要是 MSF 参数兼容性，不是命令注入；触发面较窄。 |

### [Kimi-M-018] `_cleanup_old` 按目录 mtime 清理
| 验证维度 | 结论 |
|------|------|
| Q1 触发条件 | 长期开启归档清理并跨日复用目录，目录 mtime 被新文件刷新。 |
| Q2 现有防御 | 无按目录名日期解析；但只影响保留策略精确性。 |
| Q3 成本 vs 风险 | 按 `YYYY-MM/DD` 解析成本低；不修最坏是旧报告保留过久。 |
| **最终等级** | 🔵 LOW（由 MEDIUM 降级） |
| **理由** | 维护/磁盘占用问题，非功能正确性核心路径。 |

### [CB-D1] `_match_service_fingerprint` 死语句
| 验证维度 | 结论 |
|------|------|
| Q1 触发条件 | 代码阅读/维护时触发；运行时只是无效读取规则字段。 |
| Q2 现有防御 | 不影响后续基于 `match_vuln_type` 的实际匹配；但误导读者认为 service/auth_result 生效。 |
| Q3 成本 vs 风险 | 删除或补全匹配成本低；不修增加规则语义误解。 |
| **最终等级** | 🟡 MEDIUM（确认原级） |
| **理由** | 死语句本身不炸，但位于规则引擎，容易导致规则作者误配。 |

### [CB-D2] `_match_header` 死语句
| 验证维度 | 结论 |
|------|------|
| Q1 触发条件 | header/pattern 规则被配置后，代码实际只要服务名为 http 就返回发现。 |
| Q2 现有防御 | 无；当前实现未使用 header/pattern。 |
| Q3 成本 vs 风险 | 删除字段读取或实现真实匹配成本中等；不修可能让 header 规则语义失真。 |
| **最终等级** | 🟡 MEDIUM（确认原级） |
| **理由** | 与 D1 类似，但 `_match_header` 的规则语义偏差更明显。 |

### [CB-D3] `JsonFileRepository` 当前未使用
| 验证维度 | 结论 |
|------|------|
| Q1 触发条件 | 只有直接选择 `backend="json"` 或历史兼容路径会使用。 |
| Q2 现有防御 | 工厂分支仍存在，不能证明“死代码”；可作为兼容/教学后端保留。 |
| Q3 成本 vs 风险 | 标 deprecated 可选；删除可能破坏旧调用。 |
| **最终等级** | 💡 INFO（由 LOW 降级） |
| **理由** | 未被主路径使用不等于问题，且与 H-008 的 singleton 行为不同。 |

### [CB-R1] `_reconstruct_findings` 两处重复
| 验证维度 | 结论 |
|------|------|
| Q1 触发条件 | Web routes/pages 任一处字段变更时另一处忘改；当前两处逻辑几乎一致。 |
| Q2 现有防御 | 无公共 from_dict；但重复范围小且字段直映射。 |
| Q3 成本 vs 风险 | 提取 classmethod 成本低；不修是维护漂移风险。 |
| **最终等级** | 🟡 MEDIUM（由 HIGH 降级） |
| **理由** | 真实重复，但不构成当前必须立即重构的 HIGH。 |

### [CB-R2] `db_url` + repository 获取模式重复
| 验证维度 | 结论 |
|------|------|
| Q1 触发条件 | Web 多页面/路由访问 scan/report/harden 时重复走同一 fallback/工厂模式。 |
| Q2 现有防御 | 依赖 config 与 `get_repository` 单例；没有统一 helper。 |
| Q3 成本 vs 风险 | 抽 `_get_repo()` 或 core 门面成本中等；不修主要是维护漂移，兼与 L5/A5 重复。 |
| **最终等级** | 🟡 MEDIUM（由 HIGH 降级；与 L5/A5 合并治理） |
| **理由** | 属于 Web-Core 边界债务，不是 tag 前必须修的运行时 bug。 |

### [CB-R3] 风险统计逻辑重复
| 验证维度 | 结论 |
|------|------|
| Q1 触发条件 | 风险等级枚举/统计字段新增时 RuleEngine 与 ReportGenerator 可能漂移。 |
| Q2 现有防御 | 两处当前键集合一致；测试基线绿。 |
| Q3 成本 vs 风险 | 提取 helper 成本低；不修短期影响小。 |
| **最终等级** | 🔵 LOW（由 MEDIUM 降级；与 C5 合并） |
| **理由** | 纯重复逻辑，当前无行为偏差证据。 |

### [CB-R4] 严重度排序字典重复
| 验证维度 | 结论 |
|------|------|
| Q1 触发条件 | 新增 severity 或排序策略调整时多处需同步。 |
| Q2 现有防御 | 当前值一致或接近一致，但分散在 engine/pdf/cli。 |
| Q3 成本 vs 风险 | 提取常量成本低；不修会造成展示/去重排序不一致。 |
| **最终等级** | 🟡 MEDIUM（确认原级） |
| **理由** | 影响跨模块一致性，比普通重复更接近契约常量，应迭代修。 |

### [CB-R5] `sys.path.insert` 兜底重复
| 验证维度 | 结论 |
|------|------|
| Q1 触发条件 | 直接 `python file.py` 自检路径；包安装运行不依赖。 |
| Q2 现有防御 | 属于脚本自检兜底，当前 `rg` 看到数量少于报告称 11 处但模式存在。 |
| Q3 成本 vs 风险 | 统一 `python -m` 成本中等；不修生产影响很低。 |
| **最终等级** | 🔵 LOW（由 MEDIUM 降级） |
| **理由** | 自检便利性债务，不是运行时结构风险。 |

### [CB-R6] 适配器计时模式重复
| 验证维度 | 结论 |
|------|------|
| Q1 触发条件 | 新增/修改适配器时重复写计时代码。 |
| Q2 现有防御 | 重复很简单，语义清晰。 |
| Q3 成本 vs 风险 | 装饰器可做但收益有限；不修维护成本低。 |
| **最终等级** | 🔵 LOW（确认原级） |
| **理由** | 可维护性 backlog。 |

### [CB-R7] `ScanResult` 失败构造重复
| 验证维度 | 结论 |
|------|------|
| Q1 触发条件 | 多适配器失败路径。 |
| Q2 现有防御 | 当前重复构造字段简单，未见字段缺失导致 bug。 |
| Q3 成本 vs 风险 | `ScanResult.failed()` 可改善一致性；不修影响小。 |
| **最终等级** | 🔵 LOW（确认原级） |
| **理由** | 标准低优先级重复。 |

### [CB-R8] subprocess 异常处理样板重复
| 验证维度 | 结论 |
|------|------|
| Q1 触发条件 | 多适配器运行外部命令时各自处理 timeout/FileNotFound。 |
| Q2 现有防御 | 各适配器均有基本结构化失败；但 host/docker 等特殊语义不完全适合一个 helper。 |
| Q3 成本 vs 风险 | 抽象成本中等，误抽象可能隐藏差异；不修是维护债务。 |
| **最终等级** | 🔵 LOW（确认原级；与 A1 合并） |
| **理由** | 与 Kimi-M011 只属于广义异常风格相关，不是同一个根因。 |

### [CB-L1] Web 直接 import adapters/rules/report/repository
| 验证维度 | 结论 |
|------|------|
| Q1 触发条件 | Web 页面/API 访问报告、推荐、下载等路径时体现分层穿透。 |
| Q2 现有防御 | 项目是本地内部 Web 面板，当前没有循环依赖或测试失败；core 门面不足是事实。 |
| Q3 成本 vs 风险 | 重构 core 门面成本较高；不修短期不炸，长期耦合上升。 |
| **最终等级** | 🟡 MEDIUM（由 HIGH 降级） |
| **理由** | 系统性架构债务成立，但不应阻塞 v0.0.40 tag。 |

### [CB-L2] Web 直接调用 `RuleEngine.recommend_hardening`
| 验证维度 | 结论 |
|------|------|
| Q1 触发条件 | harden 页面渲染推荐时触发。 |
| Q2 现有防御 | 逻辑可用；只是职责落在 Web 层。 |
| Q3 成本 vs 风险 | 需要新增 core 门面；不修是分层债务。 |
| **最终等级** | 🟡 MEDIUM（由 HIGH 降级） |
| **理由** | 当前阶段可接受，v0.0.41 应治理。 |

### [CB-L3] Web 从 dict 重建领域对象
| 验证维度 | 结论 |
|------|------|
| Q1 触发条件 | Web 从 repository 读取 raw_result 后展示推荐/报告。 |
| Q2 现有防御 | `_reconstruct_findings` 逻辑可工作；重复与字段漂移风险存在。 |
| Q3 成本 vs 风险 | 抽 from_dict/core load_scan 成本中等；不修短期可运行。 |
| **最终等级** | 🟡 MEDIUM（由 HIGH 降级） |
| **理由** | 和 R1 相关但不完全重复；属于 v0.0.41 边界治理。 |

### [CB-L4] `scanners/port_scanner.py` 直接依赖 `NmapAdapter`
| 验证维度 | 结论 |
|------|------|
| Q1 触发条件 | 使用 port_scanner wrapper。 |
| Q2 现有防御 | 该模块本身就是 Nmap 便捷封装，硬依赖可解释。 |
| Q3 成本 vs 风险 | 注入 BaseAdapter 可改善测试性；不修影响低。 |
| **最终等级** | 🔵 LOW（由 MEDIUM 降级） |
| **理由** | 更像 wrapper 设计选择，不是明显分层破坏。 |

### [CB-L5] Web 直接操作 repository
| 验证维度 | 结论 |
|------|------|
| Q1 触发条件 | dashboard/report/harden/verify 多处读取扫描历史。 |
| Q2 现有防御 | 逻辑可运行，但重复 db_url fallback 与单例工厂耦合。 |
| Q3 成本 vs 风险 | 与 R2 一起抽 helper/core 门面；不修长期耦合。 |
| **最终等级** | 🟡 MEDIUM（确认原级；并入 R2/A5 治理） |
| **理由** | 中等级分层债务成立。 |

### [CB-L6] CLI 顶层编排过多
| 验证维度 | 结论 |
|------|------|
| Q1 触发条件 | CLI harden/scan 命令串联 core、RuleEngine、ReportGenerator。 |
| Q2 现有防御 | CLI 作为最顶层入口承担编排职责是合理的；当前无跨层运行故障。 |
| Q3 成本 vs 风险 | 可抽 full_pipeline，但收益取决于未来 API 复用。 |
| **最终等级** | 💡 INFO（由 LOW 降级） |
| **理由** | 这是可接受的应用入口编排，不应列为问题。 |

### [CB-A1] subprocess 实现细节泄露到多个适配器
| 验证维度 | 结论 |
|------|------|
| Q1 触发条件 | 外部命令适配器都直接用 subprocess。 |
| Q2 现有防御 | 各适配器对命令参数和错误有各自语义，统一抽象未必简单。 |
| Q3 成本 vs 风险 | 与 R8 合并评估；不修主要是重复维护。 |
| **最终等级** | 🔵 LOW（由 MEDIUM 降级；与 R8 合并） |
| **理由** | 抽象建议合理，但不是当前缺陷。 |

### [CB-A2] 脚本文件命名规则泄露到 Web
| 验证维度 | 结论 |
|------|------|
| Q1 触发条件 | Web 下载 harden/rollback 脚本。 |
| Q2 现有防御 | Web 需要白名单下载文件名；目前硬编码模式虽耦合但也是安全过滤点。 |
| Q3 成本 vs 风险 | core/harden 暴露 list_scripts 更干净；不修维护影响有限。 |
| **最终等级** | 🔵 LOW（由 MEDIUM 降级） |
| **理由** | 抽象泄露成立，但安全上白名单比放宽更好。 |

### [CB-A3] Docker 默认常量放在全局 constants
| 验证维度 | 结论 |
|------|------|
| Q1 触发条件 | 读取/维护 constants 时看到 sandbox 实现参数。 |
| Q2 现有防御 | 常量集中是常见做法，未造成跨层调用。 |
| Q3 成本 vs 风险 | 移动成本低但收益小；不修无实际风险。 |
| **最终等级** | 💡 INFO（由 LOW 降级） |
| **理由** | 可接受的配置常量组织。 |

### [CB-A4] `ScanResult.to_dict()` 硬编码 `adapter_name="merged"`
| 验证维度 | 结论 |
|------|------|
| Q1 触发条件 | 所有 ScanResult 序列化。 |
| Q2 现有防御 | 当前 ScanResult 是 core 合并结果的统一结构，`merged` 是刻意默认；单 adapter 名称没有字段承载。 |
| Q3 成本 vs 风险 | 增字段可改善表达；不修暂无错误行为。 |
| **最终等级** | 💡 INFO（由 LOW 降级） |
| **理由** | 设计简化，不是漏洞或 bug。 |

### [CB-A5] Web 层硬编码 `data/lightshield.db` fallback
| 验证维度 | 结论 |
|------|------|
| Q1 触发条件 | config.db_url 为空时 Web 多处回退默认路径。 |
| Q2 现有防御 | 当前默认配置允许空 db_url；fallback 确保可用。 |
| Q3 成本 vs 风险 | 应并入 R2/L5 抽 helper 或 config 默认值；单独看风险低。 |
| **最终等级** | 🔵 LOW（由 MEDIUM 降级；与 R2/L5 合并） |
| **理由** | 是重复/分层症状，不是独立高风险问题。 |

### [CB-A6] `_substitute` 暴露模板占位格式
| 验证维度 | 结论 |
|------|------|
| Q1 触发条件 | Hardener 子类使用 `{port}`/`{target}` 模板替换。 |
| Q2 现有防御 | 基类定义模板契约是合理抽象，子类共享该约定。 |
| Q3 成本 vs 风险 | 补 docstring 即可；不修无实际问题。 |
| **最终等级** | 💡 INFO（由 LOW 降级） |
| **理由** | 这是刻意设计的模板方法辅助，不是抽象泄露缺陷。 |

### [CB-C1] `os_platform` 类型契约不一致
| 验证维度 | 结论 |
|------|------|
| Q1 触发条件 | `run_harden_closed_loop` 与 `generate_hardening` 分别接受/处理 str 和 OSPlatform，直接复用时可能错配。 |
| Q2 现有防御 | closed-loop 内部当前传 `.value`，主路径可用；直接 public API 仍不一致。 |
| Q3 成本 vs 风险 | 统一签名/转换成本低；不修会继续产生 H-005 类问题。 |
| **最终等级** | 🟡 MEDIUM（确认原级；与 Kimi-H-005 同根） |
| **理由** | 接口契约问题成立，但主路径已部分规避。 |

### [CB-C2] mode/verdict/overall 使用裸字符串
| 验证维度 | 结论 |
|------|------|
| Q1 触发条件 | 新增闭环状态或拼写变更时。 |
| Q2 现有防御 | 当前字符串集合集中在 closed_loop/verify/core，测试覆盖基线绿。 |
| Q3 成本 vs 风险 | 引入 Enum 成本中等；不修主要是未来拼写漂移。 |
| **最终等级** | 🔵 LOW（由 MEDIUM 降级） |
| **理由** | 类型改进建议，不是当前缺陷。 |

### [CB-C3] `config.to_dict()` 缺 v0.0.40 新字段
| 验证维度 | 结论 |
|------|------|
| Q1 触发条件 | 调用 `config.to_dict()` 导出/展示配置，期望包含 bark/report_auto_archive/web/db_url 等新字段。 |
| Q2 现有防御 | `_update_from_dict` 用 dataclasses 字段较完整；`to_dict` 手写且滞后。运行时读取 config 属性不受影响。 |
| Q3 成本 vs 风险 | 改为 dataclasses 遍历成本低；不修导致序列化/诊断不完整。 |
| **最终等级** | 🟡 MEDIUM（确认原级） |
| **理由** | 不是主运行 bug，但配置导出契约确实不完整。 |

### [CB-C4] `report_output_dir` 与 `output_dir` 命名不一致
| 验证维度 | 结论 |
|------|------|
| Q1 触发条件 | 阅读/调用不同层 API 时看到不同参数名。 |
| Q2 现有防御 | config 字段强调报告目录，函数参数使用通用 output_dir，语境不同可接受。 |
| Q3 成本 vs 风险 | 统一命名会带来兼容改动；不修无实际风险。 |
| **最终等级** | 💡 INFO（由 LOW 降级） |
| **理由** | 命名差异可解释，不值得作为缺陷跟踪。 |

### [CB-C5] 风险统计返回结构重复
| 验证维度 | 结论 |
|------|------|
| Q1 触发条件 | 同 R3，新增字段时可能漂移。 |
| Q2 现有防御 | 当前结构一致。 |
| Q3 成本 vs 风险 | 与 R3 合并抽公共函数；不修影响低。 |
| **最终等级** | 🔵 LOW（确认原级；与 R3 合并） |
| **理由** | 属于 R3 的契约层表述，非独立问题。 |

### [CB-C6] `findings` 语义多义
| 验证维度 | 结论 |
|------|------|
| Q1 触发条件 | 维护者区分 adapter findings、rule findings、merged findings 时。 |
| Q2 现有防御 | 类型同为 `list[VulnFinding]`，上下文变量名如 `rule_findings/all_findings` 已部分区分。 |
| Q3 成本 vs 风险 | 引入类型别名/docstring 成本低；不修可读性风险大于运行风险。 |
| **最终等级** | 🔵 LOW（由 MEDIUM 降级） |
| **理由** | 语义异味成立，但没有当前行为错误证据。 |

### [CB-C7] `ScanResult.findings` 使用前向引用字符串
| 验证维度 | 结论 |
|------|------|
| Q1 触发条件 | 静态阅读 dataclass 定义。 |
| Q2 现有防御 | `from __future__ import annotations` 下前向引用合法，且 VulnFinding 同文件稍后定义。 |
| Q3 成本 vs 风险 | 无需修；调整定义顺序收益为零。 |
| **最终等级** | 💡 INFO（由 LOW 降级） |
| **理由** | Python 常见合法写法，不是问题。 |

## 跨报告关联分析

### 关联组 1: os_platform 类型不一致
- Kimi H-005 (`generate_hardening` 对枚举 `.lower()` 崩溃)
- CB-GLM-5.2 C1 (`run_harden_closed_loop` vs `generate_hardening` 签名不一致)
- **关联判断**: 同一根因。根因是 public API 对 `os_platform` 的输入契约没有统一到 `OSPlatform` 或统一 normalization helper。最终按 1 个 MEDIUM 治理项计入去重。

### 关联组 2: 引擎版本比较 + 死代码
- Kimi H-010（字符串字典序 fallback）
- CB-GLM-5.2 D1/D2（`_match_service_fingerprint` / `_match_header` 死语句）
- **关联判断**: 非同一问题。D1/D2 是规则字段读取后未使用；H-010 指向 `_version_affected` fallback。当前 fallback 基本不可达，因此 H-010 记 INFO，D1/D2 仍按 MEDIUM 维护。

### 关联组 3: 异常处理风格
- Kimi M-011（CLI 历史保存静默吞异常）
- CB-GLM-5.2 R8（subprocess 异常处理样板重复）
- **关联判断**: 不是同一根因，只是同属“异常处理一致性”主题。M-011 是可观测性缺失；R8 是外部命令调用重复抽象。

### 关联组 4: Web repository/db_url 分层债务
- CB R2、L5、A5
- **关联判断**: 同一治理域。R2 是重复模式，L5 是分层违规，A5 是 fallback 细节泄露；建议一次性抽 `web` helper 或 core 门面。

### 关联组 5: 风险统计重复
- CB R3、C5
- **关联判断**: 同一重复逻辑的两个表述，按 LOW 合并。

### 关联组 6: subprocess 抽象重复
- CB R8、A1
- **关联判断**: 高度重叠；按 LOW 合并，HostExecutor 进程树问题（Kimi H-009）单独保持 HIGH，因为它是具体安全语义缺陷。

## 修复路线图

### 🔴 阻塞 tag v0.0.40（必须立即修）
- [ ] 无。当前 48 项中没有保留 CRITICAL。

### 🟠 v0.0.40 建议修（可合入但尽快补）
- [ ] Kimi-H-007：闭环 APPLY 的 after scan 必须与 before scan 使用同一能力集；`pre_generated` 应携带并复用 scan_types。
- [ ] Kimi-H-009：HostExecutor 超时改为跨平台进程树清理；错误信息需与实际行为一致。

### 🟡 v0.0.40 可顺手修 / v0.0.41 优先
- [ ] 输入类型健壮性：C-002/C-003/C-004，处理 EOFError、登录字段类型、scan_types 类型。
- [ ] 闭环 API 契约：H-005/CB-C1、H-006，统一 os_platform normalization，APPLY 强制覆盖 backend=host。
- [ ] 持久化/输出一致性：H-008、M-013、M-015、CB-C3。
- [ ] 规则引擎语义：CB-D1/D2、CB-R4。
- [ ] Web-Core 边界专项：CB-R1/R2/L1/L2/L3/L5/A5。

### 🔵 Backlog
- [ ] 异常/日志可观测性：M-011、M-014、M-016、M-017、M-018。
- [ ] 重复逻辑整理：CB-R3/R5/R6/R7/R8/A1/C5/C6。
- [ ] 小型抽象泄露/命名整理：CB-L4/A2/C2。

### 💡 不建议作为缺陷修复
- [ ] Kimi-H-010：当前 fallback 不可达；如要改善版本比较，应另开“语义版本解析质量”任务，而不是按本报告描述修字典序 fallback。
- [ ] Kimi-M-012：本地 CLI `--output-dir` 是显式用户控制，不按目录穿越漏洞处理。
- [ ] CB-D3/L6/A3/A4/A6/C4/C7：设计选择或合法写法，最多补文档。

## 对两份 Phase 1 报告的审查评价
- Kimi BUG 报告质量：执行路径追踪较强，发现了 H-007、H-009、M-013、M-015 等真实问题；但 CRITICAL 标准偏宽，对 CPython 并发、CLI 非交互、内部 Web API 异常输入的生产触发概率估计过高。
- CB-GLM-5.2 结构报告质量：全局结构视角有价值，Web-Core 边界债务判断准确；但 HIGH 过多，把 v0.0.41 架构治理项提升为 tag 前风险，且部分条目互相重叠，应合并成专项。

## 最终结论
- [x] 通过，可合入 + tag v0.0.40 + push（无 CRITICAL；但建议先修 2 个 HIGH 可显著提升闭环可信度）
- [ ] 有条件通过（N 项需修复后合入）
- [ ] 驳回
