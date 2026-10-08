"""Compilador determinístico (estágio 0): frases em português -> código, sem IA."""

import pytest

from codar.engine.emit import emit
from codar.engine.stage0 import Stage0

KNOWN = {"x", "y", "preco", "pedidos", "nomes", "f"}


def compile_(intent, lang="python"):
    parsed = Stage0().parse(intent, KNOWN)
    return None if parsed is None else emit(parsed.nodes, lang)[1]


@pytest.mark.parametrize("intent,lang,expected", [
    ("imprimir o tamanho de pedidos", "python", "print(len(pedidos))"),
    ("imprimir o tamanho de pedidos", "javascript", "console.log(pedidos.length);"),
    ("quantidade é igual ao tamanho de pedidos", "python", "quantidade = len(pedidos)"),
    ("mostrar o número de itens de nomes", "lua", "print(#nomes)"),
    ("imprima a soma de x e y", "python", "print(x + y)"),
    ("media recebe a média entre x e y", "python", "media = (x + y) / 2"),
    ("imprimir o dobro de preco", "python", "print(preco * 2)"),
    ("metade é igual a metade de x", "go", "metade := x / 2"),
])
def test_valores_em_linguagem_natural(intent, lang, expected):
    assert compile_(intent, lang) == expected


@pytest.mark.parametrize("intent", [
    "imprima o resultado",                         # referência a um valor que o compilador não conhece
    "imprimir a mensagem de boas vindas",          # descreve o texto, não é o texto
    "quantidade é igual ao maior de itens",        # agregação sem tradução determinística em todas as linguagens
])
def test_frase_descritiva_nunca_vira_texto_literal(intent):
    assert compile_(intent) is None


@pytest.mark.parametrize("intent,expected", [
    ("imprimir olá mundo", 'print("olá mundo")'),
    ("imprimir a mensagem: olá mundo", 'print("olá mundo")'),
    ("imprimir o texto 'oi'", 'print("oi")'),
    ("nome é Ana", 'nome = "Ana"'),
])
def test_texto_literal_continua_funcionando(intent, expected):
    assert compile_(intent) == expected


def test_powershell_imprime_expressao_entre_parenteses():
    # em modo argumento, `Write-Output $x + $y` imprimiria três valores: $x, "+" e $y
    assert compile_("imprima a soma de x e y", "powershell") == "Write-Output ($x + $y)"
    assert compile_("x = f(x + 1)", "powershell") == "$x = (f ($x + 1))"


def test_rust_promove_literal_inteiro_em_conta_com_float():
    assert compile_("imprimir o dobro de preco", "rust") == 'println!("{}", preco * 2.0);'
    assert compile_("se preco maior que 100 imprimir 'caro'", "rust").startswith("if preco > 100.0 {")


def test_bloco_reconhece_variavel_do_laco_e_parametros():
    nodes, misses = Stage0().parse_program("para cada nome em nomes\n    imprimir nome\n", set())
    assert misses == 0
    assert emit(nodes, "javascript")[1] == "for (const nome of nomes) {\n  console.log(nome);\n}"
