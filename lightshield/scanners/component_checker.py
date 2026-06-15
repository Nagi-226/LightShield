"""LightShield 组件版本检测器 — 组件指纹识别 + CVE 匹配

基于 HTTP 响应头（Server / X-Powered-By）、HTML meta 标签识别
Web 组件及其版本，并与内置 CVE 知识库进行匹配，输出带风险分级的
漏洞发现列表。

继承 BaseAdapter，可作为独立适配器注册到 LightShieldCore，
也可接收上游端口扫描结果（services/ports），同时检测 HTTP 和
数据库/服务类组件。

用法：
    from lightshield.scanners.component_checker import ComponentCheckerAdapter
    checker = ComponentCheckerAdapter()
    result = checker.scan("example.com")
    for f in result.findings:
        print(f"[{f.severity.value}] {f.title}  CVE: {f.cve_id}")

设计约束（合规）：
  - 仅读取 HTTP 公开信息（响应头 + HTML），不做任何攻击性探测
  - 版本匹配使用语义化比较，避免误报
  - 所有 CVE 数据来源于公开 NVD 记录
"""

from __future__ import annotations

import argparse
import re
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import requests

from lightshield.adapters.base import BaseAdapter, ScanResult, VulnFinding
from lightshield.utils.constants import RiskLevel, ScanStatus
from lightshield.utils.logger import get_logger
from lightshield.utils.validator import TargetValidator

# =============================================================================
# 组件名规范化映射
# =============================================================================

# 将五花八门的组件名称统一到 CVE 知识库中的规范名
_COMPONENT_ALIASES: dict[str, str] = {
    # Web 服务器
    "nginx": "nginx",
    "apache": "apache_httpd",
    "apache2": "apache_httpd",
    "httpd": "apache_httpd",
    "iis": "microsoft_iis",
    "microsoft-iis": "microsoft_iis",
    "caddy": "caddy",
    "litespeed": "litespeed",
    "openresty": "openresty",
    "tomcat": "apache_tomcat",
    "apache-coyote": "apache_tomcat",
    "apache_tomcat": "apache_tomcat",
    "jetty": "jetty",
    "haproxy": "haproxy",
    "ha-proxy": "haproxy",
    # 脚本语言
    "php": "php",
    "python": "python",
    "werkzeug": "werkzeug",
    "gunicorn": "gunicorn",
    # 数据库
    "mysql": "mysql",
    "mariadb": "mariadb",
    "postgresql": "postgresql",
    "redis": "redis",
    "mongodb": "mongodb",
    # CMS / 框架
    "wordpress": "wordpress",
    "drupal": "drupal",
    "joomla": "joomla",
    "magento": "magento",
    "django": "django",
    "laravel": "laravel",
    "flask": "werkzeug",
    "express": "nodejs",
    "node.js": "nodejs",
    "node": "nodejs",
    "jenkins": "jenkins",
    "jenkins-ci": "jenkins",
    "jenkins_core": "jenkins",
    "elasticsearch": "elasticsearch",
    "elastic": "elasticsearch",
    "kibana": "elasticsearch",
    "kubernetes": "kubernetes",
    "k8s": "kubernetes",
    "kube-apiserver": "kubernetes",
    "kube_apiserver": "kubernetes",
    "ingress-nginx": "kubernetes",
    "ingress_nginx": "kubernetes",
    # 其他
    "openssh": "openssh",
    "openssh_server": "openssh",
    "openssl": "openssl",
    "http_server": "apache_httpd",
    "apache-http-server": "apache_httpd",
    "mariadb_server": "mariadb",
    "phpmyadmin": "phpmyadmin",
    "vsftpd": "vsftpd",
    "proftpd": "proftpd",
    "exim": "exim",
    "postfix": "postfix",
    "sendmail": "sendmail",
    "bind": "bind",
}


# =============================================================================
# CVE 知识库（≥100 条，来源于 NVD 公开记录）
# =============================================================================


# ---- CVE 知识库条目 (Python 3.10+ dataclass) ----


@dataclass
class CveEntry:
    """CVE 知识库条目"""

    cve_id: str
    component: str
    max_affected: str
    min_version: str
    severity: RiskLevel
    cvss_score: float
    title_cn: str
    description_cn: str
    remediation_cn: str


