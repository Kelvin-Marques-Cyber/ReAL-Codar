"""Explicação de erros: tracebacks reais do Python e saídas típicas de Node/Bun, shell, Go, Rust, Java e C."""

import subprocess
import sys
from pathlib import Path

import pytest

from codar.explicar import explicar


def _rodar(tmp_path: Path, codigo: str, entrada: str = "") -> str:
    arquivo = tmp_path / "app.py"
    arquivo.write_text(codigo, encoding="utf-8")
    r = subprocess.run([sys.executable, str(arquivo)], input=entrada, capture_output=True, text=True, cwd=tmp_path)
    return r.stdout + r.stderr


@pytest.mark.parametrize("codigo, tipo, linha, trecho_titulo, conceito", [
    ("idade = 20\nprint(idadde)\n", "NameError", 2, "idadde", "variavel"),
    ("nome = 'Ana'\nprint('Idade: ' + 30)\n", "TypeError", 2, "texto com número", "fstring"),
    ("x = '5'\nprint(1 + x)\n", "TypeError", 2, "operação +", "conversao"),
    ("x = input()\n", "EOFError", 1, "entrada", "input"),
    ("print(10 / 0)\n", "ZeroDivisionError", 1, "divisão por zero", "if"),
    ("v = [1, 2, 3]\nprint(v[3])\n", "IndexError", 2, "posição", "lista"),
    ("d = {'a': 1}\nprint(d['b'])\n", "KeyError", 2, "'b'", "dicionario"),
    ("def f():\n    pass\nf().upper()\n", "AttributeError", 3, "None não tem .upper", "funcao"),
    ("import cv2\n", "ModuleNotFoundError", 1, "cv2", "import"),
    ("if True:\nprint('x')\n", "IndentationError", 2, "indentar", "indentacao"),
    ("if 1 > 0\n    print('x')\n", "SyntaxError", 1, "dois-pontos", "if"),
    ("n = int('abc')\n", "ValueError", 1, "'abc'", "excecao"),
    ("open('dados.csv')\n", "FileNotFoundError", 1, "dados.csv", "arquivo"),
    ("class Conta:\n    def __init__(self, saldo):\n        self.saldo = saldo\nc = Conta()\n", "TypeError", 4,
     "criar o objeto", "construtor"),
    ("class Conta:\n    def depositar(valor):\n        pass\nConta().depositar(10)\n", "TypeError", 4, "self",
     "metodo"),
    ("class Conta:\n    def __init__(self):\n        pass\nprint(Conta().saldo)\n", "AttributeError", 4,
     "não tem saldo", "atributo"),
])
def test_erros_do_python(tmp_path, codigo, tipo, linha, trecho_titulo, conceito):
    exp = explicar(_rodar(tmp_path, codigo), tmp_path)
    assert exp is not None
    assert exp.tipo == tipo
    assert exp.linha == linha and Path(exp.arquivo).name == "app.py"
    assert trecho_titulo in exp.titulo + exp.oque + exp.como
    assert exp.conceito == conceito
    assert exp.oque and exp.como


def test_sugere_o_nome_parecido_e_o_pacote_certo(tmp_path):
    exp = explicar(_rodar(tmp_path, "idade = 20\nprint(idadde)\n"), tmp_path)
    assert "Você quis dizer idade?" in exp.oque
    exp = explicar(_rodar(tmp_path, "import cv2\n"), tmp_path)
    assert "opencv-python-headless" in exp.como
    exp = explicar(_rodar(tmp_path, "from sklearn import tree\n"), tmp_path)
    assert "scikit-learn" in exp.como


def test_erro_dentro_de_biblioteca_aponta_para_o_codigo_do_projeto(tmp_path):
    saida = _rodar(tmp_path, "import json\njson.loads('{x}')\n")
    exp = explicar(saida, tmp_path)
    assert exp.tipo == "JSONDecodeError" and exp.linha == 2 and Path(exp.arquivo).name == "app.py"


def test_saida_sem_erro_nao_explica_nada(tmp_path):
    assert explicar(_rodar(tmp_path, "print('ok')\n"), tmp_path) is None
    assert explicar("tudo certo\n[exit 0]") is None


AMOSTRAS = [
    ("/p/app.js:3\nconsole.log(nome)\n            ^\n\nReferenceError: nome is not defined\n"
     "    at Object.<anonymous> (/p/app.js:3:13)\n    at Module._compile (node:internal/modules/cjs/loader:1554:14)\n",
     "ReferenceError", "nome não existe", 3),
    ("TypeError: Cannot read properties of undefined (reading 'map')\n    at render (/p/src/lista.js:8:20)\n",
     "TypeError", "leu .map de undefined", 8),
    ("error: Cannot find package \"react\" from \"/p/app.tsx\"\n", "módulo", "react não está instalado", None),
    ("error: Script not found \"dev\"\n", "bun", "script dev não existe", None),
    ("Error: listen EADDRINUSE: address already in use :::5173\n", "EADDRINUSE", "porta 5173", None),
    ("bash: bun: command not found\n", "comando não encontrado", "bun não existe", None),
    ("sh: 1: pnpm: not found\n", "comando não encontrado", "pnpm não existe", None),
    ("./main.go:5:2: undefined: total\n", "Go", "total não foi declarado", 5),
    ("error[E0425]: cannot find value `x` in this scope\n --> src/main.rs:3:20\n", "Rust", "x não foi declarado", 3),
    ("Main.java:4: error: ';' expected\n", "Java", "ponto e vírgula", 4),
    ('Exception in thread "main" java.lang.NullPointerException: Cannot invoke "String.length()"\n'
     "\tat Main.main(Main.java:5)\n", "NullPointerException", "null", 5),
    ("a.c:4:5: error: implicit declaration of function 'printf'\n", "C/C++", "printf sem #include", 4),
    ("index.ts(2,13): error TS2304: Cannot find name 'usuario'.\n", "TypeScript", "usuario não foi declarado", 2),
    ("src/app.tsx:7:3 - error TS2304: Cannot find name 'estado'.\n", "TypeScript", "estado não foi declarado", 7),
    ("Error: object 'idadee' not found\nExecution halted\n", "R", "idadee não existe", None),
    ("ERROR: LoadError: UndefVarError: `contador` not defined in local scope\n in expression starting at "
     "/w/app.jl:8\n", "Julia", "contador não existe", 8),
    ("app.kt:3:13: error: unresolved reference 'nomee'.\n", "Kotlin", "nomee não existe", 3),
]


@pytest.mark.parametrize("saida, tipo, titulo, linha", AMOSTRAS)
def test_outras_linguagens(saida, tipo, titulo, linha):
    exp = explicar(saida)
    assert exp is not None, saida
    assert exp.tipo == tipo
    assert titulo in exp.titulo
    assert exp.linha == linha
