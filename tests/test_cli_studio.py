"""Sem o Textual, `codar` oferece instalar o Studio em vez de cair no REPL sem explicar (instalação pelo pacote)."""

import argparse
import sys

import pytest

from codar import extras
from codar.cli import main as cli


@pytest.fixture()
def sem_studio(monkeypatch):
    monkeypatch.setitem(sys.modules, "codar.studio.app", None)  # import falha como se o Textual não existisse
    monkeypatch.setattr(cli, "_terminal_interativo", lambda: True)
    monkeypatch.setattr(extras, "packaged", lambda: True)
    chamadas = {"install": [], "execv": []}
    monkeypatch.setattr(extras, "install", lambda nomes: chamadas["install"].append(nomes) or 0)

    def execv(path, argv):
        chamadas["execv"].append(argv)
        raise SystemExit(0)

    monkeypatch.setattr(cli.os, "execv", execv)
    monkeypatch.setattr(cli.shutil, "which", lambda nome: "/usr/bin/codar")
    monkeypatch.setattr("codar.cli.repl.repl", lambda args: "repl")
    return chamadas


def test_aceitar_instala_e_reabre_o_studio(sem_studio, monkeypatch):
    monkeypatch.setattr("builtins.input", lambda _: "")  # Enter = sim
    with pytest.raises(SystemExit):
        cli.cmd_studio(argparse.Namespace(path=".", lang=None))
    assert sem_studio["install"] == [["studio", "syntax", "llm"]]
    assert sem_studio["execv"] == [["/usr/bin/codar", "studio", "."]]


def test_recusar_cai_no_repl_com_o_comando_de_instalacao(sem_studio, monkeypatch, capsys):
    monkeypatch.setattr("builtins.input", lambda _: "n")
    assert cli.cmd_studio(argparse.Namespace(path=".", lang=None)) == "repl"
    assert sem_studio["install"] == [] and sem_studio["execv"] == []
    assert "codar extras install" in capsys.readouterr().err
