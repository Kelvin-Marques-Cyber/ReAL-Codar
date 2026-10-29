"""POO sem IA: herança, métodos, objetos e chamadas usam as classes reais e o código gerado roda de verdade."""

import shutil
import subprocess
import sys
import textwrap

import pytest

from codar.client import RpcError
from codar.engine.local import LocalClient


@pytest.fixture()
def projeto(tmp_path, monkeypatch):
    monkeypatch.setenv("CODAR_HOME", str(tmp_path / "home"))
    raiz = tmp_path / "projeto"
    raiz.mkdir()
    (raiz / "pyproject.toml").write_text("[project]\nname = 'x'\n")
    (raiz / "pessoa.py").write_text(textwrap.dedent("""\
        from dataclasses import dataclass


        @dataclass
        class Pessoa:
            nome: str
            idade: int

            def apresentar(self):
                return f"Olá, {self.nome}"
        """))
    with LocalClient(with_model=False, db=str(tmp_path / "p.db")) as client:
        def gerar(intent, lang="python", arquivo="main.py", antes="", recuo=""):
            return client.translate(intent, lang, file=str(raiz / arquivo), before=antes, indent=recuo,
                                    project_root=str(raiz), stages=(0, 1))
        yield raiz, gerar


def _rodar_python(raiz, programa):
    (raiz / "main.py").write_text(programa, encoding="utf-8")
    saida = subprocess.run([sys.executable, "main.py"], cwd=raiz, capture_output=True, text=True, timeout=30)
    assert saida.returncode == 0, saida.stderr + "\n---\n" + programa
    return saida.stdout.strip()


def test_heranca_de_dataclass_do_projeto_importa_e_roda(projeto):
    raiz, gerar = projeto
    r = gerar("classe Aluno herda de Pessoa com matricula")
    assert r["source"] == "stage0:poo-classe" and "from pessoa import Pessoa" in r["code"]
    saida = _rodar_python(raiz, r["code"] + "\n\na = Aluno(nome='Ana', idade=20, matricula='M1')\n"
                                           "print(a.matricula, a.apresentar(), isinstance(a, Pessoa))\n")
    assert saida == "M1 Olá, Ana True"


@pytest.mark.parametrize("mae,uso,esperado", [
    ("class Pessoa:\n    def __init__(self, nome, idade):\n        self.nome = nome\n        self.idade = idade\n",
     "a = Aluno('Ana', 20, 'M1')\nprint(a.nome, a.idade, a.matricula)", "Ana 20 M1"),
    ("class Pessoa:\n    def __init__(self, nome, ativo=True):\n        self.nome = nome\n        self.ativo = ativo\n",
     "a = Aluno('Ana', matricula='M1')\nb = Aluno('Bia', matricula='M2', ativo=False)\nprint(a.ativo, b.ativo, b.matricula)",
     "True False M2"),
])
def test_heranca_de_classe_comum_repassa_os_parametros_reais(projeto, mae, uso, esperado):
    raiz, gerar = projeto
    r = gerar("classe Aluno herda de Pessoa com matricula", antes=mae)
    assert "super().__init__(" in r["code"]
    assert _rodar_python(raiz, mae + "\n\n" + r["code"] + "\n\n" + uso + "\n") == esperado


def test_heranca_de_classe_desconhecida_nao_inventa_parametros(projeto):
    raiz, gerar = projeto
    r = gerar("class Aluno extends Externa with matricula")
    assert any("não foi encontrada" in nota for nota in r["notes"]) and "*args" in r["code"]
    externa = "class Externa:\n    def __init__(self, a, b=2):\n        self.a, self.b = a, b\n"
    assert _rodar_python(raiz, externa + "\n\n" + r["code"] + "\n\nx = Aluno(1, matricula='M')\nprint(x.a, x.b, x.matricula)\n") \
        == "1 2 M"


def test_classe_com_metodos_declara_metodos_sem_inventar_corpo(projeto):
    raiz, gerar = projeto
    r = gerar("classe Conta com saldo e métodos depositar(valor) e sacar(valor)")
    programa = r["code"] + "\n\nc = Conta(saldo=10)\ntry:\n    c.depositar(5)\nexcept NotImplementedError as e:\n    print(e)\n"
    assert _rodar_python(raiz, programa) == "implemente depositar"


CONTA = "class Conta:\n    def __init__(self, saldo=0):\n        self.saldo = saldo\n\n"


@pytest.mark.parametrize("pedido,uso,esperado", [
    ("método depositar com valor que soma valor ao saldo", "c.depositar(5)\nprint(c.saldo)", "15"),
    ("método sacar com valor que subtrai valor do saldo", "c.sacar(4)\nprint(c.saldo)", "6"),
    ("método zerar que define saldo para 0", "c.zerar()\nprint(c.saldo)", "0"),
    ("método mostrar que imprime o saldo", "c.mostrar()", "10"),
    ("método consultar que retorna o saldo", "print(c.consultar())", "10"),
])
def test_metodo_com_corpo_usa_os_atributos_da_classe(projeto, pedido, uso, esperado):
    raiz, gerar = projeto
    r = gerar(pedido, antes=CONTA + "    ", recuo="    ")
    assert r["source"] == "stage0:poo-metodo" and "self.saldo" in r["code"]
    assert _rodar_python(raiz, CONTA + r["code"] + "\n\nc = Conta(10)\n" + uso + "\n") == esperado


