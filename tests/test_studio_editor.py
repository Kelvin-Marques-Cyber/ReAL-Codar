"""Editor do Studio com o comportamento do VS Code: pares que fecham sozinhos, Enter que indenta, else que se alinha,
Tab/Shift+Tab em bloco, Ctrl+/, Alt+↑/↓, tags HTML e os pontinhos de indentação."""

import asyncio

import pytest

textual = pytest.importorskip("textual")

from textual.app import App  # noqa: E402
from textual.widgets.text_area import Selection  # noqa: E402

from codar import langs  # noqa: E402
from codar.studio.widgets import CodeEditor  # noqa: E402

NOMES = {" ": "space", "\n": "enter"}


class _App(App):
    def __init__(self, texto: str, lang: str | None, path: str | None) -> None:
        super().__init__()
        self.texto, self.lang, self.path = texto, lang, path

    def compose(self):
        ts = {"python": "python", "javascript": "javascript", "html": "html", "typescript": "javascript"}.get(self.lang)
        ed = CodeEditor.code_editor(self.texto, language=ts, soft_wrap=False)
        ed.path, ed.lang_id = self.path, self.lang
        lang = langs.LANGS.get(self.lang or "")
        if lang:
            ed.indent_type = "tabs" if lang.indent == "\t" else "spaces"
            ed.indent_width = 4 if lang.indent == "\t" else len(lang.indent)
        yield ed


def editar(texto: str, teclas, lang: str | None = "python", cursor=None, selecao=None, path=None):
    """Roda as teclas no editor e devolve (texto, cursor, seleção vazia?)."""

    async def cenario():
        app = _App(texto, lang, path)
        async with app.run_test() as pilot:
            ed = app.query_one(CodeEditor)
            ed.focus()
            if selecao:
                ed.selection = Selection(*selecao)
            else:
                ed.move_cursor(cursor if cursor is not None else ed.document.end)
            for t in teclas:
                await pilot.press(NOMES.get(t, t))
            await pilot.pause()
            return ed.text, ed.cursor_location, ed.selection.start == ed.selection.end

    return asyncio.run(cenario())


def test_parentese_fecha_e_o_fechamento_passa_por_cima():
    texto, cursor, _ = editar("", list("print(x)"))
    assert texto == "print(x)" and cursor == (0, 8)


def test_aspas_e_fstring():
    assert editar("", list('s = "oi"'))[0] == 's = "oi"'
    assert editar("", list('print(f"a")'))[0] == 'print(f"a")'
    assert editar("", list("nao' "))[0] == "nao' "  # apóstrofo depois de letra não abre par


def test_backspace_apaga_o_par_vazio():
    assert editar("", ["(", "backspace"])[0] == ""


def test_selecao_fica_entre_parenteses():
    texto, _, _ = editar("abc", ["("], selecao=((0, 0), (0, 3)))
    assert texto == "(abc)"


def test_enter_indenta_depois_de_dois_pontos_e_sai_depois_de_return():
    texto, cursor, _ = editar("if x:", ["\n"])
    assert texto == "if x:\n    " and cursor == (1, 4)
    texto, cursor, _ = editar("def f():\n    return 1", ["\n"])
    assert texto == "def f():\n    return 1\n" and cursor == (2, 0)


def test_enter_entre_chaves_abre_o_bloco():
    texto, cursor, _ = editar("f() {}", ["\n"], lang="javascript", cursor=(0, 5))
    assert texto == "f() {\n  \n}" and cursor == (1, 2)


def test_enter_em_linha_so_com_espacos_nao_deixa_espaco_sobrando():
    texto, cursor, _ = editar("if x:\n    ", ["\n"])
    assert texto == "if x:\n\n    " and cursor == (2, 4)


def test_else_se_alinha_com_o_if_ao_digitar_os_dois_pontos():
    texto, _, _ = editar("if x:\n    a()\n    else", [":"])
    assert texto == "if x:\n    a()\nelse:"
    texto, _, _ = editar("for i in v:\n    if i:\n        a()\n        elif j", [":"])
    assert texto.endswith("\n    elif j:")


def test_tab_e_shift_tab_com_varias_linhas():
    texto, _, _ = editar("a\nb", ["tab"], selecao=((0, 0), (1, 1)))
    assert texto == "    a\n    b"
    texto, _, _ = editar("    a\n    b", ["shift+tab"], selecao=((0, 0), (1, 5)))
    assert texto == "a\nb"


def test_backspace_na_indentacao_apaga_um_nivel():
    assert editar("        ", ["backspace"])[0] == "    "


def test_ctrl_barra_comenta_e_descomenta():
    texto, _, _ = editar("x = 1\ny = 2", ["ctrl+underscore"], selecao=((0, 0), (1, 5)))
    assert texto == "# x = 1\n# y = 2"
    texto, _, _ = editar(texto, ["ctrl+underscore"], selecao=((0, 0), (1, 7)))
    assert texto == "x = 1\ny = 2"
    assert editar("<p>oi</p>", ["ctrl+underscore"], lang="html", path="a.html")[0] == "<!-- <p>oi</p> -->"


def test_alt_setas_movem_e_duplicam_linhas():
    texto, cursor, _ = editar("a\nb\nc", ["alt+down"], cursor=(0, 0))
    assert texto == "b\na\nc" and cursor == (1, 0)
    texto, cursor, _ = editar("a\nb", ["alt+shift+down"], cursor=(0, 0))
    assert texto == "a\na\nb" and cursor == (1, 0)


def test_tag_html_fecha_sozinha_mas_generico_do_typescript_nao():
    texto, cursor, _ = editar("", list("<div>"), lang="html", path="a.html")
    assert texto == "<div></div>" and cursor == (0, 5)
    assert editar("", list("<br>"), lang="html", path="a.html")[0] == "<br>"
    assert "</string>" not in editar("", list("useState<string>"), lang="typescript", path="a.tsx")[0]


def test_esc_limpa_a_selecao_sem_sair_do_editor():
    _, _, vazia = editar("abc", ["escape"], selecao=((0, 0), (0, 3)))
    assert vazia


def test_pontinhos_marcam_a_indentacao():
    async def cenario():
        app = _App("if x:\n    y = 1\n", "python", None)
        async with app.run_test() as pilot:
            ed = app.query_one(CodeEditor)
            ed.move_cursor((0, 0))
            await pilot.pause()
            return ed.render_line(1).text

    linha = asyncio.run(cenario())
    assert "····y = 1" in linha
