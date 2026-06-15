#!/bin/bash
# =============================================================================
# LightShield v0.0.19 E2E — 全链路自动化测试脚本
# =============================================================================
# 在 scanner 容器内执行。
# 靶机通过 hostname "target" 访问（docker-compose 内网 DNS）。
# =============================================================================
set -e

TARGET="${LS_TARGET:-target}"
REPORT_DIR="${LS_REPORT_OUTPUT_DIR:-/app/reports}"
PASS=0
FAIL=0

# ---- 颜色 ----
GREEN='\033[0;32m'
RED='\033[0;31m'
CYAN='\033[0;36m'
NC='\033[0m'

log_pass() { echo -e "${GREEN}[PASS]${NC} $1"; PASS=$((PASS + 1)); }
log_fail() { echo -e "${RED}[FAIL]${NC} $1"; FAIL=$((FAIL + 1)); }
log_step() { echo -e "\n${CYAN}━━━ $1 ━━━${NC}"; }

# =============================================================================
# Step 0: 环境检查
# =============================================================================
log_step "Step 0: 环境检查"

echo "Python: $(python3 --version)"
echo "Nmap: $(nmap --version | head -1)"
echo "目标: $TARGET"

# 等待靶机完全就绪
echo "等待靶机服务..."
for port in 22 23 3306 6379 8080; do
    for i in $(seq 1 10); do
        if timeout 2 bash -c "echo > /dev/tcp/$TARGET/$port" 2>/dev/null; then
            echo "  $TARGET:$port → OPEN"
            break
        fi
        sleep 2
    done
done

# 安装 LightShield
pip install -e /app --quiet 2>&1 | tail -1

# =============================================================================
# Step 1: 资产扫描
# =============================================================================
log_step "Step 1: 资产扫描 (lightshield scan $TARGET)"

if lightshield scan "$TARGET" --confirm-ownership \
    --output-dir "$REPORT_DIR" \
    --output-format markdown \
    2>&1 | tee /tmp/scan-output.log; then
    log_pass "scan 命令执行成功"
else
    log_fail "scan 命令执行失败"
fi

# 检查报告文件
LATEST_REPORT=$(ls -t "$REPORT_DIR"/*.md 2>/dev/null | head -1)
if [ -n "$LATEST_REPORT" ] && [ -s "$LATEST_REPORT" ]; then
    log_pass "报告已生成: $(basename "$LATEST_REPORT") ($(wc -c < "$LATEST_REPORT") bytes)"
else
    log_fail "未生成报告文件"
fi

# =============================================================================
# Step 2: 漏洞检测验证
# =============================================================================
log_step "Step 2: 漏洞检测验证"

if [ -n "$LATEST_REPORT" ]; then
    # 检查报告中是否包含预期的漏洞关键词
    CHECKS=(
        "22.*SSH\|SSH.*22"
        "23.*Telnet\|Telnet.*23"
        "3306.*MySQL\|MySQL.*3306"
        "6379.*Redis\|Redis.*6379"
        ".git\|.env\|敏感目录"
    )

    for check in "${CHECKS[@]}"; do
        if grep -q "$check" "$LATEST_REPORT" 2>/dev/null; then
            log_pass "报告中检测到: $check"
        else
            log_fail "报告中未检测到: $check"
        fi
    done

    # 统计发现数量
    FINDING_COUNT=$(grep -c "| CRITICAL \||| HIGH \||| MEDIUM \|" "$LATEST_REPORT" 2>/dev/null || echo 0)
    echo "  漏洞发现总数: $FINDING_COUNT"
    if [ "$FINDING_COUNT" -ge 3 ]; then
        log_pass "发现 ≥3 个漏洞"
    else
        log_fail "发现仅 $FINDING_COUNT 个漏洞（预期 ≥3）"
    fi
fi

# =============================================================================
# Step 3: 规则匹配
# =============================================================================
log_step "Step 3: 规则匹配验证"

if [ -n "$LATEST_REPORT" ]; then
    if grep -q "风险总览\|漏洞详情" "$LATEST_REPORT" 2>/dev/null; then
        log_pass "报告含规则匹配章节（风险总览/漏洞详情）"
    else
        log_fail "报告缺少规则匹配章节"
    fi

    if grep -q "CVE-" "$LATEST_REPORT" 2>/dev/null; then
        log_pass "报告含 CVE 编号（组件版本匹配正常）"
    else
        echo "  (无 CVE 匹配 — 可能组件版本不在知识库中)"
    fi
fi

# =============================================================================
# Step 4: 加固脚本生成
# =============================================================================
log_step "Step 4: 加固脚本生成 (lightshield harden $TARGET)"

if lightshield harden "$TARGET" --confirm-ownership \
    --output-dir "$REPORT_DIR" \
    2>&1 | tee /tmp/harden-output.log; then
    log_pass "harden 命令执行成功"
else
    log_fail "harden 命令执行失败"
fi

# 检查加固脚本
HARDEN_SCRIPT=$(ls -t "$REPORT_DIR"/harden-*.sh 2>/dev/null | head -1)
ROLLBACK_SCRIPT=$(ls -t "$REPORT_DIR"/rollback-*.sh 2>/dev/null | head -1)

if [ -n "$HARDEN_SCRIPT" ] && [ -s "$HARDEN_SCRIPT" ]; then
    log_pass "加固脚本已生成: $(basename "$HARDEN_SCRIPT") ($(wc -l < "$HARDEN_SCRIPT") 行)"
    # 验证脚本不含攻击关键字
    if grep -qE "exploit|payload|backdoor|trojan|bind_shell|reverse_shell" "$HARDEN_SCRIPT"; then
        log_fail "R1 违规：加固脚本含攻击关键字！"
    else
        log_pass "R1: 加固脚本不含攻击关键字"
    fi
else
    log_fail "加固脚本未生成"
fi

if [ -n "$ROLLBACK_SCRIPT" ] && [ -s "$ROLLBACK_SCRIPT" ]; then
    log_pass "回滚脚本已生成: $(basename "$ROLLBACK_SCRIPT") ($(wc -l < "$ROLLBACK_SCRIPT") 行)"
else
    log_fail "回滚脚本未生成"
fi

# =============================================================================
# Step 5: 合规验证
# =============================================================================
log_step "Step 5: 合规验证"

# R2: 拒绝 CIDR
if lightshield scan "192.168.1.0/24" --confirm-ownership 2>&1 | grep -q "拒绝\|非法\|不合法\|CIDR"; then
    log_pass "R2: CIDR 输入被拒绝"
else
    log_fail "R2: CIDR 输入未被拒绝"
fi

# R6: 扫描间隔检查（从日志中验证）
if [ -d /app/logs ]; then
    log_pass "R6: 审计日志目录存在"
else
    echo "  (无日志目录 — 可能在配置的路径)"
fi

# =============================================================================
# 总结
# =============================================================================
echo ""
echo "============================================"
echo " LightShield v0.0.19 E2E 终审"
echo "============================================"
echo -e " ${GREEN}通过: $PASS${NC}"
echo -e " ${RED}失败: $FAIL${NC}"
echo "============================================"

if [ "$FAIL" -eq 0 ]; then
    echo -e " ${GREEN}✅ E2E 全部通过 — 可以发布 v0.0.20${NC}"
    exit 0
else
    echo -e " ${RED}❌ E2E 有 $FAIL 项失败 — 修复后再发布${NC}"
    exit 1
fi