def test_metodo_fora_da_classe_explica(projeto):
    _, gerar = projeto
    with pytest.raises(RpcError, match="dentro de uma classe"):
        gerar("método depositar com valor que soma valor ao saldo")


def test_objeto_confere_o_construtor_real(projeto):
    raiz, gerar = projeto
    r = gerar("objeto ana da classe Pessoa com nome 'Ana' e idade 20")
    assert 'ana = Pessoa(nome="Ana", idade=20)' in r["code"] and "from pessoa import Pessoa" in r["code"]
    assert _rodar_python(raiz, r["code"] + "\nprint(ana.apresentar())\n") == "Olá, Ana"
    with pytest.raises(RpcError, match="faltam argumentos obrigatórios para Pessoa: idade"):
        gerar("objeto ana da classe Pessoa com nome 'Ana'")
    with pytest.raises(RpcError, match="não tem o\\(s\\) parâmetro\\(s\\) altura"):
        gerar("objeto ana da classe Pessoa com nome 'Ana', idade 20 e altura 1.7")


def test_chamada_confere_os_metodos_da_classe_do_objeto(projeto):
    raiz, gerar = projeto
    antes = "from pessoa import Pessoa\nana = Pessoa(nome='Ana', idade=20)\n"
    r = gerar("chame apresentar de ana e guarde em mensagem", antes=antes)
    assert r["code"] == "mensagem = ana.apresentar()"
    assert _rodar_python(raiz, antes + r["code"] + "\nprint(mensagem)\n") == "Olá, Ana"
    with pytest.raises(RpcError, match="Pessoa não tem o método voar; métodos disponíveis: apresentar"):
        gerar("chame voar de ana", antes=antes)


@pytest.fixture()
def projeto_js(projeto):
    raiz, gerar = projeto
    web = raiz / "web"
    web.mkdir()
    (web / "package.json").write_text('{"type": "module"}')
    (web / "pessoa.js").write_text("export class Pessoa {\n  constructor(nome, idade) {\n    this.nome = nome;\n"
                                   "    this.idade = idade;\n  }\n\n  apresentar() {\n    return `Olá, ${this.nome}`;\n  }\n}\n")
    return raiz, gerar


def _rodar_node(pasta, programa, nome="main.js"):
    if not shutil.which("node"):
        pytest.skip("Node.js ausente")
    (pasta / nome).write_text(programa, encoding="utf-8")
    saida = subprocess.run(["node", nome], cwd=pasta, capture_output=True, text=True, timeout=30)
    assert saida.returncode == 0, saida.stderr + "\n---\n" + programa
    return saida.stdout.strip()


def test_js_heranca_importa_a_mae_e_chama_super_com_os_parametros_dela(projeto_js):
    raiz, gerar = projeto_js
    r = gerar("classe Aluno herda de Pessoa com matricula", "javascript", "web/main.js")
    assert 'import { Pessoa } from "./pessoa.js";' in r["code"] and "super(nome, idade);" in r["code"]
    uso = "\nconst a = new Aluno('Ana', 20, 'M1');\nconsole.log(a.matricula, a.apresentar());\n"
    assert _rodar_node(raiz / "web", r["code"] + uso) == "M1 Olá, Ana"


def test_js_objeto_ordena_argumentos_pelo_construtor(projeto_js):
    raiz, gerar = projeto_js
    r = gerar("objeto ana da classe Pessoa com idade 20 e nome 'Ana'", "javascript", "web/main.js")
    assert 'new Pessoa("Ana", 20)' in r["code"]
    assert _rodar_node(raiz / "web", r["code"] + "\nconsole.log(ana.apresentar(), ana.idade);\n") == "Olá, Ana 20"


def test_js_metodo_com_corpo(projeto_js):
    raiz, gerar = projeto_js
    conta = "class Conta {\n  constructor(saldo) {\n    this.saldo = saldo;\n  }\n\n"
    r = gerar("método depositar com valor que soma valor ao saldo", "javascript", "web/main.js", antes=conta + "  ", recuo="  ")
    programa = conta + r["code"] + "\n}\nconst c = new Conta(10);\nc.depositar(5);\nconsole.log(c.saldo);\n"
    assert _rodar_node(raiz / "web", programa) == "15"


def test_ts_heranca_de_classe_desconhecida_usa_constructor_parameters(projeto):
    _, gerar = projeto
    r = gerar("classe Aluno herda de Base com matricula", "typescript", "main.ts")
    assert "...args: ConstructorParameters<typeof Base>" in r["code"] and "matricula: string;" in r["code"]


@pytest.mark.parametrize("pedido", ["clase Alumno hereda de Pessoa con matricula", "class Aluno extends Pessoa with matricula"])
def test_heranca_em_outros_idiomas(projeto, pedido):
    _, gerar = projeto
    r = gerar(pedido)
    assert r["source"] == "stage0:poo-classe" and "(Pessoa):" in r["code"]


def test_classe_simples_continua_no_compilador_comum(projeto):
    _, gerar = projeto
    assert gerar("classe Produto com nome e preco")["source"] == "stage0:class"
