#!/bin/bash
# ============================================================================
# LightShield 集群安全防线 —— 拦截破坏性 git 命令
# ----------------------------------------------------------------------------
# 来源 : mattpocock git-guardrails-claude-code（已定制）
# 定制 : 1) 去除 push 拦截（本项目每版需 git push 推 GitHub）
#        2) 用 grep -oP 精确截取 command 字段（本机 python3/python 为 WindowsApps
#           死桩；改用 PCRE 提取，免依赖。提取失败回退为对原始 JSON 直接匹配，
#           确保安全防线绝不静默失效）
# 机制 : 注册为 Claude Code PreToolUse(Bash) 钩子；命中黑名单 → 退出码 2
#        → Claude 收到「无权执行」提示并放弃该命令。
# 定制 : 增删模式请直接编辑下方 DANGEROUS_PATTERNS 数组。
# ============================================================================

INPUT=$(cat)

# 提取 tool_input.command（PCRE，精确截到下一个引号）；失败则回退原始 JSON
COMMAND=$(printf '%s' "$INPUT" | grep -oP '"command"\s*:\s*"\K[^"]*' | head -n1)
[ -z "$COMMAND" ] && COMMAND="$INPUT"

# 破坏性 git 命令黑名单（已剔除 "git push" / "push --force"）
DANGEROUS_PATTERNS=(
  "git reset --hard"
  "git clean -fd"
  "git clean -f"
  "git branch -D"
  "git checkout \."
  "git restore \."
  "reset --hard"
)

for pattern in "${DANGEROUS_PATTERNS[@]}"; do
  if printf '%s' "$COMMAND" | grep -qE "$pattern"; then
    echo "BLOCKED: '$COMMAND' 命中破坏性 git 模式 '$pattern'。集群安全防线已拦截——如确需执行，请人工在终端运行。" >&2
    exit 2
  fi
done

exit 0
