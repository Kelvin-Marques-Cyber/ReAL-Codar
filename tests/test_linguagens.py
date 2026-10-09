"""Compilador (estágio 0) em todas as linguagens: os mesmos programas em pseudocódigo viram código com sintaxe válida
em cada uma (validado com as gramáticas tree-sitter) e, onde o compilador existe na máquina, rodam com a saída certa."""

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from codar.engine.emit import EMITTERS, EmitError, emit
from codar.engine.postprocess import join_imports
from codar.engine.stage0 import Stage0
from codar.evals import patternlint

PROGRAMAS = {
    "texto_numero": "total é igual a 10\nimprimir 'Total: ' + total\nnome é igual a 'Ana'\n"
                    "msg é igual a 'Olá, ' + nome + ' (' + total + ')'\nimprimir msg",
    "entrada": "pedir o nome ao usuário\nperguntar a idade do usuário como inteiro\n"
               "imprimir 'Ano que vem: ' + (idade + 1)",
    "se_senao": "nota é igual a 7\nse nota maior ou igual a 7\n    imprimir 'aprovado'\nsenão se nota maior que 4\n"
                "    imprimir 'recuperação'\nsenão\n    imprimir 'reprovado'",
    "lacos": "repetir 3 vezes imprimir 'oi'\npara i de 1 até 5 imprimir i\ncontador é igual a 0\n"
             "enquanto contador menor que 3\n    contador é igual a contador mais 1\nimprimir contador",
    "listas": "nomes é igual a ['Ana', 'Bia']\nadicionar 'Caio' em nomes\npara cada nome em nomes imprimir nome\n"
              "imprimir o tamanho de nomes\nimprimir nomes[0]",
    "funcao": "definir função dobro que recebe x e retorna x vezes 2\nresultado é igual a dobro(5)\nimprimir resultado",
    "classe": "criar uma classe Pessoa com nome e idade",
    "media": "a é igual a 7\nb é igual a 8\nmedia é igual a (a + b) / 2\nimprimir media",
}


def compilar(nome: str, lang: str) -> str:
    nodes, misses = Stage0().parse_program(PROGRAMAS[nome], set())
    assert not misses, nome
    try:
        imports, corpo = emit(nodes, lang)
    except EmitError as exc:
        pytest.skip(f"{nome} não existe em {lang}: {exc}")
    return join_imports(imports, corpo, lang)


def _go_programa(trecho: str) -> str:
    """Em Go, instruções só existem dentro de funções: monta um arquivo com as funções no topo e o resto em main."""
    imports, corpo = __import__("codar.engine.postprocess", fromlist=["split_imports"]).split_imports(trecho, "go")
    linhas, decl, resto, dentro = corpo.split("\n"), [], [], False
    for ln in linhas:
        if ln.startswith("func "):
            dentro = True
        (decl if dentro else resto).append(ln)
        if dentro and ln == "}":
            dentro = False
    return "package main\n" + "\n".join(imports) + "\n" + "\n".join(decl) + "\nfunc main() {\n" + \
        "\n".join(resto) + "\n}\n"


@pytest.mark.parametrize("lang", sorted(EMITTERS))
@pytest.mark.parametrize("nome", sorted(PROGRAMAS))
def test_sintaxe_valida_em_toda_linguagem(nome, lang):
    codigo = compilar(nome, lang)
    assert "TODO" not in codigo
    if lang == "go" and "\nfunc " in "\n" + codigo:  # trecho com função + instruções: as instruções vão num main
        codigo = _go_programa(codigo)
    resultado = patternlint.check(codigo, lang)
    if resultado is None:
        pytest.skip(f"sem gramática tree-sitter para {lang}")
    ok, linha, coluna = resultado
    assert ok, f"{lang}/{nome}: erro de sintaxe na linha {linha}, coluna {coluna}\n{codigo}"


@pytest.mark.parametrize("lang, esperado", [
    ("python", 'print(f"Total: {total}")'), ("go", 'fmt.Printf("Total: %v\\n", total)'),
    ("ruby", 'puts "Total: #{total}"'), ("rust", 'println!("Total: {}", total);'),
    ("c", 'printf("Total: %d\\n", total);'), ("cpp", 'std::cout << "Total: " << total << \'\\n\';'),
    ("bash", 'echo "Total: ${total}"'), ("kotlin", 'println("Total: ${total}")'),
    ("swift", 'print("Total: \\(total)")'), ("dart", 'print("Total: ${total}");'),
    ("julia", 'println("Total: $(total)")'), ("r", 'cat(paste0("Total: ", total), "\\n", sep = "")'),
])
def test_texto_com_numero_no_jeito_de_cada_linguagem(lang, esperado):
    assert esperado in compilar("texto_numero", lang)


def test_indices_comecam_em_1_onde_a_linguagem_conta_assim():
    assert "nomes[1]" in compilar("listas", "julia") and "nomes[1]" in compilar("listas", "r")
    assert "nomes[0]" in compilar("listas", "python")


