"""Dicas de pacotes: imports de bibliotecas não instaladas viram o comando certo para o gerenciador do projeto."""

import asyncio
import json
import sys
import shlex
from pathlib import Path

import pytest

from codar.advisor import pacotes


def test_imports_js_ignora_caminhos_relativos_e_modulos_do_node():
    codigo = ('import React, { useState } from "react";\nimport "./estilo.css";\nimport fs from "node:fs";\n'
              'import path from "path";\nconst x = require("express");\nexport { a } from "@tanstack/react-query/dev";\n'
              'const m = await import("lodash/merge");\nimport { serve } from "bun";\nimport db from "bun:sqlite";\n')
    assert pacotes.imports_js(codigo) == ["react", "express", "@tanstack/react-query", "lodash"]


def _projeto(tmp_path: Path, deps: dict | None = None, lock: str = "bun.lock") -> Path:
    if deps is not None:
        (tmp_path / "package.json").write_text(json.dumps({"name": "app", "dependencies": deps}), encoding="utf-8")
    (tmp_path / lock).write_text("", encoding="utf-8")
    return tmp_path


def test_react_nao_instalado_vira_bun_add_com_react_dom(tmp_path):
    raiz = _projeto(tmp_path, {})
    arquivo = raiz / "App.jsx"
    lista = pacotes.dicas_js(raiz, arquivo, 'import { useState } from "react";\n', caminho="/nada")
    assert [d.comando for d in lista if d.id.startswith("pacotes:js")] == ["bun add react react-dom"]


def test_declarado_mas_nao_instalado_pede_install_e_npm_sem_lock(tmp_path):
    raiz = _projeto(tmp_path, {"express": "^4"}, lock="package-lock.json")
    lista = pacotes.dicas_js(raiz, raiz / "app.js", 'const app = require("express")();\n', caminho="/nada")
    assert [d.comando for d in lista] == ["npm install"]


def test_typescript_pede_os_tipos_e_projeto_sem_package_json(tmp_path):
    raiz = _projeto(tmp_path, None, lock="pnpm-lock.yaml")
    lista = pacotes.dicas_js(raiz, raiz / "server.ts", 'import express from "express";\nimport fs from "fs";\n',
                             caminho="/nada")
    comandos = [d.comando for d in lista]
    assert "pnpm init -y" in comandos
    assert "pnpm add express" in comandos
    assert "pnpm add -D @types/express @types/node" in comandos


def test_pacote_instalado_nao_gera_dica(tmp_path):
    raiz = _projeto(tmp_path, {"react": "^19"})
    (raiz / "node_modules" / "react").mkdir(parents=True)
    (raiz / "node_modules" / "react" / "package.json").write_text("{}", encoding="utf-8")
    assert pacotes.dicas_js(raiz, raiz / "a.js", 'import React from "react";\n', caminho="/nada") == []


def test_python_usa_o_nome_do_pip_e_cria_o_venv_do_projeto(tmp_path):
    (tmp_path / "util.py").write_text("x = 1\n", encoding="utf-8")
    codigo = "import os, json\nimport util\nimport cv2\nfrom pacote_que_nao_existe_xyz import algo\n"
    lista = pacotes.dicas_python(tmp_path, tmp_path / "app.py", codigo)
    assert len(lista) == 1
    dica = lista[0]
    assert "pacote_que_nao_existe_xyz" in dica.titulo and "util" not in dica.titulo and "os" not in dica.titulo.split()
    before, after, select = dica.comando.split(" && ")
    assert shlex.split(before) == [sys.executable, "-m", "venv", ".venv"]
    assert after.startswith(".venv/bin/python -m pip install")
    assert 'toolchains use python' in select and str(tmp_path / '.venv/bin/python') in select
    if "cv2" in dica.titulo:  # sem OpenCV instalado aqui: o pacote certo para servidores
        assert "opencv-python-headless" in dica.comando


def test_python_do_projeto_prefere_o_venv(tmp_path):
    assert pacotes.python_do_projeto(tmp_path) == sys.executable
    (tmp_path / ".venv" / "bin").mkdir(parents=True)
    (tmp_path / ".venv" / "bin" / "python").write_text("", encoding="utf-8")
    assert pacotes.python_do_projeto(tmp_path) == str(tmp_path / ".venv" / "bin" / "python")