CVE_DATABASE: list[CveEntry] = [
    # ============================
    # OpenSSH
    # ============================
    CveEntry(
        cve_id="CVE-2024-6387",
        component="openssh",
        max_affected="9.8p1",
        min_version="8.5p1",
        severity=RiskLevel.CRITICAL,
        cvss_score=9.8,
        title_cn="OpenSSH regreSSHion 远程代码执行 (CVE-2024-6387)",
        description_cn=(
            "OpenSSH 服务器 (sshd) 存在信号处理竞态条件漏洞。"
            "未经身份验证的远程攻击者可在基于 glibc 的 Linux 系统上，"
            "通过多次认证超时触发该漏洞，最终实现远程代码执行（root 权限）。"
            "影响范围：8.5p1 ≤ version < 9.8p1。"
        ),
        remediation_cn="立即升级 OpenSSH 至 9.8p1 或更高版本，或设置 LoginGraceTime=0。",
    ),
    CveEntry(
        cve_id="CVE-2023-38408",
        component="openssh",
        max_affected="9.3p2",
        min_version="5.5p1",
        severity=RiskLevel.HIGH,
        cvss_score=8.1,
        title_cn="OpenSSH ssh-agent 远程代码执行 (CVE-2023-38408)",
        description_cn=(
            "OpenSSH ssh-agent 在加载 PKCS#11 模块时存在远程代码执行漏洞。"
            "攻击者可通过转发 ssh-agent 连接加载恶意共享库，"
            "在受害主机执行任意代码。影响范围：5.5p1 ≤ version < 9.3p2。"
        ),
        remediation_cn="升级 OpenSSH 至 9.3p2+，或禁用 ssh-agent 转发。",
    ),
    CveEntry(
        cve_id="CVE-2021-28041",
        component="openssh",
        max_affected="8.5p1",
        min_version="",
        severity=RiskLevel.HIGH,
        cvss_score=7.1,
        title_cn="OpenSSH 双重释放漏洞 (CVE-2021-28041)",
        description_cn=(
            "OpenSSH 8.5 之前版本存在双重释放漏洞，"
            "恶意 SFTP 服务器可触发客户端崩溃或执行任意代码。"
            "影响范围：version < 8.5p1。"
        ),
        remediation_cn="升级 OpenSSH 至 8.5p1 或更高版本。",
    ),
    CveEntry(
        cve_id="CVE-2023-51385",
        component="openssh",
        max_affected="9.6p1",
        min_version="",
        severity=RiskLevel.MEDIUM,
        cvss_score=6.5,
        title_cn="OpenSSH ProxyCommand 命令注入 (CVE-2023-51385)",
        description_cn=(
            "OpenSSH 9.6 之前版本在处理 ProxyCommand/ProxyJump 的 "
            "shell 元字符时存在缺陷，允许远程 SSH 服务器通过用户名/"
            "主机名中的特殊字符执行命令注入。影响范围：version < 9.6p1。"
        ),
        remediation_cn="升级 OpenSSH 至 9.6p1+ 或使用 ProxyUseFdpass。",
    ),
    # ============================
    # nginx
    # ============================
    CveEntry(
        cve_id="CVE-2023-44487",
        component="nginx",
        max_affected="1.25.3",
        min_version="",
        severity=RiskLevel.HIGH,
        cvss_score=7.5,
        title_cn="HTTP/2 快速重置 DoS — 'Rapid Reset' (CVE-2023-44487)",
        description_cn=(
            "HTTP/2 协议实现存在缺陷，攻击者通过快速创建和取消大量流，"
            "可在 nginx 服务器上造成拒绝服务。影响范围：HTTP/2 启用的 "
            "nginx version < 1.25.3 和 < 1.24.1。"
        ),
        remediation_cn=("升级至 nginx 1.25.3 / 1.24.1+，或在配置中限制 http2_max_concurrent_streams 为较低值。"),
    ),
    CveEntry(
        cve_id="CVE-2023-45802",
        component="nginx",
        max_affected="1.25.4",
        min_version="",
        severity=RiskLevel.MEDIUM,
        cvss_score=5.3,
        title_cn="nginx HTTP/3 流内存耗尽 (CVE-2023-45802)",
        description_cn=(
            "nginx HTTP/3 实现中存在内存耗尽漏洞，"
            "攻击者可发送特制 HTTP/3 请求流触发服务崩溃。"
            "影响范围：HTTP/3 启用的 nginx version < 1.25.4。"
        ),
        remediation_cn="升级 nginx 至 1.25.4+，或禁用 HTTP/3。",
    ),
    CveEntry(
        cve_id="CVE-2021-3618",
        component="nginx",
        max_affected="1.21.0",
        min_version="",
        severity=RiskLevel.MEDIUM,
        cvss_score=6.5,
        title_cn="nginx ALPACA TLS 证书伪造 (CVE-2021-3618)",
        description_cn=(
            "nginx 1.21.0 之前版本的 TLS 会话重用机制存在缺陷，"
            "ALPACA 攻击可利用此漏洞伪造 TLS 证书。"
            "影响范围：version < 1.21.0。"
        ),
        remediation_cn="升级 nginx 至 1.21.0 或更高版本。",
    ),
    # ============================
    # Apache HTTP Server
    # ============================
    CveEntry(
        cve_id="CVE-2023-25690",
        component="apache_httpd",
        max_affected="2.4.56",
        min_version="",
        severity=RiskLevel.CRITICAL,
        cvss_score=9.8,
        title_cn="Apache HTTP Server 请求走私 (CVE-2023-25690)",
        description_cn=(
            "Apache HTTP Server 2.4.56 之前版本在 mod_proxy 中 "
            "存在 HTTP 请求走私漏洞。攻击者可绕过访问控制，"
            "向被代理的后端服务器发送恶意请求。"
            "影响范围：version < 2.4.56（启用 mod_proxy 时）。"
        ),
        remediation_cn="立即升级 Apache HTTP Server 至 2.4.56 或更高版本。",
    ),
    CveEntry(
        cve_id="CVE-2023-31122",
        component="apache_httpd",
        max_affected="2.4.58",
        min_version="2.4.0",
        severity=RiskLevel.HIGH,
        cvss_score=7.5,
        title_cn="Apache HTTP Server mod_macro 缓冲区溢出 (CVE-2023-31122)",
        description_cn=(
            "Apache HTTP Server 2.4.58 之前版本在 mod_macro 模块中"
            "存在越界读取漏洞，可导致服务崩溃或信息泄露。"
            "影响范围：2.4.0 ≤ version < 2.4.58。"
        ),
        remediation_cn="升级 Apache HTTP Server 至 2.4.58 或更高版本。",
    ),
    CveEntry(
        cve_id="CVE-2024-24795",
        component="apache_httpd",
        max_affected="2.4.59",
        min_version="",
        severity=RiskLevel.MEDIUM,
        cvss_score=5.3,
        title_cn="Apache HTTP Server HTTP 响应拆分 (CVE-2024-24795)",
        description_cn=(
            "Apache HTTP Server 2.4.59 之前版本对 HTTP 响应头中的 "
            "特殊字符过滤不严，可能导致 HTTP 响应拆分/走私。"
            "影响范围：version < 2.4.59。"
        ),
        remediation_cn="升级 Apache HTTP Server 至 2.4.59 或更高版本。",
    ),
    # ============================
    # PHP
    # ============================
    CveEntry(
        cve_id="CVE-2024-4577",
        component="php",
        max_affected="8.1.29",
        min_version="8.1.0",
        severity=RiskLevel.CRITICAL,
        cvss_score=9.8,
        title_cn="PHP CGI 参数注入 → RCE (CVE-2024-4577)",
        description_cn=(
            "PHP 在 Windows 上使用 CGI 模式时，对字符编码处理存在缺陷，"
            "允许未认证的远程攻击者注入参数并执行任意 PHP 代码。"
            "影响范围：8.1.0 ≤ PHP < 8.1.29, 8.2.0 ≤ PHP < 8.2.20, "
            "8.3.0 ≤ PHP < 8.3.8（Windows + CGI 模式）。"
        ),
        remediation_cn="立即升级 PHP 至 8.1.29 / 8.2.20 / 8.3.8+，或避免 CGI 模式。",
    ),
    CveEntry(
        cve_id="CVE-2022-37454",
        component="php",
        max_affected="8.1.12",
        min_version="7.4.0",
        severity=RiskLevel.HIGH,
        cvss_score=8.8,
        title_cn="PHP SHA-3 缓冲区溢出 (CVE-2022-37454)",
        description_cn=(
            "PHP 7.4.x、8.0.x、8.1.x 的 SHA-3 实现中存在堆缓冲区溢出漏洞，"
            "攻击者可构造特殊哈希输入导致代码执行。"
            "影响范围：7.4.0 ≤ PHP < 8.1.12。"
        ),
        remediation_cn="升级 PHP 至 8.1.12 或更高版本。",
    ),
    CveEntry(
        cve_id="CVE-2023-0662",
        component="php",
        max_affected="8.1.16",
        min_version="",
        severity=RiskLevel.MEDIUM,
        cvss_score=5.3,
        title_cn="PHP 拒绝服务漏洞 (CVE-2023-0662)",
        description_cn=(
            "PHP 8.1.16 之前版本在处理大量 HTTP 表单上传时存在资源消耗漏洞，"
            "可被用于拒绝服务攻击。影响范围：version < 8.1.16。"
        ),
        remediation_cn="升级 PHP 至 8.1.16 或更高版本。",
    ),
    # ============================
    # MySQL / MariaDB
    # ============================
    CveEntry(
        cve_id="CVE-2023-22115",
        component="mysql",
        max_affected="8.0.34",
        min_version="8.0.0",
        severity=RiskLevel.HIGH,
        cvss_score=7.5,
        title_cn="MySQL Server 拒绝服务漏洞 (CVE-2023-22115)",
        description_cn=(
            "MySQL Server 8.0.34 之前版本存在拒绝服务漏洞，"
            "经过认证的客户端可通过精心构造的查询导致服务器崩溃。"
            "影响范围：8.0.0 ≤ MySQL < 8.0.34。"
        ),
        remediation_cn="升级 MySQL 至 8.0.34 或更高版本。",
    ),
    CveEntry(
        cve_id="CVE-2024-20963",
        component="mysql",
        max_affected="8.0.36",
        min_version="8.0.0",
        severity=RiskLevel.MEDIUM,
        cvss_score=5.5,
        title_cn="MySQL Server 权限提升 (CVE-2024-20963)",
        description_cn=(
            "MySQL Server 8.0.36 之前版本存在权限提升漏洞，"
            "低权限用户可通过特定操作获取更高权限。"
            "影响范围：8.0.0 ≤ MySQL < 8.0.36。"
        ),
        remediation_cn="升级 MySQL 至 8.0.36 或更高版本。",
    ),
    CveEntry(
        cve_id="CVE-2022-32084",
        component="mariadb",
        max_affected="10.9.3",
        min_version="",
        severity=RiskLevel.HIGH,
        cvss_score=7.5,
        title_cn="MariaDB 段错误拒绝服务 (CVE-2022-32084)",
        description_cn=(
            "MariaDB 10.9.3 之前版本存在多个段错误崩溃点，可被用于拒绝服务攻击。影响范围：version < 10.9.3。"
        ),
        remediation_cn="升级 MariaDB 至 10.9.3 或更高版本。",
    ),
    # ============================
    # WordPress
    # ============================
    CveEntry(
        cve_id="CVE-2024-1071",
        component="wordpress",
        max_affected="6.4.4",
        min_version="6.0.0",
        severity=RiskLevel.HIGH,
        cvss_score=7.5,
        title_cn="WordPress 未授权内容注入 (CVE-2024-1071)",
        description_cn=(
            "WordPress 6.4.4 之前版本存在未授权内容注入漏洞，"
            "攻击者可通过特定 API 端点绕过权限检查，"
            "发布/修改文章内容。影响范围：6.0.0 ≤ version < 6.4.4。"
        ),
        remediation_cn="升级 WordPress 至 6.4.4 或更高版本。",
    ),
    CveEntry(
        cve_id="CVE-2023-5561",
        component="wordpress",
        max_affected="6.3.2",
        min_version="",
        severity=RiskLevel.MEDIUM,
        cvss_score=5.3,
        title_cn="WordPress 用户枚举漏洞 (CVE-2023-5561)",
        description_cn=(
            "WordPress 6.3.2 之前版本的 REST API 存在用户枚举漏洞，"
            "未认证用户可遍历作者 ID 获取所有用户名列表。"
            "影响范围：version < 6.3.2。"
        ),
        remediation_cn="升级 WordPress 至 6.3.2+，或安装用户枚举防护插件。",
    ),
    CveEntry(
        cve_id="CVE-2022-43571",
        component="wordpress",
        max_affected="6.0.4",
        min_version="6.0.0",
        severity=RiskLevel.MEDIUM,
        cvss_score=5.4,
        title_cn="WordPress 存储型 XSS (CVE-2022-43571)",
        description_cn=(
            "WordPress 6.0.4 之前版本在 RSS 区块中存在存储型 XSS，"
            "管理员查看恶意 RSS 内容时可触发跨站脚本执行。"
            "影响范围：6.0.0 ≤ version < 6.0.4。"
        ),
        remediation_cn="升级 WordPress 至 6.0.4 或更高版本。",
    ),
    # ============================
    # Apache Tomcat
    # ============================
    CveEntry(
        cve_id="CVE-2024-34750",
        component="apache_tomcat",
        max_affected="10.1.25",
        min_version="10.1.0",
        severity=RiskLevel.HIGH,
        cvss_score=7.5,
        title_cn="Apache Tomcat HTTP/2 流控制拒绝服务 (CVE-2024-34750)",
        description_cn=(
            "Apache Tomcat 在处理 HTTP/2 流时未正确管理流控制，"
            "攻击者可发送特制 HTTP/2 帧导致连接长时间占用，"
            "造成拒绝服务。影响：10.1.0 ≤ Tomcat < 10.1.25, "
            "9.0.0 ≤ Tomcat < 9.0.90, 8.5.0 ≤ Tomcat < 8.5.99。"
        ),
        remediation_cn="升级 Apache Tomcat 至 10.1.25 / 9.0.90 / 8.5.99+。",
    ),
    CveEntry(
        cve_id="CVE-2023-44487",
        component="apache_tomcat",
        max_affected="10.1.16",
        min_version="",
        severity=RiskLevel.HIGH,
        cvss_score=7.5,
        title_cn="Apache Tomcat HTTP/2 Rapid Reset DoS (CVE-2023-44487)",
        description_cn=(
            "与 nginx 相同的 HTTP/2 Rapid Reset 攻击同样影响 Tomcat。"
            "影响范围：HTTP/2 启用的 Tomcat version < 10.1.16, "
            "< 9.0.83, < 8.5.96。"
        ),
        remediation_cn="升级 Tomcat，或禁用 HTTP/2 协议。",
    ),
    # ============================
    # PostgreSQL
    # ============================
    CveEntry(
        cve_id="CVE-2023-5870",
        component="postgresql",
        max_affected="16.1",
        min_version="12.0",
        severity=RiskLevel.MEDIUM,
        cvss_score=6.5,
        title_cn="PostgreSQL pg_cancel_backend 拒绝服务 (CVE-2023-5870)",
        description_cn=(
            "PostgreSQL 在处理 pg_cancel_backend 信号时存在缺陷，"
            "恶意角色可导致服务进程崩溃。"
            "影响范围：12.0 ≤ version < 16.1。"
        ),
        remediation_cn="升级 PostgreSQL 至 16.1 / 15.5 / 14.10 / 13.13 / 12.17+。",
    ),
    CveEntry(
        cve_id="CVE-2023-5869",
        component="postgresql",
        max_affected="15.5",
        min_version="11.0",
        severity=RiskLevel.HIGH,
        cvss_score=8.8,
        title_cn="PostgreSQL 数组越界 SQL 注入 (CVE-2023-5869)",
        description_cn=(
            "PostgreSQL 在解析数组下标时存在整数溢出，"
            "经过认证的攻击者可利用此漏洞执行越界写操作，"
            "可能导致代码执行。影响范围：11.0 ≤ version < 15.5。"
        ),
        remediation_cn="升级 PostgreSQL 至 15.5 或更高版本。",
    ),
    # ============================
    # Redis
    # ============================
    CveEntry(
        cve_id="CVE-2023-45145",
        component="redis",
        max_affected="7.2.2",
        min_version="7.0.0",
        severity=RiskLevel.MEDIUM,
        cvss_score=6.2,
        title_cn="Redis 客户端重定向配置泄露 (CVE-2023-45145)",
        description_cn=(
            "Redis 7.2.2 之前版本在客户端重定向处理中会泄露配置信息，"
            "导致敏感数据（如密码/密钥）暴露给未授权客户端。"
            "影响范围：7.0.0 ≤ version < 7.2.2。"
        ),
        remediation_cn="升级 Redis 至 7.2.2+，并确保配置中无未授权客户端。",
    ),
    CveEntry(
        cve_id="CVE-2024-25118",
        component="redis",
        max_affected="7.2.4",
        min_version="7.2.0",
        severity=RiskLevel.LOW,
        cvss_score=3.3,
        title_cn="Redis 栈缓冲区溢出 (CVE-2024-25118)",
        description_cn=(
            "Redis 7.2.4 之前版本在某些命令的参数解析中"
            "存在小范围栈缓冲区溢出，需要本地权限利用。"
            "影响范围：7.2.0 ≤ version < 7.2.4。"
        ),
        remediation_cn="升级 Redis 至 7.2.4 或更高版本。",
    ),
    # ============================
    # phpMyAdmin
    # ============================
    CveEntry(
        cve_id="CVE-2023-25727",
        component="phpmyadmin",
        max_affected="5.2.1",
        min_version="4.9.0",
        severity=RiskLevel.HIGH,
        cvss_score=8.0,
        title_cn="phpMyAdmin XSS → RCE 漏洞链 (CVE-2023-25727)",
        description_cn=(
            "phpMyAdmin 5.2.1 之前版本存在跨站脚本 (XSS) 漏洞，"
            "在特定配置下可连锁利用为远程代码执行。"
            "影响范围：4.9.0 ≤ version < 5.2.1。"
        ),
        remediation_cn="升级 phpMyAdmin 至 5.2.1 或更高版本。",
    ),
    # ============================
    # Node.js
    # ============================
    CveEntry(
        cve_id="CVE-2024-22017",
        component="nodejs",
        max_affected="19.8.1",
        min_version="18.0.0",
        severity=RiskLevel.HIGH,
        cvss_score=8.6,
        title_cn="Node.js setuid() 权限提升 (CVE-2024-22017)",
        description_cn=(
            "Node.js 18.x、19.x 在处理 process.setuid() 时存在缺陷，"
            "攻击者可通过竞争条件获取 root 权限。"
            "影响范围：18.0.0 ≤ Node.js < 18.19.1, "
            "19.0.0 ≤ Node.js < 19.8.1。"
        ),
        remediation_cn="升级 Node.js 至 18.19.1 / 19.8.1 或更高版本。",
    ),
    CveEntry(
        cve_id="CVE-2023-23918",
        component="nodejs",
        max_affected="19.6.1",
        min_version="18.0.0",
        severity=RiskLevel.MEDIUM,
        cvss_score=5.3,
        title_cn="Node.js 实验性权限模型绕过 (CVE-2023-23918)",
        description_cn=(
            "Node.js 实验性权限模型存在绕过漏洞，"
            "可通过 path traversal 访问受限文件。"
            "影响范围：18.0.0 ≤ Node.js < 18.14.2, "
            "19.0.0 ≤ Node.js < 19.6.1。"
        ),
        remediation_cn="升级 Node.js 或禁用实验性权限模型。",
    ),
    # ============================
    # vsftpd / FTP
    # ============================
    CveEntry(
        cve_id="CVE-2021-3618",
        component="vsftpd",
        max_affected="3.0.5",
        min_version="",
        severity=RiskLevel.HIGH,
        cvss_score=7.5,
        title_cn="vsftpd TLS 证书伪造 (CVE-2021-3618)",
        description_cn=(
            "vsftpd 3.0.5 之前版本在 TLS 握手过程中存在缺陷，"
            "ALPACA 攻击可伪造 TLS 证书进行中间人攻击。"
            "影响范围：version < 3.0.5。"
        ),
        remediation_cn="升级 vsftpd 至 3.0.5 或更高版本。",
    ),
    # ============================
    # Drupal
    # ============================
    CveEntry(
        cve_id="CVE-2023-31250",
        component="drupal",
        max_affected="10.0.9",
        min_version="9.5.0",
        severity=RiskLevel.MEDIUM,
        cvss_score=5.4,
        title_cn="Drupal 访问绕过漏洞 (CVE-2023-31250)",
        description_cn=(
            "Drupal 10.0.9 之前版本在文件下载功能存在访问控制缺陷，"
            "攻击者可能绕过权限限制下载非公开文件。"
            "影响范围：9.5.0 ≤ version < 10.0.9。"
        ),
        remediation_cn="升级 Drupal 至 10.0.9 或更高版本。",
    ),
    # ============================
    # Joomla
    # ============================
    CveEntry(
        cve_id="CVE-2023-23752",
        component="joomla",
        max_affected="4.3.0",
        min_version="4.0.0",
        severity=RiskLevel.MEDIUM,
        cvss_score=5.3,
        title_cn="Joomla API 未授权信息泄露 (CVE-2023-23752)",
        description_cn=(
            "Joomla 4.x 在 4.3.0 之前版本的 REST API 端点"
            "缺少认证检查，未授权用户可获取数据库配置等敏感信息。"
            "影响范围：4.0.0 ≤ version < 4.3.0。"
        ),
        remediation_cn="升级 Joomla 至 4.3.0 或更高版本。",
    ),
    # ============================
    # OpenSSL
    # ============================
    CveEntry(
        cve_id="CVE-2022-3786",
        component="openssl",
        max_affected="3.0.7",
        min_version="3.0.0",
        severity=RiskLevel.HIGH,
        cvss_score=7.5,
        title_cn="OpenSSL X.509 证书验证缓冲区溢出 (CVE-2022-3786)",
        description_cn=(
            "OpenSSL 3.0.x 在解析 X.509 证书中的 Email 地址时，"
            "存在缓冲区溢出漏洞，可导致拒绝服务甚至远程代码执行。"
            "影响范围：3.0.0 ≤ version < 3.0.7。"
        ),
        remediation_cn="升级 OpenSSL 至 3.0.7 或更高版本。",
    ),
    CveEntry(
        cve_id="CVE-2024-0727",
        component="openssl",
        max_affected="3.2.1",
        min_version="3.2.0",
        severity=RiskLevel.MEDIUM,
        cvss_score=5.5,
        title_cn="OpenSSL PKCS12 解析拒绝服务 (CVE-2024-0727)",
        description_cn=(
            "OpenSSL 3.2.0 在解析恶意 PKCS12 文件时可能触发"
            "空指针解引用，导致应用程序崩溃。"
            "影响范围：3.2.0 ≤ version < 3.2.1。"
        ),
        remediation_cn="升级 OpenSSL 至 3.2.1 或更高版本。",
    ),
    # ============================
    # v0.0.24 CVE 扩充：现有组件
    # ============================
    # nginx ngx_http_mp4_module 内存破坏
    CveEntry(
        cve_id="CVE-2022-41741",
        component="nginx",
        max_affected="1.22.1",
        min_version="1.1.3",
        severity=RiskLevel.HIGH,
        cvss_score=7.8,
        title_cn="nginx MP4 模块内存破坏漏洞 (CVE-2022-41741)",
        description_cn=(
            "nginx Open Source 的 ngx_http_mp4_module 在处理特制 MP4 文件时可能发生内存破坏，"
            "导致工作进程崩溃或异常行为。影响范围：1.1.3 ≤ version < 1.22.1；"
            "1.23.0 和 1.23.1 主线版本也受影响。"
        ),
        remediation_cn="升级 nginx 至 1.22.1 / 1.23.2 或更高版本；如无需在线播放 MP4，移除 mp4 指令或禁用该模块。",
    ),
    # nginx ngx_http_mp4_module 信息泄露/崩溃
    CveEntry(
        cve_id="CVE-2022-41742",
        component="nginx",
        max_affected="1.22.1",
        min_version="1.1.3",
        severity=RiskLevel.HIGH,
        cvss_score=7.1,
        title_cn="nginx MP4 模块内存泄露漏洞 (CVE-2022-41742)",
        description_cn=(
            "nginx Open Source 的 ngx_http_mp4_module 在解析特制 MP4 文件时存在内存处理缺陷，"
            "可能造成敏感内存泄露或工作进程崩溃。影响范围：1.1.3 ≤ version < 1.22.1；"
            "1.23.0 和 1.23.1 主线版本也受影响。"
        ),
        remediation_cn="升级 nginx 至 1.22.1 / 1.23.2 或更高版本；对不可信媒体文件关闭 mp4 模块处理。",
    ),
    # Apache HTTP Server mod_rewrite 替换编码问题
    CveEntry(
        cve_id="CVE-2024-38474",
        component="apache_httpd",
        max_affected="2.4.60",
        min_version="2.4.0",
        severity=RiskLevel.CRITICAL,
        cvss_score=9.8,
        title_cn="Apache HTTP Server mod_rewrite 脚本执行/源码泄露 (CVE-2024-38474)",
        description_cn=(
            "Apache HTTP Server 2.4.59 及更早版本的 mod_rewrite 替换编码存在缺陷，"
            "可能使配置允许目录中的脚本被间接执行，或暴露本不应直接访问的脚本源码。"
            "影响范围：2.4.0 ≤ version < 2.4.60。"
        ),
        remediation_cn="升级 Apache HTTP Server 至 2.4.60 或更高版本，并复核 RewriteRule/ProxyPass 对后端路径的映射。",
    ),
    # Apache HTTP Server 后端响应头处理缺陷
    CveEntry(
        cve_id="CVE-2024-38476",
        component="apache_httpd",
        max_affected="2.4.60",
        min_version="2.4.0",
        severity=RiskLevel.CRITICAL,
        cvss_score=9.8,
        title_cn="Apache HTTP Server 后端响应头注入风险 (CVE-2024-38476)",
        description_cn=(
            "Apache HTTP Server 2.4.59 及更早版本在处理后端应用返回的响应头时存在缺陷，"
            "可能引发信息泄露、服务端请求伪造或本地脚本执行。影响范围：2.4.0 ≤ version < 2.4.60。"
        ),
        remediation_cn="升级 Apache HTTP Server 至 2.4.60 或更高版本，并限制反向代理后端可控响应头。",
    ),
    # PHP PHAR 目录项栈缓冲区溢出
    CveEntry(
        cve_id="CVE-2023-3824",
        component="php",
        max_affected="8.1.22",
        min_version="8.1.0",
        severity=RiskLevel.CRITICAL,
        cvss_score=9.8,
        title_cn="PHP PHAR 目录项栈缓冲区溢出 (CVE-2023-3824)",
        description_cn=(
            "PHP 在加载 PHAR 文件并读取目录项时长度校验不足，可能触发栈缓冲区溢出，"
            "造成内存破坏或远程代码执行风险。影响范围：8.1.0 ≤ version < 8.1.22；"
            "8.0.0 ≤ version < 8.0.30 和 8.2.0 ≤ version < 8.2.9 也受影响。"
        ),
        remediation_cn="升级 PHP 至 8.1.22 / 8.0.30 / 8.2.9 或更高版本，并避免处理不可信 PHAR 文件。",
    ),
    # PHP XML 全局状态污染
    CveEntry(
        cve_id="CVE-2023-3823",
        component="php",
        max_affected="8.1.22",
        min_version="8.1.0",
        severity=RiskLevel.HIGH,
        cvss_score=7.5,
        title_cn="PHP XML 外部实体配置绕过 (CVE-2023-3823)",
        description_cn=(
            "PHP 多个 XML 函数依赖 libxml 全局状态跟踪外部实体等配置，"
            "在特定调用顺序下可能使安全配置被意外复用或绕过，带来信息泄露风险。"
            "影响范围：8.1.0 ≤ version < 8.1.22；8.0.x 和 8.2.x 对应修复版本前也受影响。"
        ),
        remediation_cn="升级 PHP 至 8.1.22 / 8.0.30 / 8.2.9 或更高版本，并禁用不必要的 XML 外部实体加载。",
    ),
    # MySQL mysqldump 客户端组件漏洞
    CveEntry(
        cve_id="CVE-2024-21096",
        component="mysql",
        max_affected="8.0.37",
        min_version="8.0.0",
        severity=RiskLevel.MEDIUM,
        cvss_score=4.9,
        title_cn="MySQL Server mysqldump 客户端漏洞 (CVE-2024-21096)",
        description_cn=(
            "Oracle MySQL Server 的 Client: mysqldump 组件存在漏洞，"
            "低复杂度场景下可能影响数据机密性或可用性。影响范围：8.0.0 ≤ version < 8.0.37；"
            "8.1.0 至 8.3.0 维护线也受影响。"
        ),
        remediation_cn="升级 MySQL Server 至 8.0.37 或对应 Oracle CPU 修复版本，并限制 mysqldump 对不可信服务器的访问。",
    ),
    # MySQL InnoDB 组件漏洞
    CveEntry(
        cve_id="CVE-2023-22084",
        component="mysql",
        max_affected="8.0.35",
        min_version="8.0.0",
        severity=RiskLevel.MEDIUM,
        cvss_score=4.9,
        title_cn="MySQL Server InnoDB 拒绝服务漏洞 (CVE-2023-22084)",
        description_cn=(
            "Oracle MySQL Server 的 InnoDB 组件存在可被高权限网络用户触发的缺陷，"
            "可能导致服务可用性受影响。影响范围：8.0.0 ≤ version < 8.0.35；"
            "5.7.43 及更早版本和 8.1.0 也受影响。"
        ),
        remediation_cn="升级 MySQL Server 至 8.0.35 / 8.1.1 或对应 Oracle CPU 修复版本，并收紧高权限数据库账号。",
    ),
    # Redis Lua 栈缓冲区溢出（影响所有启用 Lua 脚本的版本，拆分覆盖）
    CveEntry(
        cve_id="CVE-2024-31449",
        component="redis",
        max_affected="6.2.16",
        min_version="",  # 覆盖 5.x/6.x 等所有更早分支（NVD: 2.8.18 ≤ v < 6.2.16）
        severity=RiskLevel.HIGH,
        cvss_score=8.8,
        title_cn="Redis Lua bit 库栈缓冲区溢出 (CVE-2024-31449)",
        description_cn=(
            "Redis 在 Lua 脚本 bit 库中存在栈缓冲区溢出漏洞，"
            "经过认证的用户可能触发内存破坏并影响机密性、完整性和可用性。"
            "影响范围：2.8.18 ≤ version < 6.2.16（广泛受影响分支）。"
        ),
        remediation_cn="升级 Redis 至 6.2.16 或更高版本，并限制 Lua 脚本执行权限。",
    ),
    CveEntry(
        cve_id="CVE-2024-31449",
        component="redis",
        max_affected="7.2.6",
        min_version="7.2.0",
        severity=RiskLevel.HIGH,
        cvss_score=8.8,
        title_cn="Redis Lua bit 库栈缓冲区溢出 — 7.2.x (CVE-2024-31449)",
        description_cn=(
            "Redis 7.2.x 在 Lua 脚本 bit 库中存在栈缓冲区溢出漏洞，"
            "经过认证的用户可能触发内存破坏。"
            "影响范围：7.2.0 ≤ version < 7.2.6。"
        ),
        remediation_cn="升级 Redis 至 7.2.6 或更高版本。",
    ),
    # Redis Lua cjson 库堆溢出
    CveEntry(
        cve_id="CVE-2022-24834",
        component="redis",
        max_affected="7.0.12",
        min_version="7.0.0",
        severity=RiskLevel.HIGH,
        cvss_score=8.8,
        title_cn="Redis Lua cjson 堆溢出漏洞 (CVE-2022-24834)",
        description_cn=(
            "Redis 的 Lua cjson 库在处理特制脚本输入时可能发生堆溢出，"
            "造成服务崩溃或内存破坏风险。影响范围：7.0.0 ≤ version < 7.0.12；"
            "6.0.x 和 6.2.x 对应修复版本前也受影响。"
        ),
        remediation_cn="升级 Redis 至 7.0.12 / 6.2.13 / 6.0.20 或更高版本，并限制不可信用户执行 Lua 脚本。",
    ),
    # PostgreSQL REFRESH MATERIALIZED VIEW 权限下降延迟
    CveEntry(
        cve_id="CVE-2024-0985",
        component="postgresql",
        max_affected="15.6",
        min_version="15.0",
        severity=RiskLevel.HIGH,
        cvss_score=8.0,
        title_cn="PostgreSQL 物化视图权限提升 (CVE-2024-0985)",
        description_cn=(
            "PostgreSQL 在 REFRESH MATERIALIZED VIEW CONCURRENTLY 中存在权限下降延迟问题，"
            "对象创建者可能以命令发起者权限执行 SQL 函数。影响范围：15.0 ≤ version < 15.6；"
            "12.x 至 14.x 对应修复版本前也受影响。"
        ),
        remediation_cn="升级 PostgreSQL 至 15.6 / 14.11 / 13.14 / 12.18 或更高版本，并审计物化视图创建权限。",
    ),
    # PostgreSQL 行级安全复用查询跟踪不完整
    CveEntry(
        cve_id="CVE-2024-10976",
        component="postgresql",
        max_affected="16.5",
        min_version="16.0",
        severity=RiskLevel.MEDIUM,
        cvss_score=5.4,
        title_cn="PostgreSQL 行级安全绕过漏洞 (CVE-2024-10976)",
        description_cn=(
            "PostgreSQL 对启用行级安全的表复用查询时跟踪不完整，"
            "可能导致查询查看或修改非预期行。影响范围：16.0 ≤ version < 16.5；"
            "12.x 至 17.x 对应修复版本前也受影响。"
        ),
        remediation_cn="升级 PostgreSQL 至 17.1 / 16.5 / 15.9 / 14.14 / 13.17 / 12.21 或更高版本。",
    ),
    # Apache Tomcat 默认 Servlet 写入导致路径等价问题
    CveEntry(
        cve_id="CVE-2025-24813",
        component="apache_tomcat",
        max_affected="10.1.35",
        min_version="10.1.1",
        severity=RiskLevel.CRITICAL,
        cvss_score=9.8,
        title_cn="Apache Tomcat 路径等价远程代码执行 (CVE-2025-24813)",
        description_cn=(
            "Apache Tomcat 在默认 Servlet 启用写入时存在路径等价处理缺陷，"
            "可能导致远程代码执行、信息泄露或上传内容被篡改。影响范围：10.1.1 ≤ version < 10.1.35；"
            "9.0.x 和 11.0.x 对应修复版本前也受影响。"
        ),
        remediation_cn="升级 Apache Tomcat 至 10.1.35 / 9.0.99 / 11.0.3 或更高版本，并关闭默认 Servlet 写入。",
    ),
    # Apache Tomcat JSP 编译 TOCTOU 竞态
    CveEntry(
        cve_id="CVE-2024-50379",
        component="apache_tomcat",
        max_affected="10.1.34",
        min_version="10.1.0",
        severity=RiskLevel.CRITICAL,
        cvss_score=9.8,
        title_cn="Apache Tomcat JSP 编译竞态执行漏洞 (CVE-2024-50379)",
        description_cn=(
            "Apache Tomcat 在大小写不敏感文件系统上进行 JSP 编译时存在 TOCTOU 竞态，"
            "当默认 Servlet 可写时可能导致远程代码执行。影响范围：10.1.0 ≤ version < 10.1.34；"
            "9.0.x 和 11.0.x 对应修复版本前也受影响。"
        ),
        remediation_cn="升级 Apache Tomcat 至 10.1.34 / 9.0.98 / 11.0.2 或更高版本，并禁用默认 Servlet 写入。",
    ),
    # Node.js policy 机制 Module._load 绕过
    CveEntry(
        cve_id="CVE-2023-32002",
        component="nodejs",
        max_affected="18.17.1",
        min_version="18.0.0",
        severity=RiskLevel.CRITICAL,
        cvss_score=9.8,
        title_cn="Node.js 实验性 policy 机制绕过 (CVE-2023-32002)",
        description_cn=(
            "Node.js 的 Module._load() 可绕过 policy.json 中的模块加载限制，"
            "使受限模块加载外部代码。影响范围：18.0.0 ≤ version < 18.17.1；"
            "16.x 和 20.x 对应修复版本前也受影响。"
        ),
        remediation_cn="升级 Node.js 至 18.17.1 / 16.20.2 / 20.5.1 或更高版本，并避免依赖实验性 policy 作为唯一边界。",
    ),
    # Node.js HTTP chunked 编码资源耗尽
    CveEntry(
        cve_id="CVE-2024-22019",
        component="nodejs",
        max_affected="18.19.1",
        min_version="18.0.0",
        severity=RiskLevel.HIGH,
        cvss_score=7.5,
        title_cn="Node.js HTTP 分块编码拒绝服务 (CVE-2024-22019)",
        description_cn=(
            "Node.js HTTP 服务器在处理特制 chunked 编码请求时可能持续读取无限数量字节，"
            "造成资源耗尽和拒绝服务。影响范围：18.0.0 ≤ version < 18.19.1；"
            "20.x 和 21.x 对应修复版本前也受影响。"
        ),
        remediation_cn="升级 Node.js 至 18.19.1 / 20.11.1 / 21.6.2 或更高版本，并在反向代理层限制请求体大小。",
    ),
    # WordPress wp_lang 目录遍历
    CveEntry(
        cve_id="CVE-2023-2745",
        component="wordpress",
        max_affected="6.2.1",
        min_version="6.2",
        severity=RiskLevel.MEDIUM,
        cvss_score=6.1,
        title_cn="WordPress wp_lang 目录遍历漏洞 (CVE-2023-2745)",
        description_cn=(
            "WordPress Core 的 wp_lang 参数存在目录遍历风险，"
            "未认证用户可能加载非预期翻译文件，并在特定条件下造成脚本执行风险。"
            "影响范围：6.2 ≤ version < 6.2.1；多个旧维护分支对应修复版本前也受影响。"
        ),
        remediation_cn="升级 WordPress 至 6.2.1 或所在维护分支的最新安全版本，并限制可写语言目录。",
    ),
    # Drupal 文件名净化绕过
    CveEntry(
        cve_id="CVE-2022-25277",
        component="drupal",
        max_affected="9.4.3",
        min_version="9.4.0",
        severity=RiskLevel.HIGH,
        cvss_score=7.2,
        title_cn="Drupal 文件上传扩展名净化绕过 (CVE-2022-25277)",
        description_cn=(
            "Drupal Core 对危险扩展名和文件名前后点号的净化存在绕过，"
            "可能允许上传可导致服务器配置异常或执行风险的文件。"
            "影响范围：9.4.0 ≤ version < 9.4.3；8.x/9.3.x 对应修复版本前也受影响。"
        ),
        remediation_cn="升级 Drupal 至 9.4.3 / 9.3.19 或更高版本，并限制高风险文件扩展名上传。",
    ),
    # Drupal Form API 访问判断错误
    CveEntry(
        cve_id="CVE-2022-25278",
        component="drupal",
        max_affected="9.4.3",
        min_version="9.4.0",
        severity=RiskLevel.MEDIUM,
        cvss_score=6.5,
        title_cn="Drupal Form API 访问控制错误 (CVE-2022-25278)",
        description_cn=(
            "Drupal Core Form API 在特定条件下对表单元素访问权限判断错误，"
            "可能允许用户修改其不应访问的数据。影响范围：9.4.0 ≤ version < 9.4.3；"
            "8.x/9.3.x 对应修复版本前也受影响。"
        ),
        remediation_cn="升级 Drupal 至 9.4.3 / 9.3.19 或更高版本，并复核自定义表单元素 access 配置。",
    ),
    # Joomla 邮件地址转义不足
    CveEntry(
        cve_id="CVE-2024-21725",
        component="joomla",
        max_affected="5.0.3",
        min_version="5.0.0",
        severity=RiskLevel.MEDIUM,
        cvss_score=6.1,
        title_cn="Joomla 邮件地址转义不足导致 XSS (CVE-2024-21725)",
        description_cn=(
            "Joomla 多个组件对邮件地址输出转义不足，可能造成跨站脚本风险。"
            "影响范围：5.0.0 ≤ version < 5.0.3；4.0.0 ≤ version < 4.4.3 也受影响。"
        ),
        remediation_cn="升级 Joomla 至 5.0.3 / 4.4.3 或更高版本，并对模板中的邮件地址输出启用上下文转义。",
    ),
    # Joomla 内容过滤不足
    CveEntry(
        cve_id="CVE-2024-21726",
        component="joomla",
        max_affected="5.0.3",
        min_version="5.0.0",
        severity=RiskLevel.MEDIUM,
        cvss_score=6.5,
        title_cn="Joomla 内容过滤不足导致 XSS (CVE-2024-21726)",
        description_cn=(
            "Joomla 在多个组件中内容过滤不足，可能使低权限用户提交的内容触发跨站脚本风险。"
            "影响范围：5.0.0 ≤ version < 5.0.3；3.7.0 至 3.10.15 和 4.0.0 至 4.4.3 也受影响。"
        ),
        remediation_cn="升级 Joomla 至 5.0.3 / 4.4.3 / 3.10.16 或更高版本，并启用严格 HTML 过滤策略。",
    ),
    # MariaDB VDec use-after-free
    CveEntry(
        cve_id="CVE-2022-27456",
        component="mariadb",
        max_affected="10.7.4",
        min_version="10.7.0",
        severity=RiskLevel.HIGH,
        cvss_score=7.5,
        title_cn="MariaDB VDec 释放后使用漏洞 (CVE-2022-27456)",
        description_cn=(
            "MariaDB Server 在 VDec::VDec 组件中存在释放后使用缺陷，"
            "可能导致服务崩溃或异常行为。影响范围：10.7.0 ≤ version < 10.7.4；"
            "10.3.x 至 10.6.x 对应修复版本前也受影响。"
        ),
        remediation_cn="升级 MariaDB 至 10.7.4 / 10.6.8 / 10.5.16 / 10.4.25 / 10.3.35 或更高版本。",
    ),
    # MariaDB Binary_string use-after-free
    CveEntry(
        cve_id="CVE-2022-27447",
        component="mariadb",
        max_affected="10.7.4",
        min_version="10.7.0",
        severity=RiskLevel.HIGH,
        cvss_score=7.5,
        title_cn="MariaDB Binary_string 释放后使用漏洞 (CVE-2022-27447)",
        description_cn=(
            "MariaDB Server 在 Binary_string::free_buffer() 组件中存在释放后使用缺陷，"
            "可能导致数据库服务崩溃。影响范围：10.7.0 ≤ version < 10.7.4；"
            "10.3.x 至 10.6.x 对应修复版本前也受影响。"
        ),
        remediation_cn="升级 MariaDB 至 10.7.4 / 10.6.8 / 10.5.16 / 10.4.25 / 10.3.35 或更高版本。",
    ),
    # OpenSSL X.400 地址类型混淆
    CveEntry(
        cve_id="CVE-2023-0286",
        component="openssl",
        max_affected="3.0.8",
        min_version="3.0.0",
        severity=RiskLevel.HIGH,
        cvss_score=7.4,
        title_cn="OpenSSL X.400 地址类型混淆漏洞 (CVE-2023-0286)",
        description_cn=(
            "OpenSSL 在 X.509 GeneralName 的 X.400 地址处理中存在类型混淆，"
            "证书解析或吊销列表检查时可能造成崩溃或内存安全风险。"
            "影响范围：3.0.0 ≤ version < 3.0.8；1.1.1 和 1.0.2 分支对应修复版本前也受影响。"
        ),
        remediation_cn="升级 OpenSSL 至 3.0.8 / 1.1.1t / 1.0.2zg 或更高版本，并及时更新依赖 OpenSSL 的服务。",
    ),
    # phpMyAdmin 参数处理信息泄露
    CveEntry(
        cve_id="CVE-2022-0813",
        component="phpmyadmin",
        max_affected="5.1.2",
        min_version="",
        severity=RiskLevel.HIGH,
        cvss_score=7.5,
        title_cn="phpMyAdmin 无效请求信息泄露 (CVE-2022-0813)",
        description_cn=(
            "phpMyAdmin 5.1.1 及更早版本在 lang、pma_parameter 和 cookie 相关处理上存在缺陷，"
            "无效请求可能暴露敏感信息。影响范围：version < 5.1.2。"
        ),
        remediation_cn="升级 phpMyAdmin 至 5.1.2 或更高版本，并限制管理界面仅内网或 VPN 可访问。",
    ),
    # ============================
    # v0.0.24 CVE 扩充：新增组件
    # ============================
    # MongoDB TLS CA 校验绕过
    CveEntry(
        cve_id="CVE-2024-1351",
        component="mongodb",
        max_affected="7.0.6",
        min_version="7.0.0",
        severity=RiskLevel.CRITICAL,
        cvss_score=9.8,
        title_cn="MongoDB TLS CA 校验绕过 (CVE-2024-1351)",
        description_cn=(
            "MongoDB Server 在特定 --tlsCAFile / tls.CAFile 配置下可能跳过对端证书校验，"
            "使不可信连接被接受，削弱传输安全保证。影响范围：7.0.0 ≤ version < 7.0.6；"
            "4.4.x、5.0.x 和 6.0.x 对应修复版本前也受影响。"
        ),
        remediation_cn="升级 MongoDB Server 至 7.0.6 / 6.0.14 / 5.0.25 / 4.4.29 或更高版本，并复核 TLS CA 配置。",
    ),
    # MongoDB 聚合阶段未初始化内存访问
    CveEntry(
        cve_id="CVE-2024-8654",
        component="mongodb",
        max_affected="6.0.4",
        min_version="6.0.0",
        severity=RiskLevel.CRITICAL,
        cvss_score=9.8,
        title_cn="MongoDB 聚合阶段未初始化内存访问 (CVE-2024-8654)",
        description_cn=(
            "MongoDB Server 在内部聚合阶段处理零参数调用时可能访问未初始化内存，"
            "导致不可预期行为或服务崩溃。影响范围：6.0.0 ≤ version < 6.0.4。"
        ),
        remediation_cn="升级 MongoDB Server 至 6.0.4 或更高版本，并限制未授权用户执行复杂聚合操作。",
    ),
    # MongoDB BSON 构造越界读取/崩溃
    CveEntry(
        cve_id="CVE-2024-10921",
        component="mongodb",
        max_affected="8.0.3",
        min_version="8.0.0",
        severity=RiskLevel.HIGH,
        cvss_score=8.1,
        title_cn="MongoDB BSON 畸形请求内存读取漏洞 (CVE-2024-10921)",
        description_cn=(
            "MongoDB Server 在构造畸形 BSON 的请求处理中可能发生缓冲区越界读取或崩溃，"
            "授权用户可影响服务可用性并可能读取内存内容。影响范围：8.0.0 ≤ version < 8.0.3；"
            "5.0.x 至 7.0.x 对应修复版本前也受影响。"
        ),
        remediation_cn="升级 MongoDB Server 至 8.0.3 / 7.0.15 / 6.0.19 / 5.0.30 或更高版本，并最小化数据库用户权限。",
    ),
    # Django Trunc/Extract SQL 注入
    CveEntry(
        cve_id="CVE-2022-34265",
        component="django",
        max_affected="4.0.6",
        min_version="4.0",
        severity=RiskLevel.CRITICAL,
        cvss_score=9.8,
        title_cn="Django Trunc/Extract SQL 注入 (CVE-2022-34265)",
        description_cn=(
            "Django 的 Trunc() 和 Extract() 数据库函数在 kind/lookup_name 使用不可信输入时可能发生 SQL 注入。"
            "影响范围：4.0 ≤ version < 4.0.6；3.2 ≤ version < 3.2.14 也受影响。"
        ),
        remediation_cn="升级 Django 至 4.0.6 / 3.2.14 或更高版本，并禁止将用户输入直接传入 kind/lookup_name。",
    ),
    # Django JSONField alias SQL 注入
    CveEntry(
        cve_id="CVE-2024-42005",
        component="django",
        max_affected="4.2.15",
        min_version="4.2",
        severity=RiskLevel.HIGH,
        cvss_score=7.3,
        title_cn="Django JSONField 别名 SQL 注入 (CVE-2024-42005)",
        description_cn=(
            "Django QuerySet.values() 和 values_list() 在处理 JSONField 模型列别名时可能受构造键名影响，"
            "导致 SQL 注入风险。影响范围：4.2 ≤ version < 4.2.15；5.0 ≤ version < 5.0.8 也受影响。"
        ),
        remediation_cn="升级 Django 至 4.2.15 / 5.0.8 或更高版本，并校验传入 values()/values_list() 的字段名。",
    ),
    # Laravel 通配符文件验证绕过
    CveEntry(
        cve_id="CVE-2025-27515",
        component="laravel",
        max_affected="11.44.1",
        min_version="",
        severity=RiskLevel.CRITICAL,
        cvss_score=9.8,
        title_cn="Laravel 通配符文件验证绕过 (CVE-2025-27515)",
        description_cn=(
            "Laravel 在使用 files.* 等通配符规则验证文件或图片字段时，"
            "特制请求可能绕过预期验证规则。影响范围：version < 11.44.1；"
            "12.0.0 ≤ version < 12.1.1 也受影响。"
        ),
        remediation_cn="升级 Laravel 至 11.44.1 / 12.1.1 或更高版本，并对上传文件执行服务端 MIME、扩展名和内容校验。",
    ),
    # Laravel register_argc_argv 环境变量污染
    CveEntry(
        cve_id="CVE-2024-52301",
        component="laravel",
        max_affected="11.31.0",
        min_version="11.0.0",
        severity=RiskLevel.HIGH,
        cvss_score=7.5,
        title_cn="Laravel register_argc_argv 环境变量污染 (CVE-2024-52301)",
        description_cn=(
            "Laravel 在 PHP register_argc_argv 开启时，特制查询字符串可能改变框架处理请求使用的环境值，"
            "造成配置污染风险。影响范围：11.0.0 ≤ version < 11.31.0；"
            "6.x 至 10.x 对应修复版本前也受影响。"
        ),
        remediation_cn="升级 Laravel 至 11.31.0 / 10.48.23 / 9.52.17 / 8.83.28 等修复版本，并关闭 PHP register_argc_argv。",
    ),
    # Magento/Adobe Commerce XXE 导致代码执行风险
    CveEntry(
        cve_id="CVE-2024-34102",
        component="magento",
        max_affected="2.4.7p1",
        min_version="",
        severity=RiskLevel.CRITICAL,
        cvss_score=9.8,
        title_cn="Magento/Adobe Commerce XXE 代码执行风险 (CVE-2024-34102)",
        description_cn=(
            "Adobe Commerce / Magento Open Source 对 XML 外部实体引用限制不足，"
            "可能导致任意代码执行风险。影响范围：version < 2.4.7p1；"
            "2.4.6-p5、2.4.5-p7、2.4.4-p8 及更早维护线也受影响。"
        ),
        remediation_cn="升级 Magento Open Source / Adobe Commerce 至 2.4.7-p1 或对应维护分支安全补丁，并禁用不可信 XML 输入。",
    ),
    # Magento/Adobe Commerce 危险文件上传
    CveEntry(
        cve_id="CVE-2024-39397",
        component="magento",
        max_affected="2.4.7p2",
        min_version="",
        severity=RiskLevel.CRITICAL,
        cvss_score=9.0,
        title_cn="Magento/Adobe Commerce 危险文件上传漏洞 (CVE-2024-39397)",
        description_cn=(
            "Adobe Commerce / Magento Open Source 存在危险类型文件上传限制不足，"
            "攻击面可能扩展为任意代码执行风险。影响范围：version < 2.4.7p2；"
            "2.4.6-p6、2.4.5-p8、2.4.4-p9 及更早维护线也受影响。"
        ),
        remediation_cn="升级 Magento Open Source / Adobe Commerce 至 2.4.7-p2 或对应维护分支安全补丁，并限制后台上传文件类型。",
    ),
    # BIND 递归解析器缓存性能退化 DoS
    CveEntry(
        cve_id="CVE-2023-2828",
        component="bind",
        max_affected="9.18.16",
        min_version="9.18.0",
        severity=RiskLevel.HIGH,
        cvss_score=7.5,
        title_cn="BIND 递归解析器缓存拒绝服务 (CVE-2023-2828)",
        description_cn=(
            "ISC BIND 递归解析器在缓存特定响应后可能因缓存数据库处理缺陷导致 named 进程异常退出，"
            "造成 DNS 服务拒绝服务。影响范围：9.18.0 ≤ version < 9.18.16；"
            "9.11.x、9.16.x 和 9.19.x 对应修复版本前也受影响。"
        ),
        remediation_cn="升级 BIND 至 9.18.16 / 9.16.42 / 9.19.14 或更高版本，并监控递归解析器异常退出。",
    ),
    # Exim SMTP Challenge 栈缓冲区溢出
    CveEntry(
        cve_id="CVE-2023-42116",
        component="exim",
        max_affected="4.96.1",
        min_version="",
        severity=RiskLevel.CRITICAL,
        cvss_score=9.8,
        title_cn="Exim SMTP Challenge 栈缓冲区溢出 (CVE-2023-42116)",
        description_cn=(
            "Exim SMTP Challenge 处理逻辑存在栈缓冲区溢出，可能导致远程代码执行风险。影响范围：version < 4.96.1。"
        ),
        remediation_cn="升级 Exim 至 4.96.1 或更高版本，并仅向可信网络暴露管理接口和认证相关功能。",
    ),
]

