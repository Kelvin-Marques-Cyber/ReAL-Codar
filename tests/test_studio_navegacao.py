"""Studio só pelo teclado: atalhos para cada área, Esc volta ao editor, tradução de linha e de bloco (com limite)."""

import asyncio
from pathlib import Path

import pytest

textual = pytest.importorskip("textual")


class Backend:
    """Daemon falso: devolve a frase como comentário, com a indentação pedida (como o roteador faz)."""

    def __init__(self) -> None:
        self.pedidos: list[dict] = []

    def translate(self, intent, lang, *, indent="", **kw):
        self.pedidos.append({"intent": intent, "indent": indent, **kw})
        corpo = "\n".join(indent + ln if ln.strip() else ln for ln in TRADUCOES.get(intent, f"# {intent}").split("\n"))
        return {"stage": "0", "source": "teste", "timings": {"total_ms": 1.0}, "body": corpo, "code": corpo,
                "imports": [], "findings": [], "notes": [], "lang": lang or "python", "confidence": 1.0}

    def stats(self):
        raise RuntimeError("sem daemon")

    def audit(self, code, lang):
        return {"findings": [], "ms": 0.1}

    def close(self):
        pass


TRADUCOES = {"se idade maior que 17 imprimir 'pode'": "if idade > 17:\n    print('pode')",
             "senão imprimir 'não'": "else:\n    print('não')"}


def _studio(tmp_path: Path, monkeypatch, arquivos: dict[str, str]):
    from codar.studio.app import Studio

    monkeypatch.setenv("CODAR_HOME", str(tmp_path / "home"))
    monkeypatch.setenv("CODAR_NO_AUTOSTART", "1")
    for nome, texto in arquivos.items():
        (tmp_path / nome).write_text(texto, encoding="utf-8")
    app = Studio(tmp_path)
    app.preview_edits = False  # os cenários de revisão têm sua própria suíte
    app.backend = Backend()
    return app


async def _esperar(pilot, condicao, limite=50):
    for _ in range(limite):
        await pilot.pause(0.05)
        if condicao():
            return True
    return False


def test_atalhos_levam_a_cada_area_e_esc_volta_ao_editor(tmp_path, monkeypatch):
    from textual.widgets import Input

    from codar.studio.explorer import Explorer
    from codar.studio.widgets import CodeEditor

    app = _studio(tmp_path, monkeypatch, {"a.py": "x = 1\n", "b.py": "y = 2\n"})

    async def cenario():
        async with app.run_test(size=(150, 42)) as pilot:
            await app.open_file(tmp_path / "a.py")
            await app.open_file(tmp_path / "b.py")
            await pilot.pause(0.3)  # a troca de aba devolve o foco ao editor um instante depois de abrir
            await pilot.press("ctrl+e")
            assert isinstance(app.focused, Explorer)
            await pilot.press("escape")
            assert isinstance(app.focused, CodeEditor)
            await pilot.press("ctrl+t")
            assert isinstance(app.focused, Input) and app.focused.id == "term-input"
            await pilot.press("escape")
            await pilot.press("ctrl+l")
            assert app.focused.id == "intent"
            await pilot.press("escape")
            assert Path(app.current_editor().path).name == "b.py"
            await pilot.press("ctrl+pagedown")
            assert Path(app.current_editor().path).name == "a.py" and isinstance(app.focused, CodeEditor)

    asyncio.run(cenario())


def test_enter_depois_da_traducao_nao_apaga_o_codigo(tmp_path, monkeypatch):
    app = _studio(tmp_path, monkeypatch, {"a.py": ""})

    async def cenario():
        async with app.run_test(size=(150, 42)) as pilot:
            ed = await _abrir(app, pilot, tmp_path / "a.py")
            for ch in "se idade maior que 17 imprimir 'pode' ":
                await pilot.press({" ": "space"}.get(ch, ch))
            await pilot.press("enter")
            assert await _esperar(pilot, lambda: "if idade" in ed.text)
            assert ed.selection.start == ed.selection.end  # nada selecionado: o próximo Enter não apaga
            await pilot.press("enter")
            assert ed.text == "if idade > 17:\n    print('pode')\n    "  # continua no corpo do if
            for ch in "senão imprimir 'não' ":
                await pilot.press({" ": "space"}.get(ch, ch))
            await pilot.press("enter")
            assert await _esperar(pilot, lambda: "else" in ed.text)
            assert app.backend.pedidos[-1]["indent"] == ""  # o senão sai alinhado com o if
            assert ed.text == "if idade > 17:\n    print('pode')\nelse:\n    print('não')"

    asyncio.run(cenario())


def test_ctrl_g_traduz_o_bloco_selecionado_com_limite(tmp_path, monkeypatch):
    from textual.widgets.text_area import Selection

    linhas = "\n".join(f"    imprimir {i}" for i in range(40))
    app = _studio(tmp_path, monkeypatch, {"a.py": "def f():\n" + linhas + "\n"})

    async def cenario():
        async with app.run_test(size=(150, 42)) as pilot:
            ed = await _abrir(app, pilot, tmp_path / "a.py")
            ed.selection = Selection((1, 0), (4, 0))  # 3 linhas (a quarta só no começo não conta)
            await pilot.press("ctrl+g")
            assert await _esperar(pilot, lambda: app.backend.pedidos)
            pedido = app.backend.pedidos[-1]
            assert pedido["intent"] == "imprimir 0\nimprimir 1\nimprimir 2" and pedido["indent"] == "    "
            assert await _esperar(pilot, lambda: "# imprimir 0" in ed.text)
            assert ed.document.get_line(1) == "    # imprimir 0\nimprimir 1\nimprimir 2".split("\n")[0]

            app.backend.pedidos.clear()
            ed.selection = Selection((1, 0), (40, 0))  # 39 linhas: acima do máximo (30)
            await pilot.press("ctrl+g")
            await pilot.pause(0.2)
            assert app.backend.pedidos == []

    asyncio.run(cenario())


async def _abrir(app, pilot, caminho):
    await app.open_file(caminho)
    await pilot.pause(0.3)
    ed = app.current_editor()
    ed.focus()
    ed.move_cursor(ed.document.end)
    return ed


def test_barra_de_intencao_cria_e_abre_arquivos(tmp_path, monkeypatch):
    from codar.studio.comandos import interpretar

    assert interpretar("crie um arquivo python chamado app").caminhos == ["app.py"]
    assert interpretar("crie as pastas src e tests").acao == "criar_pasta"
    assert interpretar("crie uma calculadora") is None  # pedido de código continua indo para o tradutor

    app = _studio(tmp_path, monkeypatch, {"conta.py": "x = 1\n"})

    async def cenario():
        async with app.run_test(size=(150, 42)) as pilot:
            for frase in ("crie a pasta modelos", "crie o arquivo modelos/pessoa.py"):
                await pilot.press("ctrl+l")
                for ch in frase:
                    await pilot.press({" ": "space"}.get(ch, ch))
                await pilot.press("enter")
                await pilot.pause(0.3)
            assert (tmp_path / "modelos").is_dir() and (tmp_path / "modelos" / "pessoa.py").is_file()
            assert app.current_editor().path == str(tmp_path / "modelos" / "pessoa.py")
            await pilot.press("ctrl+l")
            for ch in "abra conta.py":
                await pilot.press({" ": "space"}.get(ch, ch))
            await pilot.press("enter")
            await pilot.pause(0.3)
            assert Path(app.current_editor().path).name == "conta.py"
            assert app.backend.pedidos == []  # nada disso foi para o tradutor

    asyncio.run(cenario())