def test_studio_mostra_a_dica_e_instala_pelo_terminal(tmp_path, monkeypatch):
    pytest.importorskip("textual")
    from codar.studio.app import Studio

    monkeypatch.setenv("CODAR_HOME", str(tmp_path / "home"))
    monkeypatch.setenv("CODAR_NO_AUTOSTART", "1")
    chamadas = []

    def dicas_falsas(raiz, arquivo, codigo, lang, caminho=None):
        chamadas.append(arquivo)
        if len(chamadas) > 1:  # depois de "instalar", não falta mais nada
            return []
        return [pacotes.DicaPacote("pacotes:js:react", "react não está instalado", "o arquivo importa react",
                                   "echo instalando-react", "REACT FALTA")]

    monkeypatch.setattr(pacotes, "dicas", dicas_falsas)
    (tmp_path / "App.jsx").write_text('import React from "react";\n', encoding="utf-8")

    async def cenario():
        app = Studio(tmp_path)
        async with app.run_test(size=(150, 42)) as pilot:
            await app.open_file(tmp_path / "App.jsx")
            await pilot.pause(0.5)
            assert "REACT FALTA" in app.context_hint()
            await pilot.press("f8")
            await pilot.pause(0.3)
            assert app.advice[0]["source"] == "pacotes"
            lista = app.query_one("#advice-list")
            lista.focus()
            lista.index = 0
            await pilot.press("enter")
            from codar.studio.screens import AdviceScreen
            assert isinstance(app.screen, AdviceScreen)
            assert app.terminal.sessao.proc is None  # somente selecionar a dica não executa o comando
            await pilot.click("#opt-instalar")
            sessao = app.terminal.sessao
            for _ in range(50):
                await pilot.pause(0.1)
                if len(chamadas) > 1:
                    break
            assert any("instalando-react" in linha.text for linha in sessao.log.lines)
            assert len(chamadas) > 1  # conferiu de novo depois de instalar

    asyncio.run(cenario())


def test_tkinter_ausente_vira_instalacao_nativa_e_nao_pip(tmp_path, monkeypatch):
    monkeypatch.setattr(pacotes.sys, "platform", "linux")
    monkeypatch.setattr(pacotes.platform, "freedesktop_os_release", lambda: {"ID": "opensuse-tumbleweed", "ID_LIKE": "suse"})
    info = dict(ok=False, version=[3, 13], base="/usr", executable="/usr/bin/python3.13")
    monkeypatch.setattr(pacotes, "ambiente_tk", lambda python: info)
    monkeypatch.setattr(pacotes, "modulos_ausentes", lambda python, modules: modules)
    hints = pacotes.dicas_python(tmp_path, tmp_path / "interface.py", "import tkinter as tk\nimport requests\n")
    assert len(hints) == 2
    assert hints[0].comando == "sudo zypper install python313-tk"
    assert hints[0].como_sugestao()["options"][0]["label"] == "Instalar Tcl/Tk"
    assert "pip install requests" in hints[1].comando
    assert "pip install tkinter" not in hints[1].comando


@pytest.mark.parametrize("distro,expected", [
    ("ubuntu", "sudo apt-get install python3.13-tk"),
    ("fedora", "sudo dnf install python3.13-tkinter"),
    ("arch", "sudo pacman -S tk"),
    ("alpine", "sudo apk add py3-tkinter"),
])
def test_tk_seleciona_a_distribuicao_do_python(tmp_path, monkeypatch, distro, expected):
    monkeypatch.setattr(pacotes.sys, "platform", "linux")
    monkeypatch.setattr(pacotes.platform, "freedesktop_os_release", lambda: {"ID": distro})
    info = dict(ok=False, version=[3, 13], base="/usr", executable="/usr/bin/python3.13")
    assert pacotes.dica_tk(tmp_path, sys.executable, info).comando == expected


def test_tk_instalado_nao_pede_instalacao_e_python_personalizado_da_instrucoes(tmp_path, monkeypatch):
    monkeypatch.setattr(pacotes, "ambiente_tk", lambda python: {"ok": True})
    assert pacotes.dicas_python(tmp_path, tmp_path / "a.py", "from tkinter import ttk\n") == []
    monkeypatch.setattr(pacotes.sys, "platform", "linux")
    info = dict(ok=False, version=[3, 13], base="/opt/pyenv", executable="/opt/pyenv/bin/python3.13")
    dica = pacotes.dica_tk(tmp_path, sys.executable, info)
    assert "sudo" not in dica.comando and "pip install" not in dica.comando
    assert dica.rotulo == "Ver instruções oficiais"
    assert "recompile" in " ".join(dica.instrucoes)


def test_tk_verifica_o_interpretador_do_projeto_sem_abrir_janela():
    result = pacotes.ambiente_tk(sys.executable)
    assert type(result["ok"]) is bool
    assert result["version"] == list(sys.version_info[:2])