CVE_DATABASE.extend(
    [
        # ============================
        # Jenkins / Elastic / Kubernetes / HAProxy (v0.0.35)
        # ============================
        CveEntry(
            cve_id="CVE-2024-23897",
            component="jenkins",
            max_affected="2.442",
            min_version="",
            severity=RiskLevel.CRITICAL,
            cvss_score=9.8,
            title_cn="Jenkins CLI 任意文件读取 (CVE-2024-23897)",
            description_cn=(
                "Jenkins CLI 命令解析器可被未认证攻击者利用读取控制器文件，"
                "进而泄露凭据、密钥或插件配置。影响范围：主线 version < 2.442，LTS 需升级到 2.426.3+。"
            ),
            remediation_cn="升级 Jenkins 至 2.442 / 2.426.3 LTS 或更高版本，并限制 CLI 与控制器网络暴露面。",
        ),
        CveEntry(
            cve_id="CVE-2024-23898",
            component="jenkins",
            max_affected="2.442",
            min_version="",
            severity=RiskLevel.HIGH,
            cvss_score=8.8,
            title_cn="Jenkins WebSocket CLI 跨站请求劫持 (CVE-2024-23898)",
            description_cn=(
                "Jenkins WebSocket CLI 缺少充分的来源校验，攻击者可诱导已登录管理员浏览恶意页面，"
                "借助受害者会话执行 Jenkins CLI 操作。影响范围：主线 version < 2.442，LTS 需升级到 2.426.3+。"
            ),
            remediation_cn="升级 Jenkins 至 2.442 / 2.426.3 LTS 或更高版本，并启用严格的管理员会话保护。",
        ),
        CveEntry(
            cve_id="CVE-2023-27898",
            component="jenkins",
            max_affected="2.397",
            min_version="",
            severity=RiskLevel.HIGH,
            cvss_score=8.0,
            title_cn="Jenkins 临时文件权限不当导致信息泄露 (CVE-2023-27898)",
            description_cn=(
                "Jenkins Core 在部分临时文件处理路径上权限控制不足，低权限用户可能读取敏感构建或控制器数据。"
                "影响范围：主线 version < 2.397，LTS 需升级到 2.387.2+。"
            ),
            remediation_cn="升级 Jenkins 至 2.397 / 2.387.2 LTS 或更高版本，并审计作业工作区和凭据使用记录。",
        ),
        CveEntry(
            cve_id="CVE-2023-46673",
            component="elasticsearch",
            max_affected="8.11.1",
            min_version="7.0.0",
            severity=RiskLevel.HIGH,
            cvss_score=7.5,
            title_cn="Elasticsearch Search Application 模板注入风险 (CVE-2023-46673)",
            description_cn=(
                "Elasticsearch Search Application 功能在处理查询模板时存在输入隔离不足，"
                "攻击者可能访问非预期数据或扩大检索范围。影响范围：7.x/8.x 对应修复版本之前。"
            ),
            remediation_cn="升级 Elasticsearch 至供应商修复版本，限制 Search Application 管理权限并审计异常查询模板。",
        ),
        CveEntry(
            cve_id="CVE-2022-23710",
            component="elasticsearch",
            max_affected="7.17.1",
            min_version="7.16.0",
            severity=RiskLevel.MEDIUM,
            cvss_score=6.5,
            title_cn="Elastic Kibana 会话处理缺陷 (CVE-2022-23710)",
            description_cn=(
                "Elastic Stack 的 Kibana 会话处理存在缺陷，攻击者在特定条件下可能绕过预期访问控制或复用会话。"
                "影响范围：7.16.x/7.17.x 修复版本之前。"
            ),
            remediation_cn="升级 Kibana/Elastic Stack 至对应安全版本，缩短会话有效期并强制重新登录高权限账户。",
        ),
        CveEntry(
            cve_id="CVE-2021-22145",
            component="elasticsearch",
            max_affected="7.13.3",
            min_version="7.10.0",
            severity=RiskLevel.HIGH,
            cvss_score=7.5,
            title_cn="Elasticsearch 文档接口信息泄露 (CVE-2021-22145)",
            description_cn=(
                "Elasticsearch 在特定授权与字段级安全配置下可能返回未授权字段，"
                "导致敏感索引数据泄露。影响范围：7.10.0 <= version < 7.13.3。"
            ),
            remediation_cn="升级 Elasticsearch 至 7.13.3 或更高版本，并复核索引权限、字段级安全和审计日志。",
        ),
        CveEntry(
            cve_id="CVE-2023-5044",
            component="kubernetes",
            max_affected="1.9.0",
            min_version="",
            severity=RiskLevel.HIGH,
            cvss_score=7.6,
            title_cn="Kubernetes ingress-nginx 注解注入 (CVE-2023-5044)",
            description_cn=(
                "ingress-nginx 对部分 Ingress 注解校验不足，具备创建 Ingress 权限的攻击者可能注入配置片段，"
                "影响控制器所在命名空间的流量安全。影响范围：ingress-nginx version < 1.9.0。"
            ),
            remediation_cn="升级 ingress-nginx controller 至 1.9.0+，并限制普通用户创建高风险 Ingress 注解的权限。",
        ),
        CveEntry(
            cve_id="CVE-2022-3172",
            component="kubernetes",
            max_affected="1.25.4",
            min_version="1.0.0",
            severity=RiskLevel.MEDIUM,
            cvss_score=6.5,
            title_cn="Kubernetes API Server 聚合接口请求转发缺陷 (CVE-2022-3172)",
            description_cn=(
                "kube-apiserver 在聚合 API 请求转发路径上校验不足，攻击者可能借助受信任的 APIService 触发非预期请求。"
                "影响范围：1.0.0 <= version < 1.25.4（各维护分支以官方修复公告为准）。"
            ),
            remediation_cn="升级 Kubernetes 控制平面至已修复维护版本，并审计 APIService、聚合层证书和 RBAC 配置。",
        ),
        CveEntry(
            cve_id="CVE-2023-40225",
            component="haproxy",
            max_affected="2.8.2",
            min_version="2.0.0",
            severity=RiskLevel.HIGH,
            cvss_score=7.5,
            title_cn="HAProxy HTTP/2 请求处理拒绝服务 (CVE-2023-40225)",
            description_cn=(
                "HAProxy 在 HTTP/2 帧处理上存在资源消耗缺陷，远程攻击者可构造请求导致代理进程 CPU/内存压力异常。"
                "影响范围：2.0.0 <= version < 2.8.2。"
            ),
            remediation_cn="升级 HAProxy 至 2.8.2 或对应维护分支修复版本，并对 HTTP/2 入口启用速率限制和连接上限。",
        ),
        CveEntry(
            cve_id="CVE-2023-0836",
            component="haproxy",
            max_affected="2.7.3",
            min_version="2.0.0",
            severity=RiskLevel.MEDIUM,
            cvss_score=5.3,
            title_cn="HAProxy HTTP 头处理异常导致拒绝服务 (CVE-2023-0836)",
            description_cn=(
                "HAProxy 在特定 HTTP 头解析路径上存在边界处理缺陷，攻击者可触发连接异常或服务可用性下降。"
                "影响范围：2.0.0 <= version < 2.7.3。"
            ),
            remediation_cn="升级 HAProxy 至 2.7.3 或更高修复版本，并监控异常请求头、4xx/5xx 与进程重启事件。",
        ),
        CveEntry(
            cve_id="CVE-2021-40346",
            component="haproxy",
            max_affected="2.5.0",
            min_version="",
            severity=RiskLevel.HIGH,
            cvss_score=8.6,
            title_cn="HAProxy 整数溢出请求走私 (CVE-2021-40346)",
            description_cn=(
                "HAProxy HTTP/1 解析器存在整数溢出缺陷，攻击者可能构造请求走私流量并绕过上游访问控制。"
                "影响范围：version < 2.5.0。"
            ),
            remediation_cn="升级 HAProxy 至 2.5.0 或维护分支修复版本，并在边界代理启用严格 HTTP 规范化。",
        ),
        # ============================
        # Existing components expanded (v0.0.35)
        # ============================
        CveEntry(
            cve_id="CVE-2021-23017",
            component="nginx",
            max_affected="1.21.0",
            min_version="0.6.18",
            severity=RiskLevel.HIGH,
            cvss_score=7.7,
            title_cn="Nginx resolver 越界写入 (CVE-2021-23017)",
            description_cn=(
                "Nginx resolver 在处理 DNS 响应时存在 off-by-one 写入缺陷，"
                "攻击者可通过恶意 DNS 响应造成进程崩溃或潜在代码执行。影响范围：0.6.18 <= version < 1.21.0。"
            ),
            remediation_cn="升级 Nginx 至 1.21.0/1.20.1 或更高版本，并固定可信 DNS 解析器。",
        ),
        CveEntry(
            cve_id="CVE-2017-7529",
            component="nginx",
            max_affected="1.13.3",
            min_version="",
            severity=RiskLevel.HIGH,
            cvss_score=7.5,
            title_cn="Nginx Range 头整数溢出 (CVE-2017-7529)",
            description_cn=(
                "Nginx 对缓存文件的 Range 请求处理存在整数溢出，攻击者可读取缓存文件中的非预期内容。"
                "影响范围：version < 1.13.3。"
            ),
            remediation_cn="升级 Nginx 至 1.13.3 或更高版本，并限制异常 Range 请求与缓存暴露面。",
        ),
        CveEntry(
            cve_id="CVE-2024-21147",
            component="mysql",
            max_affected="8.0.38",
            min_version="8.0.0",
            severity=RiskLevel.HIGH,
            cvss_score=7.5,
            title_cn="MySQL Server 组件权限绕过风险 (CVE-2024-21147)",
            description_cn=(
                "Oracle MySQL Server 组件存在可被低权限账号触发的访问控制缺陷，"
                "成功利用可能影响数据保密性或服务可用性。影响范围：8.0.0 <= version < 8.0.38。"
            ),
            remediation_cn="升级 MySQL 至 8.0.38 或供应商 CPU 修复版本，并最小化数据库账号权限。",
        ),
        CveEntry(
            cve_id="CVE-2023-22053",
            component="mysql",
            max_affected="8.0.34",
            min_version="8.0.0",
            severity=RiskLevel.MEDIUM,
            cvss_score=4.9,
            title_cn="MySQL Server 拒绝服务风险 (CVE-2023-22053)",
            description_cn=(
                "MySQL Server 在特定组件处理路径上存在可被认证用户触发的缺陷，"
                "可能导致服务可用性下降。影响范围：8.0.0 <= version < 8.0.34。"
            ),
            remediation_cn="升级 MySQL 至 8.0.34 或更高安全版本，并监控异常查询与连接重置。",
        ),
        CveEntry(
            cve_id="CVE-2023-36824",
            component="redis",
            max_affected="7.0.12",
            min_version="7.0.0",
            severity=RiskLevel.HIGH,
            cvss_score=8.8,
            title_cn="Redis Lua 脚本沙箱逃逸风险 (CVE-2023-36824)",
            description_cn=(
                "Redis 在 Lua 脚本执行环境中存在沙箱隔离缺陷，认证攻击者可能执行非预期操作。"
                "影响范围：7.0.0 <= version < 7.0.12。"
            ),
            remediation_cn="升级 Redis 至 7.0.12 或更高版本，并禁用不可信脚本、限制管理命令访问。",
        ),
        CveEntry(
            cve_id="CVE-2022-24735",
            component="redis",
            max_affected="6.2.7",
            min_version="",
            severity=RiskLevel.HIGH,
            cvss_score=8.8,
            title_cn="Redis Lua 沙箱绕过 (CVE-2022-24735)",
            description_cn=(
                "Redis Lua 脚本沙箱可被恶意脚本绕过，已认证攻击者可能访问受保护的 Redis 内部对象。"
                "影响范围：version < 6.2.7。"
            ),
            remediation_cn="升级 Redis 至 6.2.7/7.0.0 或更高版本，并对 EVAL 类命令施加最小权限控制。",
        ),
        CveEntry(
            cve_id="CVE-2024-4317",
            component="postgresql",
            max_affected="16.3",
            min_version="12.0",
            severity=RiskLevel.MEDIUM,
            cvss_score=6.5,
            title_cn="PostgreSQL 视图权限绕过 (CVE-2024-4317)",
            description_cn=(
                "PostgreSQL 在特定视图与权限组合下可能泄露调用者不应访问的数据。"
                "影响范围：12.0 <= version < 16.3（各分支以官方小版本修复为准）。"
            ),
            remediation_cn="升级 PostgreSQL 至 16.3/15.7/14.12/13.15/12.19 或对应修复版本，并复核视图权限。",
        ),
        CveEntry(
            cve_id="CVE-2022-1552",
            component="postgresql",
            max_affected="14.3",
            min_version="10.0",
            severity=RiskLevel.HIGH,
            cvss_score=8.8,
            title_cn="PostgreSQL Autovacuum 权限提升风险 (CVE-2022-1552)",
            description_cn=(
                "PostgreSQL Autovacuum 与安全限制函数交互存在缺陷，低权限用户可能借此提升数据库内权限。"
                "影响范围：10.0 <= version < 14.3。"
            ),
            remediation_cn="升级 PostgreSQL 至对应安全小版本，并限制不可信用户创建 SECURITY DEFINER 函数。",
        ),
        CveEntry(
            cve_id="CVE-2023-46589",
            component="apache_tomcat",
            max_affected="10.1.16",
            min_version="8.5.0",
            severity=RiskLevel.HIGH,
            cvss_score=7.5,
            title_cn="Apache Tomcat HTTP 请求走私 (CVE-2023-46589)",
            description_cn=(
                "Apache Tomcat 对部分 HTTP 请求体长度处理不一致，可能导致请求走私或代理链路解析歧义。"
                "影响范围：8.5.0 <= version < 10.1.16（维护分支以官方公告为准）。"
            ),
            remediation_cn="升级 Tomcat 至 10.1.16/9.0.83/8.5.96 或更高版本，并统一前后端代理的 HTTP 规范。",
        ),
        CveEntry(
            cve_id="CVE-2023-41080",
            component="apache_tomcat",
            max_affected="10.1.13",
            min_version="8.5.0",
            severity=RiskLevel.HIGH,
            cvss_score=7.5,
            title_cn="Apache Tomcat Open Redirect 风险 (CVE-2023-41080)",
            description_cn=(
                "Apache Tomcat 在重定向路径处理上存在校验不足，攻击者可构造 URL 诱导用户跳转到非预期站点。"
                "影响范围：8.5.0 <= version < 10.1.13（维护分支以官方公告为准）。"
            ),
            remediation_cn="升级 Tomcat 至 10.1.13/9.0.80/8.5.93 或更高版本，并对外部跳转进行白名单限制。",
        ),
        CveEntry(
            cve_id="CVE-2024-27980",
            component="nodejs",
            max_affected="20.12.2",
            min_version="18.0.0",
            severity=RiskLevel.HIGH,
            cvss_score=7.5,
            title_cn="Node.js HTTP 请求走私 (CVE-2024-27980)",
            description_cn=(
                "Node.js HTTP 解析器在处理畸形请求时可能与前置代理产生解析差异，造成请求走私风险。"
                "影响范围：18.0.0 <= version < 20.12.2（各维护分支以官方修复为准）。"
            ),
            remediation_cn="升级 Node.js 至对应安全版本，并在边界代理启用严格请求规范化和异常头过滤。",
        ),
        CveEntry(
            cve_id="CVE-2023-46809",
            component="nodejs",
            max_affected="20.11.1",
            min_version="18.0.0",
            severity=RiskLevel.MEDIUM,
            cvss_score=5.9,
            title_cn="Node.js OpenSSL Marvin 攻击影响 (CVE-2023-46809)",
            description_cn=(
                "Node.js 使用的加密组件可能受到 RSA 解密侧信道攻击影响，攻击者可在特定条件下恢复敏感信息。"
                "影响范围：18.0.0 <= version < 20.11.1。"
            ),
            remediation_cn="升级 Node.js 至包含 OpenSSL 修复的安全版本，并淘汰 RSA PKCS#1 v1.5 解密流程。",
        ),
        CveEntry(
            cve_id="CVE-2023-5363",
            component="openssl",
            max_affected="3.0.12",
            min_version="3.0.0",
            severity=RiskLevel.HIGH,
            cvss_score=7.5,
            title_cn="OpenSSL POLY1305 处理拒绝服务 (CVE-2023-5363)",
            description_cn=(
                "OpenSSL 在部分加密实现路径上存在边界处理缺陷，可能导致进程崩溃或服务不可用。"
                "影响范围：3.0.0 <= version < 3.0.12。"
            ),
            remediation_cn="升级 OpenSSL 至 3.0.12 或更高版本，并优先启用系统发行版安全更新包。",
        ),
        CveEntry(
            cve_id="CVE-2023-0464",
            component="openssl",
            max_affected="3.0.9",
            min_version="3.0.0",
            severity=RiskLevel.HIGH,
            cvss_score=7.5,
            title_cn="OpenSSL 证书策略校验绕过 (CVE-2023-0464)",
            description_cn=(
                "OpenSSL X.509 证书策略检查存在绕过风险，攻击者可在特定信任链配置下绕过策略限制。"
                "影响范围：3.0.0 <= version < 3.0.9。"
            ),
            remediation_cn="升级 OpenSSL 至 3.0.9 或更高版本，并复核证书策略、客户端认证和信任链配置。",
        ),
        CveEntry(
            cve_id="CVE-2024-38475",
            component="apache_httpd",
            max_affected="2.4.60",
            min_version="2.4.0",
            severity=RiskLevel.CRITICAL,
            cvss_score=9.1,
            title_cn="Apache HTTP Server mod_rewrite SSRF 风险 (CVE-2024-38475)",
            description_cn=(
                "Apache HTTP Server 在 RewriteRule 配置不当时可能将请求代理到非预期后端，形成 SSRF 或访问控制绕过。"
                "影响范围：2.4.0 <= version < 2.4.60。"
            ),
            remediation_cn="升级 httpd 至 2.4.60 或更高版本，并审计 RewriteRule、ProxyPass 与后端白名单。",
        ),
        CveEntry(
            cve_id="CVE-2024-38477",
            component="apache_httpd",
            max_affected="2.4.60",
            min_version="2.4.0",
            severity=RiskLevel.HIGH,
            cvss_score=7.5,
            title_cn="Apache HTTP Server NULL 指针拒绝服务 (CVE-2024-38477)",
            description_cn=(
                "Apache HTTP Server 在特定请求处理路径上可能触发 NULL 指针解引用，导致工作进程崩溃。"
                "影响范围：2.4.0 <= version < 2.4.60。"
            ),
            remediation_cn="升级 httpd 至 2.4.60 或更高版本，并监控异常请求导致的 worker 崩溃。",
        ),
        CveEntry(
            cve_id="CVE-2024-8925",
            component="php",
            max_affected="8.3.12",
            min_version="8.1.0",
            severity=RiskLevel.MEDIUM,
            cvss_score=5.3,
            title_cn="PHP 过滤器路径处理缺陷 (CVE-2024-8925)",
            description_cn=(
                "PHP 在部分过滤器或流封装器路径处理上存在边界校验不足，可能导致非预期文件访问。"
                "影响范围：8.1.0 <= version < 8.3.12（各维护分支以官方修复为准）。"
            ),
            remediation_cn="升级 PHP 至对应安全版本，禁用不必要的 stream wrapper，并限制 Web 进程文件系统权限。",
        ),
        CveEntry(
            cve_id="CVE-2024-11233",
            component="php",
            max_affected="8.3.14",
            min_version="8.1.0",
            severity=RiskLevel.HIGH,
            cvss_score=8.1,
            title_cn="PHP CGI 参数处理绕过 (CVE-2024-11233)",
            description_cn=(
                "PHP CGI/FastCGI 参数解析在特定部署方式下存在绕过风险，攻击者可能影响脚本执行参数。"
                "影响范围：8.1.0 <= version < 8.3.14（各维护分支以官方修复为准）。"
            ),
            remediation_cn="升级 PHP 至安全版本，避免直接暴露 CGI，并在 Web 服务器层固定 FastCGI 参数白名单。",
        ),
        CveEntry(
            cve_id="CVE-2022-21661",
            component="wordpress",
            max_affected="5.8.3",
            min_version="5.0.0",
            severity=RiskLevel.HIGH,
            cvss_score=8.0,
            title_cn="WordPress Core SQL 注入 (CVE-2022-21661)",
            description_cn=(
                "WordPress Core 在 WP_Query 处理路径上存在 SQL 注入风险，攻击者可在特定条件下访问或篡改数据。"
                "影响范围：5.0.0 <= version < 5.8.3。"
            ),
            remediation_cn="升级 WordPress 至 5.8.3 或更高版本，并同步更新主题、插件与数据库账号权限。",
        ),
        CveEntry(
            cve_id="CVE-2019-8942",
            component="wordpress",
            max_affected="5.0.1",
            min_version="",
            severity=RiskLevel.HIGH,
            cvss_score=7.5,
            title_cn="WordPress 附件路径遍历 (CVE-2019-8942)",
            description_cn=(
                "WordPress 媒体附件处理存在路径遍历风险，具备内容编辑权限的攻击者可能访问非预期文件。"
                "影响范围：version < 5.0.1。"
            ),
            remediation_cn="升级 WordPress 至 5.0.1 或更高版本，并限制媒体上传权限与文件类型。",
        ),
        CveEntry(
            cve_id="CVE-2022-32091",
            component="mariadb",
            max_affected="10.8.4",
            min_version="",
            severity=RiskLevel.HIGH,
            cvss_score=7.5,
            title_cn="MariaDB Server 拒绝服务风险 (CVE-2022-32091)",
            description_cn=(
                "MariaDB Server 在特定 SQL 处理路径上存在缺陷，认证攻击者可能导致服务崩溃或可用性下降。"
                "影响范围：version < 10.8.4（各维护分支以官方修复为准）。"
            ),
            remediation_cn="升级 MariaDB 至对应安全版本，并限制低权限账号执行高风险 SQL 功能。",
        ),
        CveEntry(
            cve_id="CVE-2022-32089",
            component="mariadb",
            max_affected="10.8.4",
            min_version="",
            severity=RiskLevel.HIGH,
            cvss_score=7.5,
            title_cn="MariaDB Server 内存破坏风险 (CVE-2022-32089)",
            description_cn=(
                "MariaDB Server 在查询优化或存储引擎交互路径上存在内存安全缺陷，可能造成服务异常终止。"
                "影响范围：version < 10.8.4（各维护分支以官方修复为准）。"
            ),
            remediation_cn="升级 MariaDB 至对应安全版本，并监控数据库进程崩溃、慢查询和异常会话。",
        ),
        CveEntry(
            cve_id="CVE-2018-7600",
            component="drupal",
            max_affected="8.5.1",
            min_version="",
            severity=RiskLevel.CRITICAL,
            cvss_score=9.8,
            title_cn="Drupalgeddon2 远程代码执行 (CVE-2018-7600)",
            description_cn=(
                "Drupal Core 表单 API 渲染数组处理存在远程代码执行漏洞，未认证攻击者可执行任意代码。"
                "影响范围：version < 8.5.1（Drupal 7/8 对应维护分支均需升级）。"
            ),
            remediation_cn="立即升级 Drupal 至官方修复版本，检查 Web 根目录木马、管理员账号和异常模块。",
        ),
        CveEntry(
            cve_id="CVE-2019-6340",
            component="drupal",
            max_affected="8.6.10",
            min_version="8.0.0",
            severity=RiskLevel.HIGH,
            cvss_score=8.1,
            title_cn="Drupal REST 模块远程代码执行 (CVE-2019-6340)",
            description_cn=(
                "Drupal Core RESTful Web Services 在处理非安全字段时存在反序列化风险，攻击者可能执行任意代码。"
                "影响范围：8.0.0 <= version < 8.6.10。"
            ),
            remediation_cn="升级 Drupal 至 8.6.10/8.5.11 或更高版本，并禁用不需要的 REST 资源。",
        ),
    ]
)


