#!/bin/bash
# =============================================================================
# LightShield v0.0.19 E2E — 靶机启动脚本
# =============================================================================
set -e

echo "=== LightShield E2E 靶机启动 ==="

# 启动所有漏洞服务
service mysql start
service redis-server start
service ssh start
service xinetd start 2>/dev/null || true

# 启动 HTTP 敏感目录服务（后台）
cd /var/www/sensitive && python3 -m http.server 8080 &
HTTP_PID=$!

echo ""
echo "=== 靶机服务状态 ==="
echo "SSH    (22):   $(ss -tlnp | grep -q ':22 ' && echo 'OPEN' || echo 'DOWN')"
echo "Telnet (23):   $(ss -tlnp | grep -q ':23 ' && echo 'OPEN' || echo 'DOWN')"
echo "MySQL  (3306): $(ss -tlnp | grep -q ':3306 ' && echo 'OPEN' || echo 'DOWN')"
echo "Redis  (6379): $(ss -tlnp | grep -q ':6379 ' && echo 'OPEN' || echo 'DOWN')"
echo "HTTP   (8080): $(ss -tlnp | grep -q ':8080 ' && echo 'OPEN' || echo 'DOWN')"
echo ""
echo "✅ 靶机就绪，等待扫描..."

# 保持运行
wait $HTTP_PID
