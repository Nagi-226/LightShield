# LightShield Nuclei 模板库

本目录存放 LightShield 精选的安全检测 Nuclei 模板。

## 安全标签策略（R1 防线）

所有模板必须满足以下标签安全策略：

### 允许的标签（白名单）

| 标签 | 用途 | 示例 |
|------|------|------|
| `detection` | 版本/服务检测 | 检测 nginx 版本、PHP 版本 |
| `discovery` | 服务发现 | 发现开放的 API 端点 |
| `tech` | 技术栈识别 | 识别 WordPress/Django 等框架 |
| `config` | 配置检测 | 检查安全头、CORS 配置 |
| `exposure` | 暴露面检测 | 检测 .git 泄露、备份文件暴露 |
| `enum` | 枚举 | 枚举公开资源 |
| `misconfig` | 错误配置 | 检测默认密码、不安全的配置 |
| `token-spray` | Token 喷洒（仅检测） | GitHub token 泄露检测 |

### 禁止的标签（黑名单）

以下标签的模板**不得**放入本目录：`exploit`, `intrusive`, `attack`, `dos`, `fuzz`, `bruteforce`, `sqli`, `xss`, `rce`, `lfi`, `ssrf`, `injection`, `file-upload`, `code-injection`, `command-injection`, `deserialization`

## 如何添加模板

### 从 Nuclei 官方模板库精选

```bash
# 1. 克隆官方模板库（如果已有则跳过）
git clone https://github.com/projectdiscovery/nuclei-templates.git /tmp/nuclei-templates

# 2. 筛选安全标签模板（示例）
cd /tmp/nuclei-templates
for t in $(grep -rl "detection\|discovery\|tech\|config\|exposure\|misconfig" http/); do
    # 检查是否包含禁止标签
    if ! grep -q "exploit\|sqli\|xss\|rce\|dos\|fuzz" "$t"; then
        echo "Safe: $t"
    fi
done
```

### 手动编写模板

参考 [Nuclei 模板编写指南](https://docs.projectdiscovery.io/templates/introduction)，
确保 `info.tags` 仅包含白名单标签：

```yaml
id: example-detection
info:
  name: Example Service Detection
  author: lightshield
  severity: info
  tags: [tech, detection]  # ← 仅使用白名单标签
  description: Detects example service version

requests:
  - method: GET
    path:
      - "{{BaseURL}}"
    matchers:
      - type: word
        words:
          - "X-Powered-By: Example"
```

## 注意事项

1. **所有模板必须经过标签安全校验**：`is_template_safe(tags)` 返回 `True` 才可放入
2. **不包含硬编码的凭证或敏感信息**
3. **仅针对单目标检测**，不包含批量扫描逻辑
4. **请求频率合理**，不对目标造成压力
5. **本目录中的模板由 LightShield 适配器自动加载**

## 当前状态

本目录为模板占位目录。LightShield 适配器在 `nuclei` CLI 可用时才执行扫描。
首次部署时可通过社区模板库精选导入，或使用 `--templates` 参数指定外部模板路径。