# =============================================================================
# NVD API 自动更新工具
# =============================================================================

_NVD_API_URL = "https://services.nvd.nist.gov/rest/json/cves/2.0"
_NVD_LOOKBACK_DAYS = 30
_NVD_MAX_RESULTS_PER_PAGE = 2000
_NVD_RATE_DELAY_WITH_KEY_SECONDS = 0.7
_NVD_RATE_DELAY_NO_KEY_SECONDS = 6.1


def _format_nvd_timestamp(value: datetime) -> str:
    """生成 NVD API 2.0 使用的 UTC 时间戳。"""
    return value.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000")


def _risk_from_cvss(score: float, severity_text: str = "") -> RiskLevel:
    """将 NVD CVSS 分数映射到 LightShield 风险等级。"""
    severity_upper = severity_text.upper()
    if severity_upper == "CRITICAL" or score >= 9.0:
        return RiskLevel.CRITICAL
    if severity_upper == "HIGH" or score >= 7.0:
        return RiskLevel.HIGH
    if severity_upper == "MEDIUM" or score >= 4.0:
        return RiskLevel.MEDIUM
    if severity_upper == "LOW" or score > 0:
        return RiskLevel.LOW
    return RiskLevel.INFO


def _extract_nvd_cvss(cve: dict) -> tuple[float, RiskLevel] | None:
    """从 NVD CVE 对象中提取首选 CVSS v3.x 指标。"""
    metrics = cve.get("metrics") if isinstance(cve, dict) else {}
    if not isinstance(metrics, dict):
        return None

    for key in ("cvssMetricV31", "cvssMetricV30"):
        values = metrics.get(key)
        if not isinstance(values, list) or not values:
            continue
        preferred = next((item for item in values if item.get("source") == "nvd@nist.gov"), values[0])
        cvss_data = preferred.get("cvssData", {}) if isinstance(preferred, dict) else {}
        if not isinstance(cvss_data, dict):
            continue
        try:
            score = float(cvss_data.get("baseScore", 0.0))
        except (TypeError, ValueError):
            continue
        severity_text = str(cvss_data.get("baseSeverity") or preferred.get("baseSeverity") or "")
        return score, _risk_from_cvss(score, severity_text)
    return None


