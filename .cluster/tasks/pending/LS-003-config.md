# LS-003: config.py — 配置管理模块

## 任务信息
- **Task ID**: LS-003
- **Phase**: Phase 1 — 项目骨架
- **分配给**: Reasonix（DeepSeek-V4，标准配置加载模式无需 GPT-5.5）
- **优先级**: P0
- **依赖**: LS-001 (base.py 接口定义)
- **输出文件**: `lightshield/config.py`

## 项目上下文

LightShield（轻盾）是一个面向初创企业 & 个人站长的开源轻量化安全自检 + 防御加固工具。
技术栈：Python 3.10+，使用 Nmap + 自研脚本 + Metasploit auxiliary/scanner 子集。

## ⚠️ 合规约束（不可违反）

1. 代码中不得包含对外攻击、漏洞利用、Payload 生成逻辑
2. 不得包含 `bind_shell`、`reverse_shell`、`backdoor`、`trojan` 等关键字
3. 项目仅允许自查自有资产，所有扫描目标必须经过所有权确认

## 接口契约

`config.py` 需要实现 `LightShieldConfig` 类，负责管理全局配置。

### 需要支持的配置项

```python
# 扫描配置
SCAN_TIMEOUT: int = 30          # 扫描超时（秒）
MAX_CONCURRENT_SCANS: int = 20  # 最大并发数（合规 R6）
SCAN_INTERVAL: float = 5.0      # 扫描间隔（合规 R6）

# MSF 配置
MSF_PATH: str = ""              # Metasploit 安装路径
MSF_WHITELIST: list[str]        # 允许的 MSF 模块前缀（合规 R5）
MSF_BLACKLIST: list[str]        # 禁止的 MSF 模块前缀（合规 R5）

# Nmap 配置
NMAP_PATH: str = "nmap"         # Nmap 可执行文件路径
NMAP_ARGS: str = "-sV -O"       # Nmap 默认参数

# 报告配置
REPORT_OUTPUT_DIR: str = "./reports"
REPORT_FORMAT: str = "markdown"  # markdown / text
REPORT_LANG: str = "zh-CN"

# 日志配置
LOG_DIR: str = "./logs"
LOG_LEVEL: str = "INFO"

# 加固配置
HARDEN_DRY_RUN: bool = True     # 加固前预览模式
HARDEN_BACKUP: bool = True      # 加固前自动备份
```

### 需要实现的功能

1. **从 YAML/JSON 文件加载配置**：支持 `lightshield.yaml` 或 `lightshield.json`
2. **环境变量覆盖**：`LS_` 前缀的环境变量可覆盖任何配置项（如 `LS_SCAN_TIMEOUT=60`）
3. **默认值**: 所有配置项都有合理默认值
4. **MSF 白名单/黑名单校验**：`validate_msf_config()` 方法，确保白名单不包含黑名单路径
5. **单例模式**：整个应用共享一个配置实例
6. **配置导出**：`to_dict()` 方法，方便传给其他模块

### 代码要求

- Python 3.10+，带完整中文注释
- 异常捕获（文件不存在、格式错误等）
- 使用 dataclass 或 Pydantic
- 不引入重型依赖（保持轻盾定位）

### 示例调用

```python
from lightshield.config import LightShieldConfig

config = LightShieldConfig()
config.load("lightshield.yaml")
config.validate_msf_config()
print(config.to_dict())
```
