"""Pedidos encadeados ("agora adicione tipagem") modificam a implementação certa, sem criar outra função."""

import asyncio

import pytest

from codar.engine.continuity import declarations, followup_target, wants_followup


@pytest.mark.parametrize("intent", [
    "agora adicione tipagem", "adicione type hints", "now add type hints", "y ahora añade tipos",  # pt-BR, en, es
    "agora acrescente a documentação", "add docstrings", "añade documentación", "documente a função",
    "adicione tratamento de erros", "now add error handling", "agora adicione validação", "agora corrija",
    "corrija esta função", "fix it", "transforme em async", "make it async", "torne a função recursiva",
    "renomeie x para total", "# agora adicione tipagem", "por favor, adicione comentários"])
def test_reconhece_continuacoes_nos_idiomas(intent):
    assert wants_followup(intent)


@pytest.mark.parametrize("intent", [
    "corrija",  # sem alvo explícito continua editando o arquivo aberto, como antes
    "adicione uma função que soma dois números", "adicione validação de CPF", "add tests", "crie uma função",
    "agora crie uma classe Conta", "documentação da api do numpy", "x é igual a 10", "importe numpy"])
def test_pedido_novo_nao_e_continuacao(intent):
    assert not wants_followup(intent)


PY = ("import os\n\n"
      "@cache\n"
      "def somar(a, b):\n"
      "    return a + b\n\n\n"
      "class Conta:\n"
      "    def __init__(self, saldo):\n"
      "        self.saldo = saldo\n\n"
      "    def depositar(self, valor):\n"
      "        self.saldo += valor\n")


def test_declaracoes_python_incluem_decoradores_e_metodos():
    found = [(d.start, d.end, d.name, d.container) for d in declarations(PY, "python")]
    assert found == [(2, 4, "somar", False), (7, 12, "Conta", True), (8, 9, "__init__", False),
                     (11, 12, "depositar", False)]
    # Arquivo que ainda não compila (pedido digitado no editor): o recuo delimita a função.
    broken = "def somar(a, b):\n    return a + b\nagora adicione tipagem\n"
    assert [(d.start, d.end) for d in declarations(broken, "python")] == [(0, 1)]


@pytest.mark.parametrize("lang,code,expected", [
    ("javascript", "/** soma */\nfunction somar(a, b) {\n  return a + b;\n}\nconst dobro = (x) => x * 2;\n"
                   "describe('x', () => {\n  it('y', () => {});\n});\nconsole.log(somar(1, 2));\n",
     [(0, 3, "somar"), (4, 4, "dobro")]),
    ("typescript", "class Conta {\n  depositar(v: number): void {\n    if (v > 0) {\n      this.s += v;\n    }\n  }\n}\n",
     [(0, 6, "Conta"), (1, 5, "depositar")]),
    ("go", "package main\n\nfunc (c *Conta) Depositar(v int) {\n\tc.s += v\n}\n", [(2, 4, "Depositar")]),
    ("rust", "#[test]\nfn soma() {\n    println!(\"{}\", \"}\");\n}\n", [(0, 3, "soma")]),
    ("java", "class Main {\n    @Override\n    public String toString() {\n        return \"{\";\n    }\n\n"
             "    static int soma(int a, int b)\n    {\n        return a + b;\n    }\n}\n",
     [(0, 10, "Main"), (1, 4, "toString"), (6, 9, "soma")]),
    ("csharp", "class A {\n    public int Soma(int a, int b) => a + b;\n}\n", [(0, 2, "A"), (1, 1, "Soma")]),
    ("dart", "int soma(int a, int b) => a + b;\n\nvoid main() {\n  print('${soma(1, 2)}');\n  return soma(1, 2);\n}\n",
     [(0, 0, "soma"), (2, 5, "main")]),
    ("c", "int soma(int a, int b);\n\nint soma(int a, int b) {\n    return a + b;\n}\n", [(2, 4, "soma")]),
    ("powershell", "function Get-Soma {\n    param($a, $b)\n    $a + $b\n}\nGet-Soma 1 2\n", [(0, 3, "Get-Soma")]),
    ("bash", "soma() {\n  echo $(( $1 + $2 ))\n}\nsoma 1 2\n", [(0, 2, "soma")]),
])
def test_declaracoes_de_linguagens_de_chaves_ignoram_chamadas_e_prototipos(lang, code, expected):
    assert [(d.start, d.end, d.name) for d in declarations(code, lang)] == expected


def test_linguagem_nao_analisada_nao_inventa_alvo():
    assert declarations("def soma(a, b)\n  a + b\nend\n", "ruby") is None
    assert followup_target("def soma(a, b)\n  a + b\nend\n", 1, "ruby") is None


def test_alvo_sob_o_cursor_recente_ou_logo_acima():
    assert followup_target(PY, 12, "python") == (11, 12, "depositar")  # cursor dentro do método
    assert followup_target(PY, 10, "python") == (8, 9, "__init__")  # linha vazia entre métodos: o de cima
    assert followup_target(PY + "\n\n", 14, "python") == (7, 12, "Conta")  # logo abaixo da classe recém-escrita
    assert followup_target(PY, 0, "python") is None  # nenhuma evidência: não adivinha entre várias funções
    # O resultado do pedido anterior vale mesmo com o cursor longe, desde que as linhas sejam as mesmas.
    assert followup_target(PY, 0, "python", recent=(2, 5)) == (2, 4, "somar")
    assert followup_target(PY, 0, "python", recent=(7, 12)) == (7, 12, "Conta")