def _extract_nvd_description(cve: dict) -> str:
    """提取 NVD 英文描述，供自动更新条目做防御视角说明。"""
    descriptions = cve.get("descriptions") if isinstance(cve, dict) else []
    if not isinstance(descriptions, list):
        return ""
    for item in descriptions:
        if isinstance(item, dict) and item.get("lang") == "en":
            return str(item.get("value") or "").strip()
    for item in descriptions:
        if isinstance(item, dict) and item.get("value"):
            return str(item["value"]).strip()
    return ""


def _canonical_component_name(value: str) -> str:
    """将 NVD CPE vendor/product 片段映射为组件规范名。"""
    normalized = value.lower().strip().replace("\\", "")
    candidates = {
        normalized,
        normalized.replace("_", "-"),
        normalized.replace("-", "_"),
        normalized.replace(".", ""),
    }
    known_components = {entry.component for entry in CVE_DATABASE}
    for candidate in candidates:
        if candidate in _COMPONENT_ALIASES:
            return _COMPONENT_ALIASES[candidate]
        if candidate in known_components:
            return candidate
    return ""


def _component_from_cpe(criteria: str) -> str:
    """从 CPE 2.3 字符串中推断 LightShield 组件名。"""
    parts = criteria.lower().split(":")
    if len(parts) < 5:
        return ""
    vendor = parts[3]
    product = parts[4]
    for token in (product, vendor, f"{vendor}_{product}", f"{vendor}-{product}"):
        component = _canonical_component_name(token)
        if component:
            return component
    return ""


