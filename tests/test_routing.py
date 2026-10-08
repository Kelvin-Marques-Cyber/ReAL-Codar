"""Regras de roteamento: pseudocódigo -> compilador/IA literal; pedidos de funcionalidade -> banco de padrões.

Cada caso aqui veio de um teste real do usuário que falhou.
"""

import pytest

from codar.engine.router import is_pseudocode, refers_to_context


@pytest.mark.parametrize("intent,lang,expected", [
    ("x é igual a 10", "python", "x = 10"),
    ("x igual a 10", "go", "x := 10"),
    ("x vale 10", "javascript", "const x = 10;"),
    ("total += preco", "python", "total += preco"),
    ("total += preco", "powershell", "$total += $preco"),
    ("contador passa a ser contador * 2 + 1", "go", "contador = contador * 2 + 1"),
    ("x é igual a x menos 1", "lua", "x = x - 1"),
    ("nome é Ana", "python", 'nome = "Ana"'),
    ("salvar(dados)", "python", "salvar(dados)"),
])
def test_pseudocodigo_vai_para_o_compilador(translate, intent, lang, expected):
    res = translate(intent, lang)
    assert res.stage == "0", res.source
    assert res.body == expected


def test_frase_sobre_o_contexto_vai_para_ia_literal(translate, router):
    router.stage2.answer = "print(x + y)\n"
    res = translate("some os dois números e imprima", before="x = 10\ny = 20\n")
    assert res.stage == "2:pseudo"
    assert res.body == "print(x + y)"
    prompt = router.stage2.prompts[-1]
    assert "x = 10" in prompt and "do not repeat" in prompt.lower()
    assert "Reference pattern" not in prompt  # sem RAG: nada de copiar padrões no modo literal


def test_padrao_parcial_nao_sequestra_pseudocodigo(translate):
    # "some os dois números" já casou por engano com util.digits ("somar dígitos")
    res = translate("some os dois números e imprima", before="x = 10\ny = 20\n")
    assert "soma_digitos" not in res.code


def test_ia_literal_corta_o_que_vem_depois_do_primeiro_bloco(translate, router):
    router.stage2.answer = "x *= 2\n\nprint(x)\n\ndef extra():\n    pass\n"
    assert translate("dobrar o valor de x").body == "x *= 2"


def test_imports_nao_usados_sao_podados(translate, router):
    router.stage2.answer = "from typing import *\nimport os\nresultado = len(itens)\n"
    res = translate("contar quantos itens existem")
    assert res.imports == [] and "import" not in res.code


def test_imprimir_referencia_nao_vira_texto(translate, router):
    router.stage2.answer = "print(resultado)\n"
    res = translate("imprima o resultado", before="resultado = x + y\n")
    assert res.body == "print(resultado)"


@pytest.mark.parametrize("intent,lang,answer,expected", [
    ("inverter a lista itens", "javascript", "const itens = [1, 2, 3, 4];\nitens.reverse();\n", "itens.reverse();"),
    ("converter preco para inteiro", "rust", "let preco = 12.34;\nlet preco_inteiro: i32 = preco as i32;\n",
     "let preco_inteiro: i32 = preco as i32;"),
    ("dividir o texto por vírgula", "powershell", '$texto = "a,b,c"\n$partes = $texto -split ","\n',
     '$partes = $texto -split ","'),
    ("ordenar itens", "go", "itens := []int{3, 1, 2}\nsort.Ints(itens)\n", "sort.Ints(itens)"),
])
def test_ia_literal_nao_inventa_dados_de_exemplo(translate, router, intent, lang, answer, expected):
    router.stage2.answer = answer
    assert translate(intent, lang).body == expected


@pytest.mark.parametrize("intent,answer", [
    ("ler o nome e imprimir", "nome = input()\nprint(nome)\n"),            # chamada, não é dado de exemplo
    ("zerar o contador e somar 1", "contador = 0\ncontador += 1\n"),      # a frase pede a atribuição
    ("juntar a e b em itens", "itens = [a, b]\nprint(itens)\n"),         # lista calculada, não constante
])
def test_ia_literal_preserva_atribuicoes_legitimas(translate, router, intent, answer):
    router.stage2.answer = answer
    assert translate(intent).body == answer.strip()


@pytest.mark.parametrize("intent,pattern", [
    ("criar uma calculadora", "app.calculator"),
    ("algoritmo de dijkstra", "algo.dijkstra"),
    ("validar cnpj", "br.cnpj"),
    ("remover duplicados", "util.dedupe"),
])
def test_pedido_de_funcionalidade_usa_o_banco(translate, intent, pattern):
    res = translate(intent)
    assert res.stage == "1" and res.source == f"pattern:{pattern}"


def test_classificadores():
    assert is_pseudocode("trocar os valores de a e b")
    assert not is_pseudocode("criar uma calculadora")
    assert not is_pseudocode("conectar ao redis em localhost")
    assert refers_to_context("calcule a média dos dois", {"x", "y"})
    assert refers_to_context("imprima x", {"x"})
    assert not refers_to_context("imprima x", set())


@pytest.mark.parametrize("intent,pattern,path", [
    ("frequência de palavras do arquivo livro.txt", "algo.word_frequency", "livro.txt"),
    ("remover linhas duplicadas do arquivo nomes.txt", "util.dedupe", "nomes.txt"),
    ("formatar json do arquivo config.json", "util.json_pretty", "config.json"),
])
def test_nome_de_arquivo_nao_derruba_o_padrao(translate, intent, pattern, path):
    # antes, "livro.txt" e "arquivo" contavam contra a cobertura e o pedido ia para a IA,
    # que gerou `sort -u nomes.txt > nomes.txt` (apaga o arquivo)
    res = translate(intent, "bash")
    assert res.stage == "1" and res.source == f"pattern:{pattern}"
    assert res.slots.get("path") == path and path in res.code


# Mesma tabela usada nos testes do VS Code (clients/vscode/test) e do Neovim: as quatro implementações batem.
INTENT_LINES = ["x é igual a 10", "x é igual a y mais 1", "total += preco", "imprimir o tamanho de pedidos",
                "some os dois números e imprima", "se total maior que 100 imprimir 'caro'",
                "# calcular a média das notas", "x vale 10", "print total", "imprimir total"]
CODE_LINES = ["for i in range(10):", "return x + y", "import os", "console.log(x)", "if x > 10", "pass", "x = 1",
              "}", "elif x == 2:", "foo(bar, baz)", "let x = [1, 2]", "é", "i += 1"]


@pytest.mark.parametrize("line", INTENT_LINES)
def test_espaco_enter_dispara_em_frases(line):
    from codar.textutil import looks_like_intent
    assert looks_like_intent(line)


@pytest.mark.parametrize("line", CODE_LINES)
def test_espaco_enter_nao_dispara_em_codigo(line):
    from codar.textutil import looks_like_intent
    assert not looks_like_intent(line)


def test_linha_indentada_nao_gera_falso_erro_de_sintaxe(router):
    import asyncio

    from codar.engine.router import Request

    def run(intent):
        req = Request(intent=intent, lang="python", lang_explicit=True, indent="    ")
        return asyncio.run(router.translate(req))

    assert run("total é igual a 0").findings == []          # antes: PY000 "unexpected indent"
    found = run('senha é igual a "admin123"').findings
    assert [(f["id"], f["col"]) for f in found] == [("PY017", 5)]
