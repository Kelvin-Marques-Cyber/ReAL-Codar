"""Os exemplos das fichas de estudo passam pela ferramenta oficial de cada linguagem.

Guia e aulas são compilados, validados ou executados quando a ferramenta está instalada; sem ela, o caso é pulado.
Assim um exemplo com erro de sintaxe não chega ao painel ESTUDO.
"""

import json
import os
import re
import shutil
import subprocess
import sys

import pytest

from codar import langs
from codar._compat import tomllib
from codar.estudo.linguagens import FICHAS

pytestmark = pytest.mark.slow

# Os verbetes da referência são trechos; entram aqui os das linguagens em que um trecho já é um documento completo.
_TRECHOS_COMPLETOS = {"json", "toml", "graphql", "protobuf", "terraform"}
AMOSTRAS = [(lang, nome, codigo) for lang, ficha in FICHAS.items()
            for nome, codigo in [("guia", ficha.guia[2])] + [(aula[0], aula[6]) for aula in ficha.aulas]
            + [("ref_" + verbete[0], verbete[4]) for verbete in ficha.referencia if lang in _TRECHOS_COMPLETOS]]


def _precisa(*ferramentas):
    for ferramenta in ferramentas:
        if not shutil.which(ferramenta):
            pytest.skip(f"{ferramenta} ausente")


def _rodar(comando, pasta, entrada="", tempo=180):
    saida = subprocess.run(comando, cwd=pasta, input=entrada, capture_output=True, text=True, timeout=tempo,
                           env={**os.environ, "LC_ALL": "C.UTF-8"})
    assert saida.returncode == 0, f"{' '.join(map(str, comando))}\n{saida.stdout[-3000:]}\n{saida.stderr[-3000:]}"
    return saida.stdout


def _node(pasta, modulo, programa, arquivo):
    _precisa("node")
    if subprocess.run(["node", "-e", f"require({modulo!r})"], capture_output=True).returncode:
        pytest.skip(f"pacote npm {modulo} ausente (use NODE_PATH)")
    return _rodar(["node", "-e", programa, str(arquivo)], pasta)


# ------------------------------------------------------------------------------------------- documentos e dados
_PREAMBULO = r"""\documentclass{article}
\usepackage[T1]{fontenc}
\usepackage{amsmath,graphicx,booktabs}
"""


def _png() -> bytes:
    """PNG 1x1 válido para as figuras dos exemplos."""
    import struct
    import zlib

    def bloco(tipo, dados):
        return struct.pack(">I", len(dados)) + tipo + dados + struct.pack(">I", zlib.crc32(tipo + dados))

    return (b"\x89PNG\r\n\x1a\n" + bloco(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0))
            + bloco(b"IDAT", zlib.compress(b"\x00\xff\xff\xff")) + bloco(b"IEND", b""))


def _latex(pasta, codigo):
    _precisa("pdflatex")
    if r"\documentclass" not in codigo:  # trecho de aula: entra num documento mínimo
        pacotes = [linha for linha in codigo.splitlines() if linha.startswith(r"\usepackage")]
        corpo = "\n".join(linha for linha in codigo.splitlines() if linha not in pacotes)
        codigo = _PREAMBULO + "\n".join(pacotes) + "\n\\begin{document}\n" + corpo + "\n\\end{document}\n"
    for imagem in re.findall(r"\\includegraphics(?:\[[^\]]*\])?\{([^}]+)\}", codigo):
        destino = pasta / imagem
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_bytes(_png())
    (pasta / "doc.tex").write_text(codigo, encoding="utf-8")
    for _ in range(2):
        _rodar(["pdflatex", "-interaction=nonstopmode", "-halt-on-error", "doc.tex"], pasta)
    log = (pasta / "doc.log").read_text(encoding="utf-8", errors="replace")
    assert "There were undefined references" not in log, log[-2000:]
    assert (pasta / "doc.pdf").stat().st_size > 1000


def _markdown(pasta, codigo):
    markdown_it = pytest.importorskip("markdown_it")
    cercas = [linha for linha in codigo.splitlines() if re.match(r"\s{0,3}(?:```|~~~)", linha)]
    assert len(cercas) % 2 == 0, "bloco de código sem fechamento"
    html = markdown_it.MarkdownIt("commonmark").enable("table").render(codigo)
    assert "<" in html and html.count("<pre>") == len(cercas) // 2


def _json(pasta, codigo):
    json.loads(codigo)


def _toml(pasta, codigo):
    tomllib.loads(codigo)


def _xml(pasta, codigo):
    _precisa("xmllint")
    (pasta / "doc.xml").write_text(codigo, encoding="utf-8")
    _rodar(["xmllint", "--noout", "doc.xml"], pasta)
    if "<xs:schema" in codigo:  # o XSD da aula valida o catálogo do projeto
        projeto = next(a[6] for a in FICHAS["xml"].aulas if a[0] == "projeto")
        (pasta / "catalogo.xml").write_text(projeto, encoding="utf-8")
        _rodar(["xmllint", "--noout", "--schema", "doc.xml", "catalogo.xml"], pasta)


