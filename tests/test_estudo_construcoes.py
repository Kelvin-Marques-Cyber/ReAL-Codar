"""O painel ESTUDO reconhece as construções próprias de cada linguagem, não só o guia genérico."""

import pytest

from codar import estudo, langs
from codar.estudo.ampliado import GUIAS
from codar.estudo.construcoes import REFERENCIA
from codar.estudo.curriculo import AULAS

_TRIVIAIS = {"}", "{", "});", ")", "end", "};", "} }"}


def _linhas(lang):
    codigo = [aula.codigo for aula in AULAS.get(lang, [])] + [GUIAS[lang][2]]
    return [linha for bloco in codigo for linha in bloco.split("\n") if linha.strip() and linha.strip() not in _TRIVIAIS]


def _generica(linha, lang):
    return all(c.id.startswith("guia_") for c in estudo.conceitos_da_linha(linha, lang))


@pytest.mark.parametrize("lang", sorted(langs.LANGS))
def test_linhas_das_proprias_aulas_tem_explicacao_especifica(lang):
    linhas = _linhas(lang)
    genericas = [linha for linha in linhas if _generica(linha, lang)]
    # Antes desta referência, 48% das linhas das aulas caíam só no guia da linguagem.
    assert len(genericas) <= max(1, len(linhas) // 5), genericas


def test_cobertura_total_das_aulas():
    pares = [(linha, lang) for lang in langs.LANGS for linha in _linhas(lang)]
    assert sum(_generica(linha, lang) for linha, lang in pares) / len(pares) < .05


@pytest.mark.parametrize("lang,chave", [(lang, v[0]) for lang, verbetes in REFERENCIA.items() for v in verbetes])
def test_verbete_reconhece_o_proprio_exemplo(lang, chave):
    conceito = estudo.POR_ID[f"{lang}_ref_{chave}"]
    codigo = conceito.exemplos[lang]
    assert conceito.trilha == "referencia" and conceito.texto and conceito.fontes
    assert any(conceito in estudo.conceitos_da_linha(linha, lang) for linha in codigo.split("\n")), codigo


@pytest.mark.parametrize("lang,linha,esperado", [
    ("c", "#include <stdio.h>", "c_ref_include"),
    ("cpp", "std::vector<int> v{1, 2};", "cpp_ref_vector"),
    ("csharp", "var pares = valores.Where(n => n % 2 == 0).ToList();", "csharp_ref_linq"),
    ("java", "List<String> nomes = new ArrayList<>();", "java_ref_colecoes"),
    ("kotlin", "val nome: String? = null", "kotlin_ref_nulos"),
    ("swift", "guard let numero = Int(texto) else { return nil }", "swift_ref_opcionais"),
    ("dart", "final pares = valores.where((n) => n.isEven).toList();", "dart_ref_colecoes"),
    ("lua", "local contagem = {}", "lua_ref_tabelas"),
    ("php", "<?php", "php_ref_abertura"),
    ("sql", "select p.nome from pessoas p left join compras c on c.pessoa_id = p.id", "sql_ref_join"),
    ("powershell", "param([Parameter(Mandatory)][int]$Quantidade)", "powershell_ref_param"),
    ("go", "idade, existe := idades[\"Bia\"]", "go_ref_declarar"),
    ("rust", "#[derive(Debug, PartialEq)]", "rust_ref_atributos"),
    ("bash", "#!/usr/bin/env bash", "bash_ref_shebang"),
    ("python", "@dataclass(frozen=True)", "python_ref_decorador"),
])
def test_construcao_tipica_tem_verbete_proprio(lang, linha, esperado):
    assert esperado in [c.id for c in estudo.conceitos_da_linha(linha, lang)]


@pytest.mark.parametrize("lang,linha,comentario", [
    ("python", "# soma dos itens", True), ("c", "#include <stdio.h>", False), ("rust", "#[test]", False),
    ("csharp", "#region Dados", False), ("c", "*p = 3;", False), ("java", " * continuação do Javadoc", True),
    ("css", "* { box-sizing: border-box; }", False), ("sql", "-- total por categoria", True), ("c", "--i;", False),
    ("html", "# o que é a tag img", True),  # consultas da barra chegam como "# pergunta"
])
def test_comentario_depende_da_linguagem(lang, linha, comentario):
    from codar.estudo import _comentario

    assert _comentario(linha.strip(), lang) is comentario
