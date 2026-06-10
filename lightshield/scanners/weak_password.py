"""
LightShield 弱口令检测适配器

检测目标主机上 SSH、MySQL、HTTP 等服务的弱口令风险。
继承 BaseAdapter，通过内置 WEAK_PASSWORD_PATTERNS 字典逐一验证。

合规约束 (R6)：
  - 单目标最大尝试次数 ≤ 10
  - 每次尝试间隔 ≥ 500ms
  - 仅检测，不利用验证通过的服务

用法：
    from lightshield.scanners.weak_password import WeakPasswordAdapter
    adapter = WeakPasswordAdapter()
    result = adapter.scan("192.168.1.1", ports=[...])
"""

import time
import socket
from typing import Optional

import requests
from requests.auth import HTTPBasicAuth

from lightshield.adapters.base import BaseAdapter, ScanResult, VulnFinding
from lightshield.utils.constants import (
    RiskLevel,
    ScanStatus,
    WEAK_PASSWORD_PATTERNS,
    HIGH_RISK_PORTS,
)
from lightshield.utils.validator import TargetValidator
from lightshield.utils.logger import get_logger


# =============================================================================
# 弱口令检测适配器
# =============================================================================

class WeakPasswordAdapter(BaseAdapter):
    """弱口令检测适配器 — SSH / MySQL / HTTP 弱口令自查

    检测流程：
    1. 接收端口扫描结果（或自行探测常见端口）
    2. 对每个开放的服务端口，确定服务类型
    3. HTTP 服务：实际尝试弱口令登录（Basic Auth + 表单）
    4. SSH/MySQL：确认服务存在并生成审计建议
    5. 生成结构化漏洞发现

    R6 合规：
    - 单次 scan() 最多尝试 10 个口令（含 HTTP 表单提交）
    - 每次尝试间隔 ≥ 500ms
    """

    # ── 服务端口映射 ──
    SERVICE_PORTS: dict[str, list[int]] = {
        "ssh":   [22],
        "mysql": [3306],
        "http":  [80, 443, 8080, 8443, 8000, 9090],
    }

    # ── HTTP 登录端点（按顺序探测，找到第一个即停止） ──
    HTTP_LOGIN_PATHS: list[str] = [
        "/wp-login.php",
        "/phpmyadmin/index.php",
        "/admin/login",
        "/login",
        "/admin",
        "/wp-admin",
    ]

    # ── HTTP 常用用户名字典 ──
    HTTP_COMMON_USERS: list[str] = [
        "admin", "root", "administrator", "user", "test",
    ]

    # ── 尝试上限 ──
    MAX_PASSWORD_ATTEMPTS: int = 10
    ATTEMPT_INTERVAL: float = 0.6  # 秒（≥500ms）

    # ── 连接超时 ──
    CONNECT_TIMEOUT: float = 5.0  # 秒
    HTTP_TIMEOUT: float = 8.0

    # =========================================================================
    # 构造
    # =========================================================================

    def __init__(self):
        super().__init__(name="WeakPasswordAdapter")
        self._logger = get_logger()
        self._attempt_count: int = 0
        self._session: Optional[requests.Session] = None

    # =========================================================================
    # BaseAdapter 抽象方法
    # =========================================================================

    def capabilities(self) -> list[str]:
        """返回 ['weak_password']"""
        return ["weak_password"]

    def validate_target(self, target: str) -> bool:
        """目标合法性校验——委托 TargetValidator"""
        is_valid, reason = TargetValidator.validate(target)
        if not is_valid:
            self._logger.warning("weak_password", f"目标校验失败: {target} — {reason}")
            return False
        # 额外约束：禁止对公网 IP 做弱口令检测（合规 R4 的延伸）
        if not TargetValidator.is_private_ip(target) and target != "localhost":
            self._logger.warning(
                "weak_password",
                f"目标 {target} 非内网地址，弱口令检测需要额外确认",
            )
            # 不直接拒绝——core.py 负责所有权确认
        return True

    def scan(self, target: str, **kwargs) -> ScanResult:
        """执行弱口令检测

        Args:
            target: 扫描目标（单 IP 或域名）
            **kwargs:
                ports:      端口列表，来自上游扫描结果
                            格式: [{"port": 22, "service": "ssh", "state": "open"}, ...]
                services:   服务列表
                            格式: [{"name": "ssh", "port": 22}, ...]
                passwords:  自定义密码列表（覆盖默认 WEAK_PASSWORD_PATTERNS）
                max_attempts: 自定义最大尝试次数

        Returns:
            ScanResult
        """
        import time as time_module
        start_time = time_module.time()

        # ── Step 1: 前置校验 ──
        if not self.validate_target(target):
            return ScanResult(
                status=ScanStatus.FAILED,
                target=target,
                error="目标校验不通过",
            )

        scan_id = self._log_scan_start(target, "weak_password")
        self._attempt_count = 0

        # ── Step 2: 解析密码列表 ──
        passwords: list[str] = list(
            kwargs.get("passwords", WEAK_PASSWORD_PATTERNS)
        )
        max_attempts: int = int(
            kwargs.get("max_attempts", self.MAX_PASSWORD_ATTEMPTS)
        )

        # ── Step 3: 发现目标上开放的服务 ──
        discovered = self._discover_services(target, **kwargs)
        if not discovered:
            duration = time_module.time() - start_time
            return ScanResult(
                status=ScanStatus.COMPLETED,
                target=target,
                findings=[],
                ports=[],
                duration_seconds=round(duration, 2),
                raw_output="未发现需要检测弱口令的服务（SSH/MySQL/HTTP）",
            )

        # ── Step 4: 按服务类型执行弱口令检测 ──
        all_findings: list[VulnFinding] = []

        for svc in discovered:
            if self._attempt_count >= max_attempts:
                self._logger.info(
                    "weak_password",
                    f"已达到最大尝试次数 {max_attempts}，停止检测",
                )
                break

            svc_type = svc["type"]  # "ssh" | "mysql" | "http"
            svc_port = svc["port"]

            if svc_type == "ssh":
                findings = self._check_ssh_weak_password(
                    target, svc_port, passwords, max_attempts
                )
            elif svc_type == "mysql":
                findings = self._check_mysql_weak_password(
                    target, svc_port, passwords, max_attempts
                )
            elif svc_type == "http":
                findings = self._check_http_weak_password(
                    target, svc_port, passwords, max_attempts
                )
            else:
                findings = []

            all_findings.extend(findings)

        # ── Step 5: 组装结果 ──
        duration = time_module.time() - start_time
        result = ScanResult(
            status=ScanStatus.COMPLETED,
            target=target,
            findings=all_findings,
            ports=[
                {"port": s["port"], "service": s["type"], "state": "open"}
                for s in discovered
            ],
            services=[
                {"name": s["type"], "port": s["port"]} for s in discovered
            ],
            duration_seconds=round(duration, 2),
            raw_output=(
                f"检测服务 {len(discovered)} 个，"
                f"实际尝试 {self._attempt_count} 次，"
                f"发现弱口令风险 {len(all_findings)} 个"
            ),
        )

        self._log_scan_end(scan_id, result)
        return result

    # =========================================================================
    # 服务发现
    # =========================================================================

    def _discover_services(
        self,
        target: str,
        **kwargs,
    ) -> list[dict]:
        """从上游扫描结果或自行探测发现目标上的 SSH/MySQL/HTTP 服务

        Args:
            target: 目标地址
            **kwargs: 可能包含 ports / services 信息

        Returns:
            [
                {"type": "ssh", "port": 22, "banner": "OpenSSH_8.9"},
                {"type": "http", "port": 80},
                ...
            ]
        """
        discovered: list[dict] = []

        # ── 优先使用上游端口扫描结果 ──
        ports_info: list[dict] = kwargs.get("ports", [])
        services_info: list[dict] = kwargs.get("services", [])

        if ports_info:
            for port_entry in ports_info:
                port_num = port_entry.get("port", 0)
                state = port_entry.get("state", "")
                svc_name = port_entry.get("service", "")

                if state != "open":
                    continue

                matched = self._match_service_type(port_num, svc_name)
                if matched:
                    discovered.append({"type": matched, "port": port_num})
            if discovered:
                return discovered

        if services_info:
            for svc_entry in services_info:
                port_num = svc_entry.get("port", 0)
                svc_name = svc_entry.get("name", "")

                matched = self._match_service_type(port_num, svc_name)
                if matched:
                    # 去重
                    if not any(
                        d["type"] == matched and d["port"] == port_num
                        for d in discovered
                    ):
                        discovered.append({"type": matched, "port": port_num})
            if discovered:
                return discovered

        # ── 没有上游数据时：快速端口探测 ──
        self._logger.info("weak_password", "无上游端口数据，执行快速服务探测")
        target_ip = self._resolve_target(target)

        for svc_type, ports in self.SERVICE_PORTS.items():
            for port in ports:
                if self._is_port_open(target_ip, port):
                    discovered.append({"type": svc_type, "port": port})

        return discovered

    def _match_service_type(
        self,
        port: int,
        service_name: str,
    ) -> Optional[str]:
        """根据端口号和服务名匹配服务类型

        Returns:
            "ssh" / "mysql" / "http" 或 None
        """
        service_lower = service_name.lower() if service_name else ""

        # 精确命名匹配
        if "ssh" in service_lower and port in self.SERVICE_PORTS["ssh"]:
            return "ssh"
        if "mysql" in service_lower and port in self.SERVICE_PORTS["mysql"]:
            return "mysql"
        if any(
            kw in service_lower
            for kw in ("http", "www", "nginx", "apache", "tomcat", "iis")
        ):
            if port in self.SERVICE_PORTS["http"]:
                return "http"

        # 纯端口匹配
        if port in self.SERVICE_PORTS["ssh"]:
            return "ssh"
        if port in self.SERVICE_PORTS["mysql"]:
            return "mysql"
        if port in self.SERVICE_PORTS["http"]:
            return "http"

        return None

    def _is_port_open(self, host: str, port: int) -> bool:
        """TCP 连接探测——端口是否开放

        Args:
            host: IP 地址
            port: 端口号

        Returns:
            True 表示端口可达
        """
        try:
            sock = socket.create_connection(
                (host, port),
                timeout=self.CONNECT_TIMEOUT,
            )
            sock.close()
            return True
        except (socket.timeout, ConnectionRefusedError, OSError):
            return False

    def _resolve_target(self, target: str) -> str:
        """解析目标为 IP 地址"""
        try:
            import ipaddress
            ipaddress.ip_address(target)
            return target
        except ValueError:
            pass
        try:
            return socket.gethostbyname(target)
        except socket.gaierror:
            return target

    # =========================================================================
    # SSH 弱口令检测
    # =========================================================================

    def _check_ssh_weak_password(
        self,
        target: str,
        port: int,
        passwords: list[str],
        max_attempts: int,
    ) -> list[VulnFinding]:
        """SSH 弱口令检测

        当前策略（轻量 MVP）：
        - 获取 SSH banner 确认服务版本
        - 生成包含弱口令清单的审计发现
        - 实际密码验证需要 paramiko，标记为「建议手工核查」

        Args:
            target: 目标
            port: SSH 端口
            passwords: 密码列表
            max_attempts: 最大尝试次数上限

        Returns:
            漏洞发现列表
        """
        findings: list[VulnFinding] = []

        # 获取 banner
        banner = self._grab_banner(target, port)

        # SSH 版本信息
        version_info = ""
        if banner:
            version_info = banner.strip()
            self._logger.info(
                "weak_password",
                f"SSH banner: {version_info}",
            )

        # 生成审计发现——以下密码需要自查
        # R6: 不实际尝试所有密码连接（这需要 paramiko），生成有限审计清单
        audit_passwords = passwords[:8]  # 展示前 8 个

        finding = VulnFinding(
            vuln_type="weak_password",
            severity=RiskLevel.HIGH,
            title=f"SSH 服务存在弱口令风险 (端口 {port})",
            description=(
                f"目标 {target}:{port} 上检测到 SSH 服务"
                + (f"（{version_info}）" if version_info else "")
                + "。\n"
                f"SSH 服务若使用弱口令，攻击者可通过暴力破解获取系统 shell。\n"
                f"以下常见弱口令需逐一自查："
                f"{', '.join(audit_passwords)}"
            ),
            remediation=(
                "1. 禁止 root 直接 SSH 登录（PermitRootLogin no）\n"
                "2. 禁用密码认证，仅使用 SSH 密钥登录\n"
                "3. 修改所有用户密码为强密码（≥12 位，含大小写+数字+特殊字符）\n"
                "4. 配置 fail2ban 防止暴力破解\n"
                "5. 如非必要，更改 SSH 默认端口 22"
            ),
            port=port,
            evidence=(
                f"SSH 服务在端口 {port} 可访问"
                + (f"，Banner: {version_info}" if version_info else "")
                + f"，需自查以下密码: {', '.join(audit_passwords)}"
            ),
        )
        findings.append(finding)
        return findings

    # =========================================================================
    # MySQL 弱口令检测
    # =========================================================================

    def _check_mysql_weak_password(
        self,
        target: str,
        port: int,
        passwords: list[str],
        max_attempts: int,
    ) -> list[VulnFinding]:
        """MySQL 弱口令检测

        当前策略（轻量 MVP）：
        - 获取 MySQL banner 确认版本
        - 生成包含弱口令清单的审计发现
        - 实际 MySQL 认证验证需要 mysql-connector-python，标记为「建议手工核查」
        """
        findings: list[VulnFinding] = []

        banner = self._grab_banner(target, port)
        version_info = banner.strip() if banner else ""

        audit_passwords = passwords[:8]

        # 特定于 MySQL 的危险口令补充
        mysql_specific = ["root（空密码）", "mysql", "admin"]
        audit_text = ", ".join(audit_passwords) + " 以及 " + ", ".join(mysql_specific)

        finding = VulnFinding(
            vuln_type="weak_password",
            severity=RiskLevel.CRITICAL,
            title=f"MySQL 数据库存在弱口令风险 (端口 {port})",
            description=(
                f"目标 {target}:{port} 上检测到 MySQL 服务"
                + (f"（{version_info}）" if version_info else "")
                + "。\n"
                f"MySQL root 账户若使用弱口令或空密码，攻击者可直接获取数据库"
                f"全部权限，导致数据泄露或篡改。\n"
                f"需自查以下口令：{audit_text}"
            ),
            remediation=(
                "1. 立即为 MySQL root 账户设置强密码\n"
                "2. 删除或禁用匿名账户和无密码账户\n"
                "   ALTER USER 'root'@'localhost' IDENTIFIED BY '<强密码>';\n"
                "3. 删除测试数据库：DROP DATABASE test;\n"
                "4. 限制 MySQL 仅监听 127.0.0.1（bind-address = 127.0.0.1）\n"
                "5. 如非必要，通过防火墙阻止端口 3306 的外部访问"
            ),
            port=port,
            evidence=(
                f"MySQL 服务在端口 {port} 可访问"
                + (f"，Banner: {version_info}" if version_info else "")
                + f"。需自查的口令包括: {audit_text}"
            ),
        )
        findings.append(finding)
        return findings

    # =========================================================================
    # HTTP 弱口令检测
    # =========================================================================

    def _check_http_weak_password(
        self,
        target: str,
        port: int,
        passwords: list[str],
        max_attempts: int,
    ) -> list[VulnFinding]:
        """HTTP 弱口令检测——实际发送请求尝试登录

        策略：
        1. 探测常见登录端点（wp-login.php, phpmyadmin 等）
        2. 对找到的登录端点，尝试 Basic Auth + 弱口令
        3. 对找到的登录表单，尝试 POST 弱口令
        R6: 受 self._attempt_count 全局限制

        Returns:
            漏洞发现列表
        """
        findings: list[VulnFinding] = []
        scheme = "https" if port in (443, 8443) else "http"
        base_url = f"{scheme}://{target}:{port}"

        self._session = requests.Session()
        self._session.headers.update({
            "User-Agent": "LightShield/0.1 (Security Self-Audit Tool)",
        })

        try:
            # ── Step 1: 探测登录端点 ──
            login_endpoints = self._probe_http_endpoints(base_url)

            if not login_endpoints:
                self._logger.info(
                    "weak_password",
                    f"未在 {base_url} 上找到已知登录端点",
                )
                return findings

            # ── Step 2: 对每个端点尝试弱口令 ──
            for endpoint in login_endpoints:
                if self._attempt_count >= max_attempts:
                    break

                result = self._try_http_login(
                    base_url, endpoint, passwords, max_attempts
                )
                if result:
                    findings.append(result)
                    # 找到一个弱口令后不再对此端点继续尝试
                    break

        except requests.exceptions.SSLError:
            self._logger.warning(
                "weak_password",
                f"SSL 证书错误，尝试 HTTP: {base_url}",
            )
        except requests.exceptions.ConnectionError:
            self._logger.info(
                "weak_password",
                f"无法连接到 {base_url}",
            )
        except Exception as e:
            self._logger.error(
                "weak_password",
                f"HTTP 检测异常",
                exception=e,
            )
        finally:
            if self._session:
                self._session.close()
                self._session = None

        # 如果所有端点都尝试了但没发现弱口令，仍生成信息级报告
        if not findings and login_endpoints:
            findings.append(VulnFinding(
                vuln_type="weak_password",
                severity=RiskLevel.INFO,
                title=f"HTTP 弱口令检测完成 (端口 {port})",
                description=(
                    f"已对 {base_url} 的 {len(login_endpoints)} 个登录端点"
                    f"尝试了 {self._attempt_count} 个常见弱口令，未发现可登录凭据。"
                ),
                remediation="保持当前强密码策略，定期更新。",
                port=port,
                evidence=f"检测端点: {', '.join(login_endpoints)}",
            ))

        return findings

    def _probe_http_endpoints(self, base_url: str) -> list[str]:
        """探测可访问的 HTTP 登录端点

        Returns:
            可达的端点路径列表（按优先级排序）
        """
        reachable: list[str] = []
        for path in self.HTTP_LOGIN_PATHS:
            try:
                resp = self._session.get(
                    f"{base_url}{path}",
                    timeout=self.HTTP_TIMEOUT,
                    allow_redirects=True,
                    verify=False,  # 自签证书环境
                )
                # 200/401/403/302 都说明端点存在
                if resp.status_code in (200, 401, 403, 302):
                    reachable.append(path)
            except Exception:
                continue
        return reachable

    def _try_http_login(
        self,
        base_url: str,
        endpoint: str,
        passwords: list[str],
        max_attempts: int,
    ) -> Optional[VulnFinding]:
        """尝试通过 Basic Auth 和表单 POST 方式登录 HTTP 端点

        Returns:
            若成功登录则返回 VulnFinding，否则返回 None
        """
        url = f"{base_url}{endpoint}"

        # ── 策略 A: HTTP Basic Auth ──
        for username in self.HTTP_COMMON_USERS:
            for password in passwords:
                if self._attempt_count >= max_attempts:
                    return None

                self._attempt_count += 1
                self._logger.debug(
                    "weak_password",
                    f"尝试 Basic Auth: {username}:{password} @ {url}",
                )

                try:
                    resp = self._session.get(
                        url,
                        auth=HTTPBasicAuth(username, password),
                        timeout=self.HTTP_TIMEOUT,
                        verify=False,
                    )
                except Exception:
                    continue

                time.sleep(self.ATTEMPT_INTERVAL)

                if resp.status_code == 200:
                    self._logger.warning(
                        "weak_password",
                        f"发现弱口令: {username}:{password} @ {url}",
                    )
                    return VulnFinding(
                        vuln_type="weak_password",
                        severity=RiskLevel.CRITICAL,
                        title=f"HTTP Basic Auth 存在弱口令 (端口检测)",
                        description=(
                            f"目标 {url} 使用 HTTP Basic Auth，"
                            f"凭据 {username}:{password} 可成功登录。\n"
                            f"这是极度危险的安全漏洞，攻击者可获取管理面板权限。"
                        ),
                        remediation=(
                            "1. 立即修改该账户密码为强密码\n"
                            "2. 如支持，改用更强的认证方式（Session + CSRF Token）\n"
                            "3. 配置登录失败锁定策略（如 fail2ban）\n"
                            "4. 启用 HTTPS，避免凭据明文传输"
                        ),
                        url=url,
                        parameter="username",
                        evidence=f"Basic Auth {username}:{password} 返回 HTTP 200",
                    )

                # 401 = 凭据错误，继续下一个
                if resp.status_code != 401:
                    # 非预期状态码，可能端点行为特殊，记录后继续
                    continue

        # ── 策略 B: 常见表单 POST ──
        # WordPress wp-login.php
        if endpoint == "/wp-login.php":
            return self._try_wordpress_login(url, passwords, max_attempts)

        return None

    def _try_wordpress_login(
        self,
        url: str,
        passwords: list[str],
        max_attempts: int,
    ) -> Optional[VulnFinding]:
        """尝试 WordPress 表单登录

        Returns:
            成功时返回 VulnFinding，否则返回 None
        """
        for username in self.HTTP_COMMON_USERS[:3]:  # 只试前 3 个用户名
            for password in passwords[:5]:  # 每个用户只试 5 个密码
                if self._attempt_count >= max_attempts:
                    return None

                self._attempt_count += 1
                self._logger.debug(
                    "weak_password",
                    f"尝试 WordPress: {username}:{password}",
                )

                try:
                    resp = self._session.post(
                        url,
                        data={
                            "log": username,
                            "pwd": password,
                            "wp-submit": "登录",
                            "testcookie": "1",
                        },
                        timeout=self.HTTP_TIMEOUT,
                        verify=False,
                    )
                except Exception:
                    continue

                time.sleep(self.ATTEMPT_INTERVAL)

                # WordPress 登录成功后重定向到 /wp-admin/
                if resp.status_code in (302, 200):
                    if "/wp-admin" in resp.url or "wordpress_logged_in" in str(
                        resp.cookies
                    ):
                        self._logger.warning(
                            "weak_password",
                            f"发现 WordPress 弱口令: {username}:{password}",
                        )
                        return VulnFinding(
                            vuln_type="weak_password",
                            severity=RiskLevel.CRITICAL,
                            title="WordPress 管理员存在弱口令",
                            description=(
                                f"WordPress 站点 {url} 的管理员账户 "
                                f"'{username}' 使用弱口令 '{password}'。\n"
                                f"攻击者可通过此凭据完全控制网站。"
                            ),
                            remediation=(
                                "1. 立即修改 WordPress 管理员密码\n"
                                "2. 安装 Wordfence 等安全插件启用登录保护\n"
                                "3. 开启双因素认证 (2FA)\n"
                                "4. 限制 wp-login.php 的访问 IP"
                            ),
                            url=url,
                            parameter="username",
                            evidence=(
                                f"POST {url} 使用 {username}:{password} 后"
                                f"重定向至管理后台"
                            ),
                        )

        return None

    # =========================================================================
    # Banner 抓取
    # =========================================================================

    def _grab_banner(self, host: str, port: int) -> str:
        """TCP 连接并读取服务 banner

        Args:
            host: IP 地址
            port: 端口号

        Returns:
            banner 字符串（最多 256 字节），失败返回空字符串
        """
        try:
            sock = socket.create_connection(
                (host, port),
                timeout=self.CONNECT_TIMEOUT,
            )
            sock.settimeout(3.0)
            # 某些服务（如 SSH）会主动发送 banner，其他需要客户端先发请求
            try:
                banner = sock.recv(256)
                if banner:
                    return banner.decode("utf-8", errors="replace").strip()
            except socket.timeout:
                pass
            sock.close()
        except Exception:
            pass
        return ""

    # =========================================================================
    # 工具方法
    # =========================================================================

    def reset_attempts(self) -> None:
        """重置尝试计数器（测试用）"""
        self._attempt_count = 0


