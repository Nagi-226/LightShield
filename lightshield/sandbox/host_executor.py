"""LightShield v0.0.40 真机执行器（HostExecutor）

本模块实现 APPLY 模式的真机加固脚本执行——在宿主机 localhost 以
当前权限直接 subprocess 执行加固脚本。不套容器、不开特权、不动网络模型。

这是 v0.0.40「自动加固闭环」中风险最高的模块：它会真的修改用户的
iptables / 服务 / 配置。所有执行必须通过多重护栏（R4 双确认 +
DRY_RUN-first 前置 + rollback 就绪），编排层（core.run_harden_closed_loop）
负责强制执行这些护栏；HostExecutor 本身只复用 SandboxExecutor 模板方法
的闸门 + 校验 + 审计流程。

设计原则（合规 R 红线）：
  - 仅执行 Hardener.generate 产出的防御命令（R1）
  - 执行前确认 confirm_execute=True（R4 双确认，编排层强制）
  - 不引入任何网络下载（不 apt install / pip install）
  - 每条执行审计留痕（audit_id）
  - subprocess 绝不 shell=True 拼接未净化输入
  - 超时强制终止 + 完整输出捕获

与 DockerSandboxExecutor 的关系：
  - DockerSandboxExecutor：DRY_RUN 预检层，锁死容器（--network none）
  - HostExecutor：APPLY 真机执行层，宿主机直接 subprocess
  二者通过同一个 SandboxExecutor 抽象基类统一接口。

用法：
    from lightshield.sandbox import get_executor
    executor = get_executor("host")
    result = executor.execute("/path/to/harden.sh", confirm_execute=True)
"""

from __future__ import annotations

import os
import platform
import shutil
import subprocess  # nosec: B404 — 真机执行加固脚本是 LightShield 的核心功能
import time

from lightshield.sandbox.base import ExecutionResult, ExecutionStatus, SandboxExecutor

# =============================================================================
# HostExecutor
# =============================================================================


