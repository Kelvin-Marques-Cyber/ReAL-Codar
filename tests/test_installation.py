"""Regressões de origem Git, instalações duplicadas e daemon anterior à atualização."""

import argparse
import json
from importlib import metadata

import pytest

from codar import __version__, installation
from codar.cli import main as cli


@pytest.fixture
def installed_package(tmp_path, monkeypatch):
    module = tmp_path / "site-packages" / "codar" / "installation.py"
    module.parent.mkdir(parents=True)
    module.touch()
    monkeypatch.setattr(installation, "__file__", str(module))

    class Distribution:
        direct = {}

        def locate_file(self, path):
            return module.parent.parent / path

        def read_text(self, name):
            assert name == "direct_url.json"
            return json.dumps(self.direct)

    dist = Distribution()
    monkeypatch.setattr(metadata, "distribution", lambda name: dist)
    return dist


def test_git_install_reports_commit_and_redacts_url(installed_package):
    installed_package.direct = {
        "url": "https://user:secret@example.com/owner/repo.git?token=secret#secret",
        "vcs_info": {"vcs": "git", "commit_id": "a" * 40, "requested_revision": "main"},
    }
    info = installation.installation_info()
    assert info["commit"] == "a" * 40 and info["ref"] == "main"
    assert info["source"] == "https://example.com/owner/repo.git"
    assert info["version"] == __version__


@pytest.mark.parametrize("direct", [{}, None, [], {"vcs_info": []}])
def test_missing_or_incomplete_provenance_is_not_invented(installed_package, direct):
    installed_package.direct = direct
    assert installation.installation_info()["commit"] is None


def test_other_distribution_cannot_supply_provenance(installed_package, tmp_path):
    installed_package.direct = {"vcs_info": {"commit_id": "wrong"}}
    installed_package.locate_file = lambda path: tmp_path / "other" / path
    assert installation.installation_info()["commit"] is None


def test_system_package_without_distribution(installed_package, monkeypatch):
    def missing(name):
        raise metadata.PackageNotFoundError(name)

    monkeypatch.setattr(metadata, "distribution", missing)
    assert installation.installation_info()["source"] is None


def test_cli_json_and_verbose_do_not_need_daemon(installed_package, capsys):
    assert cli.main(["version", "--json"]) == 0
    info = json.loads(capsys.readouterr().out)
    assert info["version"] == __version__ and info["module"].endswith("codar/__init__.py")
    assert cli.main(["version", "--verbose"]) == 0
    assert "Commit: não registrado" in capsys.readouterr().out
    assert cli.main(["--version"]) == 0
    assert capsys.readouterr().out.startswith(f"codar {__version__} (Python ")


def test_same_version_can_still_have_an_old_daemon():
    local = {"version": "0.1.1", "commit": "new", "module": "/pipx/codar/__init__.py"}
    remote = {"version": "0.1.1", "installation": {**local, "commit": "old"}}
    assert "commits diferentes" in installation.daemon_mismatch(remote, local)
    remote["installation"] = {**local, "module": "/usr/lib/codar/codar/__init__.py"}
    assert "instalações diferentes" in installation.daemon_mismatch(remote, local)
    assert installation.daemon_mismatch({"version": "0.1.1"}, local) is None
    assert installation.daemon_mismatch({"version": "0.1.0"}, local)


def test_restart_must_not_succeed_when_old_daemon_does_not_stop(monkeypatch):
    monkeypatch.setattr(cli, "cmd_stop", lambda args: cli.EXIT_ERR)

    def must_not_start(args):
        pytest.fail("não deve iniciar/reusar um daemon cuja parada falhou")

    monkeypatch.setattr(cli, "cmd_start", must_not_start)
    assert cli.cmd_restart(argparse.Namespace()) == cli.EXIT_ERR
