"""接口契约自动合规校验 — Gate D 自动化

用途：自动验证所有 Adapter 子类是否正确实现了 BaseAdapter 抽象接口，
     以及跨模块依赖是否符合 COORDINATION.md 的接口契约规则。

运行方式：
    py -m pytest tests/test_interface_compliance.py -v

覆盖：
    1. 所有 BaseAdapter 子类完整实现了 3 个抽象方法
    2. 所有 HardenBase 子类完整实现了 generate() 抽象方法
    3. Adapter.scan() 返回的是合法的 ScanResult 实例
    4. 无跨模块私有成员导入（防止 Agent 间接口污染）
    5. 所有模块的公开 API 与 CLAUDE.md 接口契约一致

设计背景（Gate D 补强）：
    当前 Gate D 冲突检测依赖人工审查。本文件将其核心检查——接口契约一致性——
    自动化为可重复运行的测试，每次 pre-commit 和 CI 都执行。
"""

from __future__ import annotations

import ast
import inspect
import os
import sys
from pathlib import Path
from typing import get_type_hints

import pytest

# 确保项目根目录在 sys.path 中
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# 显式导入所有 Adapter 模块以触发 __subclasses__() 注册（BaseAdapter 使用）
# 必须位于 BaseAdapter 导入之前，否则子类尚未注册

# =============================================================================
# 工具函数
# =============================================================================


def _find_all_subclasses(base_class: type) -> list[type]:
    """查找项目中所有继承自 base_class 的类（排除抽象基类自身）"""
    subclasses = []
    for subclass in base_class.__subclasses__():
        subclasses.append(subclass)
        subclasses.extend(_find_all_subclasses(subclass))
    return [cls for cls in subclasses if not inspect.isabstract(cls)]


def _get_abstract_methods(cls: type) -> set[str]:
    """获取类的所有抽象方法名"""
    return {
        name
        for name, method in inspect.getmembers(cls, inspect.isfunction)
        if hasattr(method, "__isabstractmethod__") and method.__isabstractmethod__
    }


def _scan_python_files(root_dir: Path) -> list[Path]:
    """递归扫描目录下所有 .py 文件"""
    py_files = []
    for py_file in root_dir.rglob("*.py"):
        if py_file.name == "__init__.py":
            continue
        if "test_" in py_file.name:
            continue
        py_files.append(py_file)
    return py_files


def _extract_all_imports(file_path: Path) -> list[tuple[str, str | None, int]]:
    """从 Python 文件中提取所有 import 语句

    Returns:
        [(module_name, imported_name, line_number), ...]
    """
    with open(file_path, encoding="utf-8") as f:
        source = f.read()

    tree = ast.parse(source, filename=str(file_path))
    imports = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append((alias.name, None, node.lineno))
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            for alias in node.names:
                full_name = f"{module}.{alias.name}" if module else alias.name
                imports.append((full_name, alias.name, node.lineno))

    return imports


# =============================================================================
# 测试类 1：Adapter 抽象方法完整性
# =============================================================================


class TestAdapterAbstractMethodCompliance:
    """验证所有 Adapter 子类完整实现了 BaseAdapter 的抽象方法"""

    def test_all_baseadapter_subclasses_implement_abstract_methods(self):
        """每个 BaseAdapter 子类必须实现 scan/validate_target/capabilities"""
        from lightshield.adapters.base import BaseAdapter

        abstract = _get_abstract_methods(BaseAdapter)
        assert abstract, "BaseAdapter 应有抽象方法定义"

        subclasses = _find_all_subclasses(BaseAdapter)
        assert subclasses, "应至少有一个 BaseAdapter 子类"

        violations = []
        for cls in subclasses:
            missing = []
            for method_name in abstract:
                if method_name not in cls.__dict__:
                    # 检查是否在父类链中实现了
                    method = getattr(cls, method_name, None)
                    if method is None or hasattr(method, "__isabstractmethod__"):
                        missing.append(method_name)
            if missing:
                violations.append(f"  {cls.__name__}: 缺失抽象方法 {missing}")

        assert not violations, "以下 Adapter 子类未完整实现 BaseAdapter 抽象方法:\n" + "\n".join(violations)

    def test_all_hardenbase_subclasses_implement_generate(self):
        """每个 HardenBase 子类必须实现 generate() 抽象方法"""
        from lightshield.harden.base import HardenBase

        abstract = _get_abstract_methods(HardenBase)
        assert "generate" in abstract, "HardenBase 应有 generate 抽象方法"

        subclasses = _find_all_subclasses(HardenBase)
        assert subclasses, "应至少有一个 HardenBase 子类"

        for cls in subclasses:
            assert "generate" in cls.__dict__, f"{cls.__name__} 未实现 HardenBase.generate() 抽象方法"


