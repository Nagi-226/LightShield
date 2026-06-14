# ============================================================
# LightShield 轻盾 — Docker 多阶段构建
# 目标：镜像 < 300MB，非 root 运行，生产安全默认
# ============================================================

# ---------- 阶段一：构建依赖 ----------
FROM python:3.12-slim AS builder

ENV DEBIAN_FRONTEND=noninteractive

# 安装编译期依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libc6-dev \
    && rm -rf /var/lib/apt/lists/*

# 复制项目代码并安装
COPY . /build
WORKDIR /build
RUN pip install --no-cache-dir -e ".[web]"

# ---------- 阶段二：运行镜像 ----------
FROM python:3.12-slim

ENV DEBIAN_FRONTEND=noninteractive

# 安装运行时系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    nmap \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 从构建阶段复制已安装的 Python 包和 CLI 入口
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin/lightshield /usr/local/bin/lightshield

# 创建非 root 用户
RUN groupadd -r lightshield && \
    useradd -r -g lightshield -m -d /home/lightshield lightshield

# 创建数据目录并赋予权限
RUN mkdir -p /data && chown lightshield:lightshield /data

# 切换非 root 用户
USER lightshield
WORKDIR /home/lightshield

# 暴露 Web 仪表板端口
EXPOSE 5000

# 数据持久化卷（SQLite 数据库 + 扫描报告）
VOLUME /data

# 健康检查：验证 Flask 静态文件可访问
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -sf http://127.0.0.1:5000/static/style.css > /dev/null || exit 1

# 启动 Web 服务
# 默认监听 0.0.0.0:5000（容器内部），通过 docker-compose ports 限制外部访问
CMD ["lightshield", "serve", "--host", "0.0.0.0", "--port", "5000"]