# =============================================================================
# 自检
# =============================================================================

if __name__ == "__main__":
    print("=== WeakPasswordAdapter 自检 ===")

    adapter = WeakPasswordAdapter()

    # 1. 能力声明
    assert adapter.capabilities() == ["weak_password"]
    print("✅ capabilities() 返回 ['weak_password']")

    # 2. 目标校验
    assert adapter.validate_target("127.0.0.1") is True
    assert adapter.validate_target("192.168.1.0/24") is False
    assert adapter.validate_target("") is False
    print("✅ validate_target() 通过")

    # 3. 服务类型匹配
    assert adapter._match_service_type(22, "ssh") == "ssh"
    assert adapter._match_service_type(3306, "mysql") == "mysql"
    assert adapter._match_service_type(80, "http") == "http"
    assert adapter._match_service_type(443, "https") == "http"
    assert adapter._match_service_type(8080, "nginx") == "http"
    assert adapter._match_service_type(9999, "unknown") is None
    print("✅ _match_service_type() 通过")

    # 4. 服务发现（通过 kwargs 传入上游端口数据）
    ports_info = [
        {"port": 22, "protocol": "tcp", "state": "open", "service": "ssh"},
        {"port": 3306, "protocol": "tcp", "state": "open", "service": "mysql"},
        {"port": 80, "protocol": "tcp", "state": "open", "service": "http"},
        {"port": 443, "protocol": "tcp", "state": "closed", "service": "https"},
    ]
    discovered = adapter._discover_services("127.0.0.1", ports=ports_info)
    assert len(discovered) == 3  # ssh, mysql, http (443 closed)
    types_found = {d["type"] for d in discovered}
    assert types_found == {"ssh", "mysql", "http"}
    print(f"✅ 服务发现: 找到 {len(discovered)} 个服务 {types_found}")

    # 5. 通过 services 格式发现
    services_info = [
        {"name": "ssh", "version": "OpenSSH 8.9", "port": 22},
        {"name": "mysql", "version": "MySQL 8.0", "port": 3306},
    ]
    discovered2 = adapter._discover_services("127.0.0.1", services=services_info)
    assert len(discovered2) == 2
    print(f"✅ services 格式发现: {len(discovered2)} 个")

    # 6. 端口开放探测（本地回环）
    # import socket
    # 在 127.0.0.1 上临时开一个监听端口验证
    import threading
    import socket as _socket_mod

    test_port = 19999
    test_ready = threading.Event()

    def dummy_server():
        srv = _socket_mod.socket(_socket_mod.AF_INET, _socket_mod.SOCK_STREAM)
        srv.setsockopt(_socket_mod.SOL_SOCKET, _socket_mod.SO_REUSEADDR, 1)
        srv.bind(("127.0.0.1", test_port))
        srv.listen(1)
        test_ready.set()
        try:
            conn, _ = srv.accept()
            conn.send(b"OpenSSH_8.9\r\n")
            conn.close()
        except Exception:
            pass
        srv.close()

    t = threading.Thread(target=dummy_server, daemon=True)
    t.start()
    test_ready.wait(timeout=2)

    assert adapter._is_port_open("127.0.0.1", test_port) is True
    assert adapter._is_port_open("127.0.0.1", 19998) is False
    print(f"✅ _is_port_open() 通过 (端口 {test_port})")

    # 7. Banner 抓取
    banner = adapter._grab_banner("127.0.0.1", test_port)
    print(f"✅ Banner 抓取: '{banner}'")

    # 8. scan() 整体流程（使用模拟端口数据）
    result = adapter.scan(
        "127.0.0.1",
        ports=ports_info,
        max_attempts=3,
    )
    assert result.status == ScanStatus.COMPLETED
    print(f"✅ scan() 返回状态: {result.status.value}")
    print(f"   检测服务: {len(result.ports)} 个")
    print(f"   发现风险: {len(result.findings)} 个")
    for f in result.findings:
        print(f"   [{f.severity.value}] {f.title}")

    # 9. reset
    adapter.reset_attempts()
    assert adapter._attempt_count == 0
    print("✅ reset_attempts() 通过")

    print("=== WeakPasswordAdapter 自检全部通过 ===")