class Backend:
    def __init__(self, reply=None):
        self.requests = []
        self.reply = reply

    def stats(self):
        raise RuntimeError("sem daemon")

    def close(self):
        pass

    def translate(self, intent, lang, **kw):
        self.requests.append(dict(intent=intent, lang=lang, **kw))
        body = self.reply(kw) if self.reply else kw.get("selected", "")
        return dict(stage="2:edit", source="teste", timings={}, body=body, code=body, lang=lang,
                    imports=[], findings=[], notes=[], complete=True)


def _studio(tmp_path, monkeypatch, code, backend):
    pytest.importorskip("textual")
    from codar.studio.app import Studio

    monkeypatch.setenv("CODAR_HOME", str(tmp_path / "home"))
    monkeypatch.setenv("CODAR_NO_AUTOSTART", "1")
    monkeypatch.setenv("CODAR_SHELL_ENV", "0")
    file = tmp_path / "calc.py"
    file.write_text(code, encoding="utf-8")
    app = Studio(tmp_path)
    app.backend = backend
    app.preview_edits = False
    return app, file


async def _wait(pilot, condition):
    for _ in range(200):
        await pilot.pause(0.05)
        if condition():
            return
    assert condition()


async def _submit(app, pilot, text):
    from textual.widgets import Input

    field = app.query_one("#intent", Input)
    field.focus()
    field.value = text
    await pilot.press("enter")


def test_studio_edita_somente_a_funcao_sob_o_cursor(tmp_path, monkeypatch):
    code = "def somar(a, b):\n    return a + b\n\n\ndef dobro(x):\n    return x * 2\n"
    typed = "def dobro(x: int) -> int:\n    return x * 2"
    backend = Backend(lambda kw: typed)
    app, file = _studio(tmp_path, monkeypatch, code, backend)

    async def scenario():
        async with app.run_test(size=(150, 42)) as pilot:
            await app.open_file(file)
            editor = app.current_editor()
            editor.move_cursor((5, 4))
            await _submit(app, pilot, "agora adicione tipagem")
            await _wait(pilot, lambda: backend.requests and typed in editor.text)
            request = backend.requests[0]
            assert request["mode"] == "edit"
            assert request["selected"] == "def dobro(x):\n    return x * 2"
            assert request["before"].endswith("return a + b\n\n\n")
            assert editor.text == "def somar(a, b):\n    return a + b\n\n\n" + typed + "\n"
            editor.action_undo()
            assert editor.text == code
    asyncio.run(scenario())


def test_studio_continua_no_resultado_recem_inserido(tmp_path, monkeypatch):
    """Gera uma função e, em seguida, "agora adicione tipagem" altera essa mesma função."""
    code = "def somar(a, b):\n    return a + b\n\n"
    generated = "def dobro(x):\n    return x * 2"
    typed = "def dobro(x: int) -> int:\n    return x * 2"
    backend = Backend(lambda kw: typed if kw["mode"] == "edit" else generated)
    app, file = _studio(tmp_path, monkeypatch, code, backend)

    async def scenario():
        async with app.run_test(size=(150, 42)) as pilot:
            await app.open_file(file)
            editor = app.current_editor()
            editor.move_cursor((3, 0))
            await _submit(app, pilot, "uma função que retorna o dobro")
            await _wait(pilot, lambda: generated in editor.text)
            # Na linha vazia logo abaixo de somar, o resultado recém-inserido tem prioridade sobre a função de cima.
            editor.move_cursor((2, 0))
            await _submit(app, pilot, "agora adicione tipagem")
            await _wait(pilot, lambda: typed in editor.text)
            assert backend.requests[1]["mode"] == "edit" and backend.requests[1]["selected"] == generated
            assert editor.text.count("def somar(a, b):") == 1 and editor.text.count("def dobro") == 1
    asyncio.run(scenario())


def test_studio_ambiguo_nao_altera_nem_envia(tmp_path, monkeypatch):
    code = "import os\n\ndef somar(a, b):\n    return a + b\n\n\ndef dobro(x):\n    return x * 2\n"
    backend = Backend()
    app, file = _studio(tmp_path, monkeypatch, code, backend)

    async def scenario():
        from textual.widgets import Input

        async with app.run_test(size=(150, 42)) as pilot:
            await app.open_file(file)
            editor = app.current_editor()
            editor.move_cursor((0, 0))
            await _submit(app, pilot, "agora adicione tipagem")
            await pilot.pause(0.3)
            assert backend.requests == [] and editor.text == code
            assert "selecione a implementação" in str(app.query_one("#output-status").content)
            assert app.query_one("#intent", Input).value == "agora adicione tipagem"  # pronto para reenviar
    asyncio.run(scenario())


def test_linha_do_editor_abaixo_da_funcao_sai_junto_com_a_edicao(tmp_path, monkeypatch):
    code = "def somar(a, b):\n    return a + b\n# agora adicione tipagem\n"
    typed = "def somar(a: int, b: int) -> int:\n    return a + b"
    backend = Backend(lambda kw: typed)
    app, file = _studio(tmp_path, monkeypatch, code, backend)

    async def scenario():
        async with app.run_test(size=(150, 42)) as pilot:
            await app.open_file(file)
            editor = app.current_editor()
            editor.focus()
            editor.move_cursor((2, 5))
            await _wait(pilot, lambda: app.focused is editor)  # com a barra em foco, o atalho envia a barra
            await app.action_translate_line()
            await _wait(pilot, lambda: typed in editor.text)
            assert backend.requests[0]["selected"] == "def somar(a, b):\n    return a + b\n# agora adicione tipagem"
            assert editor.text == typed + "\n"
    asyncio.run(scenario())
