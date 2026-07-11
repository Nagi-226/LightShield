"""Distribution-level guards for installed LightShield resources."""

from __future__ import annotations

import importlib.util
import sys
import zipfile
from pathlib import Path

import pytest
import tomllib

ROOT = Path(__file__).resolve().parents[1]
VERIFIER_PATH = ROOT / "scripts" / "verify_wheel.py"

REQUIRED_MEMBERS = {
    "lightshield/rules/vuln_rules.json",
    "lightshield/nuclei-templates/README.md",
    "lightshield/web/templates/base.html",
    "lightshield/web/static/openapi.json",
    "lightshield/web/static/vendor/swagger-ui/swagger-ui-bundle.js",
    "lightshield/web/locales/en-US.json",
}


def _load_verifier():
    assert VERIFIER_PATH.is_file(), "scripts/verify_wheel.py must exist"
    spec = importlib.util.spec_from_file_location("lightshield_verify_wheel", VERIFIER_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_pyproject_declares_all_runtime_resource_groups() -> None:
    """PEP 621 package data must cover every runtime resource tree."""
    data = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    patterns = set(data["tool"]["setuptools"]["package-data"]["lightshield"])

    assert "rules/*.json" in patterns
    assert "nuclei-templates/*" in patterns
    assert "web/templates/*.html" in patterns
    assert "web/static/*.json" in patterns
    assert "web/static/vendor/swagger-ui/*.js" in patterns
    assert "web/locales/*.json" in patterns


def test_setup_py_is_metadata_free_compatibility_shim() -> None:
    """Legacy setup invocation must consume pyproject metadata, not duplicate it."""
    setup_text = (ROOT / "setup.py").read_text(encoding="utf-8")

    assert "version=" not in setup_text
    assert "install_requires=" not in setup_text
    assert "setup()" in setup_text


def test_wheel_verifier_rejects_missing_runtime_resources(tmp_path: Path) -> None:
    """A syntactically valid wheel without Web data must fail verification."""
    verifier = _load_verifier()
    wheel = tmp_path / "broken.whl"
    with zipfile.ZipFile(wheel, "w") as archive:
        archive.writestr("lightshield/__init__.py", "")

    with pytest.raises(verifier.WheelVerificationError, match="missing runtime resources"):
        verifier.verify_wheel(wheel)


def test_wheel_verifier_accepts_required_runtime_resources(tmp_path: Path) -> None:
    """The archive verifier returns the installed member list on success."""
    verifier = _load_verifier()
    wheel = tmp_path / "complete.whl"
    with zipfile.ZipFile(wheel, "w") as archive:
        archive.writestr("lightshield/__init__.py", "")
        for member in REQUIRED_MEMBERS:
            archive.writestr(member, "test")

    members = verifier.verify_wheel(wheel)

    assert REQUIRED_MEMBERS.issubset(members)