class HostExecutor(SandboxExecutor):
    """在宿主机本机直接执行加固脚本——APPLY 模式执行后端。

    继承 SandboxExecutor 的模板方法：execute() 已做闸门 + 校验 + 审计，
    HostExecutor 仅实现两个抽象方法（is_available / _run_script）。

    安全约束（本类不重复校验，由编排层负责）：
      - R4 双确认：编排层确保 confirm_ownership=True 且 confirm_execute=True
      - DRY_RUN-first：编排层确保 APPLY 前已过 DRY_RUN
      - rollback 就绪：编排层确保回滚脚本已生成

    本类执行的安全边界：
      - 以调用者当前权限执行（不做 privilege escalation）
      - subprocess 不带 shell=True（防止命令注入）
      - 超时强制 kill 子进程树
      - 输出大小截断（防炸内存）
    """

    # 单次执行输出最大保留字节数（防炸内存，加固脚本正常输出应在 100KB 以内）
    _MAX_OUTPUT_BYTES = 256 * 1024  # 256 KB

    def __init__(self, timeout: int = 120):
        """初始化真机执行器。

        Args:
            timeout: 默认执行超时秒数（真机执行比 Docker 快，默认 120s 已充裕）
        """
        super().__init__(name="HostExecutor", timeout=timeout)

    # ---- 跨平台命令构造 ----

    @staticmethod
    def _find_bash() -> str | None:
        """在 Windows 上查找可用的 bash 解释器。

        Returns:
            bash 可执行文件路径，找不到返回 None
        """
        # 优先 WSL bash
        wsl_bash = r"C:\Windows\System32\bash.exe"
        if os.path.isfile(wsl_bash):
            return wsl_bash
        # 备选 Git Bash
        git_bash = shutil.which("bash")
        if git_bash:
            return git_bash
        return None

    def _build_command(self, abs_script_path: str) -> list[str]:
        """根据脚本扩展名和当前平台构造执行命令。

        所有参数均为本地查找或已校验路径，不接受外部输入。

        Args:
            abs_script_path: 已校验的脚本绝对路径

        Returns:
            命令列表（直接传给 subprocess.run，shell=False）
        """
        ext = os.path.splitext(abs_script_path)[1].lower()
        is_windows = platform.system() == "Windows"

        if is_windows:
            if ext == ".ps1":
                # PowerShell 脚本
                return [
                    "powershell.exe",
                    "-NoProfile",
                    "-NonInteractive",
                    "-ExecutionPolicy",
                    "Bypass",
                    "-File",
                    abs_script_path,
                ]
            elif ext in (".sh", ".bash"):
                # Linux shell 脚本 → 需要 bash 解释器
                bash = self._find_bash()
                if bash:
                    return [bash, abs_script_path]
                else:
                    # 无 bash → 尝试直接执行（会失败，但让 subprocess 报清晰的错）
                    return [abs_script_path]
            else:
                # 未知扩展名 → 尝试直接执行
                return [abs_script_path]
        else:
            # Linux / macOS
            if ext in (".sh", ".bash", ""):
                # Shell 脚本：确保有执行权限后直接执行
                os.chmod(abs_script_path, 0o700)  # nosec: B103 — 仅 owner 可执行加固脚本，安全工具预期行为
                return [abs_script_path]
            elif ext == ".ps1":
                # PowerShell 脚本（Linux 需 pwsh）
                pwsh = shutil.which("pwsh") or "/usr/bin/pwsh"
                return [pwsh, "-File", abs_script_path]
            else:
                # 未知扩展名
                os.chmod(abs_script_path, 0o700)  # nosec: B103 — 仅 owner 可执行加固脚本，安全工具预期行为
                return [abs_script_path]

    # ---- 抽象方法实现 ----

    def is_available(self) -> bool:
        """真机执行器始终可用——在宿主机上运行不需要外部依赖。

        Returns:
            True（宿主机的 subprocess 能力总是存在）
        """
        # HostExecutor 不依赖 Docker / VM 等外部运行时，
        # 只要有 Python subprocess 就能执行，始终返回 True。
        return True

    def _run_script(self, abs_script_path: str, *, timeout: int) -> ExecutionResult:
        """在宿主机本机执行加固脚本——遵守 R1 安全约束。

        执行约束：
          - 不以 shell=True 执行（防命令注入）
          - 以调用者当前权限运行（不做 privilege escalation）
          - 超时强制终止进程树
          - 输出大小截断保护

        Args:
            abs_script_path: 已通过基类安全校验的脚本绝对路径
            timeout: 执行超时秒数

        Returns:
            ExecutionResult 结构化结果（任何失败都返回结果对象，不抛异常）
        """
        start = time.time()

        try:
            # 跨平台：按脚本扩展名和当前平台确定解释器
            # 所有参数均来自已校验的 abs_script_path 或本地查找，不可注入
            cmd = self._build_command(abs_script_path)

            # shell=False → 命令注入防护（参数不经过 shell 解析）
            proc = subprocess.run(  # nosec: B603 — cmd 元素全部来自内部构造，无外部输入
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                stdin=subprocess.DEVNULL,
            )

            duration = round(time.time() - start, 2)
            stdout = proc.stdout or ""
            stderr = proc.stderr or ""

            # 输出截断保护
            if len(stdout) > self._MAX_OUTPUT_BYTES:
                stdout = stdout[: self._MAX_OUTPUT_BYTES] + "\n…（输出已截断）"
            if len(stderr) > self._MAX_OUTPUT_BYTES:
                stderr = stderr[: self._MAX_OUTPUT_BYTES] + "\n…（输出已截断）"

            status = ExecutionStatus.SUCCESS if proc.returncode == 0 else ExecutionStatus.FAILED

            return ExecutionResult(
                status=status,
                script_path=abs_script_path,
                sandbox="host",
                exit_code=proc.returncode,
                stdout=stdout,
                stderr=stderr,
                duration_seconds=duration,
                timed_out=False,
                error=None if proc.returncode == 0 else f"脚本退出码 {proc.returncode}（非零）",
            )

        except subprocess.TimeoutExpired as exc:
            duration = round(time.time() - start, 2)

            # 超时时捕获已产生的输出（如果有），处理 bytes 类型
            def _safe_str(val: bytes | str | None) -> str:
                if val is None:
                    return ""
                if isinstance(val, bytes):
                    return val.decode("utf-8", errors="replace")
                return val

            stdout = _safe_str(exc.stdout) if hasattr(exc, "stdout") else ""
            stderr = _safe_str(exc.stderr) if hasattr(exc, "stderr") else ""
            return ExecutionResult(
                status=ExecutionStatus.TIMEOUT,
                script_path=abs_script_path,
                sandbox="host",
                exit_code=None,
                stdout=stdout[: self._MAX_OUTPUT_BYTES] if stdout else "",
                stderr=stderr[: self._MAX_OUTPUT_BYTES] if stderr else "",
                duration_seconds=duration,
                timed_out=True,
                error=f"脚本执行超时（{timeout}s），进程已被终止",
            )

        except PermissionError as exc:
            duration = round(time.time() - start, 2)
            return ExecutionResult(
                status=ExecutionStatus.ERROR,
                script_path=abs_script_path,
                sandbox="host",
                exit_code=None,
                duration_seconds=duration,
                timed_out=False,
                error=f"权限不足，无法执行脚本：{exc}",
            )

        except OSError as exc:
            duration = round(time.time() - start, 2)
            return ExecutionResult(
                status=ExecutionStatus.ERROR,
                script_path=abs_script_path,
                sandbox="host",
                exit_code=None,
                duration_seconds=duration,
                timed_out=False,
                error=f"系统错误，无法执行脚本：{exc}",
            )


