"""Modo Estudo em HTML e CSS: cada linha explica seus elementos, atributos e propriedades, sem IA."""

import asyncio

import pytest

from codar import estudo
from codar.estudo.web import especificidade


PAGINA = """<!doctype html>
<html lang="pt-BR">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Padaria do bairro</title>
  <link rel="stylesheet" href="estilo.css">
  <script src="app.js" defer></script>
</head>
<body>
  <header>
    <nav aria-label="Principal">
      <ul>
        <li><a href="#produtos" aria-current="page">Produtos</a></li>
      </ul>
    </nav>
  </header>
  <main id="conteudo">
    <h1>Produtos</h1>
    <section id="produtos">
      <h2>Pães</h2>
      <p>Assados todos os dias &mdash; inclusive domingo.</p>
      <img src="pao.jpg" alt="Pão de fermentação natural fatiado" width="800" height="600">
      <table>
        <caption>Preços</caption>
        <tr><th scope="col">Item</th><th scope="col">Preço</th></tr>
      </table>
      <form action="/encomenda" method="post">
        <label for="email">Email</label>
        <input id="email" name="email" type="email" autocomplete="email" required>
        <button type="submit">Encomendar</button>
      </form>
    </section>
  </main>
  <footer><p>Contato</p></footer>
</body>
</html>"""


@pytest.mark.parametrize("linha", [l for l in PAGINA.split("\n") if l.strip().startswith("<") and not l.strip().startswith("</")])
def test_cada_linha_html_tem_explicacao_propria_e_nao_so_o_guia(linha):
    achados = estudo.conceitos_da_linha(linha, "html")
    assert achados[0].trilha == "referencia", linha
    assert achados[0].exemplos["html"] and achados[0].fontes


def test_pagina_correta_nao_recebe_alertas():
    for linha in PAGINA.split("\n"):
        assert [t for k, t in estudo.anotacoes(linha, "html") if k == "alerta"] == [], linha


def test_atributos_e_tipos_explicados_na_linha():
    notas = dict(estudo.anotacoes('<input id="cpf" name="cpf" type="number">', "html"))
    texto = " ".join(t for _k, t in estudo.anotacoes('<input id="cpf" name="cpf" type="number">', "html"))
    assert "atributo" in notas
    assert "zeros à esquerda" in texto and "label for" in texto and "enviado" in texto
    texto = " ".join(t for _k, t in estudo.anotacoes('<html lang="pt-BR">', "html"))
    assert "pronúncia" in texto
    assert any("dataset.produtoId" in t for _k, t in estudo.anotacoes('<li data-produto-id="7">', "html"))


@pytest.mark.parametrize("linha,trecho", [
    ('<img src="foto.jpg">', "img sem alt"),
    ('<img src="a.png" alt="foto.png" width="1" height="1">', "nome do arquivo"),
    ('<button>Salvar</button>', "button sem type"),
    ('<a>Menu</a>', "a sem href"),
    ('<meta name="viewport" content="width=device-width, user-scalable=no">', "bloqueia o zoom"),
    ('<input type="email" placeholder="Email">', "placeholder some"),
    ('<label>Nome</label>', "label sem for"),
    ('<iframe src="mapa.html"></iframe>', "iframe sem title"),
    ('<div onclick="abrir()">Abrir</div>', "não recebe foco"),
    ('<center>Promoção</center>', "obsoleto"),
    ('<html>', "sem lang"),
    ('<video src="a.mp4" autoplay></video>', "autoplay com som"),
    ('<buton type="submit">', "Não reconheço <buton>"),
])
def test_problemas_comuns_sao_apontados_na_propria_linha(linha, trecho):
    assert any(trecho in t for k, t in estudo.anotacoes(linha, "html") if k == "alerta"), estudo.anotacoes(linha, "html")


@pytest.mark.parametrize("linha", ['<label><input type="checkbox" name="aceito"> Aceito</label>', '<sup>2</sup>',
                                   '<circle cx="5" cy="5" r="4"/>', '<meu-cartao>', '<input type="hidden" name="t" value="1">'])
def test_construcoes_validas_nao_geram_falso_alerta(linha):
    assert [t for k, t in estudo.anotacoes(linha, "html") if k == "alerta"] == []


def test_exemplos_da_referencia_seguem_os_proprios_conselhos():
    for conceito in estudo.CONCEITOS:
        if conceito.trilha != "referencia":
            continue
        for lang, codigo in conceito.exemplos.items():
            for i, linha in enumerate(codigo.split("\n")):
                efetiva = estudo.linguagem_na_posicao(codigo, i, lang)
                assert not [t for k, t in estudo.anotacoes(linha, efetiva) if k == "alerta"], (conceito.id, linha)


@pytest.mark.parametrize("seletor,esperada", [
    ("a", (0, 0, 1)), (".menu a", (0, 1, 1)), ("#topo .item::before", (1, 1, 1)), ("nav > a:hover", (0, 1, 2)),
    ('input[type="email"]:focus', (0, 2, 1)), (":where(.x) a", (0, 0, 1)), (":is(#a, .b) p", (1, 0, 1)),
])
def test_especificidade(seletor, esperada):
    assert especificidade(seletor) == esperada


