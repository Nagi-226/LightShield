# Reasonix v0.0.22 — CLI + Core 测试批量生成

> **角色**：🔧 主力开发工程师 | **模型**：DeepSeek-V4 | **成本**：🟢 低
> **前置**：v0.0.21 mypy 收紧已完成（check_untyped_defs=true, 0 errors）
> **目标**：将 CLI(0%) 和 core(0%) 的测试覆盖率提升至 60%+

---

## 项目上下文

LightShield v0.2.0 已发布。当前覆盖率 61%，但 `cli.py` 和 `core.py` 为 0%（需要真实 Nmap 环境，之前无法测试）。
v0.0.22 的任务：通过 mock 所有外部依赖（Nmap/subprocess/HTTP），为 CLI 和 core 编写单元测试。

项目路径：E:/Github Project/LightShield/

---

## 合规红线

R1-R6 全部遵守。测试代码中可能引用黑名单术语（如 `is_module_allowed("exploit/...")`），这在测试中合法——合规 hook 已排除测试文件。

---

## 任务 A：tests/test_cli.py（CLI arg 解析 + 错误处理）

被测模块：`lightshield/cli.py`

### 必须覆盖的场景

**1. create_parser() — 参数解析**
- `lightshield scan 127.0.0.1` → target="127.0.0.1"
- `lightshield scan 127.0.0.1 --confirm-ownership` → confirm_ownership=True
- `lightshield quick-scan 127.0.0.1` → 子命令正确
- `lightshield harden 127.0.0.1` → 子命令正确
- `lightshield version` → 子命令正确
- `lightshield`（无参数）→ 显示 help 并 exit 0

**2. 输入校验（不依赖 Nmap）**
- `scan 192.168.1.0/24` → 拦截，exit code ≠ 0，stderr 含 "CIDR" 或 "拒绝"
- `scan "" (空字符串)` → 拦截
- `scan http://example.com` → 拦截
- `scan 127.0.0.1` → 通过（mock Nmap）

**3. 加固命令**
- `harden 127.0.0.1 --confirm-ownership` → 生成脚本（mock Nmap）
- `harden 127.0.0.1`（无 --confirm-ownership）→ 应要求交互确认（测试非交互模式下的警告）

### 技术要点
- mock `lightshield.core.LightShieldCore.run_scan` 返回假 ScanResult
- mock `lightshield.core.LightShieldCore.generate_hardening` 返回假 HardenResult
- 使用 `capsys` fixture 捕获 stdout/stderr
- 每个测试独立，不依赖真实网络或工具

---

## 任务 B：tests/test_core.py（调度器核心方法）

被测模块：`lightshield/core.py`

已有文件：`lightshield/core.py`（内嵌 `if __name__ == "__main__"` 自检块）

### 必须覆盖的场景

**1. 适配器管理**
- `register_adapter(adapter)` → 成功注册，`list_adapters()` 可见
- `register_adapter(None)` → TypeError
- 重复注册同名 adapter → `list_adapters()` 去重

**2. _validate_request() — R2 防线**
- `_validate_request("127.0.0.1")` → (True, ...)
- `_validate_request("192.168.1.0/24")` → (False, ...)
- `_validate_request("")` → (False, ...)
- `_validate_request("*.example.com")` → (False, ...)

**3. submit_scan() + get_scan_status() — v0.2.0 新增异步接口**
- `submit_scan("127.0.0.1")` → 返回 task_id（格式 "LS-YYYYMMDD-..."）
- `get_scan_status(task_id)` → 返回 dict 含 status/target/findings
- `get_scan_status("nonexistent")` → {"status": "not_found"}

**4. 合规确认**
- `_confirm_ownership("127.0.0.1")` → 返回非空字符串（所有权确认提示）
- `_validate_request` 对合法目标的拒绝原因不含敏感信息

**5. 无适配器时的行为**
- 未注册任何 adapter 时 `run_scan("127.0.0.1")` → 返回 FAILED（不是 crash）
- `list_adapters()` → 空列表

### 技术要点
- 使用 `LightShieldCore` 实例，不依赖全局状态
- mock NmapAdapter/Nmap 避免真实扫描
- 每个测试后清理 `_task_results`

---

## 代码规范

- pytest 风格，函数名 `test_xxx`
- mock 所有外部依赖（`unittest.mock.patch`）
- 中文 docstring 说明测试意图
- 每个测试函数一个断言主题
- 使用 `@pytest.mark.parametrize` 减少重复

---

## 输出

1. `tests/test_cli.py`
2. `tests/test_core.py`

完成后运行：`py -m pytest tests/test_cli.py tests/test_core.py -v`
