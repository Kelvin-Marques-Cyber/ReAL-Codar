"""Estrutura automática de projetos: cria pastas e arquivos de um modelo, sem sobrescrever e sem sair da pasta."""

import asyncio
import json
import shutil
import subprocess
import sys

import pytest

from codar import config, estruturas
from codar._compat import tomllib
from codar.plugin_loader import _estruturas_from, discover

MODELOS = discover(config.load()).estruturas


def _modelo(identidade):
    return next(e for e in MODELOS if e.id == identidade)


def test_modelos_embutidos_cobrem_as_stacks_principais():
    ids = {e.id for e in MODELOS}
    assert {"fullstack-ts", "fullstack-js", "web-estatico", "python-pacote", "python-api", "go-modulo",
            "rust-binario", "java-maven", "c-cmake", "cpp-cmake", "latex-documento"} <= ids


@pytest.mark.parametrize("caminho", ["../fora.txt", "/etc/passwd", "a\\b.txt", "C:/x", ".git/config", "a/../b", ""])
def test_carregador_recusa_caminhos_perigosos(caminho):
    with pytest.raises(ValueError):
        _estruturas_from({"estrutura": [{"id": "x", "titulo": "X", "arquivos": {caminho: ""}}]}, "plugin")


@pytest.mark.parametrize("consulta,esperado", [("full stack typescript", "fullstack-ts"), ("full stack js", "fullstack-js"),
                                               ("api python", "python-api"), ("ciência de dados", "python-dados"),
                                               ("projeto go", "go-modulo"), ("tcc em latex", "latex-documento"),
                                               ("site html", "web-estatico"), ("c++", "cpp-cmake")])
def test_busca_por_descricao(consulta, esperado):
    assert estruturas.buscar(MODELOS, consulta)[0].id == esperado


def test_pedido_na_barra_de_intencao():
    assert estruturas.pedido("crie a estrutura de um projeto full stack typescript") == "full stack typescript"
    assert estruturas.pedido("Monte o esqueleto de uma API Python") == "api python"
    assert estruturas.pedido("crie uma função que soma") is None


def test_nunca_sobrescreve_e_preenche_o_nome(tmp_path):
    raiz = tmp_path / "Minha Loja"
    raiz.mkdir()
    (raiz / "package.json").write_text('{"meu": true}')
    criados, mantidos = estruturas.aplicar(raiz, estruturas.plano(raiz, _modelo("fullstack-ts")))
    assert mantidos == ["package.json"] and json.loads((raiz / "package.json").read_text()) == {"meu": True}
    assert "src/server/index.ts" in criados and (raiz / "src/server/index.ts").read_text() == ""
    assert (raiz / "src/client").is_dir() and (raiz / "public").is_dir()
    assert "# minha-loja" in (raiz / "README.md").read_text()
    # Rodar de novo não muda nada.
    assert estruturas.aplicar(raiz, estruturas.plano(raiz, _modelo("fullstack-ts")))[0] == []


def test_nao_escreve_atraves_de_link_simbolico(tmp_path):
    raiz, fora = tmp_path / "projeto", tmp_path / "fora"
    raiz.mkdir()
    fora.mkdir()
    (raiz / "src").symlink_to(fora, target_is_directory=True)
    with pytest.raises(ValueError):
        estruturas.plano(raiz, _modelo("fullstack-js"))
    assert not any(fora.iterdir())


@pytest.mark.parametrize("modelo", [e.id for e in MODELOS])
def test_configuracoes_geradas_sao_validas(tmp_path, modelo):
    raiz = tmp_path / "app-teste"
    raiz.mkdir()
    estruturas.aplicar(raiz, estruturas.plano(raiz, _modelo(modelo)))
    for arquivo in raiz.rglob("*"):
        if arquivo.name in ("package.json", "tsconfig.json"):
            json.loads(arquivo.read_text())
        elif arquivo.suffix == ".toml":
            tomllib.loads(arquivo.read_text())
        elif arquivo.name == "pom.xml":
            import xml.dom.minidom

            xml.dom.minidom.parseString(arquivo.read_text())
    assert "{{" not in "".join(p.read_text() for p in raiz.rglob("*") if p.is_file())


@pytest.mark.parametrize("modelo,ferramenta,comando", [
    ("go-modulo", "go", ["go", "build", "./..."]),
    ("rust-binario", "rustc", ["rustc", "--edition", "2021", "src/main.rs", "-o", "programa"]),
    ("c-cmake", "gcc", ["gcc", "src/main.c", "-o", "programa"]),
    ("cpp-cmake", "g++", ["g++", "src/main.cpp", "-o", "programa"]),
    ("python-pacote", None, [sys.executable, "-c", "import sys; sys.path.insert(0, 'src'); import app_teste.main"]),
])
def test_pontos_de_entrada_compilam(tmp_path, modelo, ferramenta, comando):
    if ferramenta and not shutil.which(ferramenta):
        pytest.skip(f"{ferramenta} ausente")
    raiz = tmp_path / "app-teste"
    raiz.mkdir()
    estruturas.aplicar(raiz, estruturas.plano(raiz, _modelo(modelo)))
    resultado = subprocess.run(comando, cwd=raiz, capture_output=True, text=True, timeout=120,
                               env={**__import__("os").environ, "GOFLAGS": "-mod=mod", "GOTOOLCHAIN": "local"})
    assert resultado.returncode == 0, resultado.stderr


def test_cli_lista_mostra_previa_e_cria(tmp_path, capsys):
    from codar.cli.main import main

    assert main(["project", "scaffold"]) == 0 and "fullstack-ts" in capsys.readouterr().out
    assert main(["project", "scaffold", "rust", "--root", str(tmp_path), "--dry-run"]) == 0
    assert "+ src/main.rs" in capsys.readouterr().out and not (tmp_path / "src").exists()
    assert main(["project", "estrutura", "rust-binario", "--root", str(tmp_path), "--name", "Jogo"]) == 0
    assert 'name = "jogo"' in (tmp_path / "Cargo.toml").read_text()


def test_studio_cria_pela_barra_de_intencao_com_confirmacao(tmp_path, monkeypatch):
    pytest.importorskip("textual")
    from textual.widgets import Input

    from codar.studio.app import Studio
    from codar.studio.explorer import ConfirmScreen

    monkeypatch.setenv("CODAR_HOME", str(tmp_path / "home"))
    monkeypatch.setenv("CODAR_NO_AUTOSTART", "1")
    raiz = tmp_path / "loja"
    raiz.mkdir()

    async def cenario():
        app = Studio(raiz, local=True)
        async with app.run_test(size=(150, 42)) as pilot:
            campo = app.query_one("#intent", Input)
            campo.focus()
            campo.value = "crie a estrutura de um projeto full stack typescript"
            await pilot.press("enter")
            for _ in range(40):
                await pilot.pause(0.05)
                if isinstance(app.screen, ConfirmScreen):
                    break
            assert isinstance(app.screen, ConfirmScreen) and "Full Stack TypeScript" in app.screen.pergunta
            assert not (raiz / "src").exists()  # nada antes de confirmar
            await pilot.press("enter")
            for _ in range(40):
                await pilot.pause(0.05)
                if (raiz / "src" / "server" / "index.ts").exists():
                    break
            assert (raiz / "tsconfig.json").is_file() and (raiz / "src" / "server" / "index.ts").is_file()
    asyncio.run(cenario())