def test_css_explica_seletor_propriedade_valor_e_unidade():
    notas = [t for _k, t in estudo.anotacoes(".galeria { display: grid; gap: 1rem; margin: 0 auto; }", "css")]
    texto = " ".join(notas)
    assert ".galeria — especificidade (0,1,0)" in notas
    assert "linhas e colunas" in texto and "rem = relativo à fonte da raiz" in texto
    assert "esquerda/direita auto" in texto and "centraliza" in texto
    ids = [c.id for c in estudo.conceitos_da_linha(".galeria { display: grid; gap: 1rem; }", "css")]
    assert ids[:3] == ["css_ref_seletores", "css_ref_display", "css_ref_grid"]


@pytest.mark.parametrize("linha,trecho", [("colr: red;", "você quis dizer color?"), ("outline: none;", "indicador de foco")])
def test_css_aponta_erro_de_grafia_e_perda_de_foco(linha, trecho):
    assert any(trecho in t for k, t in estudo.anotacoes(linha, "css") if k == "alerta")


@pytest.mark.parametrize("linha", ["content: \"\";", "vertical-align: middle;", "scroll-snap-type: x mandatory;",
                                   "border-top-left-radius: 4px;", "-webkit-line-clamp: 3;", "--cor-marca: #0b6e4f;"])
def test_css_valido_fora_da_tabela_nao_e_erro(linha):
    assert [t for k, t in estudo.anotacoes(linha, "css") if k == "alerta"] == []


def test_script_e_style_no_html_usam_a_propria_linguagem():
    texto = ('<head>\n<style>\n  .x { color: red; }\n</style>\n<script type="application/json">\n{"a": 1}\n</script>\n'
             '</head>\n<body>\n<script>\n  const total = 1;\n</script>\n</body>')
    linhas = texto.split("\n")
    lang = {i: estudo.linguagem_na_posicao(texto, i, "html") for i in range(len(linhas))}
    assert lang[1] == "html" and lang[2] == "css" and lang[3] == "html"  # a própria tag continua HTML
    assert lang[5] == "html"  # JSON não é JavaScript executável
    assert lang[10] == "javascript" and lang[11] == "html"
    assert estudo.linguagem_na_posicao(texto, 2, "python") == "python"


def test_referencia_no_catalogo_e_na_busca_mas_fora_do_percurso(tmp_path):
    from codar.estudo.curriculo import buscar, percurso

    ids = {c.id for c in estudo.catalogo("html")}
    assert {"html_ref_img", "html_ref_form", "html_ref_table"} <= ids
    assert "html_ref_img" not in {lesson["id"] for lesson in percurso("html", tmp_path)["lessons"]}
    assert "html_ref_img" in {c.id for c in buscar("html", "texto alternativo")}
    # Consulta pela barra: "o que é a tag img" usa a referência local.
    assert estudo.conceitos_da_linha("# o que é a tag img", "html")[0].id == "html_ref_img"


def test_cli_explica_linha_do_arquivo_e_mostra_verbete(tmp_path, capsys):
    from codar.cli.main import main

    pagina = tmp_path / "index.html"
    pagina.write_text('<!doctype html>\n<html lang="pt-BR">\n<body>\n<img src="a.png">\n<script>\n  let n = 0;\n</script>\n'
                      '</body>\n</html>\n', encoding="utf-8")
    assert main(["study", "explain", "--file", str(pagina), "--line", "4"]) == 0
    saida = capsys.readouterr().out
    assert "<img> · imagem" in saida and "⚠ img sem alt" in saida
    assert main(["study", "explain", "--file", str(pagina), "--line", "6", "--json"]) == 0
    assert '"language": "javascript"' in capsys.readouterr().out
    assert main(["study", "show", "html_ref_img", "-l", "html", "--root", str(tmp_path)]) == 0
    assert "Percurso: referência" in capsys.readouterr().out


def test_painel_do_studio_explica_a_linha_html_e_o_script(tmp_path, monkeypatch):
    pytest.importorskip("textual")
    from textual.widgets import Static

    from codar.studio.app import Studio
    from test_estudo import _texto

    monkeypatch.setenv("CODAR_HOME", str(tmp_path / "home"))
    monkeypatch.setenv("CODAR_NO_AUTOSTART", "1")
    pagina = tmp_path / "index.html"
    pagina.write_text('<!doctype html>\n<html lang="pt-BR">\n<body>\n<img src="a.png">\n<script>\n'
                      '  const dobro = (x) => x * 2;\n</script>\n</body>\n</html>\n', encoding="utf-8")

    async def scenario():
        app = Studio(tmp_path, local=True)
        async with app.run_test(size=(150, 42)):
            app.estudo = True
            await app.open_file(pagina)
            editor = app.current_editor()
            editor.move_cursor((3, 2))
            app.atualizar_estudo()
            painel = _texto(app.query_one("#estudo-corpo", Static).content)
            assert "<IMG> · IMAGEM" in painel and "NESTA LINHA" in painel and "img sem alt" in painel
            editor.move_cursor((5, 4))
            app.atualizar_estudo()
            painel = _texto(app.query_one("#estudo-corpo", Static).content)
            assert "FUNÇÕES DE SETA" in painel.upper() and "<IMG>" not in painel
    asyncio.run(scenario())
