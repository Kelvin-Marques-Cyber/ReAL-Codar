"""O código gerado usa funções e classes de outros arquivos do projeto com o import certo, sem adivinhar."""

import pytest

from codar.engine.vinculos import imports_do_projeto


@pytest.fixture()
def projeto(tmp_path):
    (tmp_path / "pyproject.toml").write_text("[project]\nname = 'x'\n")
    (tmp_path / "calculos.py").write_text("def somar(a, b):\n    return a + b\n\n\nclass Conta:\n    pass\n")
    (tmp_path / "util").mkdir()
    (tmp_path / "util" / "__init__.py").write_text("")
    (tmp_path / "util" / "texto.py").write_text("def saudar(nome):\n    return nome\n")
    (tmp_path / "util" / "datas.py").write_text("")
    (tmp_path / "a.py").write_text("def repetida():\n    pass\n")
    (tmp_path / "b.py").write_text("def repetida():\n    pass\n")
    return tmp_path


def test_python_importa_funcao_classe_e_pacote(projeto):
    codigo = "total = somar(2, 3)\nconta = Conta()\nprint(saudar('Ana'), len([1]))\n"
    imports, notas = imports_do_projeto(codigo, "python", projeto, str(projeto / "main.py"), "")
    assert imports == ["from calculos import somar, Conta", "from util.texto import saudar"]
    assert "importado do projeto" in notas[-1]


def test_python_relativo_dentro_do_pacote(projeto):
    imports, _ = imports_do_projeto("x = saudar('a')\n", "python", projeto, str(projeto / "util" / "datas.py"), "")
    assert imports == ["from .texto import saudar"]


def test_python_nao_importa_o_que_o_arquivo_ja_conhece(projeto):
    for contexto in ("from calculos import somar\n", "def f(somar):\n    pass\n", "def somar(x):\n    return x\n"):
        assert imports_do_projeto("total = somar(1, 2)\n", "python", projeto, str(projeto / "main.py"), contexto) == ([], [])
    # Definido no próprio código gerado também não é importado.
    assert imports_do_projeto("def somar(a, b):\n    return a\nprint(somar(1, 2))\n", "python", projeto,
                              str(projeto / "main.py"), "")[0] == []


def test_python_ambiguo_vira_nota_sem_import(projeto):
    imports, notas = imports_do_projeto("repetida()\n", "python", projeto, str(projeto / "main.py"), "")
    assert imports == [] and "repetida existe em a.py, b.py" in notas[0]


def test_python_layout_src(tmp_path):
    (tmp_path / "pyproject.toml").write_text("[project]\nname = 'x'\n")
    (tmp_path / "src" / "app").mkdir(parents=True)
    (tmp_path / "src" / "app" / "__init__.py").write_text("")
    (tmp_path / "src" / "app" / "servicos.py").write_text("def cadastrar():\n    pass\n")
    imports, _ = imports_do_projeto("cadastrar()\n", "python", tmp_path, str(tmp_path / "main.py"), "")
    assert imports == ["from app.servicos import cadastrar"]


@pytest.fixture()
def web(tmp_path):
    (tmp_path / "package.json").write_text('{"name": "x", "type": "module"}')
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "api.js").write_text("export function buscar(u) { return u; }\nfunction interna() {}\n"
                                              "export default class Cliente {}\n")
    (tmp_path / "src" / "cjs.js").write_text("function antigo() {}\nmodule.exports = { antigo };\n")
    (tmp_path / "src" / "tipos.ts").write_text("export const formatar = (x: number) => String(x);\n")
    return tmp_path


def test_js_esm_segue_a_convencao_do_arquivo(web):
    atual = str(web / "src" / "main.js")
    imports, _ = imports_do_projeto("const d = buscar('/x');\nconst c = new Cliente();\n", "javascript", web, atual, "")
    assert imports == ['import Cliente from "./api.js";', 'import { buscar } from "./api.js";']
    sem_extensao = "import { y } from './y';\n"
    assert imports_do_projeto("buscar(1);\n", "javascript", web, atual, sem_extensao)[0] == ['import { buscar } from "./api";']


def test_js_commonjs_usa_require(web):
    contexto = "const fs = require('fs');\n"
    imports, _ = imports_do_projeto("antigo();\nbuscar(1);\n", "javascript", web, str(web / "src" / "main.js"), contexto)
    assert imports == ['const { antigo } = require("./cjs.js");', 'const { buscar } = require("./api.js");']


def test_ts_sem_extensao_e_nao_exportado_vira_nota(web):
    imports, notas = imports_do_projeto("const t = formatar(2);\ninterna();\n", "typescript", web,
                                        str(web / "src" / "main.ts"), "")
    assert imports == ['import { formatar } from "./tipos";']
    assert any("interna existe em src/api.js, mas não é exportado" in n for n in notas)


def test_sem_projeto_ou_outra_linguagem_nao_faz_nada(projeto):
    assert imports_do_projeto("somar(1, 2)\n", "python", None, None, "") == ([], [])
    assert imports_do_projeto("somar(1, 2);", "go", projeto, None, "") == ([], [])


def test_roteador_importa_do_projeto_e_revalida_o_cache(projeto, monkeypatch):
    from codar.engine.local import LocalClient

    monkeypatch.setenv("CODAR_HOME", str(projeto / "home"))
    with LocalClient(with_model=False, db=str(projeto / "p.db")) as client:
        def pedir():
            return client.translate("total recebe dobrar(4)", "python", file=str(projeto / "main.py"),
                                    project_root=str(projeto), stages=(0, 1))
        assert pedir()["code"] == "total = dobrar(4)"  # dobrar ainda não existe no projeto
        (projeto / "matematica.py").write_text("def dobrar(x):\n    return 2 * x\n")
        resultado = pedir()  # mesmo pedido: o cache não pode esconder a função nova
        assert resultado["code"] == "from matematica import dobrar\n\ntotal = dobrar(4)"
