"""LightShield 打包配置。"""

from __future__ import annotations

from pathlib import Path

from setuptools import find_packages, setup

ROOT = Path(__file__).parent


def _read_requirements() -> list[str]:
    """读取 requirements.txt，忽略注释和空行。"""
    req_file = ROOT / "requirements.txt"
    if not req_file.exists():
        return []
    requirements: list[str] = []
    for raw_line in req_file.read_text(encoding="utf-8").splitlines():
        line = raw_line.split("#", 1)[0].strip()
        if line:
            requirements.append(line)
    return requirements


setup(
    name="lightshield",
    version="0.0.38",
    description="LightShield 轻盾 — 开源轻量化安全自检 + 防御加固工具",
    packages=find_packages(),
    python_requires=">=3.10",
    install_requires=_read_requirements(),
    entry_points={
        "console_scripts": [
            "lightshield=lightshield.cli:main",
        ],
    },
)