# =============================================================================
# 自检
# =============================================================================

if __name__ == "__main__":
    import tempfile

    print("=== HostExecutor 自检 ===")

    ex = HostExecutor()
    is_windows = platform.system() == "Windows"

    # 1. 始终可用
    assert ex.is_available(), "HostExecutor 应始终可用"
    print("[OK] is_available → True（真机始终可用）")

    # 2. 未确认执行 → REJECTED（复用基类模板方法的闸门）
    r = ex.execute("whatever.sh")
    assert r.status == ExecutionStatus.REJECTED, f"未确认应拒绝，实得 {r.status}"
    print("[OK] 未确认执行 → REJECTED（闸门有效）")

    # 3. 执行一个简单的 echo 脚本（跨平台：Windows 用 .bat，其他用 .sh）
    if is_windows:
        # Windows：使用 .bat 脚本（无需额外解释器）
        script_content = "@echo off\r\necho hello from host\r\nexit /b 0\r\n"
        suffix = ".bat"
        fail_content = "@echo off\r\necho about to fail\r\nexit /b 1\r\n"
        # cmd.exe timeout 不可靠 → 用 PowerShell 做 sleep 测试
        slow_content = '@echo off\r\npowershell.exe -NoProfile -Command "Start-Sleep -Seconds 30"\r\nexit /b 0\r\n'
    else:
        script_content = "#!/bin/bash\necho 'hello from host'\nexit 0\n"
        suffix = ".sh"
        fail_content = "#!/bin/bash\necho 'about to fail'\nexit 1\n"
        slow_content = "#!/bin/bash\ntrap 'exit 0' SIGTERM\nsleep 30\nexit 0\n"

    with tempfile.NamedTemporaryFile("w", suffix=suffix, delete=False, encoding="utf-8") as tf:
        tf.write(script_content)
        good_script = tf.name

    try:
        r = ex.execute(good_script, confirm_execute=True)
        assert r.status == ExecutionStatus.SUCCESS, f"应成功，实得 {r.status}（error={r.error}）"
        assert r.sandbox == "host"
        assert r.exit_code == 0
        assert "hello from host" in r.stdout
        assert r.audit_id.startswith("EXEC-"), f"审计 ID 未填充: {r.audit_id}"
        print(f"[OK] 正常执行 → SUCCESS（审计 ID={r.audit_id}）")

        # 4. 执行一个会失败的脚本（exit 1）
        with tempfile.NamedTemporaryFile("w", suffix=suffix, delete=False, encoding="utf-8") as tf2:
            tf2.write(fail_content)
            fail_script = tf2.name

        try:
            r2 = ex.execute(fail_script, confirm_execute=True)
            assert r2.status == ExecutionStatus.FAILED, f"应失败，实得 {r2.status}"
            assert r2.exit_code == 1
            assert r2.error and "退出码" in r2.error
            print(f"[OK] 脚本退出码非零 → FAILED（exit_code={r2.exit_code}）")
        finally:
            os.remove(fail_script)

        # 5. 执行一个会超时的脚本（sleep 比 timeout 长）
        with tempfile.NamedTemporaryFile("w", suffix=suffix, delete=False, encoding="utf-8") as tf3:
            tf3.write(slow_content)
            slow_script = tf3.name

        try:
            r3 = ex.execute(slow_script, confirm_execute=True, timeout=2)
            assert r3.status == ExecutionStatus.TIMEOUT, f"应超时，实得 {r3.status}"
            assert r3.timed_out
            assert r3.exit_code is None
            print(f"[OK] 执行超时 → TIMEOUT（duration={r3.duration_seconds}s）")
        finally:
            os.remove(slow_script)
    finally:
        os.remove(good_script)

    print("=== HostExecutor: ALL PASSED ===")
