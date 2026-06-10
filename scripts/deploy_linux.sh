#!/bin/bash
# =============================================================================
# LightShield 轻盾 — Linux 一键部署脚本
# 兼容：CentOS 7+ / Ubuntu 18.04+ / Debian 10+
# 用法：sudo bash deploy_linux.sh
# =============================================================================
set -e

# ── 合规声明 ──
echo "============================================"
echo "  LightShield 轻盾 — 一键部署"
echo "============================================"
echo ""
echo "【合规声明】本工具仅用于自有资产安全自查，禁止用于非法用途。"
echo ""

# ── 检查 root 权限 ──
if [ "$(id -u)" -ne 0 ]; then
    echo "[错误] 请使用 root 权限运行此脚本：sudo bash deploy_linux.sh"
    exit 1
fi

# ── 检测操作系统 ──
echo "[1/7] 检测操作系统..."

OS=""
OS_VERSION=""
PKG_MANAGER=""

if [ -f /etc/os-release ]; then
    . /etc/os-release
    OS="$ID"
    OS_VERSION="$VERSION_ID"
elif [ -f /etc/centos-release ]; then
    OS="centos"
    OS_VERSION=$(grep -oP '\d+\.\d+' /etc/centos-release | head -1)
else
    echo "[错误] 无法识别操作系统，仅支持 CentOS 7+ / Ubuntu 18.04+ / Debian 10+"
    exit 1
fi

echo "  检测到: $OS $OS_VERSION"

case "$OS" in
    ubuntu|debian)
        PKG_MANAGER="apt"
        ;;
    centos|rhel|fedora)
        PKG_MANAGER="yum"
        # CentOS 8+ 使用 dnf，但 yum 兼容
        if command -v dnf &>/dev/null; then
            PKG_MANAGER="dnf"
        fi
        ;;
    *)
        echo "[错误] 不支持的操作系统: $OS（仅支持 CentOS 7+ / Ubuntu 18.04+ / Debian 10+）"
        exit 1
        ;;
esac
echo "  包管理器: $PKG_MANAGER"

# ── 更新包索引 ──
echo "[2/7] 更新软件包索引..."
case "$PKG_MANAGER" in
    apt)
        apt update -qq
        ;;
    yum|dnf)
        $PKG_MANAGER check-update -q || true  # check-update 返回 100 表示有可用更新，不算错误
        ;;
esac
echo "  完成"

# ── 安装 Python 3 + pip + Nmap ──
echo "[3/7] 安装 Python 3 + pip + Nmap..."

case "$PKG_MANAGER" in
    apt)
        apt install -y python3 python3-pip python3-venv nmap
        ;;
    yum|dnf)
        $PKG_MANAGER install -y python3 python3-pip nmap
        ;;
esac

# 验证安装
python3 --version
pip3 --version
nmap --version | head -1
echo "  依赖安装完成"

# ── 创建安装目录 ──
echo "[4/7] 创建安装目录 /opt/lightshield..."

INSTALL_DIR="/opt/lightshield"
if [ -d "$INSTALL_DIR" ]; then
    echo "  目录已存在，备份旧版本..."
    BACKUP_DIR="/opt/lightshield.bak.$(date +%Y%m%d-%H%M%S)"
    mv "$INSTALL_DIR" "$BACKUP_DIR"
    echo "  旧版本已备份到 $BACKUP_DIR"
fi
mkdir -p "$INSTALL_DIR"
echo "  目录创建完成: $INSTALL_DIR"

# ── 获取脚本所在目录并复制源码 ──
echo "[5/7] 复制源码到 $INSTALL_DIR..."

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

# 检查项目源码是否存在
if [ -f "$PROJECT_DIR/pyproject.toml" ] && [ -d "$PROJECT_DIR/lightshield" ]; then
    # 复制整个项目（排除不需要的目录）
    rsync -a --exclude='.git' --exclude='__pycache__' --exclude='*.pyc' \
          --exclude='.gitignore' --exclude='.claude' --exclude='.cursor' \
          --exclude='.codex' --exclude='.codewhale' --exclude='.codebuddy' \
          --exclude='.workbuddy' --exclude='.remember' --exclude='.guardrails' \
          --exclude='.githooks' --exclude='.cluster' \
          --exclude='node_modules' --exclude='.venv' \
          "$PROJECT_DIR/" "$INSTALL_DIR/"
    echo "  源码复制完成"
elif [ -f "$SCRIPT_DIR/../pyproject.toml" ]; then
    rsync -a --exclude='.git' --exclude='__pycache__' --exclude='*.pyc' \
          "$SCRIPT_DIR/../" "$INSTALL_DIR/"
    echo "  源码复制完成（从脚本上级目录）"
else
    echo "[错误] 未找到项目源码（缺少 pyproject.toml 或 lightshield/ 目录）"
    echo "  请将 deploy_linux.sh 放在项目根目录的 scripts/ 下执行"
    exit 1
fi

# ── 安装 Python 依赖 ──
echo "[6/7] 安装 Python 依赖..."
cd "$INSTALL_DIR"

# 创建虚拟环境
python3 -m venv .venv
source .venv/bin/activate

pip install --upgrade pip -q
pip install -r requirements.txt -q
pip install -e . -q
echo "  Python 依赖安装完成"

# ── 验证安装 ──
echo "[7/7] 验证安装..."
lightshield version
echo ""

# ── 完成提示 ──
echo "============================================"
echo "  LightShield 轻盾 — 部署成功！"
echo "============================================"
echo ""
echo "  安装路径: $INSTALL_DIR"
echo "  虚拟环境: $INSTALL_DIR/.venv"
echo ""
echo "  【快速开始】"
echo "    sudo $INSTALL_DIR/.venv/bin/lightshield scan 127.0.0.1 --confirm-ownership"
echo ""
echo "  【常用命令】"
echo "    lightshield scan <目标> --confirm-ownership    # 全量扫描"
echo "    lightshield quick-scan <目标> --confirm-ownership  # 快速扫描"
echo "    lightshield version                            # 查看版本"
echo ""
echo "  【重要】"
echo "  1. 本工具仅用于自有资产安全自查"
echo "  2. 首次使用请确认目标所有权 (--confirm-ownership)"
echo "  3. 如需激活虚拟环境: source $INSTALL_DIR/.venv/bin/activate"
echo "  4. 卸载: rm -rf $INSTALL_DIR"
echo "============================================"
