"""O guard de publicação recusa tags e manifestos divergentes antes do build."""

import runpy
import shutil
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
check = runpy.run_path(str(ROOT / "packaging/check_versions.py"))["check"]


def test_repository_versions_agree():
    from codar import __version__

    assert check(ROOT, f"v{__version__}") == []
    assert any("tag" in error for error in check(ROOT, "v9.9.9"))


@pytest.mark.parametrize("path", ["clients/vscode/package.json", "clients/vscode/package-lock.json",
                                   "clients/powershell/Codar/Codar.psd1", "packaging/rpm/codar.spec",
                                   "packaging/debian/changelog", "packaging/codar.1"])
def test_guard_rejects_stale_manifest(tmp_path, path):
    from codar import __version__

    for name in ("src/codar/__init__.py", "src/codar/_compat.py", "pyproject.toml", "CHANGELOG.md",
                 "clients/vscode/package.json", "clients/vscode/package-lock.json",
                 "clients/powershell/Codar/Codar.psd1", "packaging/rpm/codar.spec",
                 "packaging/debian/changelog", "packaging/codar.1"):
        target = tmp_path / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / name, target)
    target = tmp_path / path
    target.write_text(target.read_text(encoding="utf-8").replace(__version__, "9.9.9"), encoding="utf-8")
    assert any(path in error for error in check(tmp_path))
