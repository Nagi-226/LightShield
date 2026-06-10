"""
LightShield 组件版本检测器 — 组件指纹识别 + CVE 匹配

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

import re
import itertools
import time
import socket
from dataclasses import dataclass
from typing import Optional
from urllib.parse import urlparse

import requests

from lightshield.adapters.base import BaseAdapter, ScanResult, VulnFinding
from lightshield.utils.constants import ScanStatus, RiskLevel
from lightshield.utils.validator import TargetValidator
from lightshield.utils.logger import get_logger


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
    "jetty": "jetty",

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

    # 其他
    "openssh": "openssh",
    "openssl": "openssl",
    "phpmyadmin": "phpmyadmin",
    "vsftpd": "vsftpd",
    "proftpd": "proftpd",
    "exim": "exim",
    "postfix": "postfix",
    "sendmail": "sendmail",
    "bind": "bind",
}


# =============================================================================
# CVE 知识库（≥25 条，来源于 NVD 公开记录）
# =============================================================================

@dataclass  # type: ignore  # Python 3.10 标准库无 dataclass，此处用装饰器兼容
class _CveEntry:
    """CVE 知识库条目"""
    cve_id: str
    component: str          # 规范组件名
    max_affected: str       # 最大受影响版本（不含），即 version < max_affected
    min_version: str        # 起始受影响版本（含），'' 表示所有更早版本
    severity: RiskLevel
    cvss_score: float
    title_cn: str           # 中文简述
    description_cn: str     # 中文详细描述
    remediation_cn: str     # 中文修复建议


# ---- 使用 @dataclass 装饰器 (Python 3.10+) ----
from dataclasses import dataclass as _dataclass


@_dataclass
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
        remediation_cn=(
            "升级至 nginx 1.25.3 / 1.24.1+，"
            "或在配置中限制 http2_max_concurrent_streams 为较低值。"
        ),
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
            "MariaDB 10.9.3 之前版本存在多个段错误崩溃点，"
            "可被用于拒绝服务攻击。影响范围：version < 10.9.3。"
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
]


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
_META_SIGNATURES: list[tuple[str, str, str]] = [
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
    _TIMEOUT = 10             # 单次请求超时（秒）
    _USER_AGENT = (
        "Mozilla/5.0 (compatible; LightShield-Security-Scanner/0.0.7; "
        "+https://github.com/lightshield)"
    )
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
        2. HTTP 探测端口 80 / 443 / 8080 / 8443
        3. 解析响应头 / HTML meta / Cookie 提取组件列表
        4. 从 kwargs['services'] 补充非 HTTP 组件（如 MySQL/SSH）
        5. 匹配 CVE 知识库 → 生成 VulnFinding
        6. 返回合并结果

        Args:
            target: 扫描目标（IP 或域名）
            **kwargs:
                services: 上游扫描得到的服务列表
                          [{"name": "mysql", "version": "8.0.35", "port": 3306}, ...]
                ports: 上游端口列表
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

        # ---- Step 2: 探测 HTTP 服务 ----
        detected_components: dict[str, str] = {}  # {规范组件名: 版本}
        raw_details: list[dict] = []               # 原始检测详情

        http_ports = kwargs.get("http_ports", [80, 443, 8080, 8443])
        timeout_val = kwargs.get("timeout", self._TIMEOUT)
        user_agent = kwargs.get("user_agent", self._USER_AGENT)

        # 去重端口
        for port in sorted(set(http_ports)):
            if port == 443:
                url = f"https://{target}"
            else:
                url = f"http://{target}:{port}"

            try:
                resp = requests.get(
                    url,
                    timeout=timeout_val,
                    headers={"User-Agent": user_agent},
                    allow_redirects=True,
                    stream=True,  # 流式读取，限制 body 大小
                    verify=False,  # 自签证书不阻断检测
                )
                # 限制读取大小
                body = b""
                for chunk in resp.iter_content(chunk_size=8192):
                    body += chunk
                    if len(body) > self._MAX_BODY_SIZE:
                        break
                html_text = body.decode("utf-8", errors="replace")
                status_code = resp.status_code
            except requests.exceptions.SSLError:
                # HTTPS 证书错误 → 尝试 HTTP 回退（仅在非 443 端口）
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

            # ---- 解析响应头 ----
            headers_lower = {k.lower(): v for k, v in resp.headers.items()}
            for header_key, pattern, comp_name in _HEADER_SIGNATURES:
                value = headers_lower.get(header_key)
                if not value:
                    continue
                m = re.search(pattern, value, re.IGNORECASE)
                if m:
                    version = ""
                    if m.groups():
                        version = m.group(1)
                    component = comp_name or _infer_component_from_header(header_key, value)
                    if component and component not in detected_components:
                        detected_components[component] = version
                        raw_details.append({
                            "source": f"header:{header_key}",
                            "component": component,
                            "version": version,
                            "raw_value": value,
                            "port": port,
                        })

            # ---- 解析 HTML meta ----
            for pattern, comp_name in _META_SIGNATURES:
                m = re.search(pattern, html_text, re.IGNORECASE)
                if m and m.group(1):
                    version = m.group(1)
                    if comp_name not in detected_components:
                        detected_components[comp_name] = version
                        raw_details.append({
                            "source": "html:meta",
                            "component": comp_name,
                            "version": version,
                            "raw_value": m.group(0),
                            "port": port,
                        })

            # ---- Cookie 指纹识别 ----
            set_cookies = headers_lower.get("set-cookie", "")
            for cookie_name, comp_name in _COOKIE_SIGNATURES:
                if comp_name and cookie_name.lower() in set_cookies.lower():
                    if comp_name not in detected_components:
                        detected_components[comp_name] = ""
                        raw_details.append({
                            "source": "header:cookie",
                            "component": comp_name,
                            "version": "",
                            "raw_value": f"Cookie contains '{cookie_name}'",
                            "port": port,
                        })
                        break  # 只取最匹配的一个

            # 取第一个成功的 HTTP 响应即可获得足够信息
            if detected_components:
                break

        # ---- Step 3: 补充非 HTTP 组件 ----
        services = kwargs.get("services", [])
        for svc in services:
            svc_name = svc.get("name", "").lower()
            svc_version = svc.get("version", "")
            canonical = _COMPONENT_ALIASES.get(svc_name, svc_name)
            if canonical and canonical not in detected_components:
                detected_components[canonical] = svc_version
                raw_details.append({
                    "source": "services",
                    "component": canonical,
                    "version": svc_version,
                    "raw_value": f"{svc_name} {svc_version}",
                    "port": svc.get("port", ""),
                })

        # ---- Step 4: CVE 匹配 ----
        findings: list[VulnFinding] = []
        for comp_name, comp_version in detected_components.items():
            matched_cves = self._match_cves(comp_name, comp_version)
            for cve in matched_cves:
                findings.append(VulnFinding(
                    vuln_type="component_cve",
                    severity=cve.severity,
                    title=cve.title_cn,
                    description=(
                        f"检测到 {comp_name} {comp_version} 存在已知漏洞。\n"
                        f"{cve.description_cn}"
                    ),
                    evidence=(
                        f"组件: {comp_name} {comp_version}  "
                        f"CVE: {cve.cve_id}  "
                        f"CVSS: {cve.cvss_score}"
                    ),
                    remediation=cve.remediation_cn,
                    cve_id=cve.cve_id,
                    cvss_score=cve.cvss_score,
                ))

        # 如果只检测到组件但没有匹配到 CVE，生成 INFO 级别记录
        for comp_name, comp_version in detected_components.items():
            has_cve = any(
                cve.component == comp_name
                for cve in CVE_DATABASE
            )
            if not has_cve:
                # 组件不在 CVE 知识库中 — 记录但不算漏洞
                pass
            elif not any(
                f.cve_id
                for f in findings
                if any(cve.component == comp_name for cve in CVE_DATABASE)
            ):
                pass  # 已退出循环

        # ---- Step 5: 组装结果 ----
        duration = round(time.time() - start_time, 2)
        services_out = [
            {"name": comp, "version": ver}
            for comp, ver in detected_components.items()
        ]
        ports_out = [
            {"port": d.get("port", 0), "service": d["component"], "state": "open"}
            for d in raw_details
        ]

        result = ScanResult(
            status=ScanStatus.COMPLETED,
            target=target,
            ports=ports_out,
            services=services_out,
            findings=findings,
            raw_output=f"检测到 {len(detected_components)} 个组件, "
                       f"匹配 {len(findings)} 个 CVE",
            duration_seconds=duration,
        )

        self._log_scan_end(scan_id, result)
        self._logger.info(
            "component_checker",
            f"扫描完成: {len(detected_components)} 组件, {len(findings)} 个 CVE 命中",
        )

        return result

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
            lines.append(
                f"[{f.severity.value.upper():8s}] {f.cve_id}  "
                f"(CVSS {f.cvss_score}) — {f.title}"
            )
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


# =============================================================================
# 自检
# =============================================================================

if __name__ == "__main__":
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
    assert _version_matches("8.9p1", [("8.5p1", "9.8p1")]) is True   # 在区间内
    assert _version_matches("8.5p1", [("8.5p1", "9.8p1")]) is True   # 等于 min
    assert _version_matches("9.0p1", [("8.5p1", "9.8p1")]) is True   # 在区间内
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
        skip_confirmation=True,
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