def test_nota_e_variavel_e_nao_comentario():
    assert "nota = 7" in compilar("se_senao", "python")


SAIDAS = {"texto_numero": "Total: 10\nOlá, Ana (10)\n", "lacos": "oi\noi\noi\n1\n2\n3\n4\n5\n3\n",
          "listas": "Ana\nBia\nCaio\n3\nAna\n", "funcao": "10\n", "se_senao": "aprovado\n", "media": "7.5\n",
          "entrada": "Nome: Idade: Ano que vem: 31\n"}
ENTRADA = "Ana\n30\n"
EXECUTORES = {
    "python": ("app.py", lambda a: [sys.executable, a]),
    "javascript": ("app.mjs", lambda a: ["node", a]),
    "c": ("app.c", lambda a: ["sh", "-c", f"gcc -std=c11 -o app {a} && ./app"]),
}


@pytest.mark.parametrize("lang", sorted(EXECUTORES))
@pytest.mark.parametrize("nome", sorted(SAIDAS))
def test_programas_rodam_com_a_saida_certa(nome, lang, tmp_path):
    arquivo, comando = EXECUTORES[lang]
    if not shutil.which(comando("x")[0]) or (lang == "c" and not shutil.which("gcc")):
        pytest.skip(f"sem {lang} nesta máquina")
    codigo = compilar(nome, lang)
    if lang == "c":
        codigo = "\n".join(ln for ln in codigo.splitlines() if ln.startswith("#include")) + "\n\nint main(void) {\n" + \
            "\n".join("    " + ln for ln in codigo.splitlines() if not ln.startswith("#include")) + "\n    return 0;\n}\n"
    (tmp_path / arquivo).write_text(codigo, encoding="utf-8")
    r = subprocess.run(comando(arquivo), cwd=tmp_path, input=ENTRADA, capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stderr
    assert r.stdout == SAIDAS[nome], codigo


# Execução de verdade nas linguagens que não costumam estar instaladas: imagens oficiais (docker) e o kotlinc.
# Opcional, porque baixa ~1,5 GB por imagem:  CODAR_TESTE_CONTAINERS=1 KOTLINC=/caminho/kotlinc pytest -k imagens
IMAGENS = {"r": ("r-base:latest", "app.R", "Rscript app.R"), "julia": ("julia:1.11", "app.jl", "julia app.jl"),
           "dart": ("dart:stable", "app.dart", "dart run app.dart")}
SAIDAS_R = {**SAIDAS, "funcao": "[1] 10\n"}  # print() do R mostra "[1]" antes de valores sem tipo conhecido


def _main(codigo: str, lang: str, abre: str, recuo: str = "  ") -> str:
    from codar.engine.postprocess import split_imports

    imports, corpo = split_imports(codigo, lang)
    return "\n".join(imports) + f"\n\n{abre} {{\n" + "\n".join(recuo + ln for ln in corpo.splitlines()) + "\n}\n"


@pytest.mark.skipif(os.environ.get("CODAR_TESTE_CONTAINERS") != "1", reason="CODAR_TESTE_CONTAINERS=1 roda nas imagens")
@pytest.mark.parametrize("lang", sorted(IMAGENS))
@pytest.mark.parametrize("nome", sorted(SAIDAS))
def test_programas_rodam_nas_imagens_oficiais(nome, lang, tmp_path):
    imagem, arquivo, comando = IMAGENS[lang]
    codigo = compilar(nome, lang)
    if lang == "dart":
        codigo = _main(codigo, "dart", "void main()")
    (tmp_path / arquivo).write_text(codigo, encoding="utf-8")
    r = subprocess.run(["docker", "run", "--rm", "-i", "--network", "none", "--security-opt", "label=disable", "-v",
                        f"{tmp_path}:/w", "-w", "/w", imagem, "sh", "-c", comando], input=ENTRADA,
                       capture_output=True, text=True, timeout=300)
    assert r.returncode == 0, r.stderr
    assert r.stdout == (SAIDAS_R if lang == "r" else SAIDAS)[nome], codigo


@pytest.mark.skipif(not os.environ.get("KOTLINC"), reason="KOTLINC=/caminho/do/kotlinc roda os programas em Kotlin")
@pytest.mark.parametrize("nome", sorted(SAIDAS))
def test_programas_rodam_em_kotlin(nome, tmp_path):
    (tmp_path / "app.kt").write_text(_main(compilar(nome, "kotlin"), "kotlin", "fun main()", "    "), encoding="utf-8")
    c = subprocess.run([os.environ["KOTLINC"], "app.kt", "-include-runtime", "-d", "app.jar", "-nowarn"],
                       cwd=tmp_path, capture_output=True, text=True, timeout=600)
    assert c.returncode == 0, c.stderr[-2000:]
    r = subprocess.run(["java", "-jar", "app.jar"], cwd=tmp_path, input=ENTRADA, capture_output=True, text=True,
                       timeout=120)
    assert r.returncode == 0, r.stderr
    assert r.stdout == SAIDAS[nome]
