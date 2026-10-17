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


def test_compilador_reconhece_nome_no_codigo_abaixo(translate):
    result = translate("imprimir resultado", after="resultado = calcular(10)\n", stages=(0,))
    assert result.stage == "0" and result.body == "print(resultado)"


def test_literal_recebe_codigo_abaixo_e_reduz_contexto_opcional(translate, router, monkeypatch):
    below = 'def salvar(dados):\n    return dados\n' + '# contexto longo\n' * 300
    prompts = []
    original = router.stage2.generate

    def generate(builder, **kwargs):
        prompts.extend(builder(level) for level in range(3))
        return original(builder, **kwargs)

    monkeypatch.setattr(router.stage2, "generate", generate)
    router.stage2.answer = "salvar(itens)\n"
    result = translate("salvar todos os itens", after=below)
    assert result.body == "salvar(itens)"
    assert all("def salvar(dados)" in prompt for prompt in prompts)
    assert "before and after the cursor" in prompts[0]
    assert len(prompts[0]) > len(prompts[1]) > len(prompts[2])


def test_padrao_parcial_nao_sequestra_pseudocodigo(translate):
    # "some os dois números" já casou por engano com util.digits ("somar dígitos")
    res = translate("some os dois números e imprima", before="x = 10\ny = 20\n")
    assert "soma_digitos" not in res.code


def test_ia_literal_preserva_toda_a_resposta_sem_corte_por_linha_em_branco(translate, router):
    router.stage2.answer = "x *= 2\n\nprint(x)\n\ndef extra():\n    pass\n"
    assert translate("dobrar o valor de x").body == router.stage2.answer.rstrip('\n')


def test_imports_sao_preservados_mesmo_quando_usados_fora_do_snippet(translate, router):
    router.stage2.answer = "from typing import *\nimport os\nresultado = len(itens)\n"
    res = translate("contar quantos itens existem")
    assert res.imports == ['from typing import *', 'import os']
    assert 'resultado = len(itens)' in res.code


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


@pytest.mark.parametrize("intent,lang,expected", [
    ("senão imprimir 'oi'", "python", 'else:\n    print("oi")'),
    ("senão se x maior que 1 imprimir x", "python", "elif x > 1:\n    print(x)"),
    ("senão imprimir 'oi'", "javascript", 'else {\n  console.log("oi");\n}'),
])
def test_senao_sozinho_continua_o_if_de_cima(translate, intent, lang, expected):
    res = translate(intent, lang)
    assert (res.stage, res.source, res.body) == ("0", "stage0:else", expected)
    assert res.findings == []  # o "else:" isolado não é um erro de sintaxe do usuário


def test_senao_sozinho_em_go_explica_em_vez_de_chamar_a_ia(translate, router):
    from codar.engine.router import TranslateError

    with pytest.raises(TranslateError, match="selecione"):
        translate("senão imprimir 'oi'", "go")
    assert router.stage2.prompts == []  # antes, a IA inventava um if inteiro ("if not pedidos")

def test_frase_nominal_youtube_usa_gerador_e_preserva_import(translate, router, monkeypatch):
    from codar.engine.router import is_pseudocode

    assert not is_pseudocode("uma playlist do youtube, variável")
    monkeypatch.setattr(router.store, "search", lambda *args, **kwargs: [])
    router.stage2.answer = "from yt_dlp import YoutubeDL\n"
    res = translate("uma playlist do youtube, variável")
    assert res.complete
    assert res.code.strip() == "from yt_dlp import YoutubeDL"
    assert res.imports == ["from yt_dlp import YoutubeDL"]


def test_saida_python_invalida_tenta_uma_vez_e_recupera(translate, router, monkeypatch):
    from codar.engine.stage2 import GenResult

    answers = iter(["dt lp\n.Y\noutube\nDL\n()\n", "from yt_dlp import YoutubeDL\n"])
    prompts = []

    def generate(builder, **kwargs):
        prompts.append(builder(0))
        return GenResult(next(answers), 25, 50, 1.0, "stop")

    monkeypatch.setattr(router.stage2, "generate", generate)
    monkeypatch.setattr(router.store, "search", lambda *args, **kwargs: [])
    res = translate("uma playlist do youtube, variável")
    assert len(prompts) == 2
    assert res.complete and res.imports == ["from yt_dlp import YoutubeDL"]
    assert res.code.strip() == "from yt_dlp import YoutubeDL"


def test_saida_python_invalida_duas_vezes_nao_autoinserida(translate, router, monkeypatch):
    monkeypatch.setattr(router.store, "search", lambda *args, **kwargs: [])
    router.stage2.answer = "dt lp\n.Y\noutube\nDL\n()\n"
    res = translate("uma playlist do youtube, variável")
    assert not res.complete
    assert any("geração inválida" in note for note in res.notes)
    assert len(router.stage2.prompts) == 2


def test_playlist_youtube_usa_padrao_verificado_sem_chamar_modelo(translate, router, monkeypatch):
    def nao_chamar_modelo(*args, **kwargs):
        raise AssertionError("padrão determinístico não deve gerar com IA")

    monkeypatch.setattr(router.stage2, "generate", nao_chamar_modelo)
    res = translate("ler uma playlist do youtube, variável", stages=(0, 1))
    assert res.source == "pattern:io.youtube_playlist"
    assert "def ler_playlist_youtube" in res.code
    assert "download=False" in res.code
    assert "from yt_dlp import YoutubeDL" in res.code