def _make(pasta, codigo):
    _precisa("make")
    for arquivo in ("main.c", "util.c", "util.h", "src/calc.c"):
        (pasta / arquivo).parent.mkdir(parents=True, exist_ok=True)
        (pasta / arquivo).write_text("", encoding="utf-8")
    (pasta / "Makefile").write_text(codigo, encoding="utf-8")
    _rodar(["make", "-n"], pasta)


def _graphql(pasta, codigo):
    (pasta / "doc.graphql").write_text(codigo, encoding="utf-8")
    _node(pasta, "graphql", "require('graphql').parse(require('fs').readFileSync(process.argv[1], 'utf8'))",
          pasta / "doc.graphql")


def _protobuf(pasta, codigo):
    _precisa("protoc")
    if not re.match(r"\s*(?:syntax|edition)\b", codigo):
        codigo = 'syntax = "proto3";\n' + codigo
    (pasta / "doc.proto").write_text(codigo, encoding="utf-8")
    padrao = [f"-I{d}" for d in ("/usr/include", "/usr/local/include") if os.path.isfile(f"{d}/google/protobuf/any.proto")]
    if "google/protobuf/" in codigo and not padrao:
        pytest.skip("tipos padrão do protobuf ausentes (libprotobuf-dev)")
    _rodar(["protoc", "-I.", *padrao, "--python_out=.", "doc.proto"], pasta)


def _terraform(pasta, codigo):
    _precisa("terraform")
    (pasta / "main.tf").write_text(codigo + "\n", encoding="utf-8")
    _rodar(["terraform", "fmt", "-check", "-diff", "main.tf"], pasta)


# --------------------------------------------------------------------------------------- hardware e contratos
def _verilog(pasta, codigo):
    _precisa("iverilog", "vvp")
    (pasta / "circuito.v").write_text(codigo, encoding="utf-8")
    _rodar(["iverilog", "-g2012", "-Wall", "-o", "sim", "circuito.v"], pasta)
    if "$finish" in codigo:  # o testbench roda e termina sozinho
        saida = _rodar(["vvp", "-n", "sim"], pasta, tempo=60)
        assert "FALHOU" not in saida, saida


def _vhdl(pasta, codigo):
    _precisa("ghdl")
    (pasta / "circuito.vhd").write_text(codigo, encoding="utf-8")
    _rodar(["ghdl", "-a", "--std=08", "circuito.vhd"], pasta)
    if re.search(r"^entity\s+teste\b", codigo, re.M):
        _rodar(["ghdl", "-e", "--std=08", "teste"], pasta)
        saida = subprocess.run(["ghdl", "-r", "--std=08", "teste", "--assert-level=error"], cwd=pasta,
                               capture_output=True, text=True, timeout=60)
        assert saida.returncode == 0 and "error" not in saida.stdout + saida.stderr, saida.stdout + saida.stderr


_SOLC = """
const solc = require('solc'), fs = require('fs');
const entrada = {language: 'Solidity', sources: {'c.sol': {content: fs.readFileSync(process.argv[1], 'utf8')}},
                 settings: {outputSelection: {'*': {'*': ['abi']}}}};
const saida = JSON.parse(solc.compile(JSON.stringify(entrada)));
const problemas = (saida.errors || []).filter(e => e.severity !== 'info');
if (problemas.length) { console.error(problemas.map(e => e.formattedMessage).join('\\n')); process.exit(1); }
"""


def _solidity(pasta, codigo):
    (pasta / "c.sol").write_text(codigo, encoding="utf-8")
    _node(pasta, "solc", _SOLC, pasta / "c.sol")  # erros e avisos reprovam o exemplo


VALIDADORES = {"verilog": _verilog, "vhdl": _vhdl, "solidity": _solidity, "latex": _latex, "markdown": _markdown, "json": _json, "toml": _toml, "xml": _xml, "makefile": _make,
               "graphql": _graphql, "protobuf": _protobuf, "terraform": _terraform}


@pytest.mark.parametrize("lang,nome,codigo", AMOSTRAS, ids=[f"{lang}-{nome}" for lang, nome, _ in AMOSTRAS])
def test_exemplo_passa_pela_ferramenta_oficial(tmp_path, lang, nome, codigo):
    assert lang in VALIDADORES, f"{lang} precisa de um validador"
    VALIDADORES[lang](tmp_path, codigo)


def test_toda_linguagem_registrada_tem_ficha_ou_estudo_proprio():
    from codar.estudo.ampliado import GUIAS
    from codar.estudo.curriculo import AMBIENTES, AULAS

    for lang in langs.LANGS:
        assert lang in GUIAS and lang in AMBIENTES and AULAS.get(lang), lang


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
