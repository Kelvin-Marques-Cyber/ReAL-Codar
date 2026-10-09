"""Modo estudo: conceitos da linha e dos comentários, exemplos em várias linguagens, trilha de POO com o próximo
passo e o main.py sugerido (que precisa rodar de verdade)."""

import asyncio
import subprocess
import sys
from pathlib import Path

import pytest

from codar import estudo


@pytest.mark.parametrize("linha, lang, esperado", [
    ("class Poupanca(Conta):", "python", "heranca"),
    ("class Conta:", "python", "classe"),
    ("    def __init__(self, titular, saldo=0):", "python", "construtor"),
    ("        self.saldo = saldo", "python", "atributo"),
    ("        self._saldo = saldo", "python", "encapsulamento"),
    ("    def depositar(self, valor):", "python", "metodo"),
    ("    def __str__(self):", "python", "str"),
    ("        super().__init__(titular)", "python", "super"),
    ("conta = Conta('Ana', 100)", "python", "objeto"),
    ("nome = input('Nome: ')", "python", "input"),
    ("for nome in nomes:", "python", "for"),
    ("print(f'Olá, {nome}')", "python", "fstring"),
    ("if __name__ == '__main__':", "python", "main"),
    ("# quero uma lista de compras", "python", "lista"),
    ("// laço para cada aluno", "javascript", "for"),
    ("class Gato extends Animal {", "javascript", "heranca"),
    ("const total = precos.reduce((s, p) => s + p, 0);", "javascript", "array_metodos"),
    ("  const [n, setN] = useState(0);", "typescript", "componente"),
    ("interface Produto {", "typescript", "tipos_ts"),
    ("for _, n := range nums {", "go", "for"),
])
def test_conceito_da_linha(linha, lang, esperado):
    achados = estudo.conceitos_da_linha(linha, lang)
    assert achados and achados[0].id == esperado, [c.id for c in achados]


def test_comentario_nao_confunde_palavras_dentro_de_outras():
    assert "if" not in [c.id for c in estudo.conceitos_da_linha("# uma classe com herança", "python")]


@pytest.mark.parametrize("lang", ["python", "javascript", "typescript", "java", "go", "rust", "c", "csharp", "bash",
                                  "lua", "ruby", "php"])
def test_todo_conceito_tem_exemplo_em_toda_linguagem(lang):
    for c in estudo.CONCEITOS:
        codigo, _lang_ex = estudo.exemplo(c, lang)
        assert codigo.strip() and "TODO" not in codigo, (c.id, lang)


def test_exemplo_compilado_para_a_linguagem_do_arquivo():
    codigo, lang = estudo.exemplo(estudo.POR_ID["for"], "go")
    assert lang == "go" and "range nomes" in codigo


CONTA = "class Conta:\n    def __init__(self, titular, saldo=0):\n        self.titular = titular\n        self.saldo = saldo\n"


def test_trilha_poo_avanca_e_o_proximo_passo_usa_os_nomes_do_codigo():
    e = estudo.trilha_poo("class Conta:\n    pass\n", "python")
    assert e.proximo == "construtor" and "Conta" in e.passo("python")
    e = estudo.trilha_poo(CONTA, "python")
    assert [k for k in estudo.TRILHA_POO if e.feitos[k]] == ["classe", "construtor", "atributo"]
    assert e.proximo == "metodo" and "self.titular" in e.passo("python")
    completo = CONTA + ("    def depositar(self, v):\n        self.saldo += v\n    def __str__(self):\n        return 'c'\n"
                        "class Poupanca(Conta):\n    def __init__(self, t):\n        super().__init__(t)\n"
                        "        self._taxa = 1\n        self.historico = Historico()\n"
                        "    def depositar(self, v):\n        pass\nc = Conta('Ana')\n")
    assert estudo.trilha_poo(completo, "python").proximo is None
    assert estudo.trilha_poo("class Conta:\n    def x(self:\n", "python") is None  # no meio da digitação


def test_trilha_poo_em_javascript():
    e = estudo.trilha_poo("export class Conta {\n  constructor(titular) {\n    this.titular = titular;\n  }\n}\n",
                          "javascript")
    assert e.feitos["construtor"] and e.feitos["atributo"] and e.proximo == "metodo"
    assert "this.titular" in e.passo("javascript")


def test_main_py_sugerido_roda_com_a_classe_do_projeto(tmp_path):
    (tmp_path / "conta.py").write_text(CONTA + "    def depositar(self, v=10):\n        self.saldo += v\n",
                                       encoding="utf-8")
    s = estudo.sugestao_main(tmp_path, tmp_path / "conta.py", (tmp_path / "conta.py").read_text(), "python")
    assert s is not None and s.caminho == "main.py"
    (tmp_path / s.caminho).write_text(s.conteudo, encoding="utf-8")
    r = subprocess.run([sys.executable, "main.py"], cwd=tmp_path, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    # com o main.py usando a classe, a sugestão some
    assert estudo.sugestao_main(tmp_path, tmp_path / "conta.py", (tmp_path / "conta.py").read_text(), "python") is None


def test_exemplo_pelo_comentario_usa_os_nomes_escritos():
    codigo, lang = estudo.pelo_comentario("# classe Pessoa com nome e idade", "python")
    assert lang == "python" and "self.idade = idade" in codigo and "class Pessoa" in codigo
    codigo, lang = estudo.pelo_comentario("// classe Produto com nome, preco e estoque", "javascript")
    assert "this.estoque = estoque" in codigo


def _texto(renderizavel) -> str:
    import io

    from rich.console import Console

    console = Console(width=140, file=io.StringIO(), color_system=None)
    console.print(renderizavel)
    return console.file.getvalue()


def test_painel_estudo_no_studio(tmp_path, monkeypatch):
    pytest.importorskip("textual")
    from textual.widgets import Static

    from codar.studio.app import Studio

    monkeypatch.setenv("CODAR_HOME", str(tmp_path / "home"))
    monkeypatch.setenv("CODAR_NO_AUTOSTART", "1")
    (tmp_path / "conta.py").write_text(CONTA, encoding="utf-8")

    async def cenario():
        app = Studio(tmp_path)
        async with app.run_test(size=(150, 42)) as pilot:
            await app.open_file(tmp_path / "conta.py")
            app.current_editor().move_cursor((0, 3))
            await pilot.press("f7")
            await pilot.pause(0.5)
            texto = _texto(app.query_one("#estudo-corpo", Static).content)
            assert "CLASSE" in texto and "TRILHA POO" in texto and "próximo passo" in texto
            assert app.sugestao_estudo is not None
            await pilot.press("shift+f7")
            await pilot.pause(0.5)
            assert (tmp_path / "main.py").is_file()
            assert Path(app.current_editor().path).name == "main.py"
            await pilot.press("f7")
            assert not app.estudo

    asyncio.run(cenario())
