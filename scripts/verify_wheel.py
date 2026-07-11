"""Verify that a LightShield wheel works without the source checkout."""

from __future__ import annotations

import glob
import os
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

REQUIRED_MEMBERS = {
    "lightshield/rules/vuln_rules.json",
    "lightshield/nuclei-templates/README.md",
    "lightshield/web/templates/base.html",
    "lightshield/web/static/openapi.json",
    "lightshield/web/static/vendor/swagger-ui/swagger-ui-bundle.js",
    "lightshield/web/locales/en-US.json",
}


class WheelVerificationError(RuntimeError):
    """Raised when a wheel omits runtime files or fails installed smoke tests."""


def verify_wheel(path: Path) -> set[str]:
    """Return archive members after validating required runtime resources."""
    wheel = Path(path).resolve(strict=True)
    try:
        with zipfile.ZipFile(wheel) as archive:
            members = set(archive.namelist())
    except (OSError, zipfile.BadZipFile) as exc:
        raise WheelVerificationError(f"invalid wheel archive: {wheel}") from exc

    missing = sorted(REQUIRED_MEMBERS - members)
    if missing:
        raise WheelVerificationError(f"missing runtime resources: {', '.join(missing)}")
    return members


def smoke_test_wheel(path: Path) -> None:
    """Extract a wheel and exercise Web/i18n resources outside the source tree."""
    wheel = Path(path).resolve(strict=True)
    verify_wheel(wheel)
    with tempfile.TemporaryDirectory(prefix="lightshield-wheel-") as temp_dir:
        install_root = Path(temp_dir)
        with zipfile.ZipFile(wheel) as archive:
            archive.extractall(install_root)

        script = """
import sys
from pathlib import Path

root = Path(sys.argv[1]).resolve()
sys.path.insert(0, str(root))
import lightshield
from lightshield.web.app import create_app
from lightshield.web.i18n import flatten_for_js

package_root = Path(lightshield.__file__).resolve().parent
if root not in package_root.parents:
    raise SystemExit(f"import escaped extracted wheel: {package_root}")
app = create_app()
app.jinja_env.get_template("base.html")
if not flatten_for_js("zh-CN") or not flatten_for_js("en-US"):
    raise SystemExit("locale resources did not load")
if not (package_root / "web" / "static" / "openapi.json").is_file():
    raise SystemExit("OpenAPI resource missing")
if not (package_root / "nuclei-templates" / "README.md").is_file():
    raise SystemExit("Nuclei template resource missing")
"""
        env = os.environ.copy()
        env.pop("PYTHONPATH", None)
        completed = subprocess.run(
            [sys.executable, "-I", "-c", script, str(install_root)],
            cwd=install_root,
            env=env,
            capture_output=True,
            text=True,
            timeout=30,
        )
        if completed.returncode != 0:
            detail = completed.stderr.strip() or completed.stdout.strip()
            raise WheelVerificationError(f"installed wheel smoke test failed: {detail}")


def _resolve_wheel(argument: str) -> Path:
    """Resolve one wheel path, allowing a shell-independent glob argument."""
    matches = [Path(match) for match in glob.glob(argument)]
    if len(matches) != 1:
        raise WheelVerificationError(f"expected exactly one wheel for {argument!r}, found {len(matches)}")
    return matches[0]


def main(argv: list[str] | None = None) -> int:
    """Run archive verification and installed smoke testing."""
    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) != 1:
        print("usage: python scripts/verify_wheel.py <wheel-or-glob>", file=sys.stderr)
        return 2
    try:
        wheel = _resolve_wheel(args[0])
        members = verify_wheel(wheel)
        smoke_test_wheel(wheel)
    except (OSError, WheelVerificationError) as exc:
        print(f"wheel verification failed: {exc}", file=sys.stderr)
        return 1
    print(f"wheel verification passed: {wheel} ({len(members)} members)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