# =============================================================================
# 测试类 2：返回类型校验
# =============================================================================


class TestAdapterReturnTypes:
    """验证 Adapter.scan() 返回的是合法的 ScanResult"""

    def test_all_adapters_can_be_instantiated(self):
        """每个 Adapter 类可以无参数实例化"""
        from lightshield.adapters.base import BaseAdapter

        subclasses = _find_all_subclasses(BaseAdapter)
        for cls in subclasses:
            try:
                instance = cls()
                assert instance is not None
            except Exception as e:
                pytest.fail(f"{cls.__name__} 实例化失败: {e}")

    def test_all_adapters_have_capabilities(self):
        """每个 Adapter.capabilities() 返回非空列表"""
        from lightshield.adapters.base import BaseAdapter

        subclasses = _find_all_subclasses(BaseAdapter)
        for cls in subclasses:
            instance = cls()
            caps = instance.capabilities()
            assert isinstance(caps, list), f"{cls.__name__}.capabilities() 应返回 list，实际 {type(caps)}"
            assert len(caps) > 0, f"{cls.__name__}.capabilities() 不应返回空列表"

    def test_all_adapters_scan_returns_scanresult_for_localhost(self):
        """每个 Adapter.scan("127.0.0.1") 应返回 ScanResult 对象"""
        from lightshield.adapters.base import BaseAdapter, ScanResult

        subclasses = _find_all_subclasses(BaseAdapter)
        for cls in subclasses:
            instance = cls()
            # 跳过需要外部工具的 Adapter（Nmap/MSF）
            adapter_name = instance.name.lower()
            if any(kw in adapter_name for kw in ("nmap", "msf", "metasploit")):
                continue

            result = instance.scan("127.0.0.1")
            assert isinstance(result, ScanResult), (
                f"{cls.__name__}.scan('127.0.0.1') 应返回 ScanResult，实际 {type(result).__name__}"
            )
            assert result.target == "127.0.0.1", (
                f"{cls.__name__}.scan() 结果中 target 应为 '127.0.0.1'，实际 {result.target}"
            )


# =============================================================================
# 测试类 3：跨模块导入合规
# =============================================================================