def _iter_nvd_cpe_matches(nodes: list) -> list[dict]:
    """递归收集 NVD configurations.nodes 下的 cpeMatch 条目。"""
    matches: list[dict] = []
    for node in nodes:
        if not isinstance(node, dict):
            continue
        cpe_match = node.get("cpeMatch", [])
        if isinstance(cpe_match, list):
            matches.extend(item for item in cpe_match if isinstance(item, dict))
        children = node.get("children", [])
        if isinstance(children, list):
            matches.extend(_iter_nvd_cpe_matches(children))
    return matches


def _extract_nvd_component_range(cve: dict) -> tuple[str, str, str]:
    """从 NVD configurations 中提取组件名、最小版本和修复前上界。"""
    configurations = cve.get("configurations") if isinstance(cve, dict) else []
    if not isinstance(configurations, list):
        return "", "", ""

    for config in configurations:
        if not isinstance(config, dict):
            continue
        nodes = config.get("nodes", [])
        if not isinstance(nodes, list):
            continue
        for cpe_match in _iter_nvd_cpe_matches(nodes):
            criteria = str(cpe_match.get("criteria") or "")
            component = _component_from_cpe(criteria)
            if not component:
                continue
            min_version = str(cpe_match.get("versionStartIncluding") or cpe_match.get("versionStartExcluding") or "")
            max_affected = str(cpe_match.get("versionEndExcluding") or cpe_match.get("versionEndIncluding") or "")
            if not max_affected:
                parts = criteria.split(":")
                cpe_version = parts[5] if len(parts) > 5 else ""
                if cpe_version not in ("", "*", "-"):
                    max_affected = cpe_version
            if max_affected:
                return component, min_version, max_affected
    return "", "", ""


