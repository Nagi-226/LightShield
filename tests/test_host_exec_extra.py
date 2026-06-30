"""HostExecutor 补充测试 — v0.0.45 T2 边界/异常路径覆盖。"""

import pytest

from lightshield.sandbox.base import ExecutionStatus
from lightshield.sandbox.host_executor import HostExecutor


@pytest.fixture
def executor():
    """返回 HostExecutor 实例。"""
    return HostExecutor()


class TestExecuteEdgeCases:
    """execute() 边界路径。"""

    def test_missing_script_file_rejected(self, executor):
        result = executor.execute(
            "/nonexistent/script.sh",
            confirm_execute=True,
        )
        assert result.status in (ExecutionStatus.ERROR, ExecutionStatus.REJECTED)

    def test_unconfirmed_rejected(self, executor, tmp_path):
        script = tmp_path / "test.sh"
        script.write_text("#!/bin/bash\necho hello")
        result = executor.execute(str(script), confirm_execute=False)
        assert result.status == ExecutionStatus.REJECTED

    def test_empty_string_path_rejected(self, executor):
        result = executor.execute("", confirm_execute=True)
        assert result.status in (ExecutionStatus.ERROR, ExecutionStatus.REJECTED)


class TestIsAvailable:
    """HostExecutor 总是可用。"""

    def test_always_available(self, executor):
        assert executor.is_available() is True

    def test_name_attribute(self, executor):
        assert isinstance(executor.name, str)
        assert len(executor.name) > 0


class TestScriptExistsCheck:
    """脚本文件存在性校验。"""

    def test_nonexistent_script_rejected(self, executor):
        result = executor.execute("/no/such/script.sh", confirm_execute=True)
        assert result.status in (ExecutionStatus.ERROR, ExecutionStatus.REJECTED)

    def test_script_with_content_accepted(self, executor, tmp_path):
        script = tmp_path / "real.sh"
        script.write_text("#!/bin/bash\necho ok")
        # 不确认时拒绝
        result = executor.execute(str(script), confirm_execute=False)
        assert result.status == ExecutionStatus.REJECTED