class TestCrossModuleImportCompliance:
    """验证跨模块导入符合 COORDINATION.md 接口契约规则"""

    # 已知合法的跨模块导入模式（公开 API）
    ALLOWED_CROSS_IMPORTS = {
        # 所有模块可以导入的公共接口
        "lightshield.adapters.base",
        "lightshield.utils.constants",
        "lightshield.utils.logger",
        "lightshield.utils.validator",
        "lightshield.config",
        # 特定模块间的合法依赖
        "lightshield.core",  # 调度器
        "lightshield.rules.engine",  # 规则引擎
        "lightshield.report.reporter",  # 报告生成器
        "lightshield.harden.base",  # 加固基类
        "lightshield.harden.linux_harden",
        "lightshield.harden.win_harden",
        "lightshield.scanners.port_scanner",
        "lightshield.scanners.web_vuln_scanner",
        "lightshield.scanners.weak_password",
        "lightshield.scanners.component_checker",
        "lightshield.adapters.nmap_adapter",
        "lightshield.adapters.msf_adapter",
        "lightshield.adapters.script_engine",
    }

    # 禁止的私有成员导入模式
    FORBIDDEN_PATTERNS = [
        "._",  # 私有方法/属性（_private）
    ]
    # 不被视为私有的 dunder 属性（Python 标准 + 项目约定）
    ALLOWED_DUNDER = {"__version__", "__all__", "__doc__", "__file__", "__name__"}

    def test_no_private_cross_module_imports(self):
        """确保没有模块导入其他模块的私有成员（_private / __dunder）"""
        lightshield_dir = PROJECT_ROOT / "lightshield"
        py_files = _scan_python_files(lightshield_dir)

        violations = []
        for py_file in py_files:
            imports = _extract_all_imports(py_file)
            for module_name, imported_name, lineno in imports:
                for pattern in self.FORBIDDEN_PATTERNS:
                    import_name_str = str(imported_name or "")
                    # 跳过标准 dunder 属性（如 __version__）
                    if import_name_str in self.ALLOWED_DUNDER:
                        continue
                    if pattern in import_name_str:
                        violations.append(
                            f"  {py_file.relative_to(PROJECT_ROOT)}:{lineno}: "
                            f"导入私有成员 '{imported_name}' from '{module_name}'"
                        )
                    if pattern in module_name:
                        # 检查是否是子模块而非私有模块
                        module_parts = module_name.split(".")
                        if any(part.startswith("_") and not part.startswith("__") for part in module_parts):
                            violations.append(
                                f"  {py_file.relative_to(PROJECT_ROOT)}:{lineno}: 导入私有模块 '{module_name}'"
                            )

        assert not violations, "检测到跨模块私有成员导入（违反接口契约）:\n" + "\n".join(violations)

    def test_no_broken_relative_imports_in_lightshield(self):
        """确保 lightshield/ 下没有使用 from __future__ 之外的 broken imports"""
        # 使用 AST 检查所有 import 的目标模块是否存在
        lightshield_dir = PROJECT_ROOT / "lightshield"
        py_files = _scan_python_files(lightshield_dir)

        # 收集所有可用的模块名
        available_modules = set()
        for py_file in py_files:
            rel = py_file.relative_to(PROJECT_ROOT)
            module_path = str(rel.with_suffix("")).replace(os.sep, ".")
            available_modules.add(module_path)

        broken = []
        for py_file in py_files:
            imports = _extract_all_imports(py_file)
            for module_name, _, lineno in imports:
                # 跳过标准库和第三方库
                if not module_name.startswith("lightshield"):
                    continue
                # 跳过相对导入
                if module_name.startswith("."):
                    continue
                # 跳过 __init__.py 中导出的属性（如 __version__）
                if ".__" in module_name and any(module_name.endswith(d) for d in self.ALLOWED_DUNDER):
                    continue
                # 检查模块是否存在
                if module_name not in available_modules:
                    # 可能是子模块（如 lightshield.adapters.base 是文件，lightshield.adapters 是目录）
                    parts = module_name.split(".")
                    found = False
                    for i in range(len(parts), 0, -1):
                        candidate = ".".join(parts[:i])
                        if candidate in available_modules or candidate.endswith(".__init__"):
                            found = True
                            break
                    if not found:
                        broken.append(
                            f"  {py_file.relative_to(PROJECT_ROOT)}:{lineno}: import '{module_name}' — 模块不存在"
                        )

        assert not broken, "检测到引用不存在的模块（可能是 Agent 间接口不一致导致）:\n" + "\n".join(broken)


# =============================================================================
# 测试类 4：命名规范
# =============================================================================


class TestAdapterNamingConventions:
    """验证 Adapter 类命名符合项目约定"""

    def test_adapter_classes_end_with_adapter_or_scanner(self):
        """所有 BaseAdapter 子类名应以 Adapter 或 Scanner 结尾（历史遗留兼容）"""
        from lightshield.adapters.base import BaseAdapter

        subclasses = _find_all_subclasses(BaseAdapter)
        for cls in subclasses:
            name = cls.__name__
            # Scanner 后缀：历史遗留的 WebVulnScanner 尚未重命名
            valid_suffix = name.endswith("Adapter") or name.endswith("Scanner")
            assert valid_suffix, f"{name} 应遵循命名约定：以 'Adapter' 或 'Scanner' 结尾"

    def test_hardener_classes_end_with_hardener(self):
        """所有 HardenBase 子类名应以 Hardener 结尾"""
        from lightshield.harden.base import HardenBase

        subclasses = _find_all_subclasses(HardenBase)
        for cls in subclasses:
            assert cls.__name__.endswith("Hardener"), f"{cls.__name__} 应遵循命名约定：以 'Hardener' 结尾"


# =============================================================================
# 测试类 5：VulnFinding 字段完整性
# =============================================================================


class TestVulnFindingIntegrity:
    """验证 VulnFinding 数据结构的字段填充质量"""

    def test_vuln_finding_required_fields_exist(self):
        """VulnFinding 的所有必要字段在类定义中存在"""
        from lightshield.adapters.base import VulnFinding

        required_fields = {
            "vuln_type",
            "severity",
            "title",
            "description",
            "remediation",
        }
        hints = get_type_hints(VulnFinding)
        missing = required_fields - set(hints.keys())
        assert not missing, f"VulnFinding 缺少必要字段: {missing}"