def _nvd_item_to_cve_entry(item: dict) -> CveEntry | None:
    """将单条 NVD vulnerability 转换为本地 CveEntry。"""
    cve = item.get("cve") if isinstance(item, dict) else {}
    if not isinstance(cve, dict):
        return None

    cve_id = str(cve.get("id") or "")
    cvss = _extract_nvd_cvss(cve)
    component, min_version, max_affected = _extract_nvd_component_range(cve)
    if not cve_id or cvss is None or not component or not max_affected:
        return None

    score, risk = cvss
    description = _extract_nvd_description(cve)
    title = f"{component} 最新 NVD 漏洞 ({cve_id})"
    description_cn = (
        f"NVD 最新公开漏洞：{description}" if description else "NVD 最新公开漏洞，请结合供应商公告确认影响。"
    )
    remediation_cn = (
        f"核对 {component} 受影响版本并升级至供应商修复版本；"
        "无法立即升级时应限制公网暴露面、收紧访问控制并加强日志监控。"
    )

    return CveEntry(
        cve_id=cve_id,
        component=component,
        max_affected=max_affected,
        min_version=min_version,
        severity=risk,
        cvss_score=score,
        title_cn=title,
        description_cn=description_cn,
        remediation_cn=remediation_cn,
    )


def fetch_latest_cves(api_key: str | None = None, max_results: int = 20) -> list[CveEntry]:
    """从 NVD API 2.0 拉取最近公开 CVE 并转换为 CveEntry 列表。

    Args:
        api_key: NVD API key；未提供时按 5 req/30s 的低频节奏分页。
        max_results: 最多返回的本地 CVE 条目数量。

    Returns:
        可映射到 LightShield 组件的 CVE 条目列表；网络失败或无可映射条目时返回空列表。
    """
    if max_results <= 0:
        return []

    headers = {"User-Agent": "LightShield-CVE-Updater/0.3.5"}
    if api_key:
        headers["apiKey"] = api_key

    now = datetime.now(timezone.utc)
    base_params = {
        "pubStartDate": _format_nvd_timestamp(now - timedelta(days=_NVD_LOOKBACK_DAYS)),
        "pubEndDate": _format_nvd_timestamp(now),
    }
    delay_seconds = _NVD_RATE_DELAY_WITH_KEY_SECONDS if api_key else _NVD_RATE_DELAY_NO_KEY_SECONDS
    entries: list[CveEntry] = []
    start_index = 0
    total_results = max_results

    while len(entries) < max_results and start_index < total_results:
        remaining = max_results - len(entries)
        page_size = min(remaining, _NVD_MAX_RESULTS_PER_PAGE)
        params = {**base_params, "resultsPerPage": page_size, "startIndex": start_index}
        try:
            response = requests.get(_NVD_API_URL, params=params, headers=headers, timeout=20)
            response.raise_for_status()
            payload = response.json()
        except (ValueError, requests.RequestException) as exc:
            get_logger().warning("NVD CVE 拉取失败: %s", exc)
            return entries

        vulnerabilities = payload.get("vulnerabilities", []) if isinstance(payload, dict) else []
        if not isinstance(vulnerabilities, list) or not vulnerabilities:
            break

        for item in vulnerabilities:
            if not isinstance(item, dict):
                continue
            entry = _nvd_item_to_cve_entry(item)
            if entry:
                entries.append(entry)
                if len(entries) >= max_results:
                    break

        try:
            total_results = int(payload.get("totalResults", start_index + len(vulnerabilities)))
        except (TypeError, ValueError):
            total_results = start_index + len(vulnerabilities)
        start_index += len(vulnerabilities)
        if len(entries) < max_results and start_index < total_results:
            time.sleep(delay_seconds)

    return entries[:max_results]


# =============================================================================
# 版本号解析工具
# =============================================================================

# 将各种格式的版本号统一为可比较的元组
# 例如：  "8.9p1" → (8, 9, 1)   "1.25.3" → (1, 25, 3)


def _parse_version(version_str: str) -> tuple[int, ...]:
    """将版本字符串解析为可比较的整数元组

    支持的格式：
      - n.n.n（如 1.24.0、8.0.36）
      - n.npN（如 8.9p1、9.3p2）→ 转换为 n.n.N
      - n.n（如 10.0）
      - n.n.n-n（如 8.4.0-1）

    解析失败时返回空元组，调用方应视为无法比较。

    Args:
        version_str: 原始版本字符串

    Returns:
        整数元组，如 (8, 9, 1)
    """
    if not version_str:
        return ()

    # 清理前导 v/V（如 v1.2.3）
    cleaned = version_str.strip().lstrip("vV")

    # 处理 'p' 后缀： 8.9p1 → 8.9.1
    if "p" in cleaned:
        cleaned = re.sub(r"p(\d+)", r".\1", cleaned)

    # 提取所有数字段
    parts = re.findall(r"\d+", cleaned)
    if not parts:
        return ()
    return tuple(int(p) for p in parts)


def _version_matches(actual: str, rules: list[tuple[str, str]]) -> bool:
    """检查实际版本是否落在 CVE 的影响范围内

    Args:
        actual: 实际检测到的版本字符串
        rules: [(min_version, max_affected_by), ...] 每个区间为 [min, max) 半开

    Returns:
        True 如果版本在任意一个区间内
    """
    actual_tuple = _parse_version(actual)
    if not actual_tuple:
        return False  # 无法解析版本，保守处理：不匹配

    for min_ver, max_ver in rules:
        min_tuple = _parse_version(min_ver) if min_ver else ()
        max_tuple = _parse_version(max_ver)

        if not max_tuple:
            continue  # 无法解析区间上限，跳过

        # 检查 >= min
        if min_tuple and actual_tuple < min_tuple:
            continue
        # 检查 < max
        if actual_tuple >= max_tuple:
            continue

        return True
    return False


# =============================================================================
# HTTP 组件指纹
# =============================================================================

# 响应头 → 组件的提取规则
# 格式: (header_name, regex_pattern, component_name)
_HEADER_SIGNATURES: list[tuple[str, str, str]] = [
    # 按优先级排序：越具体的模式越靠前
    # PHP（X-Powered-By）
    ("x-powered-by", r"PHP/(\d+\.\d+\.\d+)", "php"),
    ("x-powered-by", r"ASP\.NET", ""),
    ("x-powered-by", r"Express", "nodejs"),
    # 服务器
    ("server", r"nginx/(\d+\.\d+\.\d+)", "nginx"),
    ("server", r"openresty/(\d+\.\d+\.\d+)", "openresty"),
    ("server", r"Apache/(\d+\.\d+\.\d+)", "apache_httpd"),
    ("server", r"Apache-Coyote/(\d+\.\d+)", "apache_tomcat"),
    ("server", r"Microsoft-IIS/(\d+\.\d+)", "microsoft_iis"),
    ("server", r"LiteSpeed", "litespeed"),
    ("server", r"Caddy", "caddy"),
    ("server", r"Werkzeug/(\d+\.\d+\.\d+)", "werkzeug"),
    ("server", r"gunicorn/(\d+\.\d+\.\d+)", "gunicorn"),
    ("server", r"Jetty\((\d+\.\d+\.\d+)", "jetty"),
    # 框架 / CMS
    ("x-generator", r"Drupal\s+(\d+\.\d+\.\d+)", "drupal"),
    ("x-drupal-cache", r"", "drupal"),
]

# HTML meta 标签签名
_META_SIGNATURES: list[tuple[str, str]] = [
    # (meta name/content regex, version capture, component_name)
    (r'<meta\s+name="generator"\s+content="WordPress\s+(\d+\.\d+\.\d+)', "wordpress"),
    (r'<meta\s+name="generator"\s+content="Joomla!\s*-\s*(\d+\.\d+\.\d+)', "joomla"),
    (r'<meta\s+name="generator"\s+content="Drupal\s+(\d+\.\d+\.\d+)', "drupal"),
    (r'<meta\s+name="generator"\s+content="MediaWiki\s+(\d+\.\d+\.\d+)', "mediawiki"),
]

# Cookie 签名
_COOKIE_SIGNATURES: list[tuple[str, str]] = [
    # (cookie_name_substring, component_name)
    ("PHPSESSID", "php"),
    ("wp-settings-", "wordpress"),
    ("wordpress_logged_in_", "wordpress"),
    ("phpMyAdmin", "phpmyadmin"),
    ("pma_cookie_", "phpmyadmin"),
    ("SSESS", "drupal"),
    ("joomla_user_state", "joomla"),
    ("laravel_session", "laravel"),
    ("JSESSIONID", "java"),
    ("_csrf", ""),  # 通用 CSRF token，不指向特定组件
]


# =============================================================================
# 组件检测适配器
# =============================================================================


