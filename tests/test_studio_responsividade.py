"""Arquivos grandes: o realce cobre só a área visível e a altura do documento não é recalculada a cada tecla."""

import asyncio

import pytest

pytest.importorskip("textual")

from codar.studio.app import Studio


def _grande(raiz, linhas=2000):
    texto = ['"""Docstring', "de várias linhas", 'no topo."""']
    for i in range(linhas):
        texto += [f"def funcao_{i}(a, b):", f"    return a + b * {i}", ""]
    texto[-300:-300] = ['TEXTO = """começa aqui', *["linha da string"] * 600, 'e termina aqui"""']
    arquivo = raiz / "grande.py"
    arquivo.write_text("\n".join(texto), encoding="utf-8")
    return arquivo


def _studio(tmp_path, monkeypatch):
    monkeypatch.setenv("CODAR_HOME", str(tmp_path / "home"))
    monkeypatch.setenv("CODAR_NO_AUTOSTART", "1")
    return Studio(tmp_path, local=True)


def test_realce_so_na_janela_visivel_e_acompanha_a_rolagem(tmp_path, monkeypatch):
    pytest.importorskip("tree_sitter_python")
    arquivo = _grande(tmp_path)
    app = _studio(tmp_path, monkeypatch)

    async def cenario():
        async with app.run_test(size=(150, 42)) as pilot:
            await app.open_file(arquivo)
            await pilot.pause(0.3)
            ed = app.current_editor()
            assert ed._realce_janela is not None
            inicio, fim = ed._realce_janela
            assert fim - inicio < 600 < ed.document.line_count  # não consulta o arquivo inteiro
            assert ed._highlights[0]  # a docstring do topo tem realce
            comeco = next(i for i in range(ed.document.line_count) if ed.document[i].startswith('TEXTO = """'))
            alvo = comeco + 500  # dentro da string longa, que começa acima da janela de realce
            ed.move_cursor((alvo, 0))
            ed.scroll_cursor_visible(center=True, animate=False)
            await pilot.pause(0.3)
            inicio, fim = ed._realce_janela
            assert comeco < inicio <= alvo < fim
            assert any(nome == "string" for *_, nome in ed._highlights[alvo]), ed._highlights[alvo]
            linha_def = next(i for i in range(alvo, ed.document.line_count) if ed.document[i].startswith("def "))
            assert ed._highlights[linha_def]  # código depois da string também colorido
    asyncio.run(cenario())


def test_altura_do_documento_acompanha_edicoes_e_desfazer(tmp_path, monkeypatch):
    arquivo = _grande(tmp_path, linhas=500)
    app = _studio(tmp_path, monkeypatch)

    async def cenario():
        async with app.run_test(size=(120, 40)) as pilot:
            await app.open_file(arquivo)
            await pilot.pause(0.2)
            ed = app.current_editor()
            assert type(ed.wrapped_document).__name__ == "_DocumentoQuebrado"
            antes = ed.document.line_count
            assert ed.wrapped_document.height == antes
            ed.insert("a = 1\n" * 10, (5, 0))
            await pilot.pause(0.1)
            assert ed.wrapped_document.height == ed.document.line_count == antes + 10
            assert ed.virtual_size.height >= antes + 10
            ed.action_undo()
            await pilot.pause(0.1)
            assert ed.wrapped_document.height == ed.document.line_count == antes
    asyncio.run(cenario())
