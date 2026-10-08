"""Abreviações Emmet (HTML, CSS, JSX): as saídas seguem o Emmet do VS Code, com lang="pt-BR" no "!"."""

import pytest

from codar.engine.emmet import expand, expand_css, is_abbreviation, jsx_candidate


@pytest.mark.parametrize("abbr,html", [
    ("ul>li.item$*3", '<ul>\n  <li class="item1"></li>\n  <li class="item2"></li>\n  <li class="item3"></li>\n</ul>'),
    ("ul>li*2>a{Link $}", '<ul>\n  <li><a href="">Link 1</a></li>\n  <li><a href="">Link 2</a></li>\n</ul>'),
    ("ul>.x", '<ul>\n  <li class="x"></li>\n</ul>'),
    ("table>tr>td*2", "<table>\n  <tr>\n    <td></td>\n    <td></td>\n  </tr>\n</table>"),
    ("div>p^span", "<div>\n  <p></p>\n</div>\n<span></span>"),
    ("(header>h1)+main", "<header>\n  <h1></h1>\n</header>\n<main></main>"),
    ("p>a", '<p><a href=""></a></p>'),
    ("img", '<img src="" alt="">'),
    ("input:email", '<input type="email" name="" id="">'),
    ("a:blank{Site}", '<a href="http://" target="_blank" rel="noopener noreferrer">Site</a>'),
    ("div[data-id=1 hidden]>span{oi}", '<div data-id="1" hidden><span>oi</span></div>'),
    ("li.i$$@3*2", '<li class="i03"></li>\n<li class="i04"></li>'),
    ("li{$@-}*3", "<li>3</li>\n<li>2</li>\n<li>1</li>"),
    ("p{R\\$ 10}", "<p>R$ 10</p>"),
    ("p>lorem4", "<p>Lorem ipsum dolor sit.</p>"),
    ("my-widget", "<my-widget></my-widget>"),
])
def test_html(abbr, html):
    assert expand(abbr) == html


def test_formulario_quebra_linhas_com_tres_ou_mais_elementos_em_linha():
    assert expand("form:post>input:email+input:password+btn:s{Entrar}") == (
        '<form action="" method="post">\n  <input type="email" name="" id="">\n'
        '  <input type="password" name="" id="">\n  <button type="submit">Entrar</button>\n</form>')


def test_esqueleto_html5():
    out = expand("!")
    assert out.startswith('<!DOCTYPE html>\n<html lang="pt-BR">') and "<title>Documento</title>" in out


def test_jsx():
    assert expand("label[for=email]+input.campo", jsx=True) == (
        '<label htmlFor="email"></label>\n<input className="campo" type="text" />')
    assert jsx_candidate("ul>li*2") and not jsx_candidate("items.map") and not jsx_candidate("a+b")


@pytest.mark.parametrize("text", ["criar um formulário de login", "lista", "x é igual a 10", "", "ul>"])
def test_frases_e_lixo_nao_sao_abreviacoes(text):
    assert not is_abbreviation(text) and expand(text) is None


@pytest.mark.parametrize("abbr,css", [
    ("df+jcc+aic", "display: flex;\njustify-content: center;\nalign-items: center;"),
    ("m10-20", "margin: 10px 20px;"), ("m-10", "margin: -10px;"), ("p0", "padding: 0;"),
    ("w100p", "width: 100%;"), ("fz1.5r", "font-size: 1.5rem;"), ("op.5", "opacity: .5;"), ("zi10", "z-index: 10;"),
    ("c#3", "color: #333;"), ("bgc#e0", "background-color: #e0e0e0;"), ("bd1-s-#ccc", "border: 1px solid #ccc;"),
    ("mt5!", "margin-top: 5px !important;"), ("ma", "margin: auto;"),
])
def test_css(abbr, css):
    assert expand_css(abbr) == css


def test_css_desconhecido():
    assert expand_css("foo") is None and expand_css("margem de 10") is None


def test_roteador_expande_em_html_e_respeita_indentacao(router):
    import asyncio

    from codar.engine.router import Request

    req = Request(intent="ul>li*2", lang="html", lang_explicit=True, indent="    ", indent_unit="\t")
    res = asyncio.run(router.translate(req))
    assert res.source == "emmet:html" and res.body == "    <ul>\n    \t<li></li>\n    \t<li></li>\n    </ul>"