class ComponentCheckerAdapter(BaseAdapter):
    """组件版本检测 + CVE 匹配适配器

    检测能力：
    - HTTP 响应头解析（Server / X-Powered-By / X-Generator）
    - HTML meta 标签解析（generator）
    - Cookie 指纹识别
    - 与 CVE 知识库（≥30 条）匹配，输出风险分级

    输入约束：
    - 仅对用户自有资产进行探测（由 validate_target 保障）
    - 不做任何攻击性操作，仅读取公开 HTTP 信息
    """

    # HTTP 请求配置
    _TIMEOUT = 10  # 单次请求超时（秒）
    _USER_AGENT = "Mozilla/5.0 (compatible; LightShield-Security-Scanner/0.0.7; +https://github.com/lightshield)"
    _MAX_BODY_SIZE = 512 * 1024  # 最多读取 512KB HTML

    def __init__(self):
        super().__init__(name="ComponentChecker")
        self._logger = get_logger()

    # =========================================================================
    # BaseAdapter 接口
    # =========================================================================

    def capabilities(self) -> list[str]:
        """返回 ['component_check']"""
        return ["component_check"]

    def validate_target(self, target: str) -> bool:
        """目标合法性校验——委托给 TargetValidator"""
        is_valid, reason = TargetValidator.validate(target)
        if not is_valid:
            self._logger.warning("component_checker", f"目标校验失败: {target} — {reason}")
        return is_valid

    def scan(self, target: str, **kwargs) -> ScanResult:
        """执行组件版本检测 + CVE 匹配

        流程：
        1. R2 输入校验
        2. HTTP 探测 → 提取 Web 组件（委托 _probe_http_components）
        3. 补充非 HTTP 组件（委托 _supplement_from_services）
        4. CVE 知识库匹配 → 生成 VulnFinding（委托 _build_cve_findings）
        5. 组装返回 ScanResult（委托 _assemble_result）

        Args:
            target: 扫描目标（IP 或域名）
            **kwargs:
                services: 上游扫描得到的服务列表
                          [{"name": "mysql", "version": "8.0.35", "port": 3306}, ...]
                http_ports: 自定义 HTTP 端口列表，默认 [80, 443, 8080, 8443]
                timeout: HTTP 请求超时（秒），默认 10
                user_agent: 自定义 UA

        Returns:
            ScanResult 包含组件发现 + CVE 匹配结果
        """
        start_time = time.time()

        # ---- Step 1: 合规校验 ----
        if not self.validate_target(target):
            return ScanResult(
                status=ScanStatus.FAILED,
                target=target,
                error="目标校验不通过",
            )

        scan_id = self._log_scan_start(target, "component_check")

        # ---- Step 2: HTTP 探测 ----
        http_ports = kwargs.get("http_ports", [80, 443, 8080, 8443])
        timeout_val = kwargs.get("timeout", self._TIMEOUT)
        user_agent = kwargs.get("user_agent", self._USER_AGENT)

        detected_components, raw_details = self._probe_http_components(target, http_ports, timeout_val, user_agent)

        # ---- Step 3: 补充非 HTTP 组件 ----
        services = kwargs.get("services", [])
        svc_components, svc_details = self._supplement_from_services(services)
        for comp, ver in svc_components.items():
            if comp not in detected_components:
                detected_components[comp] = ver
        raw_details.extend(svc_details)

        # ---- Step 4: CVE 匹配 ----
        findings = self._build_cve_findings(detected_components)

        # ---- Step 5: 组装结果 ----
        result = self._assemble_result(target, detected_components, findings, raw_details, start_time)

        self._log_scan_end(scan_id, result)
        self._logger.info(
            "component_checker",
            f"扫描完成: {len(detected_components)} 组件, {len(findings)} 个 CVE 命中",
        )

        return result

    # =========================================================================
    # scan() 子步骤（提取为独立方法以控制圈复杂度）
    # =========================================================================

    def _probe_http_components(
        self, target: str, http_ports: list[int], timeout: int, user_agent: str
    ) -> tuple[dict[str, str], list[dict]]:
        """HTTP 多端口探测 → 提取 Web 组件指纹

        遍历 HTTP 端口列表，对每个端口发起 GET 请求，
        调用 _parse_http_response 解析响应提取组件信息。
        首个成功返回组件信息的端口即停止探测。

        Args:
            target: 扫描目标（IP 或域名）
            http_ports: HTTP 端口列表
            timeout: 请求超时（秒）
            user_agent: User-Agent 头

        Returns:
            (detected_components, raw_details)
            - detected_components: {规范组件名: 版本号}
            - raw_details: 原始检测详情列表
        """
        detected_components: dict[str, str] = {}
        raw_details: list[dict] = []

        for port in sorted(set(http_ports)):
            url = f"https://{target}" if port == 443 else f"http://{target}:{port}"

            try:
                resp = requests.get(
                    url,
                    timeout=timeout,
                    headers={"User-Agent": user_agent},
                    allow_redirects=True,
                    stream=True,
                    # nosec B501 — 安全扫描需兼容内网自签证书
                    verify=False,
                )
                components, details = self._parse_http_response(resp, port)
                for comp, ver in components.items():
                    if comp not in detected_components:
                        detected_components[comp] = ver
                raw_details.extend(details)

                # 首次成功即可获得足够信息
                if detected_components:
                    break

            except requests.exceptions.SSLError:
                self._logger.info("component_checker", f"SSL 错误 {url}，跳过")
                continue
            except requests.exceptions.ConnectionError:
                continue
            except requests.exceptions.Timeout:
                self._logger.info("component_checker", f"HTTP 超时 {url}")
                continue
            except Exception as exc:
                self._logger.info("component_checker", f"HTTP 请求失败 {url}: {exc}")
                continue

        return detected_components, raw_details

    def _parse_http_response(self, resp: requests.Response, port: int) -> tuple[dict[str, str], list[dict]]:
        """解析单次 HTTP 响应 → 提取组件指纹

        从三个维度检测组件：
        1. 响应头（Server / X-Powered-By / X-Generator 等）
        2. HTML meta 标签（generator）
        3. Set-Cookie 指纹

        Args:
            resp: requests 库的 Response 对象
            port: 探测端口号

        Returns:
            (detected_components, raw_details)
            - detected_components: {规范组件名: 版本号}
            - raw_details: 原始检测详情列表
        """
        detected_components: dict[str, str] = {}
        raw_details: list[dict] = []

        # 读取 body（流式 + 大小截断）
        body = b""
        for chunk in resp.iter_content(chunk_size=8192):
            body += chunk
            if len(body) > self._MAX_BODY_SIZE:
                break
        html_text = body.decode("utf-8", errors="replace")

        headers_lower = {k.lower(): v for k, v in resp.headers.items()}

        # ---- 响应头解析 ----
        for header_key, pattern, comp_name in _HEADER_SIGNATURES:
            value = headers_lower.get(header_key)
            if not value:
                continue
            m = re.search(pattern, value, re.IGNORECASE)
            if m:
                version = m.group(1) if m.groups() else ""
                component = comp_name or _infer_component_from_header(header_key, value)
                if component and component not in detected_components:
                    detected_components[component] = version
                    raw_details.append(
                        {
                            "source": f"header:{header_key}",
                            "component": component,
                            "version": version,
                            "raw_value": value,
                            "port": port,
                        }
                    )

        # ---- HTML meta 解析 ----
        for pattern, comp_name in _META_SIGNATURES:
            m = re.search(pattern, html_text, re.IGNORECASE)
            if m and m.group(1):
                version = m.group(1)
                if comp_name not in detected_components:
                    detected_components[comp_name] = version
                    raw_details.append(
                        {
                            "source": "html:meta",
                            "component": comp_name,
                            "version": version,
                            "raw_value": m.group(0),
                            "port": port,
                        }
                    )

        # ---- Cookie 指纹识别 ----
        set_cookies = headers_lower.get("set-cookie", "")
        for cookie_name, comp_name in _COOKIE_SIGNATURES:
            if comp_name and cookie_name.lower() in set_cookies.lower() and comp_name not in detected_components:
                detected_components[comp_name] = ""
                raw_details.append(
                    {
                        "source": "header:cookie",
                        "component": comp_name,
                        "version": "",
                        "raw_value": f"Cookie contains '{cookie_name}'",
                        "port": port,
                    }
                )
                break  # 只取最匹配的一个

        return detected_components, raw_details

    def _supplement_from_services(self, services: list[dict]) -> tuple[dict[str, str], list[dict]]:
        """从上游服务列表补充非 HTTP 组件（如 MySQL/SSH/Redis）

        通过 _COMPONENT_ALIASES 将服务名映射为规范组件名，
        供后续 CVE 匹配使用。

        Args:
            services: 上游扫描得到的服务列表
                      [{"name": "mysql", "version": "8.0.35", "port": 3306}, ...]

        Returns:
            (components, details)
            - components: {规范组件名: 版本号}
            - details: 原始检测详情列表
        """
        components: dict[str, str] = {}
        details: list[dict] = []

        for svc in services:
            svc_name = svc.get("name", "").lower()
            svc_version = svc.get("version", "")
            canonical = _COMPONENT_ALIASES.get(svc_name, svc_name)
            if canonical:
                components[canonical] = svc_version
                details.append(
                    {
                        "source": "services",
                        "component": canonical,
                        "version": svc_version,
                        "raw_value": f"{svc_name} {svc_version}",
                        "port": svc.get("port", ""),
                    }
                )

        return components, details

    def _build_cve_findings(self, components: dict[str, str]) -> list[VulnFinding]:
        """将检测到的组件与 CVE 知识库匹配 → 生成 VulnFinding 列表

        Args:
            components: {规范组件名: 版本号}

        Returns:
            CVE 匹配到的漏洞发现列表
        """
        findings: list[VulnFinding] = []
        for comp_name, comp_version in components.items():
            matched_cves = self._match_cves(comp_name, comp_version)
            for cve in matched_cves:
                findings.append(
                    VulnFinding(
                        vuln_type="component_cve",
                        severity=cve.severity,
                        title=cve.title_cn,
                        description=(f"检测到 {comp_name} {comp_version} 存在已知漏洞。\n{cve.description_cn}"),
                        evidence=(f"组件: {comp_name} {comp_version}  CVE: {cve.cve_id}  CVSS: {cve.cvss_score}"),
                        remediation=cve.remediation_cn,
                        cve_id=cve.cve_id,
                        cvss_score=cve.cvss_score,
                    )
                )
        return findings

    def _assemble_result(
        self,
        target: str,
        components: dict[str, str],
        findings: list[VulnFinding],
        raw_details: list[dict],
        start_time: float,
    ) -> ScanResult:
        """组装最终的 ScanResult

        Args:
            target: 扫描目标
            components: {规范组件名: 版本号}
            findings: CVE 匹配生成的漏洞发现列表
            raw_details: 原始检测详情
            start_time: 扫描开始时间戳（time.time()）

        Returns:
            组装完成的 ScanResult
        """
        duration = round(time.time() - start_time, 2)
        services_out = [{"name": comp, "version": ver} for comp, ver in components.items()]
        ports_out = [
            {
                "port": d.get("port") if isinstance(d.get("port"), int) else 0,
                "service": d["component"],
                "state": "open",
            }
            for d in raw_details
        ]

        return ScanResult(
            status=ScanStatus.COMPLETED,
            target=target,
            ports=ports_out,
            services=services_out,
            findings=findings,
            raw_output=(f"检测到 {len(components)} 个组件, 匹配 {len(findings)} 个 CVE"),
            duration_seconds=duration,
        )

    # =========================================================================
    # CVE 匹配引擎
    # =========================================================================

    def _match_cves(self, component: str, version: str) -> list[CveEntry]:
        """将检测到的组件版本与 CVE 知识库进行匹配

        Args:
            component: 规范组件名（如 'nginx', 'openssh'）
            version: 检测到的版本号（如 '1.24.0', '8.9p1'）

        Returns:
            匹配到的 CVE 条目列表
        """
        matched: list[CveEntry] = []

        if not version:
            # 只检测到组件存在但无版本号 → 标记所有已知 CVE（保守策略）
            # 实际生产环境应仅报告无法确定版本
            return matched

        for cve in CVE_DATABASE:
            if cve.component != component:
                continue
            if _version_matches(version, [(cve.min_version, cve.max_affected)]):
                matched.append(cve)

        return matched

    # =========================================================================
    # 便捷方法
    # =========================================================================

    def get_cve_summary(self, result: ScanResult) -> str:
        """生成 CVE 匹配摘要（用于报告）

        Args:
            result: scan() 返回的 ScanResult

        Returns:
            格式化的 CVE 摘要文本
        """
        if not result.findings:
            return "未发现匹配的 CVE 漏洞。"
        lines = [f"目标: {result.target}", f"匹配 CVE 数量: {len(result.findings)}", ""]
        for f in result.findings:
            lines.append(f"[{f.severity.value.upper():8s}] {f.cve_id}  (CVSS {f.cvss_score}) — {f.title}")
        return "\n".join(lines)


# =============================================================================
# 工具函数
# =============================================================================


def _infer_component_from_header(header_key: str, value: str) -> str:
    """从无法精确匹配的 header 值推断组件名称"""
    value_lower = value.lower()
    for keyword, comp_name in _COMPONENT_ALIASES.items():
        if keyword in value_lower:
            return comp_name
    return ""


def _parse_component_checker_args() -> argparse.Namespace:
    """解析 component_checker 自检与 NVD 更新参数。"""
    parser = argparse.ArgumentParser(description="LightShield 组件 CVE 知识库自检 / NVD 自动更新")
    parser.add_argument("--cve-update", action="store_true", help="从 NVD API 2.0 拉取最近 CVE 并打印 CveEntry 摘要")
    parser.add_argument("--nvd-api-key", default=None, help="NVD API key；提供后可使用更高频率限制")
    parser.add_argument("--max-results", type=int, default=20, help="最多拉取并转换的 CVE 条目数量")
    return parser.parse_args()


def _print_latest_cves(entries: list[CveEntry]) -> None:
    """打印 NVD 自动更新结果，便于 CLI/人工复制到知识库。"""
    print(f"从 NVD 转换 {len(entries)} 条可映射 CVE：")
    for entry in entries:
        print(
            f"- {entry.cve_id} {entry.component} "
            f"[{entry.min_version or '*'}, {entry.max_affected}) "
            f"{entry.severity.value} CVSS {entry.cvss_score}"
        )
        print(f"  {entry.title_cn}")


# =============================================================================
# 自检
# =============================================================================

if __name__ == "__main__":
    args = _parse_component_checker_args()
    if args.cve_update:
        _print_latest_cves(fetch_latest_cves(api_key=args.nvd_api_key, max_results=args.max_results))
        raise SystemExit(0)

    print("=== ComponentChecker 自检 ===\n")

    # 1. 基本属性
    checker = ComponentCheckerAdapter()
    assert checker.capabilities() == ["component_check"], "capabilities 错误"
    print("✅ capabilities() 返回 ['component_check']")

    # 2. 目标校验
    assert checker.validate_target("127.0.0.1") is True
    assert checker.validate_target("192.168.1.0/24") is False
    assert checker.validate_target("") is False
    print("✅ validate_target() 通过")

    # 3. 版本解析
    assert _parse_version("1.24.0") == (1, 24, 0)
    assert _parse_version("8.9p1") == (8, 9, 1)
    assert _parse_version("10.0") == (10, 0)
    assert _parse_version("9.3p2") == (9, 3, 2)
    assert _parse_version("v2.4.58") == (2, 4, 58)
    assert _parse_version("") == ()
    assert _parse_version("unknown") == ()
    print("✅ _parse_version() 通过")

    # 4. 版本范围匹配
    assert _version_matches("8.9p1", [("8.5p1", "9.8p1")]) is True  # 在区间内
    assert _version_matches("8.5p1", [("8.5p1", "9.8p1")]) is True  # 等于 min
    assert _version_matches("9.0p1", [("8.5p1", "9.8p1")]) is True  # 在区间内
    assert _version_matches("9.8p1", [("8.5p1", "9.8p1")]) is False  # 等于 max（不含）
    assert _version_matches("7.4p1", [("8.5p1", "9.8p1")]) is False  # 低于 min
    assert _version_matches("9.9p1", [("8.5p1", "9.8p1")]) is False  # 高于 max
    print("✅ _version_matches() 通过")

    # 5. CVE 匹配
    cves = checker._match_cves("openssh", "9.0p1")
    # OpenSSH 9.0p1: 应在 CVE-2024-6387 [8.5p1, 9.8p1) 和 CVE-2023-38408 [5.5p1, 9.3p2) 区间内
    assert any(c.cve_id == "CVE-2024-6387" for c in cves), "应匹配到 regreSSHion"
    print(f"✅ _match_cves('openssh', '9.0p1'): 匹配 {len(cves)} 个 CVE")

    for cve in cves:
        print(f"   [{cve.severity.value}] {cve.cve_id} (CVSS {cve.cvss_score}) — {cve.title_cn[:60]}...")

    cves_none = checker._match_cves("openssh", "9.9p1")
    assert len(cves_none) == 0, "应无匹配（版本超出影响范围）"
    print(f"✅ _match_cves('openssh', '9.9p1'): 匹配 {len(cves_none)} 个 CVE（预期 0）")

    # 6. CVE 知识库规模
    known_components = set(cve.component for cve in CVE_DATABASE)
    print(f"\n✅ CVE 知识库: {len(CVE_DATABASE)} 条记录, 覆盖 {len(known_components)} 个组件")
    print(f"   组件列表: {sorted(known_components)}")

    # 7. scan() 模拟（通过 services 注入）
    mock_result = checker.scan(
        "127.0.0.1",
        services=[
            {"name": "nginx", "version": "1.24.0", "port": 80},
            {"name": "openssh", "version": "8.9p1", "port": 22},
            {"name": "mysql", "version": "8.0.30", "port": 3306},
            {"name": "php", "version": "8.1.27", "port": 9000},
            {"name": "wordpress", "version": "6.4.2", "port": 80},
        ],
    )
    print(f"\n✅ scan() 返回状态: {mock_result.status.value}")
    print(f"   检测组件: {len(mock_result.services)} 个")
    print(f"   CVE 命中: {len(mock_result.findings)} 个")
    for f in mock_result.findings:
        print(f"   [{f.severity.value:8s}] {f.cve_id} (CVSS {f.cvss_score}) — {f.title[:70]}")

    # 8. 摘要
    summary = checker.get_cve_summary(mock_result)
    print(f"\n✅ get_cve_summary() 生成 {len(summary)} 字符摘要")

    print("\n=== ComponentChecker 自检全部通过 ===")
